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
    """Apply 前把目标文件快照到 changes/CHG-*/snapshot/（保留相对路径）。"""
    snap = os.path.join(change_dir(change_id), "snapshot")
    os.makedirs(snap, exist_ok=True)
    for t in targets:
        t = os.path.expanduser(t)
        if not os.path.exists(t):
            continue
        rel = t.lstrip("/")
        dest = os.path.join(snap, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(t, dest)
    return snap


def restore_snapshot(change_id):
    """Rollback：从 snapshot 恢复目标文件到原位置。返回恢复的文件列表。"""
    snap = os.path.join(change_dir(change_id), "snapshot")
    restored = []
    if not os.path.isdir(snap):
        return restored
    for root, _dirs, files in os.walk(snap):
        for fn in files:
            src = os.path.join(root, fn)
            rel = os.path.relpath(src, snap)
            dest = os.path.join("/", rel)   # 恢复绝对路径
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
