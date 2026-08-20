#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_core.py — Self-Evolution v2.3 共享核心（Code = Enforcement）

v2.3 核心变更：
- 统一 Evolution State Machine（OBSERVED → ... → VALIDATED / ROLLED_BACK）
- evolution_id 贯穿全链路（candidate/diagnosis/proposal/change/regression）
- Rollback 同步更新所有关联 artifact（Evidence 不删除）
- Crash Recovery（APPLYING 状态检测 + 文件 hash 验证 + 恢复决策）
- Evidence 写入隔离（只有 Verification/Evaluation 来源可写）
- compute_stats 语义修正（observation_count / unique_sessions 等）

LLM = Reasoning；本模块 = Enforcement。
"""

import json
import os
import re
import shutil
import contextlib
import hashlib
from datetime import datetime, timezone
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id as _idutil_generate_id, file_fingerprint as _idutil_fingerprint
from persistence import FileLock as _PFileLock, append_atomic as _PAppendAtmoic, atomic_write_json as _PAtomicWrite
# v1.4 C1: 统一状态中央门。_core.assert_transition 收敛到 transitions.transition，
#   全仓库 20+ 处状态变化自动走中央门（统一跳转校验 + 事实不变量 + audit）。
from transitions import transition as _central_transition

# ======================== 路径与 Workspace ========================

def _workspace():
    return (
        os.environ.get("OPENCLAW_WORKSPACE")
        or os.environ.get("OPENCLAW_WORKSPACE_DIR")
        or os.path.expanduser("~/.openclaw/workspace")
    )

def evo_dir():
    return os.path.join(_workspace(), ".agent-os", "evolution")

def ws_root():
    return os.path.realpath(_workspace())

def ws_rel(p):
    p = os.path.realpath(os.path.expanduser(p))
    try:
        return os.path.relpath(p, ws_root())
    except ValueError:
        return p.lstrip("/")

def ws_abs(rel):
    if os.path.isabs(rel):
        return rel
    return os.path.join(ws_root(), rel)

def is_within_workspace(path, root=None):
    r = root or ws_root()
    p = os.path.realpath(path)
    try:
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


class WorkspaceContext:
    """统一路径解析：所有 Snapshot/Apply/Rollback/allowed_ops/diff 共享。"""
    def __init__(self, root=None):
        self.root = root or ws_root()

    def resolve(self, rel):
        if os.path.isabs(rel):
            return os.path.realpath(rel)
        return os.path.realpath(os.path.join(self.root, rel))

    def relative(self, abs_path):
        return os.path.relpath(os.path.realpath(abs_path), self.root)

    def contains(self, abs_path):
        return is_within_workspace(abs_path, self.root)

    def snapshot_path(self, change_id):
        return os.path.join(evo_dir(), "changes", change_id, "snapshot", "files")


# ======================== 时间与 ID ========================

def now_iso():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")

def today_compact():
    return datetime.now().strftime("%Y%m%d")

def _read_index():
    p = os.path.join(evo_dir(), "index.jsonl")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]

def gen_id(prefix):
    """#35: artifact ID → UUID。统一走 id_utils.generate_id()（稳定 UUID4、
    跨进程唯一），不再用日期+序号（并发下会碰撞、跨运行不可复现）。"""
    return _idutil_generate_id(prefix)


def gen_evolution_id():
    """生成唯一 Evolution ID（一次完整演进周期的顶层实体）。"""
    return "EVO-{}-{:08x}".format(today_compact(), int.from_bytes(os.urandom(4), "big"))


# ======================== 存储 ========================

KIND_DIR = {"candidate": "candidates", "diagnosis": "diagnoses", "proposal": "proposals",
            "change": "changes", "regression": "regressions"}

def kind_dir(kind):
    return KIND_DIR.get(kind, kind + "s")

def subdir(name):
    d = os.path.join(evo_dir(), name)
    os.makedirs(d, exist_ok=True)
    return d

def index_path():
    return os.path.join(evo_dir(), "index.jsonl")


def _append_index_line(line):
    """带锁裸行追加到 index.jsonl（index 是 tab 分隔裸行，非 JSONL，不能走 append_atomic）。"""
    p = index_path()
    with _PFileLock(p) as _lk:
        d = os.path.dirname(p)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

def save_artifact(kind, record):
    """写 artifact + append index。
    L-01: artifact 文件写与 index append 包进同一把锁，形成事务一致：
    要么两者都发生，要么都不发生（锁内两写，异常不 commit）。
    """
    prefix = {"candidate": "CAND", "diagnosis": "DGN", "proposal": "PRP",
              "change": "CHG", "regression": "RGR"}[kind]
    ident = record.get("id") or gen_id(prefix)
    record["id"] = ident
    record.setdefault("updated_at", now_iso())
    sub = subdir(kind_dir(kind))
    path = os.path.join(sub, ident + ".json")
    with _PFileLock(path) as _lk:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        with open(index_path(), "a", encoding="utf-8") as f:
            f.write("{}\t{}\t{}\n".format(ident, kind, _index_summary(record)))
    return ident

def load_artifact(kind, ident):
    sub = os.path.join(evo_dir(), kind_dir(kind), ident + ".json")
    if not os.path.exists(sub):
        return None
    # AE-5 (I-008): 损坏状态(CORRUPTED) ≠ 空状态(NOT_FOUND)。artifact 文件存在但
    # 无法解析 → 语义化抛错，拒绝把损坏数据当 None 静默吞掉（对齐 proactive.load_json 口径）。
    try:
        with open(sub, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise ValueError("CORRUPTED: {} 无法解析 ({})".format(sub, e))

def _index_summary(rec):
    keys = ("scope", "target", "pattern_key", "candidate_id", "diagnosis_id",
            "proposal_id", "change_id", "root_cause", "result", "status", "evolution_id")
    return "|".join(str(rec.get(k, "")) for k in keys)

def _list_ids(kind):
    sub = os.path.join(evo_dir(), kind_dir(kind))
    if not os.path.isdir(sub):
        return []
    return sorted(f[:-5] for f in os.listdir(sub) if f.endswith(".json"))


# ======================== v2.3 统一状态机 ========================

# v1.4 C1: 状态跳转表/校验已统一收敛到 skills/_lib/transitions.py。
# _core.assert_transition 为中央门薄封装（见下），不再定义局部跳转表或 STATES，
# 避免双份状态表失同步（reviewer F1）。如需状态信息，引用 _lib/transitions。
def assert_transition(record, dst, kind="candidate", **extra):
    """统一状态跳转入口 —— v1.4 C1 收敛到中央门 transitions.transition。

    语义超集且向后兼容:_core 内 20+ 处调用 (diagnose/regression/propose/
    recovery/apply/rollback) 全部经此转发, 统一获得:
      1) 合法跳转校验 (非法 raise)
      2) 状态-事实不变量校验 (#3: COMPLETED/FAILED/RUNNING 缺事实字段 raise)
      3) audit event (who/when/from/to/reason) 写入 history
    record 含 "history" 时写入 audit; 不含则静默跳过 (兼容旧对象)。
    原 _core 实现仅做跳转校验+改 status/updated_at, 现为中央门薄封装。
    """
    return _central_transition(record, dst, kind=kind, **extra)


# ======================== 保护目标与审批 ========================

PROTECTED_TARGETS = [
    "permission", "security", "credential", "secret", "auth",
    "approval", "runtime", "infrastructure", "global_authority",
    "AGENTS.md", "SOUL.md",
]

# EVO-03/05: 保护目标从「substring match」升级为「四类语义分类」，优先 fail closed。
#   四类：exact protected file / protected path prefix / protected subsystem /
#   protected semantic class。精确匹配优先，前缀/子系统用规则而非裸子串（避免
#   'secret' 误命中 'secretary' 这类）。
PROTECTED_EXACT_FILES = {
    "agents.md", "soul.md", "identity.md", "user.md", "memory.md",
    "tools.md", "heartbeat.md",
}
PROTECTED_PATH_PREFIXES = [
    "skills/permission-security", "skills/self-evolution/scripts/",
    "_lib/", "skills/_lib/",
]
PROTECTED_SUBSYSTEMS = [
    "permission", "security", "credential", "secret", "auth", "approval",
    "runtime", "infrastructure", "global_authority",
]

APPROVAL_BY_LEVEL = {
    "G1": "optional", "G2": "optional",
    "G3": "review", "G4": "review_human",
    "G5": "human", "G6": "human",
}
LEVELS = ["G1", "G2", "G3", "G4", "G5", "G6"]

def require_human_approval(level):
    return APPROVAL_BY_LEVEL.get(level) in ("human", "review_human")

def is_protected_target(target):
    """判定 target 是否受保护（四类语义分类，fail closed）。

    优先级：exact file > 路径前缀 > 子系统词 > 遗留 substring（向后兼容）。
    """
    t = str(target)
    tl = t.lower()
    # 1) exact protected file（basename 精确匹配）
    basename = tl.split("/")[-1]
    if basename in PROTECTED_EXACT_FILES:
        return True
    # 2) protected path prefix（路径前缀匹配）
    for pfx in PROTECTED_PATH_PREFIXES:
        if tl.startswith(pfx.lower()):
            return True
    # 3) protected subsystem（关键词作为独立段匹配，而非裸子串）
    segments = re.split(r"[\/_\.\-\s]", tl)
    for p in PROTECTED_SUBSYSTEMS:
        if p in segments:
            return True
    # 4) 遗留 substring（向后兼容，仅对带 . 或 / 的精确文件/路径类关键词，如 AGENTS.md/SOUL.md）。
    #   不再对纯单词（permission/secret/security 等）做裸子串匹配——那些已由第 3 步
    #   独立段匹配正确处理，裸子串会导致 'secret' 误命中 'secretary'。
    for p in PROTECTED_TARGETS:
        pl = p.lower()
        if ("." in pl or "/" in pl) and pl in tl:
            return True
    return False

def signature(scope, target, pattern_key, agent_id=None):
    """MA-1.0 Integration#2 (P2-2): signature 加入 agent_id, 使 Candidate 去重
    区分到 Agent 维度（同 scope+target+pattern_key 不同 agent 不误合并）。
    agent_id 缺省时保持向后兼容（空串不改变去重指纹）。"""
    return "{}|{}|{}|{}".format(str(scope), str(target), str(pattern_key),
                                 str(agent_id or ""))


def classify_skill_scope(target, agent_id=None, agent_workspace=None, shared_root=None,
                         skills_manifest=None, agent_workspace_skills=()):
    """MA-1.0 Integration#4 (修复): 判定 Skill target 是 Agent-specific / Shared / DENY。

    Skill ownership **不能靠名称判断**（Agent-specific 与 Shared Skill 可同名），
    正确依据是 canonical path + Agent workspace 归属：
      1. target 解析为 canonical/real path
      2. Agent-specific 仅当 canonical_target 位于 agent 的 canonical <workspace>/skills/ 下
      3. 路径边界用 commonpath（禁止字符串 startswith 绕过，如 /workspace-research-evil/）
      4. 防 ../ path traversal → DENY
      5. 解析 symlink，ownership 以 realpath 后实际目标位置为准
      6. target 只有 skill 名时，先经 skills_manifest 解析为唯一真实路径；
         找不到唯一映射 → 视为无法确定 → shared（宁可错当 Shared，不可把 Shared 错判 Agent）
      7. 无法确定 ownership → shared（fail-safe，走更严格审批）
      8. unknown agent、非法/空 target、明确 path traversal → DENY（非 shared）

    返回 {"kind": "AGENT" | "SHARED" | "DENY", "matched_by": str, "deny": bool}。
    """
    # --- 输入校验 / DENY ---
    raw = str(target or "").strip()
    if not raw:
        return {"kind": "DENY", "matched_by": "", "deny": True}
    # unknown agent → DENY（执行身份不可信，不是 ownership 不确定）
    if agent_id is not None:
        aid = str(agent_id).strip()
        ws = str(agent_workspace or "").strip()
        if aid and not ws:
            # 声称是某 agent 但无法解析其 workspace → 身份不可信 → DENY
            return {"kind": "DENY", "matched_by": "", "deny": True}

    import os

    def _is_within(path, root):
        """路径边界包含判断，用 commonpath 防止 startswith 前缀欺骗。"""
        try:
            return os.path.commonpath([os.path.realpath(path),
                                       os.path.realpath(root)]) == os.path.realpath(root)
        except ValueError:
            return False

    # --- 路径穿越 / 非法路径检测（先于所有权判断） ---
    if ".." in raw.split("/") or ".." in raw.split(os.sep):
        return {"kind": "DENY", "matched_by": "", "deny": True}
    if raw.startswith(("/", "\\")) is False and ".." in raw:
        return {"kind": "DENY", "matched_by": "", "deny": True}

    # --- 优先：target 提供真实/相对路径 → canonical 解析 ---
    # workspace 已知时，相对路径基于 workspace 规范化
    workspace_root = None
    if agent_workspace:
        workspace_root = os.path.realpath(os.path.expanduser(str(agent_workspace)))
    abs_candidate = None
    # P2-3: 统一规范化 ./ 前缀，避免 ./<abs> 被误当相对路径
    norm_raw = raw
    if norm_raw.startswith("./"):
        norm_raw = norm_raw[2:]
    if os.path.isabs(norm_raw):
        abs_candidate = os.path.realpath(os.path.expanduser(norm_raw))
    elif norm_raw.startswith("./"):
        abs_candidate = os.path.realpath(os.path.expanduser(norm_raw[2:]))
    else:
        # 相对路径（非单一 skill 名的一般路径）：尝试基于 agent workspace 规范化
        if workspace_root and "/" in norm_raw:
            abs_candidate = os.path.realpath(os.path.join(workspace_root, norm_raw))
    # symlink 已经由 realpath 解析；shared_root 亦 realpath
    shared_root_p = os.path.realpath(os.path.expanduser(shared_root)) if shared_root else None
    agent_skills_root = None
    if workspace_root:
        agent_skills_root = os.path.realpath(os.path.join(workspace_root, "skills"))

    if abs_candidate is not None:
        # 在 agent skills 根内 → AGENT
        if agent_skills_root and _is_within(abs_candidate, agent_skills_root):
            return {"kind": "AGENT", "matched_by": agent_skills_root, "deny": False}
        # 在 shared root 内 → SHARED
        if shared_root_p and _is_within(abs_candidate, shared_root_p):
            return {"kind": "SHARED", "matched_by": shared_root_p, "deny": False}
        # 两者都不在 → 无法确定 → SHARED (fail-safe)
        return {"kind": "SHARED", "matched_by": "", "deny": False}

    # --- target 只有 Skill 名（无真实路径）→ 经 manifest 唯一解析 ---
    base = raw.split("/")[-1].strip()
    if "/" not in raw:
        # 用 skills_manifest（{skill_name: abs_path}）解析唯一归属
        if isinstance(skills_manifest, dict):
            p = skills_manifest.get(base) or skills_manifest.get(raw)
            if p:
                canon = os.path.realpath(os.path.expanduser(str(p)))
                if agent_skills_root and _is_within(canon, agent_skills_root):
                    return {"kind": "AGENT", "matched_by": agent_skills_root, "deny": False}
                if shared_root_p and _is_within(canon, shared_root_p):
                    return {"kind": "SHARED", "matched_by": shared_root_p, "deny": False}
                return {"kind": "SHARED", "matched_by": "", "deny": False}
        # 无法唯一解析 → SHARED（fail-safe: 宁可 Shared 更严审批，不可误判 Agent）
        return {"kind": "SHARED", "matched_by": "", "deny": False}

    # --- 其它无法可靠解析的情形 → SHARED fail-safe ---
    return {"kind": "SHARED", "matched_by": "", "deny": False}
def find_candidate(scope, target, pattern_key, agent_id=None):
    for cid in _list_ids("candidate"):
        rec = load_artifact("candidate", cid)
        if rec and signature(rec.get("scope"), rec.get("target"),
                             rec.get("pattern_key"), rec.get("agent_id")) == \
                signature(scope, target, pattern_key, agent_id):
            return rec
    return None


# ======================== Evidence Chain ========================

def evidence_chain(regression_id=None):
    if not regression_id:
        return {"error": "provide regression_id"}
    rgr = load_artifact("regression", regression_id)
    if not rgr:
        return {"error": "regression not found: " + regression_id}
    chg = load_artifact("change", rgr.get("change_id", ""))
    prp = load_artifact("proposal", chg.get("proposal_id", "")) if chg else None
    dgn = load_artifact("diagnosis", prp.get("diagnosis_id", "")) if prp else None
    cnd = load_artifact("candidate", dgn.get("candidate_id", "")) if dgn else None
    return {
        "regression": {k: rgr.get(k) for k in ("id", "change_id", "status", "result", "evolution_id")},
        "change": {k: chg.get(k) for k in ("id", "proposal_id", "targets", "status", "evolution_id")} if chg else None,
        "proposal": {k: prp.get(k) for k in ("id", "diagnosis_id", "level", "targets", "evolution_id")} if prp else None,
        "diagnosis": {k: dgn.get(k) for k in ("id", "candidate_id", "root_cause", "valid", "evolution_id")} if dgn else None,
        "candidate": {k: cnd.get(k) for k in ("id", "scope", "target", "pattern_key", "evidence_refs", "status", "evolution_id")} if cnd else None,
    }


# ======================== Evidence Store ========================

def evidence_store_path():
    return os.path.join(evo_dir(), "evidence.jsonl")

# v2.3: Evidence 只允许来自 Verification/Evaluation 来源写入
EVIDENCE_WRITE_SOURCES = {"verification", "evaluation", "operational", "user_feedback", "proactive", "evolution_event"}

# v2.4: evolution_event 只能通过 register_evolution_event() 写入，不允许普通 register_evidence() 使用
ALLOWED_EVENT_TYPES = {"regression", "rollback"}

def register_evidence(rec, runtime_agent_id=None, runtime_session_id=None, runtime_execution_id=None, runtime_task_id=None):
    """登记 Evidence。v2.3: 验证来源合法性（Discover/Candidate/Proposal/Apply/Rollback 不允许自造 Evidence）。

    MA-1.0 Integration#2 (P2-1 增强): Evidence 层不信任调用方 JSON 里的身份字段，
    而以 Runtime 提供的真实身份为准。当传入 runtime_* 身份时，强制覆盖 rec 中的
    agent/session/execution/task 字段（Runtime 可信，防伪造 Evidence 身份）；
    不传（legacy 单 Agent）则保留 rec 原值。
    """
    source = str(rec.get("source", "")).strip().lower()
    if not source:
        raise ValueError("Evidence 写入被拒绝：source 必须存在且非空。"
                         "允许的来源：{}".format(", ".join(sorted(EVIDENCE_WRITE_SOURCES - {"evolution_event"}))))
    if source == "evolution_event":
        raise ValueError("Evidence 写入被拒绝：source='evolution_event' 必须通过 register_evolution_event() 写入，"
                         "不允许直接调用 register_evidence()。")
    if source not in EVIDENCE_WRITE_SOURCES:
        raise ValueError("Evidence 写入被拒绝：source '{}' 不在允许列表内。"
                         "允许的来源：{}".format(source, ", ".join(sorted(EVIDENCE_WRITE_SOURCES - {"evolution_event"}))))
    # MA-1.0 Integration#2: Evidence agent 归属透传（不参与 source 合法性判定）。
    #   保留多 Agent 执行身份字段，使 Evolution 能回答“这条 Evidence 是哪个
    #   Agent/哪次执行/哪个 Task 产生的”；单 Agent legacy 允许缺省。
    for _f in ("agent_id", "session_id", "execution_id", "task_id",
               "operation_id", "correlation_id"):
        rec.setdefault(_f, "")
    # P2-1: Runtime 身份优先——若提供，覆盖 rec 中的身份字段（防 Evidence 层伪造）。
    if runtime_agent_id:
        rec["agent_id"] = runtime_agent_id
    if runtime_session_id:
        rec["session_id"] = runtime_session_id
    if runtime_execution_id:
        rec["execution_id"] = runtime_execution_id
    if runtime_task_id:
        rec["task_id"] = runtime_task_id
    if rec.get("source") == "operational" and rec.get("agent_id"):
        # operational 来源若带 agent_id，回填 source_agent 便于 compute_stats 归因
        rec.setdefault("source_agent", rec.get("agent_id"))
    rec.setdefault("id", gen_id("EVID") if "EVID" in str(rec.get("id", "")) else rec.get("id") or "EVID-" + __import__("hashlib").sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:12])
    # L-02: Evidence 走原子追加（带锁），避免崩溃/并发产生半行导致 source-of-truth 静默丢失
    _PAppendAtmoic(evidence_store_path(), rec)
    # index.jsonl 是 tab 分隔裸行（非 JSONL），需裸行带锁追加
    _append_index_line("{}\t{}\t{}\n".format(rec["id"], "evidence", rec.get("pattern_key", "")))
    return rec["id"]

def load_evidence(evids=None, agent_id=None):
    out = []
    if not os.path.exists(evidence_store_path()):
        return out
    evids = set(evids) if evids else None
    _agent_id = str(agent_id or "").strip()
    with open(evidence_store_path(), encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if evids and rec.get("id") not in evids:
                continue
            # MA-1.1 安全补：按 agent_id 过滤，防止跨 Agent evidence 串流
            if _agent_id and str(rec.get("agent_id", "") or "").strip() != _agent_id:
                continue
            out.append(rec)
    return out


def register_evolution_event(event_type, change_id, reason="", regression_id=None):
    """v2.4: 系统状态转换产生的 Evidence（不是 Evolution 自造的）。
    
    必须验证：
    - evolution_id 存在且有效
    - change_id 存在且对应 Change Record 存在
    - event_type 与当前真实状态转换一致
    - regression 只能在 Change 已确认 REGRESSED 后生成
    - rollback 只能在实际执行 rollback 成功后生成
    """
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError("非法 event_type: {}（允许：{}）".format(
            event_type, ", ".join(sorted(ALLOWED_EVENT_TYPES))))
    
    chg = load_artifact("change", change_id)
    if not chg:
        raise ValueError("Change 不存在: " + change_id)
    
    evo_id = chg.get("evolution_id", "")
    if not evo_id:
        raise ValueError("Change {} 缺少 evolution_id".format(change_id))
    
    cnd_id = chg.get("candidate_id", "")
    cnd = load_artifact("candidate", cnd_id) if cnd_id else None
    # 要求4：evolution_id 对应 Candidate 必须存在（evolution 链路的根）
    if not cnd:
        raise ValueError("Change {} 缺少 candidate_id，无法确认 evolution 链路".format(change_id))
    if cnd.get("evolution_id") != evo_id and cnd.get("id") != evo_id:
        # L-03: evolution_id/eid 不匹配必须 REJECT（v1.3 hardening），不再 pass。
        #   保底只允许 candidate.id 本身等于 evo_id（顶层实体），其余不匹配一律拒绝。
        raise ValueError(
            "Change {} 的 evolution_id={} 与 Candidate {} 的 evolution_id={}/id={} 不一致，"
            "无法确认 evolution 链路".format(change_id, evo_id, cnd_id,
                                              cnd.get("evolution_id"), cnd.get("id")))
    
    prp_id = chg.get("proposal_id", "")
    prp = load_artifact("proposal", prp_id) if prp_id else None
    
    # 要求8：关联可选 verification_id / evaluation_id
    verify_id = chg.get("verification_id", "") or (prp.get("verification_id", "") if prp else "")
    eval_id = chg.get("evaluation_id", "") or (prp.get("evaluation_id", "") if prp else "")
    
    if event_type == "regression":
        # regression 只能在 Change 已确认 REGRESSED 后生成
        if chg.get("status") not in ("REGRESSED", "ROLLED_BACK"):
            raise ValueError(
                "Regression evidence 要求 Change 状态为 REGRESSED/ROLLED_BACK，"
                "当前: {}".format(chg.get("status")))
        rec = {
            "source": "evolution_event",
            "event_type": "regression",
            "evolution_id": evo_id,
            "candidate_id": cnd_id,
            "proposal_id": prp_id,
            "change_id": change_id,
            "regression_id": regression_id or "",
            "verification_id": verify_id,
            "evaluation_id": eval_id,
            "pattern_key": cnd.get("pattern_key", "") if cnd else "",
            "scope": cnd.get("scope", "AGENT") if cnd else "AGENT",
            "target": chg.get("targets", [""])[0] if chg.get("targets") else "",
            "problem": "Evolution {} 回归: {}".format(evo_id, reason or "无说明"),
            "timestamp": now_iso(),
            "verified": True,
        }
    elif event_type == "rollback":
        # rollback 只能在实际执行 rollback 成功后生成
        if chg.get("status") != "ROLLED_BACK":
            raise ValueError(
                "Rollback evidence 要求 Change 状态为 ROLLED_BACK，"
                "当前: {}".format(chg.get("status")))
        rec = {
            "source": "evolution_event",
            "event_type": "rollback",
            "evolution_id": evo_id,
            "candidate_id": cnd_id,
            "proposal_id": prp_id,
            "change_id": change_id,
            "regression_id": regression_id or chg.get("rollback", {}).get("regression_id", ""),
            "verification_id": verify_id,
            "evaluation_id": eval_id,
            "pattern_key": cnd.get("pattern_key", "") if cnd else "",
            "scope": cnd.get("scope", "AGENT") if cnd else "AGENT",
            "target": chg.get("targets", [""])[0] if chg.get("targets") else "",
            "problem": "Evolution {} 已回滚: {}".format(evo_id, reason or "无说明"),
            "timestamp": now_iso(),
            "verified": True,
        }
    else:
        raise ValueError("未知 event_type: " + event_type)
    
    # 复用 register_evidence 的写入逻辑，但跳过 source 检查（已验证）
    rec.setdefault("id", "EVID-" + __import__("hashlib").sha256(
        json.dumps(rec, sort_keys=True).encode()).hexdigest()[:12])
    # L-02: Evidence 走原子追加（带锁）
    _PAppendAtmoic(evidence_store_path(), rec)
    _append_index_line("{}\t{}\t{}\n".format(rec["id"], "evidence", rec.get("pattern_key", "")))
    return rec["id"]

def query_evidence(pattern_key=None, scope=None, target=None, exclude_internal=True,
                   agent_id=None):
    """查询 Evidence。

    MA-1.1 安全补：新增 agent_id 参数——查询某 Agent 的 evidence 时只返回该 Agent
    的记录，防止跨 Agent 串流（同一 evidence.jsonl 混存所有 Agent 记录）。

    CHAIN-04：默认 exclude_internal=True，排除 source='evolution_event' 的内部
    governance 事件（apply succeeded / proposal promoted / regression passed 等），
    防止它们被当作外部 evidence 消费。显式传 exclude_internal=False 才用于证据链
    追溯（需要看到 regression/rollback 内部事件）。
    """
    rows = []
    for rec in load_evidence(agent_id=agent_id):
        if exclude_internal and rec.get("source") == "evolution_event":
            continue
        if pattern_key and rec.get("pattern_key") != pattern_key:
            continue
        if scope and rec.get("scope") != scope:
            continue
        if target and rec.get("target") != target:
            continue
        rows.append(rec)
    return rows

def compute_stats(evids=None, pattern_key=None, scope=None, target=None, exclude_internal=True):
    """v2.3: 字段语义修正。recurrence → observation_count，新增 unique_executions/unique_sessions。

    CHAIN-04：默认 exclude_internal=True——内部 evolution_event 不作为外部 evidence 计数
    （Evolution 成功/回归/回滚本身不得自激出新 Evolution）。只有外部/真实运行 evidence
    （verification/evaluation/operational/user_feedback/proactive）才计入 recurrence。
    """
    rows = load_evidence(evids) if evids else query_evidence(
        pattern_key, scope, target, exclude_internal=exclude_internal)
    if exclude_internal:
        rows = [r for r in rows if r.get("source") != "evolution_event"]
    if not rows:
        return {"observation_count": 0, "unique_executions": 0, "unique_sessions": 0,
                "independent_sources": 0, "verified_count": 0, "systemic": False,
                "external": False, "evids": []}
    sessions = {r.get("session") for r in rows if r.get("session")}
    executions = {r.get("execution_id", r.get("id")) for r in rows}
    sources = {r.get("source", r.get("source_agent", "unknown")) for r in rows} | \
              {r.get("source_agent") for r in rows if r.get("source_agent")}
    sources.discard(None)
    if not sources:
        sources = {"evidence"}
    surface = " ".join(str(r.get(k, "")) for r in rows
                       for k in ("class", "category", "tags", "problem", "source")).lower()
    ex = ["external_environment", "network", "timeout", "third_party", "rate_limit",
          "api", "intermittent", "transient", "server_error"]
    return {
        "observation_count": len(rows),
        "unique_executions": len(executions),
        "unique_sessions": len(sessions) if sessions else None,
        "independent_sources": len(sources),
        "verified_count": sum(1 for r in rows if r.get("verified", False)),
        "systemic": any(r.get("systemic", False) for r in rows),
        "external": any(k in surface for k in ex),
        "evids": [r.get("id") for r in rows],
    }


# ======================== 结构化 Patch 引擎 ========================

def _read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

@contextlib.contextmanager
def apply_lock():
    """#32: Apply 互斥锁（fcntl.flock 阻塞锁，跨进程安全）。

    用法: with apply_lock(): ...  并发 apply 会排队，防止同一目标文件被并发 patch
    产生脏写。锁文件放 evolution 根目录 apply.lock。
    """
    import fcntl
    lock_path = os.path.join(evo_dir(), "apply.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fh = open(lock_path, "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield fh
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def baseline_fingerprints(targets):
    """#31: Apply 前记录 targets 的当前 SHA-256（基准指纹）。"""
    fps = {}
    for t in targets or []:
        rel = ws_rel(ws_abs(t))
        fps[rel] = _idutil_fingerprint(ws_abs(t))
    return fps


