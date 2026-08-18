#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_core.py — Self-Evolution v2 共享核心（Code = Enforcement）

职责（属于 Self-Evolution 自身的治理实现，不重复 Agent OS/OpenClaw 能力）：
- Evolution artifact 存储（.agent-os/evolution/ 下的 JSON + index.jsonl）
- ID 生成（CAND/DGN/PRP/CHG/RGR 前缀 + 日期序号）
- 状态机合法跳转表（CANDIDATE → DIAGNOSED → PROPOSED → APPROVED → APPLIED → REGRESSION → PROMOTED，
  失败路径 REJECTED / UNRESOLVED / REGRESSED / ROLLED_BACK，禁止非法跳转）
- 幂等判定（scope+target+pattern_key 去重；Change/Regression 不重复 Apply/记录）
- 双向可追溯 Evidence Chain（regression_id ↔ change_id ↔ proposal_id ↔ diagnosis_id ↔ candidate_id ↔ evidence_ids）
- 保护目标白名单（Permission/Security/Credentials/Auth/AGENTS/SOUL 等，永远不可由演进自动修改）

存储布局：
    .agent-os/evolution/
    ├── candidates/     CAND-*.json
    ├── diagnoses/      DGN-*.json
    ├── proposals/      PRP-*.json
    ├── changes/        CHG-*.json + CHG-*/snapshot/ （Apply 前快照，Rollback 用）
    ├── regressions/    RGR-*.json
    └── index.jsonl     全量可追溯索引（append-only）

LLM = Reasoning；本模块 = Enforcement。阈值/状态/审批/快照/回滚/回归/晋升全部由这里决定。
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone

# ------------------------- 路径 -------------------------

def _workspace():
    return (
        os.environ.get("OPENCLAW_WORKSPACE")
        or os.environ.get("OPENCLAW_WORKSPACE_DIR")
        or os.path.expanduser("~/.openclaw/workspace")
    )


def evo_dir():
    return os.path.join(_workspace(), ".agent-os", "evolution")


def ws_root():
    """workspace 根（所有 target 以它做相对解析，避免绝对路径跨 workspace 污染）。"""
    return os.path.realpath(_workspace())


def ws_rel(p):
    """绝对路径 → workspace 相对路径（越界则原样返回相对化）。"""
    p = os.path.realpath(os.path.expanduser(p))
    try:
        return os.path.relpath(p, ws_root())
    except ValueError:
        return p.lstrip("/")


def ws_abs(rel):
    """workspace 相对路径 → 绝对路径（绝对则原样）。"""
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
    """统一路径解析：所有 Snapshot/Apply/Rollback/allowed_ops/diff 共享。
    避免 workspace 参数 vs global ws_root() 的 API 假象。"""
    def __init__(self, root=None):
        self.root = root or ws_root()

    def resolve(self, rel):
        """workspace 相对路径 → 绝对路径。"""
        if os.path.isabs(rel):
            return os.path.realpath(rel)
        return os.path.realpath(os.path.join(self.root, rel))

    def relative(self, abs_path):
        """绝对路径 → workspace 相对路径。"""
        return os.path.relpath(os.path.realpath(abs_path), self.root)

    def contains(self, abs_path):
        """路径是否在 workspace 内。"""
        return is_within_workspace(abs_path, self.root)

    def snapshot_path(self, change_id):
        """workspace-relative snapshot 路径。"""
        return os.path.join(evo_dir(), CHANGES_DIR, change_id, "snapshot", "files")


# ------------------------- Evidence Store（治理 artifact，非 Runtime） -------------------------
# Agent OS 的 Verification/Evaluation 产出 Evidence，注册进这个 JSONL 索引。
# discover 从 IDs 读取并**自算**统计，而不是信任调用者填的 recurrence/sessions。

def evidence_store_path():
    return os.path.join(evo_dir(), "evidence.jsonl")


def register_evidence(rec):
    """登记一条 Evidence（分配 EVID id）并 append 到 evidence.jsonl + index。"""
    rec.setdefault("id", gen_id("EVID"))
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


