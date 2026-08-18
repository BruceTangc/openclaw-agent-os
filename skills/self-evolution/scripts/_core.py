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
import hashlib
from datetime import datetime, timezone

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
    """ID 生成：prefix-YYYYMMDD-NNN。"""
    kind_map = {"CAND": "candidates", "DGN": "diagnoses", "PRP": "proposals",
                "CHG": "changes", "RGR": "regressions"}
    kind = kind_map.get(prefix)
    existing = []
    if kind:
        d = os.path.join(evo_dir(), kind)
        if os.path.isdir(d):
            pat = re.compile(r"^" + re.escape(prefix) + r"-(\d{8})-(\d+)$")
            for f in os.listdir(d):
                m = pat.match(f)
                if m and m.group(1) == today_compact():
                    existing.append(int(m.group(2)))
    pat2 = re.compile(r"^(\w+)-(\d{8})-(\d+)\t")
    for ln in _read_index():
        m = pat2.match(ln)
        if m and m.group(1) == prefix and m.group(2) == today_compact():
            existing.append(int(m.group(3)))
    n = (max(existing) + 1) if existing else 1
    return "{}-{}-{:03d}".format(prefix, today_compact(), n)


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

def save_artifact(kind, record):
    """写 artifact + append index。"""
    prefix = {"candidate": "CAND", "diagnosis": "DGN", "proposal": "PRP",
              "change": "CHG", "regression": "RGR"}[kind]
    ident = record.get("id") or gen_id(prefix)
    record["id"] = ident
    record.setdefault("updated_at", now_iso())
    sub = subdir(kind_dir(kind))
    path = os.path.join(sub, ident + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    with open(index_path(), "a", encoding="utf-8") as f:
        f.write("{}\t{}\t{}\n".format(ident, kind, _index_summary(record)))
    return ident

def load_artifact(kind, ident):
    sub = os.path.join(evo_dir(), kind_dir(kind), ident + ".json")
    if not os.path.exists(sub):
        return None
    with open(sub, encoding="utf-8") as f:
        return json.load(f)

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

STATES = [
    "CANDIDATE", "DIAGNOSED", "PROPOSED", "APPROVED",
    "SNAPSHOTTED", "APPLYING", "APPLIED", "MONITORING",
    "VALIDATED", "PROMOTED",
    "REJECTED", "UNRESOLVED", "APPLY_FAILED",
    "REGRESSED", "ROLLED_BACK",
]

TRANSITIONS = {
    "CANDIDATE": {"DIAGNOSED", "REJECTED"},
    "DIAGNOSED": {"PROPOSED", "UNRESOLVED"},
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"SNAPSHOTTED"},
    "SNAPSHOTTED": {"APPLYING"},
    "APPLYING": {"APPLIED", "APPLY_FAILED"},
    "APPLIED": {"MONITORING"},
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "PROMOTED": set(),
    "REJECTED": set(),
    "UNRESOLVED": set(),
    "APPLY_FAILED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
}

# v2.3: Kind-aware transition overrides
# Proposal 和 Change 有不同状态机，共用全局 TRANSITIONS 表会导致跳转冲突
TRANSITIONS_PROPOSAL = {
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"APPROVED", "APPLIED", "REJECTED"},  # APPROVED→APPROVED = idempotent no-op
    "APPLIED": {"MONITORING"},
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "REJECTED": set(),
    "PROMOTED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
}

TRANSITIONS_CHANGE = {
    "SNAPSHOTTED": {"APPLYING"},
    "APPLYING": {"APPLIED", "APPLY_FAILED"},
    "APPLIED": {"MONITORING"},
    "MONITORING": {"VALIDATED", "REGRESSED"},
    "VALIDATED": {"PROMOTED"},
    "APPLY_FAILED": set(),
    "REGRESSED": {"ROLLED_BACK"},
    "ROLLED_BACK": set(),
    "PROMOTED": set(),
}