def record_applied_fingerprints(change_id, applied_files):
    """#31: Apply 成功后，把实际变更文件的 SHA-256 记为 'expected fingerprint'，
    写入 change record（供后续 verify/regression/crash-recovery 对照）。"""
    chg = load_artifact("change", change_id)
    if not chg:
        return None
    expected = {}
    for entry in applied_files or []:
        # apply_patch 返回 [(rel, op)] 元组；归一化为纯 rel 路径
        rel = entry[0] if isinstance(entry, (tuple, list)) else entry
        f = ws_abs(rel)
        if os.path.exists(f):
            expected[rel] = _idutil_fingerprint(f)
    chg["_expected_fingerprints"] = expected
    _core_save_artifact("change", chg)
    return expected


def verify_fingerprints(change_id):
    """#31/#32: 对照 expected fingerprint 校验当前文件是否仍一致。

    返回 (all_ok, mismatches: list[(rel, expected, current)])。
    供 Apply 后校验 / 崩溃恢复 / regression 前一致性确认。
    """
    chg = load_artifact("change", change_id)
    if not chg:
        return False, [("", "change 不存在", "")]
    expected = chg.get("_expected_fingerprints", {}) or {}
    if not expected:
        return False, [("", "no expected fingerprint", "")]
    bad = []
    for rel, exp in expected.items():
        cur = _idutil_fingerprint(ws_abs(rel))
        if cur != exp:
            bad.append((rel, exp, cur))
    return (len(bad) == 0), bad