def query_evidence(pattern_key=None, scope=None, target=None):
    """按 pattern_key(必) / scope / target 取历史 Evidence，用于自算统计。"""
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
    """由 Evidence（IDs 或按 pattern 查询）**自算**统计，不信任调用者声称值。
    返回 {recurrence, sessions, independent_sources, verified_count, systemic, external, evids}。"""
    rows = []
    if evids:
        rows = load_evidence(evids)
    else:
        rows = query_evidence(pattern_key, scope, target)
    if not rows:
        return {"recurrence": 0, "sessions": 0, "independent_sources": 0,
                "verified_count": 0, "systemic": False, "external": False, "evids": []}
    sessions = {r.get("session", r.get("id")) for r in rows if r.get("session")}
    sources = {r.get("source", r.get("source_agent", r.get("source", "unknown")))
               for r in rows} | {r.get("source_agent") for r in rows if r.get("source_agent")}
    sources.discard(None)
    if not sources:
        sources = {"evidence"}
    surface = " ".join(str(r.get(k, "")) for r in rows for k in ("class", "category", "tags", "problem", "source")).lower()
    ex = ["external_environment", "network", "timeout", "third_party", "rate_limit",
          "api", "intermittent", "transient", "server_error"]
    return {
        "recurrence": len(rows),
        "sessions": len(sessions) if sessions else None,
        "independent_sources": len(sources),
        "verified_count": sum(1 for r in rows if r.get("verified", False)),
        "systemic": any(r.get("systemic", False) for r in rows),
        "external": any(k in surface for k in ex),
        "evids": [r.get("id") for r in rows],
    }


# ------------------------- 结构化 Patch 引擎（Apply 真正动手 + 校验） -------------------------
# Proposal.change 为结构化 operations，Apply 只执行这些 operation、并校验结果在允许范围内。
# operations:
#   {"op": "replace",  "file": "skills/x/SKILL.md", "anchor": "旧文本", "content": "新文本"}
#   {"op": "append",   "file": "...",                "content": "追加文本\n"}
#   {"op": "create",   "file": "new.md",            "content": "内容"}


def _read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def allowed_ops(operations, targets):
    """严格 allowlist：每个 operation 的 file 必须精确等于某个 target。
    默认 target=file，只有显式 dir: 前缀才允许目录匹配。"""
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
        # 精确匹配 OR 在显式声明的目录内
        if f in allowed:
            continue
        if any(os.path.dirname(f).startswith(d.rstrip("/") + "/") or f.startswith(d.rstrip("/") + "/")
               for d in dirs):
            continue
        bad.append("越出 targets: " + op.get("file", ""))
    return (len(bad) == 0), bad


def apply_patch(operations, workspace=None):
    """执行结构化 operations（真正写文件）。返回 [(rel_path, op)]。

    安全：每个将写文件先读原内容到内存，任一失败→恢复内存原内容（不依赖磁盘快照）。
    只允许 replace/append/create 三种 op，file 必须在 workspace 内（调用方先 allowed_ops 校验）。"""
    ws = workspace or ws_root()
    originals = {}   # rel -> 原内容（或 None=原本不存在）
    done = []
    try:
        for op in operations:
            rel = op["file"]
            path = ws_abs(rel)
            o = op.get("op")
            # 记录原状（仅首次）
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
        # 回滚：恢复内存原状
        for rel, orig in originals.items():
            path = ws_abs(rel)
            if orig is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                _write_file(path, orig)
        raise


def ws_rel_path(abs_path, ws=None):
    ws = ws or ws_root()
    try:
        return os.path.relpath(abs_path, ws)
    except ValueError:
        return os.path.basename(abs_path)



# kind -> 存储子目录名（显式映射，避免 diagnosis 复数拼错：diagnoses, 不是 diagnosiss）
KIND_DIR = {
    "candidate": "candidates",
    "diagnosis": "diagnoses",
    "proposal": "proposals",
    "change": "changes",
    "regression": "regressions",
}


def kind_dir(kind):
    return KIND_DIR.get(kind, kind + "s")


def subdir(name):
    d = os.path.join(evo_dir(), name)
    os.makedirs(d, exist_ok=True)
    return d


def index_path():
    return os.path.join(evo_dir(), "index.jsonl")


def now_iso():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def today_compact():
    return datetime.now().strftime("%Y%m%d")