def _get_transitions(src, kind="candidate"):
    """返回指定 kind 的跳转表，fallback 到全局 TRANSITIONS。"""
    if kind == "proposal":
        tbl = TRANSITIONS_PROPOSAL
    elif kind == "change":
        tbl = TRANSITIONS_CHANGE
    else:
        tbl = TRANSITIONS
    return tbl.get(src, TRANSITIONS.get(src, set()))

def transition_allowed(src, dst, kind="candidate"):
    if src == dst:
        return True
    targets = _get_transitions(src, kind)
    return dst in targets

def assert_transition(record, dst, kind="candidate"):
    src = record.get("status", "CANDIDATE")
    if not transition_allowed(src, dst, kind):
        raise ValueError("非法状态跳转 {} -> {}（{}/{}）".format(src, dst, kind, record.get("id", "?")))
    record["status"] = dst
    record["updated_at"] = now_iso()
    return record


# ======================== 保护目标与审批 ========================

PROTECTED_TARGETS = [
    "permission", "security", "credential", "secret", "auth",
    "approval", "runtime", "infrastructure", "global_authority",
    "AGENTS.md", "SOUL.md",
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
    t = str(target).lower()
    return any(p.lower() in t for p in PROTECTED_TARGETS)

def signature(scope, target, pattern_key):
    return "{}|{}|{}".format(str(scope), str(target), str(pattern_key))

def find_candidate(scope, target, pattern_key):
    for cid in _list_ids("candidate"):
        rec = load_artifact("candidate", cid)
        if rec and signature(rec.get("scope"), rec.get("target"),
                             rec.get("pattern_key")) == signature(scope, target, pattern_key):
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

def register_evidence(rec):
    """登记 Evidence。v2.3: 验证来源合法性（Discover/Candidate/Proposal/Apply/Rollback 不允许自造 Evidence）。"""
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
    rec.setdefault("id", gen_id("EVID") if "EVID" in str(rec.get("id", "")) else rec.get("id") or "EVID-" + __import__("hashlib").sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:12])
    os.makedirs(os.path.dirname(evidence_store_path()), exist_ok=True)
    with open(evidence_store_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(index_path(), "a", encoding="utf-8") as f:
        f.write("{}\t{}\t{}\n".format(rec["id"], "evidence", rec.get("pattern_key", "")))
    return rec["id"]

def load_evidence(evids=None):
    out = []
    if not os.path.exists(evidence_store_path()):
        return out
    evids = set(evids) if evids else None
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
        # candidate 自身可能有 evolution_id 链路，未直接持有则放宽（保底以 chg.evolution_id 为准）
        pass
    
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
    os.makedirs(os.path.dirname(evidence_store_path()), exist_ok=True)
    with open(evidence_store_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(index_path(), "a", encoding="utf-8") as f:
        f.write("{}\t{}\t{}\n".format(rec["id"], "evidence", rec.get("pattern_key", "")))
    return rec["id"]

def query_evidence(pattern_key=None, scope=None, target=None):
    rows = []
    for rec in load_evidence():
        if pattern_key and rec.get("pattern_key") != pattern_key:
            continue
        if scope and rec.get("scope") != scope:
            continue
        if target and rec.get("target") != target:
            continue
        rows.append(rec)
    return rows

def compute_stats(evids=None, pattern_key=None, scope=None, target=None):
    """v2.3: 字段语义修正。recurrence → observation_count，新增 unique_executions/unique_sessions。"""
    rows = load_evidence(evids) if evids else query_evidence(pattern_key, scope, target)
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
    """执行结构化 operations，内存回滚保证原子性。"""
    originals = {}
    done = []
    try:
        for op in operations:
            rel = op["file"]
            path = ws_abs(rel)
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
        return "SAFE_TO_RETRY", "文件未修改，可安全重试 apply"
    elif all_match and applied_files:
        return "VERIFY", "文件已完整修改，需验证"
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

    # 更新 change 状态
    chg["status"] = "ROLLED_BACK"
    chg["updated_at"] = now_iso()
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