def validate_applied_files(change_id):
    """Apply 后置校验：文件指纹必须与期望一致，否则判定不一致（供 #33 APPLIED 前置确认）。"""
    ok, bad = verify_fingerprints(change_id)
    return ok, bad


def allowed_ops(operations, targets):
    """v2.3: 严格 exact-file allowlist。dir: 前缀允许目录。"""
    allowed = set()
    dirs = set()
    for t in targets:
        if t.startswith("dir:"):
            dirs.add(ws_abs(t[4:]))
        else:
            allowed.add(ws_abs(t))
    bad = []
    for op in operations:
        f = ws_abs(op.get("file", ""))
        if not is_within_workspace(f):
            bad.append("越出 workspace: " + op.get("file", ""))
            continue
        if f in allowed:
            continue
        if any(f.startswith(d.rstrip("/") + "/") for d in dirs):
            continue
        bad.append("越出 targets: " + op.get("file", ""))
    return (len(bad) == 0), bad

def apply_patch(operations):
    """执行结构化 operations，内存回滚保证原子性。
    AE-8 (L-08): 写入前对每个文件重做 realpath 边界检查，消除 allowed_ops 检查后的
    TOCTOU 窗口（symlink 可能在 proposal 检查与 apply 写入之间被替换指向 workspace 外）。
    """
    originals = {}
    done = []
    try:
        for op in operations:
            rel = op["file"]
            path = ws_abs(rel)
            # AE-8: 写入时重做 workspace 边界检查（resolve 当前真实路径）
            if not is_within_workspace(path):
                raise ValueError("apply 时路径越出 workspace: " + rel)
            o = op.get("op")
            if rel not in originals:
                originals[rel] = _read_file(path) if os.path.exists(path) else None
            if o == "create":
                if os.path.exists(path):
                    raise ValueError("create 目标已存在: " + rel)
                _write_file(path, op.get("content", ""))
            else:
                if not os.path.exists(path):
                    raise ValueError("patch 目标不存在: " + rel)
                content = _read_file(path)
                if o == "replace":
                    old = op.get("anchor", "")
                    if not old or old not in content:
                        raise ValueError("anchor 未找到: " + str(old)[:40])
                    content = content.replace(old, op.get("content", ""), 1)
                elif o == "append":
                    content = content + op.get("content", "")
                else:
                    raise ValueError("不支持 op: " + str(o))
                _write_file(path, content)
            done.append(rel)
        return [(rel, op["op"]) for rel in done]
    except Exception:
        for rel, orig in originals.items():
            path = ws_abs(rel)
            if orig is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                _write_file(path, orig)
        raise