def gen_id(prefix):
    """生成 CAND-YYYYMMDD-NNN（当日自增序号，读 index + 现有文件保证单调）。

    prefix 到 kind 反查（CAND->candidate, DGN->diagnosis...）以定位正确子目录。
    """
    # prefix 前3字符 -> kind
    kind_by_prefix = {"CND": "candidate", "DGN": "diagnosis",
                      "PRP": "proposal", "CHG": "change", "RGR": "regression"}
    kind = None
    for k, p in ((k, v) for v, k in kind_by_prefix.items()):
        if prefix.startswith(p):
            kind = k
            break
    existing = []
    if kind:
        d = os.path.join(evo_dir(), kind_dir(kind))
        if os.path.isdir(d):
            pat = re.compile(r"^" + re.escape(prefix) + r"-(\d{8})-(\d+)$")
            for f in os.listdir(d):
                m = pat.match(f)
                if m and m.group(1) == today_compact():
                    existing.append(int(m.group(2)))
    pat2 = re.compile(r"^(\w+)-(\d{8})-(\d+)\t")
    for line in _read_index():
        m = pat2.match(line)
        if m and m.group(1) == prefix and m.group(2) == today_compact():
            existing.append(int(m.group(3)))
    n = (max(existing) + 1) if existing else 1
    return "{}-{}-{:03d}".format(prefix, today_compact(), n)


def _read_index():
    if not os.path.exists(index_path()):
        return []
    with open(index_path(), encoding="utf-8") as f:
        return [ln.rstrip("\n") for ln in f if ln.strip()]


def save_artifact(kind, record):
    """kind: candidate/diagnosis/proposal/change/regression。写 JSON + append index。"""
    prefix = {"candidate": "CAND", "diagnosis": "DGN",
              "proposal": "PRP", "change": "CHG", "regression": "RGR"}[kind]
    ident = record.get("id") or gen_id(prefix)
    record["id"] = ident
    record.setdefault("updated_at", now_iso())
    sub = subdir(kind_dir(kind))
    path = os.path.join(sub, ident + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    # index 一行 = id\tkind\tstatus\tparent_chain_summary
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
            "proposal_id", "change_id", "root_cause", "result", "status")
    return "|".join(str(rec.get(k, "")) for k in keys)


# ------------------------- 状态机 -------------------------

STATES = [
    "CANDIDATE", "DIAGNOSED", "PROPOSED", "APPROVED",
    "APPLIED", "REGRESSION", "PROMOTED",
    "REJECTED", "UNRESOLVED", "REGRESSED", "ROLLED_BACK",
]

# 合法状态跳转：src -> {dsts}
TRANSITIONS = {
    "CANDIDATE": {"DIAGNOSED", "REJECTED"},
    "DIAGNOSED": {"PROPOSED", "UNRESOLVED"},
    "PROPOSED": {"APPROVED", "REJECTED"},
    "APPROVED": {"APPLIED"},
    "APPLIED": {"REGRESSION"},
    "REGRESSION": {"PROMOTED", "REGRESSED"},
    "REGRESSED": {"ROLLED_BACK"},
    "REJECTED": set(),
    "UNRESOLVED": set(),
    "PROMOTED": set(),
    "ROLLED_BACK": set(),
}


def transition_allowed(src, dst):
    if src == dst:
        return True  # 幂等：同状态再确认不作跳转
    if src not in TRANSITIONS:
        return False
    return dst in TRANSITIONS[src]


def assert_transition(record, dst, kind="candidate"):
    """校验并推进状态（非法跳转抛 ValueError）。返回更新后的 record。"""
    src = record.get("status", "CANDIDATE")
    if not transition_allowed(src, dst):
        raise ValueError(
            "非法状态跳转 {} -> {}（{}/{}）".format(src, dst, kind, record.get("id", "?")))
    record["status"] = dst
    record["updated_at"] = now_iso()
    return record

# ------------------------- 幂等 -------------------------

# 保护目标：永远不可由 Self-Evolution 自动修改
PROTECTED_TARGETS = [
    "permission", "security", "credential", "secret", "auth",
    "approval", "runtime", "infrastructure", "global_authority",
    "AGENTS.md", "SOUL.md",
]

# G 级别：approval 要求（遵循 Agent OS EVOLUTION-PROTOCOL）
APPROVAL_BY_LEVEL = {
    "G1": "optional",       # 低风险指令措辞：可走已有授权策略
    "G2": "optional",       # 示例/模板：可走已有授权策略
    "G3": "review",         # 工作流/流程：需 review
    "G4": "review_human",   # 评估标准/验证等级：需 review + 人工
    "G5": "human",          # 协议/策略：必须人工
    "G6": "human",          # 安全/权限/Runtime：禁止自动，强制人工
}
LEVELS = ["G1", "G2", "G3", "G4", "G5", "G6"]


def require_human_approval(level):
    return APPROVAL_BY_LEVEL.get(level) in ("human", "review_human")


def is_protected_target(target):
    t = str(target).lower()
    for p in PROTECTED_TARGETS:
        if p.lower() in t:
            return True
    return False


def signature(scope, target, pattern_key):
    """幂等签名：scope+target+pattern_key。"""
    return "{}|{}|{}".format(str(scope), str(target), str(pattern_key))


def find_candidate(scope, target, pattern_key):
    """按幂等签名找既有未终结 Candidate。"""
    for cid in _list_ids("candidate"):
        rec = load_artifact("candidate", cid)
        if rec and signature(rec.get("scope"), rec.get("target"),
                             rec.get("pattern_key")) == signature(scope, target, pattern_key):
            return rec
    return None


def _list_ids(kind):
    sub = os.path.join(evo_dir(), kind_dir(kind))
    if not os.path.isdir(sub):
        return []
    return sorted(f[:-5] for f in os.listdir(sub) if f.endswith(".json"))

# ------------------------- 可追溯 -------------------------


def evidence_chain(regression_id=None):
    """双向追溯：从任意 artifact id 出发，沿 parent 链回溯到 Candidate + Evidence。"""
    if regression_id:
        rgr = load_artifact("regression", regression_id)
        if not rgr:
            return {"error": "regression not found: " + regression_id}
        chg = load_artifact("change", rgr.get("change_id", ""))
        prp = load_artifact("proposal", chg.get("proposal_id", "")) if chg else None
        dgn = load_artifact("diagnosis", prp.get("diagnosis_id", "")) if prp else None
        cnd = load_artifact("candidate", dgn.get("candidate_id", "")) if dgn else None
        return {
            "regression": {k: rgr.get(k) for k in ("id", "change_id", "status", "result")},
            "change": {k: chg.get(k) for k in ("id", "proposal_id", "targets", "status")} if chg else None,
            "proposal": {k: prp.get(k) for k in ("id", "diagnosis_id", "level", "targets")} if prp else None,
            "diagnosis": {k: dgn.get(k) for k in ("id", "candidate_id", "root_cause", "valid")} if dgn else None,
            "candidate": {k: cnd.get(k) for k in ("id", "scope", "target", "pattern_key",
                                                   "evidence_refs", "status")} if cnd else None,
        }
    return {"error": "provide regression_id"}


# ------------------------- Snapshot / Rollback -------------------------

CHANGES_DIR = "changes"


def change_dir(change_id):
    d = os.path.join(evo_dir(), CHANGES_DIR, change_id)
    os.makedirs(d, exist_ok=True)
    return d


def take_snapshot(change_id, targets):
    """Apply 前把目标文件快照到 changes/CHG-*/snapshot/files/<workspace相对路径>。

    workspace-relative：不产生跨 workspace / 跨用户 / 绝对路径污染；
    Change Record 记录 workspace_root，Rollback 时 root + relative 还原。
    返回 {root, files: [rel,...]}。"""
    snap_files = os.path.join(change_dir(change_id), "snapshot", "files")
    os.makedirs(snap_files, exist_ok=True)
    root = ws_root()
    rels = []
    for t in targets:
        t = os.path.expanduser(t)
        if not os.path.exists(t):
            # 尝试以 workspace root 解析
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
    """Rollback：从 snapshot/files/<rel> 恢复。

    优先使用 Change Record 记录的 workspace root（确定性）；
    仅当 Change Record 未记录时 fallback 到 workspace_root 参数或当前 workspace。
    返回恢复的绝对路径列表。"""
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


# CLI 小工具
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--chain":
        print(json.dumps(evidence_chain(sys.argv[2] if len(sys.argv) > 2 else None),
                         ensure_ascii=False, indent=2))
    else:
        print("Self-Evolution v2 core — 状态机/幂等/存储/可追溯。用各命令脚本调用。")