# ======================== Snapshot / Rollback ========================

CHANGES_DIR = "changes"

def change_dir(change_id):
    d = os.path.join(evo_dir(), CHANGES_DIR, change_id)
    os.makedirs(d, exist_ok=True)
    return d

def take_snapshot(change_id, targets):
    """Apply 前快照。workspace-relative，记录 workspace_root。"""
    snap_files = os.path.join(change_dir(change_id), "snapshot", "files")
    os.makedirs(snap_files, exist_ok=True)
    root = ws_root()
    rels = []
    for t in targets:
        t = os.path.expanduser(t)
        if not os.path.isabs(t):
            t = os.path.join(root, t)
        if not os.path.exists(t):
            continue
        rel = ws_rel(t)
        dest = os.path.join(snap_files, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(t, dest)
        rels.append(rel)
    return {"root": root, "files": rels}

def restore_snapshot(change_id, workspace_root=None):
    """v2.3: Rollback 优先用 Change Record 的 workspace root。"""
    snap_files = os.path.join(change_dir(change_id), "snapshot", "files")
    restored = []
    if not os.path.isdir(snap_files):
        return restored
    chg = load_artifact("change", change_id)
    root = (chg.get("workspace", {}).get("root") if chg else None) or workspace_root or ws_root()
    for root2, _dirs, files in os.walk(snap_files):
        for fn in files:
            src = os.path.join(root2, fn)
            rel = os.path.relpath(src, snap_files)
            dest = os.path.join(root, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            restored.append(dest)
    return restored

def target_kind(target):
    ext = os.path.splitext(str(target))[1].lower()
    if ext in (".md", ".mdx"):
        return "instruction"
    if ext in (".py", ".sh"):
        return "script"
    if ext in (".json", ".yaml", ".yml"):
        return "config"
    return "file"


# ======================== v2.3 Crash Recovery ========================

def detect_incomplete_apply():
    """启动时检测 APPLYING 状态的 change，返回需要恢复的 change_id 列表。"""
    incomplete = []
    for cid in _list_ids("change"):
        chg = load_artifact("change", cid)
        if chg and chg.get("status") == "APPLYING":
            incomplete.append(cid)
    return incomplete

def recover_apply(change_id):
    """根据 snapshot、当前文件 hash、change record 判断恢复策略。
    返回 (action, detail)。"""
    chg = load_artifact("change", change_id)
    if not chg:
        return "SKIP", "change 不存在"
    if chg.get("status") != "APPLYING":
        return "SKIP", "状态不是 APPLYING: " + str(chg.get("status"))

    snap_files = os.path.join(change_dir(change_id), "snapshot", "files")
    targets = chg.get("targets", [])
    applied_files = chg.get("_applied_files", [])

    if not os.path.isdir(snap_files):
        return "ROLLBACK", "snapshot 不存在，回滚到原始状态"

    # 检查：文件是否已被修改（snapshot 内容 != 当前内容）
    all_match = True
    any_match = False
    for rel in (chg.get("_snapshot", {}).get("files") or []):
        snap_path = os.path.join(snap_files, rel)
        cur_path = ws_abs(rel)
        if not os.path.exists(snap_path):
            continue
        snap_content = _read_file(snap_path) if os.path.exists(snap_path) else None
        cur_content = _read_file(cur_path) if os.path.exists(cur_path) else None
        if snap_content != cur_content:
            all_match = False
        else:
            any_match = True

    if all_match and not applied_files:
        # BE-7 (I-015/L-18): 副作用边界判定 — 只有当 change 明确是纯文件可逆
        # patch(create/replace/append)时才允许自动 SAFE_TO_RETRY；否则(可能带
        # 不可逆外部副作用)一律收敛为 VERIFY(人工确认)，宁可 ASK 不错 AUTO。
        if chg.get("type") != "file_patch":
            return "VERIFY", ("非纯文件 patch(type=%r)，无法确认可逆性，需人工验证"
                               % chg.get("type"))
        return "SAFE_TO_RETRY", "文件未修改，可安全重试 apply"
    elif all_match and applied_files:
        # #34: 有 expected fingerprint 时进一步校验当前文件是否与期望一致。
        # 一致→VERIFY（确认后推进）；不一致→ROLLBACK（回滚到 snapshot 保证一致）。
        ok, mism = verify_fingerprints(change_id)
        if ok or not chg.get("_expected_fingerprints"):
            return "VERIFY", "文件已完整修改，需验证"
        # BE-8: 三元整体括进首参，避免 mism 为空列表时返回字符串而非元组。
        #   原写法 `"..." + str(...) if mism else "..."` 会被解析为
        #   `(return "ROLLBACK", (...)) if mism else "..."`，空列表时解包炸裂。
        return "ROLLBACK", (
            "指纹不一致，回滚: " + str([r[0] for r in mism][:5])
            if mism else "指纹不一致")
    else:
        return "ROLLBACK", "文件部分修改，回滚到 snapshot"


# ======================== v2.3 全链路 rollback 状态同步 ========================

def rollback_full_state(change_id, reason="", regression_id=None):
    """v2.3 Rollback：同步更新 change + proposal + candidate 状态，Evidence 不删除。"""
    chg = load_artifact("change", change_id)
    if not chg:
        return None, "change 不存在"

    # 恢复文件
    restored = restore_snapshot(change_id)

    # AE-4: change 状态经状态机跳转 (REGRESSED/APPLIED → ROLLED_BACK)
    try:
        assert_transition(chg, "ROLLED_BACK", kind="change")
    except ValueError as e:
        return None, "rollback 状态跳转被拒: {}".format(e)
    chg["rollback"] = {
        "change_id": change_id,
        "rollback_at": now_iso(),
        "reason": reason or "",
        "regression_id": regression_id or "",
        "restored_files": restored,
    }
    _core_save_artifact("change", chg)

    # 更新 proposal 状态
    prp = load_artifact("proposal", chg.get("proposal_id", ""))
    if prp and prp.get("status") in ("APPLIED", "APPROVED"):
        _safe_transition(prp, "ROLLED_BACK", "proposal")
        _core_save_artifact("proposal", prp)

    # 更新 candidate 状态（标记为 regressed，不删除）
    cnd = load_artifact("candidate", chg.get("candidate_id", ""))
    if cnd and cnd.get("status") in ("DIAGNOSED", "PROPOSED", "APPROVED", "APPLIED", "APPLIED"):
        _safe_transition(cnd, "REGRESSED", "candidate")
        _core_save_artifact("candidate", cnd)

    # v2.4: Rollback 产生 evolution_event evidence
    try:
        register_evolution_event("rollback", change_id, reason=reason,
                                regression_id=regression_id)
    except ValueError:
        pass  # 状态验证失败不应阻断 rollback 本身

    # 更新 regression 记录
    if regression_id:
        rgr = load_artifact("regression", regression_id)
        if rgr:
            rgr["rolled_back_at"] = now_iso()
            _core_save_artifact("regression", rgr)

    return change_id, None


def _safe_transition(record, dst, kind):
    """安全状态跳转：失败不抛异常。"""
    try:
        assert_transition(record, dst, kind)
    except ValueError:
        pass


# ======================== #17 Progress Gate：检测器 (#16) ========================

# #16/#17 连续停滞阈值（统一常量，检测器 detect_goal_loop 与决策器 progress_gate 共用，
# 消除 magic-number 漂移；与 apply.py 的 MAX_RETRY=3 语义对称）。
STALL_THRESHOLD = 3

def _measure_progress(change_id):
    """测量 change 的当前 goal progress（量化口径：验证通过率）。

    #17 契约：Progress Gate 比较 current vs previous progress，量化口径统一为
    「验证通过的变更文件数 / 实际变更文件数（expected fingerprints 数）」。
    数据源 = apply 后置 fingerprint 校验（verify_fingerprints）的真实结果，不是
    Action changed 就视为 Goal progressed。
    返回 0.0~1.0 之间浮点；无法测量(无 targets/无 fingerprint)时返回 None，表示
    「无 Progress 信号」——交由决策器映射为 UNKNOWN（不误判为 STALL）。
    """
    chg = load_artifact("change", change_id)
    if not chg:
        return None
    targets = chg.get("targets") or []
    if not targets:
        return None
    ok, bad = verify_fingerprints(change_id)
    # verify_fingerprints 返回 (all_ok, mismatches)，mismatches 为不一致的 rel 列表。
    # 但「无 expected fingerprint」时 ok=False 且 bad=[("", "no expected fingerprint", "")]，
    # 此时不是「验证失败」而是「尚无验证基准」，不能计为 0 进展。
    expected = chg.get("_expected_fingerprints", {}) or {}
    if not expected:
        return None
    passed = len(expected) - len(bad)
    # B-1 修复：分子/分母口径统一。expected 是「实际变更文件」的子集（非全部 targets），
    # 分母用 len(expected)（而非 len(targets)），否则 progress 永远到不了 1.0。
    return float(passed) / float(len(expected))


def assess_progress(change_id):
    """#16 检测器 + #17 Progress Assessment 的数据源。

    输出（#16 ↔ #17 接口契约）：
      loop_type ∈ {ACTION, EXECUTION, GOAL}（此处固定 GOAL，Action/Execution 归 L1/L2）
      repetition_count: change 上累计的进度评估次数
      progress_delta: 本次 progress - 上次 progress（无上次则 None）
      current_progress / previous_progress
      last_action_time
    决策器 _decide_progress 消费此结构产出顶层决策词，不在此处直接改状态。
    """
    chg = load_artifact("change", change_id)
    if not chg:
        return {"loop_type": "GOAL", "repetition_count": 0, "progress_delta": None,
                "current_progress": None, "previous_progress": None,
                "last_action_time": None, "change_id": change_id}
    current = _measure_progress(change_id)
    previous = chg.get("_previous_progress")
    rep = int(chg.get("progress_assess_count", 0) or 0)
    stall = int(chg.get("consecutive_stall_count", 0) or 0)
    delta = None if (current is None or previous is None) else (current - previous)
    return {
        "loop_type": "GOAL",
        "repetition_count": rep,
        "consecutive_stall_count": stall,
        "progress_delta": delta,
        "current_progress": current,
        "previous_progress": previous,
        "progress_state": "UNKNOWN" if current is None else ("PROGRESS" if current > 0 else "STALL"),
        "last_action_time": chg.get("updated_at"),
        "change_id": change_id,
    }


def detect_goal_loop(change_id, max_stall=STALL_THRESHOLD):
    """#16 L3 Goal Progress Loop 检测器。

    检测「Action/Execution 每次都不一样，但 Goal Progress 始终为 0」的模式
    （A→B→C→D→A' 或 A→B→C 但零进展）——正是 L1/L2 检测不到的空转。

    与 assess_progress 一体两面：assess_progress 只评估进度；本函数判定是否已构成
    STALL/LOOP（连续停滞达到阈值）。不依赖 action 是否相同，只看 goal progress 信号。

    输出（#16 ↔ #17 接口契约）：
      loop_type = "GOAL"
      is_loop: bool（连续停滞 ≥ max_stall 即 True）
      repetition_count / consecutive_stall_count / progress_delta
      current_progress（0 或 None 视为无进展）
    """
    sig = assess_progress(change_id)
    stall = sig.get("consecutive_stall_count", 0)
    cur = sig.get("current_progress")
    # L3 三态修复（UNKNOWN/STALL 分离）：
    #   cur is None = 无 Progress 信号（暂时无法测量：API 不可用/验证数据未产生/无 fingerprint），
    #                 归为 UNKNOWN，不判 loop（不误停）——交由决策器映射 WAIT/VERIFY/ASK。
    #   只有「真零进展(cur<=0) 且 连续停滞(stall>=max_stall)」才是 STALL → LOOP。
    #   看 BUG：旧逻辑 no_goal_motion=(cur is None or cur<=0) 把 UNKNOWN 与 STALL 合并，
    #   当 stall 计数因别的原因已涨起时，会把「无法测量」误判成「换动作空转」→ 误 STOP。
    if cur is None:
        is_loop = False  # UNKNOWN：无法测量 ≠ 零进展，不构成 loop
    else:
        no_goal_motion = (cur <= 0)
        is_loop = no_goal_motion and stall >= max_stall
    return {
        "loop_type": "GOAL",
        "is_loop": is_loop,
        "repetition_count": sig.get("repetition_count", 0),
        "consecutive_stall_count": stall,
        "progress_delta": sig.get("progress_delta"),
        "current_progress": cur,
        "progress_state": "UNKNOWN" if cur is None else ("PROGRESS" if cur > 0 else "STALL"),
        "change_id": change_id,
    }


def record_progress_assessment(change_id, signal):
    """把一次 Progress Assessment 结果写回 change record（可溯源）。

    #17 契约：决策必须可溯源——记录 progress_signal（当前 vs 上次）+ 计数。
    只写观测字段，不改 status（状态变更由决策器经 #13 门单独落地）。
    """
    chg = load_artifact("change", change_id)
    if not chg:
        return None
    chg["_previous_progress"] = signal.get("current_progress")
    chg["progress_assess_count"] = signal.get("repetition_count", 0) + 1
    # #17 修复：单独维护连续停滞计数(consecutive_stall_count)，delta==0 自增、delta>0 清零。
    #   避免用全局评估次数误判 STOP（长期有进展、偶发一次停滞会被过早 STOP）。
    delta = signal.get("progress_delta")
    if delta is not None and delta > 0:
        chg["consecutive_stall_count"] = 0
    elif delta is not None and delta == 0:
        chg["consecutive_stall_count"] = int(chg.get("consecutive_stall_count", 0) or 0) + 1
    chg["progress_assessed_at"] = now_iso()
    _core_save_artifact("change", chg)
    return chg


def _core_save_artifact(kind, record):
    """内部保存（不走 index append，避免重复）。"""
    prefix = {"candidate": "CAND", "diagnosis": "DGN", "proposal": "PRP",
              "change": "CHG", "regression": "RGR"}[kind]
    ident = record.get("id")
    if not ident:
        record["id"] = gen_id(prefix)
        ident = record["id"]
    record["updated_at"] = now_iso()
    sub = subdir(kind_dir(kind))
    path = os.path.join(sub, ident + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


# ======================== CLI 工具 ========================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--chain":
        print(json.dumps(evidence_chain(sys.argv[2] if len(sys.argv) > 2 else None),
                         ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--recover":
        for cid in detect_incomplete_apply():
            action, detail = recover_apply(cid)
            print(json.dumps({"change_id": cid, "action": action, "detail": detail},
                             ensure_ascii=False, indent=2))
    else:
        print("Self-Evolution v2.3 core — 状态机/幂等/存储/可追溯/crash recovery。")
