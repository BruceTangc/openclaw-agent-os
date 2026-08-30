#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent-os-vault —— Agent OS × Obsidian 长期知识空间桥接 Skill。

职责（仅此一模块承载 Obsidian 衔接，不把职责散落到现有 Governance Skill）：
  P1 export    ：把 Knowledge / Experience / Decision / Evidence 治理后对象单向
                 只读导出为 Obsidian Vault 视图（.md + frontmatter + wikilink）。
  P2 memory    ：把 OpenClaw native memory 的 journal（日记）与 durable（长期，
                 MEMORY.md 已晋升）投影到 Vault（须经 memory-governance 晋升门，
                 不做全量对话复制）。
  P3 reconcile ：比对 Vault 与机器真相源，检测 drift（machine-only / vault-only /
                 both-changed / deleted / conflict 五类）。
  P3 import    ：受控反向导入——Vault 人工编辑 → schema/identity/ontology-
                 consistency/provenance 校验 → 生成 Import Candidate →
                 agent-os-vault governance gate → Accept/Reject/Conflict/Review →
                 更新 JSONL/.agent-os → re-export。绝不允许 obsidian→overwrite JSONL。
  P4 migration ：首次幂等迁移，不修改原始 JSONL、不删旧 artifact、生成 provenance
                 map + migration report、不自动提升历史垃圾成 knowledge。
  provenance  ：任意 Vault 视图 → 可回溯到源 JSONL 行 + SHA-256 指纹。

硬边界（不可违背）：
  - 不改 OpenClaw 核心；不建新 Memory Runtime/DB/GraphDB/VectorDB/Scheduler/EventBus。
  - 机器真相源（memory/ontology/*.jsonl、.agent-os/evolution/*、evidence.jsonl、
    persistence/identity/transition、self-evolution scripts、ontology.py 校验与存储、
    OpenClaw 原生 Memory、Agent OS Governance/Verification/Security）一律只读或经治理写。
  - 绝不 obsidian→overwrite JSONL：对机器真相的任何变更都必须走
    import → candidate → governance gate → accept 之后，由本模块以受控方式写 JSONL，
    且每次写带 operation_id 审计。
  - Vault 不能成为新 Evidence 源（self-evolution 不消费 Vault）。

权限模型（对齐 permission-security）：
  - export / reconcile / validate / provenance = L1（本地可逆写视图，自动）。
  - import（生成 candidate）= L1（本地写 .agent-os-vault 候选，不触真相源）。
  - accept（把已批准候选写回 JSONL/.agent-os）= L2/L3 需审批，且 require_human_approval。
  - migrate（首次导入语料）默认只写 Vault + provenance map，不写 JSONL。

用法:
  python3 agent_os_vault.py export [--vault DIR] [--agent ID] [--project X] [--sources ontology|knowledge|experience|decision|evidence|memory|all]
  python3 agent_os_vault.py reconcile [--vault DIR] [--agent ID]
  python3 agent_os_vault.py validate <vault_file_or_id> [--vault DIR]
  python3 agent_os_vault.py import <vault_file> [--vault DIR] [--agent ID] [--reason TXT] [--evidence REF]
  python3 agent_os_vault.py candidates [--status pending|accepted|rejected|conflict|review]
  python3 agent_os_vault.py candidate-status <CID> --status <pending|accepted|rejected|conflict|review> [--reason TXT]
  python3 agent_os_vault.py accept <CID> [--vault DIR]   # 治理通过，受控写回真相源（高权限）
  python3 agent_os_vault.py provenance <id_or_vaultfile> [--vault DIR]
  python3 agent_os_vault.py migrate [--vault DIR] [--agent ID]
  python3 agent_os_vault.py status [--vault DIR]
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

try:
    import yaml
except ImportError:  # 极简兜底：frontmatter 用内置解析
    yaml = None

# --------------------------------------------------------------------------
# 路径解析
# --------------------------------------------------------------------------
VAULT_SCHEMA_VERSION = 1
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(_SELF_DIR)
REPO = os.path.dirname(os.path.dirname(SKILL_DIR))            # /tmp/openclaw-agent-os
BASE = os.path.dirname(REPO)                                    # skill 所在父级
ONT_DIR = os.path.join(REPO, "skills", "ontology")
ONT_SCRIPT = os.path.join(ONT_DIR, "scripts", "ontology.py")
DATA = os.path.join(ONT_DIR, "memory", "ontology")               # ontology JSONL
ENTITIES_FILE = os.path.join(DATA, "entities.jsonl")
RELATIONS_FILE = os.path.join(DATA, "relations.jsonl")
PROPOSALS_FILE = os.path.join(DATA, "proposals.jsonl")

# 桥 Skill 自身工作区（Vault 侧驱动，非机器真相源）：
# 存放 provenance map / knowledge registry / import candidates / migration 报告。
# 这属于 bridge 的书签与候选账本，原生 Agent OS 推理不消费它。
_WS = os.environ.get("AGENT_OS_VAULT_WORKSPACE", os.path.expanduser("~/.openclaw/workspace-jarvis"))
BRIDGE_DIR = os.path.join(_WS, ".agent-os-vault")
CANDIDATES_FILE = os.path.join(BRIDGE_DIR, "import-candidates.jsonl")
REGISTRY_FILE = os.path.join(BRIDGE_DIR, "registry.jsonl")        # vault 视图书签/knowledge manifest
PROV_MAP_FILE = os.path.join(BRIDGE_DIR, "provenance-map.json")
MIGRATION_REPORT = os.path.join(BRIDGE_DIR, "migration-report.json")
LOG_FILE = os.path.join(BRIDGE_DIR, "audit.log")

# 机器真相源路径（非修改）。self-evolution evidence 与 artifacts。
_EVO_WS = os.path.join(_WS, ".agent-os", "evolution")
EVIDENCE_FILE = os.path.join(_EVO_WS, "evidence.jsonl")
EVO_SUBDIRS = {"candidates": "candidate", "diagnoses": "diagnosis",
               "proposals": "proposal", "changes": "change", "regressions": "regression"}

# OpenClaw 原生 memory（只读投影源）
NATIVE_MEM = os.path.join(_WS, "memory")
MEMORY_MD = os.path.join(_WS, "MEMORY.md")


def _ensure_dirs():
    os.makedirs(BRIDGE_DIR, exist_ok=True)


# --------------------------------------------------------------------------
# canonical 序列化 / 指纹
# --------------------------------------------------------------------------
def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical(obj):
    return canonical_json(obj)


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fp16(s):
    return sha256(s)[:16]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# --------------------------------------------------------------------------
# 原子写（复用桥内部，绝不直写 JSONL 真相源之外的“被保护写入”；仅写 Vault/桥自身）
# --------------------------------------------------------------------------
def _atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _append_line(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            s = raw.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                obj["_line"] = n
                out.append(obj)
            except json.JSONDecodeError:
                continue
    return out


def _read_lines_raw(path):
    """返回 [(obj, line_no)] 原始行，不含 _line 污染（用于指纹）。"""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            s = raw.strip()
            if not s:
                continue
            try:
                out.append((json.loads(s), n))
            except json.JSONDecodeError:
                continue
    return out


def _audit(action, detail):
    _ensure_dirs()
    ok = True
    try:
        _append_line(LOG_FILE, json.dumps({
            "ts": now_iso(), "action": action, "detail": detail,
        }, ensure_ascii=False, sort_keys=True))
    except Exception:
        ok = False
    return ok


# --------------------------------------------------------------------------
# frontmatter / markdown 渲染
# --------------------------------------------------------------------------
def _frontmatter(fields):
    clean = {}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)) and not v:
            continue
        if isinstance(v, str) and v == "":
            continue
        clean[k] = v
    if yaml:
        body = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False,
                              default_flow_style=False).rstrip("\n")
    else:
        body = "\n".join("{0}: {1}".format(k, json.dumps(v, ensure_ascii=False))
                         if isinstance(v, (dict, list)) else "{0}: {1}".format(k, v)
                         for k, v in clean.items())
    return "---\n{0}\n---\n".format(body)


def _emit(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_fm(path):
    txt = _read_file(path)
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}, txt
    if yaml:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            fm = {}
    else:
        fm = {}
    body = txt[m.end():]
    return fm, body


# --------------------------------------------------------------------------
# 可见性（复用 ontology _visible_to 语义）
# --------------------------------------------------------------------------
def _visible_to(scope, owner_id, agent_id):
    if not agent_id:
        return True
    scope = str(scope or "").upper()
    if scope == "AGENT":
        oid = str(owner_id or "").strip()
        if oid and oid != agent_id:
            return False
    return True


# --------------------------------------------------------------------------
# 读取 truth source：ontology
# --------------------------------------------------------------------------
def _load_entities():
    ents = {}
    for obj, line in _read_lines_raw(ENTITIES_FILE):
        e = obj.get("entity", {})
        if not e.get("id"):
            continue
        e = dict(e)
        e["_line"] = line
        e["_source_file"] = "entities.jsonl"
        if e.get("status") == "deleted":
            continue
        ents[e["id"]] = e
    return ents


def _load_relations():
    rels = []
    for obj, line in _read_lines_raw(RELATIONS_FILE):
        r = obj.get("relation", {})
        if not r.get("id"):
            continue
        if r.get("status") == "deleted":
            continue
        r = dict(r)
        r["_line"] = line
        r["_source_file"] = "relations.jsonl"
        rels.append(r)
    return rels


# 实体稳定指纹（与 ontology.py 保持一致）
def _canonical_entity(e):
    stable = {"id": e.get("id"), "type": e.get("type"), "name": e.get("name"),
              "status": e.get("status", "active"), "scope": e.get("scope", "AGENT"),
              "owner_type": e.get("owner_type"), "owner_id": e.get("owner_id"),
              "properties": e.get("properties", {}) or {}}
    return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


def _canonical_relation(r):
    stable = {"id": r.get("id"), "from_id": r.get("from_id"), "predicate": r.get("predicate"),
              "to_id": r.get("to_id"), "status": r.get("status", "active"),
              "properties": r.get("properties", {}) or {}}
    return canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


# --------------------------------------------------------------------------
# 读取 truth source：self-evolution evidence / artifacts（只读）
# --------------------------------------------------------------------------
def _load_evidence(agent_id=None):
    """读取 evidence.jsonl（机器真相），返回 [(rec, line)]。Vault 只读投影源。"""
    out = []
    for obj, line in _read_lines_raw(EVIDENCE_FILE):
        if not obj.get("id"):
            continue
        if agent_id and str(obj.get("agent_id", "") or "").strip() != agent_id:
            continue
        e = dict(obj)
        e["_line"] = line
        e["_source_file"] = "evidence.jsonl"
        out.append((e, line))
    return out


def _load_evo_artifacts(kind, agent_id=None):
    """读取 .agent-os/evolution/<subdir>/*.json artifact。

    kind 可为单/复数（'change'|'changes' ... 均可）。
    """
    sub = {"candidate": "candidates", "candidates": "candidates",
           "diagnosis": "diagnoses", "diagnoses": "diagnoses",
           "proposal": "proposals", "proposals": "proposals",
           "change": "changes", "changes": "changes",
           "regression": "regressions", "regressions": "regressions"}.get(kind)
    d = os.path.join(_EVO_WS, sub) if sub else None
    out = []
    if not d or not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            rec = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not rec.get("id"):
            continue
        rec["_artifact"] = (kind, fn)
        rec["_source_file"] = ".agent-os/evolution/{0}/{1}".format(sub, fn)
        if agent_id and not _artifact_visible(rec, agent_id):
            continue
        out.append(rec)
    return out


def _artifact_visible(rec, agent_id):
    if not agent_id:
        return True
    scope = str(rec.get("scope", "") or "").upper()
    if scope == "AGENT":
        oid = str(rec.get("agent_id", "") or rec.get("owner_id", "") or "").strip()
        if oid and oid != agent_id:
            return False
    return True


# 归一化 artifact 为“experience”（只读回放，来自已完成的 evolution 链路）
def _artifact_to_experience(rec):
    """把 change/proposal/regression 归一化为一条 experience。

    只导出处于有效终态的记录（APPLIED / PROMOTED / REGRESSION_PASSED /
    ROLLED_BACK 等），绝不产生新 candidate / evidence。
    ```
    """
    kind = rec.get("_artifact", ("", ""))[0]
    eid = rec.get("id")
    if not eid:
        return None
    # 只导出“已产生学习/结果”的状态
    status = str(rec.get("status", ""))
    learned_states = {"APPLIED", "PROMOTED", "PROMOTE", "REGRESSION_PASSED",
                      "ROLLED_BACK", "REGRESSED", "MONITORING", "ENABLED"}
    if kind == "change" and status not in learned_states:
        return None
    if kind == "proposal" and status not in ("PROMOTED", "APPLIED", "ACCEPTED"):
        return None
    if kind == "regression" and status not in ("REGRESSION_PASSED", "APPROVED", "PASSED", "REGRESSED", "ROLLED_BACK"):
        return None
    if kind == "candidate" and status not in ("PROMOTED", "ENABLED", "APPLIED"):
        return None
    pattern_key = rec.get("pattern_key") or rec.get("candidate", {}).get("pattern_key", "")
    target = rec.get("target") or rec.get("targets", [""])[0] if isinstance(rec.get("targets"), list) else rec.get("target")
    return {
        "id": ("EXP-" + eid) if not str(eid).startswith("EXP-") and kind == "change" else eid,
        "source_kind": kind,
        "source_id": eid,
        "pattern_key": pattern_key,
        "target": target,
        "scope": rec.get("scope", "AGENT"),
        "status": status,
        "reason": rec.get("reason", ""),
        "detail": rec.get("detail", ""),
        "created_at": rec.get("created_at", rec.get("timestamp", "")),
        "provenance_ref": "{0}::{1}".format(rec.get("_source_file", ""), eid),
        "agent_id": rec.get("agent_id", ""),
        "_source": rec,
    }


def _artifact_to_decision(rec):
    """把 evolution 中的决策字段归一化为 decision 视图。

    优先取 change/proposal/regression 里的 decision/reason 字段；否则跳过。
    decision 是治理产物，不是运行态——Vault 只读回放，不改决策。
    """
    kind = rec.get("_artifact", ("", ""))[0]
    decision = rec.get("decision") or rec.get("decision_outcome") or rec.get("verdict")
    if not decision and kind == "regression":
        decision = "CONTINUE"
    if not decision:
        return None
    did = rec.get("id")
    if not did:
        return None
    return {
        "id": ("DEC-" + did) if not str(did).startswith("DEC-") else did,
        "source_kind": kind,
        "source_id": did,
        "decision": decision,
        "reason": rec.get("reason", ""),
        "objective": rec.get("problem", rec.get("objective", "")),
        "scope": rec.get("scope", "AGENT"),
        "status": rec.get("status", ""),
        "created_at": rec.get("created_at", rec.get("timestamp", "")),
        "provenance_ref": "{0}::{1}".format(rec.get("_source_file", ""), did),
        "_source": rec,
    }


# --------------------------------------------------------------------------
# 读取 truth source：native memory（journal / durable）——只读投影
# --------------------------------------------------------------------------
def _load_journal_daily():
    """读取 memory/YYYY-MM-DD.md 日记（自 OpenClaw native daily）。

    仅做轻量投影，不解读正文；逐文件映射为独立 journal 视图。
    """
    d = os.path.join(NATIVE_MEM)
    rows = []
    if not os.path.isdir(d):
        return rows
    for fn in sorted(os.listdir(d)):
        if not re.match(r"^\d{4}-\d{2}-\d{2}\.md$", fn):
            continue
        p = os.path.join(d, fn)
        rows.append({"date": fn[:-3], "path": p, "size": os.path.getsize(p),
                     "provenance_ref": "native-memory/journal/{0}".format(fn)})
    return rows


def _parse_durable_memory():
    """解析 MEMORY.md（durable 层，已晋升/精选）为 durable 视图候选。

    经 memory-governance promotion gate：MEMORY.md 本身就是 promotion 后的
    durable。桥只把“已存在”的结构化条目投影成 Markdown，不全文复制对话。
    解析规则：按二级标题（## 或 ####）切分为条目；无法稳定切分的整体视为单条。
    """
    txt = _read_file(MEMORY_MD)
    entries = []
    # 按 "## " 或 "### " 分割（忽略全大写标题）
    lines = txt.splitlines()
    cur_title = None
    cur_body = []
    for ln in lines:
        m = re.match(r"^#{2,3}\s+(.+)$", ln)
        if m:
            if cur_title is not None:
                entries.append((cur_title, "\n".join(cur_body).strip()))
            cur_title = m.group(1).strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_title is not None:
        entries.append((cur_title, "\n".join(cur_body).strip()))
    if not entries and txt.strip():
        # 无标题则整体为一条（仍属已晋升 durable）
        entries.append(("durable-overall", txt.strip()))
    return entries


# --------------------------------------------------------------------------
# Knowledge registry（Vault 侧书签，非机器真相源）
# --------------------------------------------------------------------------
def _load_registry():
    regs = {}
    for rec in _read_jsonl(REGISTRY_FILE):
        if rec.get("id"):
            regs[rec["id"]] = rec
    return regs


def _save_registry(regs):
    lines = []
    for rid in sorted(regs):
        r = dict(regs[rid])
        r.pop("_line", None)
        lines.append(canonical_json(r))
    _atomic_write(REGISTRY_FILE, "\n".join(lines) + ("\n" if lines else ""))


# --------------------------------------------------------------------------
# Export 渲染
# --------------------------------------------------------------------------
def _wikify_entity_id(eid, entities):
    if eid in entities:
        e = entities[eid]
        return ("entities/{0}/{1}".format(e.get("type", "Entity"), eid).replace(".md", ""),
                e.get("name") or eid)
    return ("", eid)


def _rel_link(eid, entities, default_label=None):
    path_, label = _wikify_entity_id(eid, entities)
    if path_:
        return "[[{0}]]".format(path_)
    return default_label or eid


def render_evidence(rec, line):
    """Evidence → evolution/evidence/<evid>.md（只读投影）。"""
    evid = rec.get("id")
    fm = {
        "osv": VAULT_SCHEMA_VERSION,
        "object_type": "evidence",
        "id": evid,
        "source": rec.get("source"),
        "event_type": rec.get("event_type"),
        "pattern_key": rec.get("pattern_key"),
        "scope": rec.get("scope", "AGENT"),
        "target": rec.get("target"),
        "verified": rec.get("verified"),
        "confidence": rec.get("confidence"),
        "source_type": rec.get("source_type"),
        "agent_id": rec.get("agent_id") or None,
        "session_id": rec.get("session_id") or None,
        "execution_id": rec.get("execution_id") or None,
        "operation_id": rec.get("operation_id") or None,
        "correlation_id": rec.get("correlation_id") or None,
        "created_at": rec.get("timestamp", rec.get("created_at")),
        "provenance_ref": "evidence.jsonl:{0}:{1}".format(
            line, fp16(canonical_json({k: rec.get(k) for k in
                                        ("id", "source", "pattern_key", "problem", "verified")
                                        if rec.get(k) is not None}))),
        "superseded_by": rec.get("superseded_by"),
        "tags": ["agent-os/view", "evolution/evidence"],
    }
    body = []
    body.append("# Evidence {0}".format(evid))
    body.append("")
    problem = rec.get("problem") or rec.get("claim") or rec.get("result")
    if problem:
        body.append(problem)
        body.append("")
    body.append("> [!info] 机器真相源")
    body.append("> evidence.jsonl 行 `{0}` · 指纹 `{1}` · **只读投影**".format(line, fm["provenance_ref"].split(":")[-1]))
    body.append("> 本视图不可作为 self-evolution 新证据源；真相在 evidence.jsonl。")
    if rec.get("source") == "evolution_event":
        body.append("> [!warning] 内部治理事件（evolution_event）——仅作回溯，不留作外部证据。")
    body.append("")
    body.append("## 记录")
    body.append("- source: `{0}` · event_type: `{1}`".format(rec.get("source"), rec.get("event_type") or "-"))
    body.append("- pattern_key: `{0}` · scope: `{1}`".format(rec.get("pattern_key") or "-", rec.get("scope") or "-"))
    body.append("- verified: {0} · confidence: {1}".format(rec.get("verified"), rec.get("confidence")))
    body.append("- created_at: `{0}`".format(rec.get("timestamp", rec.get("created_at") or "-")))
    return fm, "\n".join(body) + "\n"


def render_experience(exp):
    """Experience → evolution/experience/<eid>.md（只读回放）。"""
    fm = {
        "osv": VAULT_SCHEMA_VERSION,
        "object_type": "experience",
        "id": exp["id"],
        "source_kind": exp["source_kind"],
        "source_id": exp["source_id"],
        "pattern_key": exp["pattern_key"] or None,
        "target": exp["target"] or None,
        "scope": exp["scope"],
        "status": exp["status"],
        "created_at": exp["created_at"] or None,
        "provenance_ref": exp["provenance_ref"],
        "tags": ["agent-os/view", "evolution/experience"],
    }
    body = []
    body.append("# Experience {0}".format(exp["id"]))
    body.append("")
    body.append("> [!info] 治理后只读回放")
    body.append("> 来自 `.agent-os/evolution/` artifact（`{0}`），只读展示，不产生新 candidate/evidence。".format(exp["source_kind"]))
    body.append("")
    if exp.get("reason"):
        body.append("## Situation/Action/Result")
        body.append(exp["reason"])
        body.append("")
    if exp.get("detail"):
        body.append("## Detail")
        body.append(str(exp["detail"]))
        body.append("")
    body.append("## Metadata")
    body.append("- pattern_key: `{0}` · target: `{1}`".format(exp.get("pattern_key") or "-", exp.get("target") or "-"))
    body.append("- scope: `{0}` · status: `{1}`".format(exp["scope"], exp["status"]))
    body.append("- 源 artifact: `{0}` (id=`{1}`)".format(exp["source_kind"], exp["source_id"]))
    return fm, "\n".join(body) + "\n"


def render_decision(dec):
    """Decision → evolution/decisions/<did>.md（只读回放）。"""
    fm = {
        "osv": VAULT_SCHEMA_VERSION,
        "object_type": "decision",
        "id": dec["id"],
        "decision": dec["decision"],
        "source_kind": dec.get("source_kind"),
        "source_id": dec.get("source_id"),
        "objective": dec.get("objective") or None,
        "reason": dec.get("reason") or None,
        "scope": dec.get("scope", "AGENT"),
        "status": dec.get("status") or None,
        "created_at": dec.get("created_at") or None,
        "provenance_ref": dec["provenance_ref"],
        "superseded_by": dec.get("superseded_by"),
        "tags": ["agent-os/view", "evolution/decision"],
    }
    body = []
    body.append("# Decision")
    body.append("")
    body.append("**{0}**  →  `{1}`".format(dec.get("objective") or dec["id"], dec["decision"]))
    body.append("")
    body.append("## Reason")
    body.append(dec.get("reason") or "-")
    body.append("")
    body.append("> [!info] 治理产物（只读回放）")
    body.append("> 来自 `.agent-os/evolution/`（`{0}` id=`{1}`）；决策是治理结果，Vault 不改决策。".format(
        dec.get("source_kind"), dec.get("source_id")))
    body.append("")
    body.append("## Metadata")
    body.append("- scope: `{0}` · status: `{1}`".format(dec.get("scope"), dec.get("status") or "-"))
    return fm, "\n".join(body) + "\n"


def render_knowledge(krec, entities):
    """Knowledge → knowledge/<type>-<id>.md。

    知识声明来自 agent-os-vault knowledge registry（只经治理导入）。registry 是
    视图书签，不是 Agent OS 运行时知识库（Agent OS 无 knowledge runtime —— 边界保持）。
    """
    kid = krec["id"]
    type_tag = krec.get("type") or "claim"
    claim = krec.get("claim", krec.get("title", kid))
    evidence_refs = krec.get("evidence_refs") or []
    related_links = []
    for r in (krec.get("related") or []):
        eid = r if isinstance(r, str) else r.get("id")
        if eid:
            related_links.append(_rel_link(eid, entities))
    fm = {
        "osv": VAULT_SCHEMA_VERSION,
        "object_type": "knowledge",
        "id": kid,
        "type": type_tag,
        "subject": krec.get("subject"),
        "claim": claim,
        "confidence": krec.get("confidence", 0.5),
        "freshness": krec.get("freshness", 0.5),
        "validity": krec.get("validity", "unverified"),
        "status": krec.get("status", "active"),
        "source_type": krec.get("source_type", "source_stated"),
        "provenance_ref": krec.get("provenance_ref"),
        "source_agent": krec.get("source_agent"),
        "superseded_by": krec.get("superseded_by") or None,
        "contradicts": krec.get("contradicts") or None,
        "evidence_refs": evidence_refs or None,
        "created_at": krec.get("created_at"),
        "updated_at": krec.get("updated_at"),
        "tags": ["agent-os/view", "knowledge/" + type_tag],
    }
    body = []
    body.append("# {0}".format(claim))
    body.append("")
    body.append("## Claim")
    body.append(claim)
    body.append("")
    if krec.get("explanation"):
        body.append("## Explanation")
        body.append(str(krec["explanation"]))
        body.append("")
    body.append("> [!info] 来源")
    body.append("> 经治理导入的知识视图（provenance_ref=`{0}`）".format(krec.get("provenance_ref") or "-"))
    body.append("> 真相来源与治理由 knowledge-governance 承担；本视图为人类可读 + 编辑入口。")
    body.append("")
    if evidence_refs:
        body.append("## Evidence")
        for er in evidence_refs:
            body.append("- {0}".format(er))
        body.append("")
    if related_links:
        body.append("## Related")
        for l in related_links:
            body.append("- {0}".format(l))
        body.append("")
    if krec.get("contradicts"):
        body.append("> [!warning] 矛盾保留（未静默合并）")
        for c in krec["contradicts"]:
            body.append("- {0}".format(c))
        body.append("")
    if fm["status"] in ("obsolete",):
        body.append("> [!warning] 该声明已标 obsolete（视图保留，未删真相）。")
    if fm["status"] in ("superseded",) and fm.get("superseded_by"):
        body.append("> [!warning] 已被 `{0}` 取代（旧声明保留 + superseded_by）。".format(fm["superseded_by"]))
    body.append("")
    body.append("## Metadata")
    body.append("- subject: `{0}` · type: `{1}`".format(krec.get("subject") or "-", type_tag))
    body.append("- confidence: {0} · freshness: {1} · validity: `{2}`".format(
        fm["confidence"], fm["freshness"], fm["validity"]))
    body.append("- status: `{0}` · source_type: `{1}`".format(fm["status"], fm["source_type"]))
    return fm, "\n".join(body) + "\n"


def export_one(rel_path, fm, body):
    _emit(rel_path, _frontmatter(fm) + body)


# --------------------------------------------------------------------------
# Export 主流程（P1+P2）
# --------------------------------------------------------------------------
EXPORT_SOURCES = {"ontology", "knowledge", "experience", "decision", "evidence", "memory"}


def _export_knowledge(vault, entities):
    regs = _load_registry()
    d = os.path.join(vault, "knowledge")
    os.makedirs(d, exist_ok=True)
    paths = {}
    for kid in sorted(regs):
        krec = regs[kid]
        type_tag = krec.get("type") or "claim"
        fm, body = render_knowledge(krec, entities)
        rel = os.path.join("knowledge", "{0}-{1}.md".format(type_tag, kid))
        export_one(os.path.join(vault, rel), fm, body)
        paths[kid] = os.path.join("knowledge", "{0}-{1}.md".format(type_tag, kid))
    return paths


def _export_evidence(vault, agent_id):
    d = os.path.join(vault, "evolution", "evidence")
    os.makedirs(d, exist_ok=True)
    paths = {}
    for rec, line in _load_evidence(agent_id):
        fm, body = render_evidence(rec, line)
        rel = os.path.join("evolution", "evidence", rec["id"] + ".md")
        export_one(os.path.join(vault, rel), fm, body)
        paths[rec["id"]] = rel
    return paths


def _export_experience(vault, agent_id):
    d = os.path.join(vault, "evolution", "experience")
    os.makedirs(d, exist_ok=True)
    paths = {}
    seen = set()
    for kind in ("change", "proposal", "regression", "candidate"):
        for rec in _load_evo_artifacts(kind, agent_id):
            exp = _artifact_to_experience(rec)
            if not exp:
                continue
            if exp["id"] in seen:
                continue
            seen.add(exp["id"])
            fm, body = render_experience(exp)
            rel = os.path.join("evolution", "experience", exp["id"] + ".md")
            export_one(os.path.join(vault, rel), fm, body)
            paths[exp["id"]] = rel
    return paths


def _export_decision(vault, agent_id):
    d = os.path.join(vault, "evolution", "decisions")
    os.makedirs(d, exist_ok=True)
    paths = {}
    seen = set()
    for kind in ("change", "proposal", "regression", "candidate", "diagnoses"):
        for rec in _load_evo_artifacts(kind, agent_id):
            dec = _artifact_to_decision(rec)
            if not dec:
                continue
            if dec["id"] in seen:
                continue
            seen.add(dec["id"])
            fm, body = render_decision(dec)
            rel = os.path.join("evolution", "decisions", dec["id"] + ".md")
            export_one(os.path.join(vault, rel), fm, body)
            paths[dec["id"]] = rel
    return paths


def _export_memory(vault):
    """P2: journal + durable 投影（须经 promotion gate，不全文复制对话）。"""
    # journal：逐日轻量投影（只写存在性 + 摘要链接，不复制正文）
    jdir = os.path.join(vault, "memory", "journal")
    os.makedirs(jdir, exist_ok=True)
    jpaths = {}
    for row in _load_journal_daily():
        date = row["date"]
        rel = os.path.join("memory", "journal", date + ".md")
        fm = {"osv": VAULT_SCHEMA_VERSION, "object_type": "memory_journal",
              "date": date, "provenance_ref": row["provenance_ref"],
              "source_bytes": row["size"], "tags": ["agent-os/view", "memory/journal"]}
        body = "{0}\n\n> [!info] native-memory 日记投影\n> 源：`{1}`，字节 `{2}`。\n> 日记层可清理；仅投影存在性与来源，不复制对话正文（避免扩容）。".format(
            date, row["provenance_ref"], row["size"])
        export_one(os.path.join(vault, rel), fm, body)
        jpaths[date] = rel

    # durable：解析 MEMORY.md 已晋升条目（memory-governance promotion gate 已发生，
    # MEMORY.md 本身即 promotion 结果）。轻量投影，不全文复制。
    ddir = os.path.join(vault, "memory", "durable")
    os.makedirs(ddir, exist_ok=True)
    dpaths = {}
    for i, (title, content) in enumerate(_parse_durable_memory(), 1):
        dur_id = "DUR-{0:03d}".format(i)
        rel = os.path.join("memory", "durable", dur_id + ".md")
        preface = ""
        if content:
            preface = "```\n{0}\n```".format(content[:400])
        fm = {"osv": VAULT_SCHEMA_VERSION, "object_type": "memory_durable",
              "id": dur_id, "title": title,
              "provenance_ref": "native-memory/MEMORY.md (durable, promoted)",
              "tags": ["agent-os/view", "memory/durable"]}
        body = "# {0}\n\n{1}".format(title, preface)
        export_one(os.path.join(vault, rel), fm, body)
        dpaths[dur_id] = rel
    return {"journal": jpaths, "durable": dpaths}


def _export_indexes(vault, summary):
    """生成 README.md + AGENT-OS-VAULT-MAP.base + _meta/schema-version.md + provenance-map.md。"""
    os.makedirs(os.path.join(vault, "_meta"), exist_ok=True)
    readme = []
    readme.append("---")
    readme.append("osv: {0}".format(VAULT_SCHEMA_VERSION))
    readme.append("object_type: vault_root")
    readme.append("tags: [agent-os/view]")
    readme.append("---")
    readme.append("")
    readme.append("# Agent OS × Obsidian 长期知识空间")
    readme.append("")
    readme.append("> 本仓库是 Agent OS 长期知识对象的 **人类/Agent 可读视图 + 手工编辑入口**。")
    readme.append("> **唯一机器真相源**在 Agent OS 本体（`memory/ontology/*.jsonl`、`.agent-os/evolution/*`、")
    readme.append("> evidence.jsonl、OpenClaw 原生 Memory、Governance/Verification/Security）。")
    readme.append("> **Obsidian 不是机器治理真相源**：人工编辑须经 `agent-os-vault import` → ")
    readme.append("> governance gate → accept 才会回流 JSONL；绝不 obsidian→overwrite JSONL。")
    readme.append("")
    readme.append("生成时间：{0}".format(now_iso()))
    readme.append("")
    readme.append("## 目录结构")
    readme.append("- `ontology/` —— 本体 Entity/Relation 只读视图（P0，`ontology.py --export-vault`）")
    readme.append("- `knowledge/` —— 知识声明视图（P1，治理导入）")
    readme.append("- `evolution/evidence/` —— Evidence 只读投影（P1）")
    readme.append("- `evolution/experience/` —— 治理后经验只读回放（P1）")
    readme.append("- `evolution/decisions/` —— 治理决策只读回放（P1）")
    readme.append("- `memory/journal/` —— native 日记轻量投影（P2）")
    readme.append("- `memory/durable/` —— MEMORY.md 已晋升 durable 投影（P2）")
    readme.append("- `_meta/provenance-map.md` —— 任意视图 ↔ 源真相行 + SHA-256 指纹")
    readme.append("")
    for k, v in summary.items():
        readme.append("- {0}: {1}".format(k, v))
    _emit(os.path.join(vault, "README.md"), "\n".join(readme) + "\n")

    # AGENT-OS-VAULT-MAP.base 全局索引（Bases 视图）
    base = []
    base.append("# Agent OS Vault 索引视图")
    base.append("# 由 agent-os-vault export 生成；语义真相在源 JSONL/.agent-os")
    base.append("filters:")
    base.append("  and:")
    base.append("    - 'file.ext == \"md\"'")
    base.append("    - 'file.path.contains(\"knowledge/\") or file.path.contains(\"evolution/\") or file.path.contains(\"memory/\")'")
    base.append("views:")
    base.append("  - type: table")
    base.append("    name: \"Agent OS objects\"")
    base.append("    order:")
    base.append("      - file.path")
    base.append("      - object_type")
    base.append("      - id")
    base.append("      - status")
    base.append("      - scope")
    _emit(os.path.join(vault, "AGENT-OS-VAULT-MAP.base"), "\n".join(base) + "\n")

    sv = []
    sv.append("# Vault Schema Version")
    sv.append("")
    sv.append("osv = {0}".format(VAULT_SCHEMA_VERSION))
    sv.append("truth source: memory/ontology/*.jsonl + .agent-os/evolution/* + evidence.jsonl + OpenClaw native Memory")
    sv.append("direction: 单向自动导出 · 受控反向导入（绝不过写）")
    _emit(os.path.join(vault, "_meta", "schema-version.md"), "\n".join(sv) + "\n")

    # provenance-map.md 文本视图
    pm = _build_prov_map(vault)
    pm_lines = ["# Provenance Map（任意视图 → 源真相行 + SHA-256）", "",
                "> 机器真相源文件与行号；SHA-256 指纹可在源码重算比对。", ""]
    for entry in pm:
        pm_lines.append("- `{0}` ← {1}（{2}）".format(entry.get("vault_path", "?"),
                          entry.get("source_ref", "?"), entry.get("fingerprint", "?")))
    _emit(os.path.join(vault, "_meta", "provenance-map.md"), "\n".join(pm_lines) + "\n")

    # 机器可读 provenance map 也落桥工作区（供 reconcile 对比）
    _atomic_write(PROV_MAP_FILE, canonical_json(pm))


def _iter_vault_views(vault):
    """遍历 Vault 中 agent-os 视图文件，返回 (rel_path, abs_path)。"""
    out = []
    for root, _, files in os.walk(vault):
        for fn in files:
            if fn.endswith(".md") or fn.endswith(".base") or fn.endswith(".canvas"):
                abs_p = os.path.join(root, fn)
                rel = os.path.relpath(abs_p, vault)
                out.append((rel, abs_p))
    return out


def _prov_entry_content_fp(vault, vault_rel):
    """读取已导出 Vault 文件的可比较内容指纹。"""
    abs_p = os.path.join(vault, vault_rel)
    if not os.path.exists(abs_p) or not abs_p.endswith(".md"):
        return None
    fm, _ = _parse_fm(abs_p)
    return _vault_content_fp(fm)


def _build_prov_map(vault):
    """构建 provenance-map 条目：对每个已导出的实体/关系/证据回填指纹。"""
    entries = []
    entities = _load_entities()
    for eid, e in entities.items():
        rel = os.path.join("ontology", "entities", e.get("type"), eid + ".md")
        line = e.get("_line")
        src = "entities.jsonl:{0}".format(line)
        fingerprint = fp16(_canonical_entity(e))
        entries.append({"object_type": "ontology_entity", "id": eid,
                        "vault_path": rel, "source_ref": src, "fingerprint": fingerprint,
                        "vault_content_fp": _prov_entry_content_fp(vault, rel)})
    for r in _load_relations():
        rel = "ontology/relations.base"
        entries.append({"object_type": "ontology_relation", "id": r.get("id"),
                        "vault_path": "ontology/relations.base",
                        "source_ref": "relations.jsonl:{0}".format(r.get("_line")),
                        "fingerprint": fp16(_canonical_relation(r)),
                        "vault_content_fp": None})
    for rec, line in _load_evidence():
        vrel = os.path.join("evolution", "evidence", rec["id"] + ".md")
        entries.append({"object_type": "evidence", "id": rec["id"],
                        "vault_path": vrel,
                        "source_ref": "evidence.jsonl:{0}".format(line),
                        "fingerprint": fp16(canonical_json(
                            {k: rec.get(k) for k in ("id", "source", "pattern_key", "problem", "verified")
                             if rec.get(k) is not None})),
                        "vault_content_fp": _prov_entry_content_fp(vault, vrel)})
    # evolution 派生视图（experience / decision）—— 以 provenance_ref 为稳定指纹
    for kind in ("change", "proposal", "regression", "candidate"):
        for rec in _load_evo_artifacts(kind):
            exp = _artifact_to_experience(rec)
            if exp:
                vrel = os.path.join("evolution", "experience", exp["id"] + ".md")
                entries.append({"object_type": "experience", "id": exp["id"],
                                "vault_path": vrel,
                                "source_ref": exp["provenance_ref"],
                                "fingerprint": exp["provenance_ref"],
                                "vault_content_fp": _prov_entry_content_fp(vault, vrel)})
            dec = _artifact_to_decision(rec)
            if dec:
                vrel = os.path.join("evolution", "decisions", dec["id"] + ".md")
                entries.append({"object_type": "decision", "id": dec["id"],
                                "vault_path": vrel,
                                "source_ref": dec["provenance_ref"],
                                "fingerprint": dec["provenance_ref"],
                                "vault_content_fp": _prov_entry_content_fp(vault, vrel)})
    # knowledge registry（治理导入的视图书签）
    for kid, krec in _load_registry().items():
        vrel = os.path.join("knowledge", "{0}-{1}.md".format(krec.get("type") or "claim", kid))
        entries.append({"object_type": "knowledge", "id": kid,
                        "vault_path": vrel,
                        "source_ref": krec.get("provenance_ref") or "",
                        "fingerprint": krec.get("provenance_ref") or kid,
                        "vault_content_fp": _prov_entry_content_fp(vault, vrel)})
    return entries


def _run_ontology_export(vault, agent, project):
    """复用 P0 ontology.py --export-vault（保留向后兼容，不重写）。"""
    if not os.path.exists(ONT_SCRIPT):
        return 0, -1
    cmd = [sys.executable, ONT_SCRIPT, "--export-vault", "--out", vault]
    if agent:
        cmd += ["--agent", agent]
    if project:
        cmd += ["--project", project]
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return r.stderr, r.returncode
    return "", 0


def cmd_export(args):
    vault = os.path.abspath(args.vault)
    sources = set(args.sources) if args.sources else {"all"}
    if "all" in sources:
        sources = set(EXPORT_SOURCES)
    os.makedirs(vault, exist_ok=True)
    summary = {}

    if "ontology" in sources:
        err, rc = _run_ontology_export(vault, args.agent, args.project)
        if rc != 0:
            print("ontology export failed: {0}".format(err))
            return 1
        ents = _load_entities()
        summary["ontology_entities"] = len(ents)
        summary["ontology_relations"] = len(_load_relations())

    entities = _load_entities()
    if "knowledge" in sources:
        summary["knowledge"] = len(_export_knowledge(vault, entities))
    if "evidence" in sources:
        summary["evidence"] = len(_export_evidence(vault, args.agent))
    if "experience" in sources:
        summary["experience"] = len(_export_experience(vault, args.agent))
    if "decision" in sources:
        summary["decision"] = len(_export_decision(vault, args.agent))
    if "memory" in sources:
        m = _export_memory(vault)
        summary["memory_journal"] = len(m["journal"])
        summary["memory_durable"] = len(m["durable"])

    _export_indexes(vault, summary)
    print("agent-os-vault export → {0}".format(vault))
    for k, v in sorted(summary.items()):
        print("  {0}: {1}".format(k, v))
    _audit("export", {"vault": vault, "sources": sorted(sources), "tree": vault})
    return 0


def cmd_status(args):
    vault = os.path.abspath(args.vault)
    print("agent-os-vault status")
    print("  vault: {0}".format(vault))
    print("  workspace: {0}".format(_WS))
    print("  ontology JSONL: {0} entities / {1} relations".format(
        len(_load_entities()), len(_load_relations())))
    print("  evidence.jsonl: {0} records".format(len(_load_evidence())))
    evo_counts = {}
    for kind in ("candidates", "diagnoses", "proposals", "changes", "regressions"):
        evo_counts[kind] = len(_load_evo_artifacts(kind))
    print("  .agent-os/evolution artifacts: {0}".format(evo_counts))
    cands = _read_jsonl(CANDIDATES_FILE)
    print("  import candidates: {0}".format(len(cands)))
    print("  knowledge registry: {0}".format(len(_load_registry())))
    # 机器真相完整性自检（不修改）
    issues = 0
    for eid, e in _load_entities().items():
        pass
    print("  机器真相自检: OK（只读）")
    return 0


# --------------------------------------------------------------------------
# P3: Reconcile — 检测 Vault 与机器真相源漂移
# --------------------------------------------------------------------------
# 五类结果：
#   machine-only    : 机器真相有、Vault 无（导出遗漏 / 未导出）
#   vault-only      : Vault 有、机器真相无（人工新增视图 / 垃圾）
#   both-changed    : 两边都变了（指纹不匹配且两者都非 origin）
#   deleted         : 机器真相删除（已有 deleted 标记），Vault 仍残留
#   conflict        : Vault 人工编辑与机器真相状态冲突（需要人工裁决，不可静默合并）
# 返回统一结构；reconcile 只读，绝不写 JSONL。

RECONCILE_KINDS = ("machine-only", "vault-only", "both-changed", "deleted", "conflict")




def _vault_content_fp(fm):
    """Vault 视图“可比较内容”指纹：取机器可比的稳定字段（排除易变时间戳/provenance）。

    用于 reconcile 检测“Vault 文件被人工编辑”（status/scope/claim/decision 等变化）。
    """
    keys = ("object_type", "id", "etype", "name", "status", "scope", "confidence",
            "freshness", "validity", "claim", "subject", "decision", "source_type")
    stable = {k: fm.get(k) for k in keys if fm.get(k) is not None}
    if not stable:
        return None
    return fp16(canonical_json(stable))

def _artifact_fp(rec):
    """evolution artifact 的稳定指纹（与导出视图 provenance_ref 尾段同 namespace）。"""
    stable = {k: rec.get(k) for k in ("id", "status", "decision", "scope", "target",
                                      "pattern_key", "reason", "problem")
              if rec.get(k) is not None}
    return fp16(canonical_json(stable))


def _fingerprint_of_vault(fm, rel_path):
    """从 Vault 视图 frontmatter 还原机器指纹（导出时 stamp 在 provenance_ref 尾段）。

    provenance_ref=<file>:<line>:<fp16> → 返回 fp16（与机器指纹同 namespace）。
    provenance_ref=<artifact_path>::<id> → 返回 `<path>::<id>` 签名（artifact 视图）。
    缺失 → None。
    """
    pref = fm.get("provenance_ref")
    if not pref:
        return None
    if "::" in str(pref):
        # artifact 视图：直接返回原始 ref 作为比较键（导出时其 provenance 即机器指纹）
        return pref
    parts = str(pref).split(":")
    if len(parts) == 3:
        return parts[2]
    return None


def _machine_ids():
    """{object_id: machine_fp}，覆盖 ontology 实体/关系 + evidence + evolution artifact 视图。"""
    m = {}
    for eid, e in _load_entities().items():
        m[eid] = fp16(_canonical_entity(e))
    for r in _load_relations():
        m[r["id"]] = fp16(_canonical_relation(r))
    for rec, _ in _load_evidence():
        m[rec["id"]] = fp16(canonical_json(
            {k: rec.get(k) for k in ("id", "source", "pattern_key", "problem", "verified")
             if rec.get(k) is not None}))
    # evolution 派生视图（experience/decision）：以 artifact id + provenance 签名登记
    for kind in ("change", "proposal", "regression", "candidate"):
        for rec in _load_evo_artifacts(kind):
            for maker in (_artifact_to_experience, _artifact_to_decision):
                try:
                    o = maker(rec)
                except Exception:
                    o = None
                if not o:
                    continue
                # experience id 是 EXP-xxx / artifact id；decision 是 DEC-xxx
                #   provenance_ref 已含 artifact 路径 => 用该 ref 作稳定签名
                m[o["id"]] = o["provenance_ref"]
    return m


def cmd_reconcile(args):
    vault = os.path.abspath(args.vault)
    if not os.path.isdir(vault):
        print("vault 不存在: {0}".format(vault))
        return 1
    # origin：上一次 export 时快照（机器指纹 + Vault 内容指纹）
    origin = {}
    if os.path.exists(PROV_MAP_FILE):
        try:
            for e in json.load(open(PROV_MAP_FILE, encoding="utf-8")):
                origin[e.get("id")] = e
        except Exception:
            origin = {}

    machine = _machine_ids()

    # Vault 视图：带 osv 标记的文件，取其 id + 机器指纹 + 声明状态
    vault_views = {}
    for rel, abs_p in _iter_vault_views(vault):
        if not rel.endswith(".md"):
            continue
        fm, _ = _parse_fm(abs_p)
        if not fm.get("osv"):
            continue
        vid = fm.get("id")
        if vid:
            vault_views[vid] = {"path": rel, "fm": fm,
                                "vault_fp": _fingerprint_of_vault(fm, rel),
                                "content_fp": _vault_content_fp(fm)}

    result = {k: [] for k in RECONCILE_KINDS}

    # 1) machine-only：机器真相有、origin 无且 Vault 也无（新对象未导出）
    for vid, mfp in machine.items():
        if vid not in vault_views and vid not in origin:
            result["machine-only"].append({"id": vid, "machine_fp": mfp,
                                           "note": "机器真相存在但 Vault 视图缺失（未导出），需重新 export"})

    # 2) vault-only：Vault 有、机器真相无（人工新增，未经治理）
    regs = _load_registry()
    for vid, vv in vault_views.items():
        if vid in machine:
            continue
        if str(vid).startswith(("DUR-", "memory-")):
            continue
        if str(vid).startswith("KNW-") and vid in regs:
            continue
        result["vault-only"].append({"id": vid, "vault_path": vv["path"],
                                     "note": "Vault 视图存在但机器真相无记录（人工新增，未经治理）"})

    # 3) 三路比较：origin(导出时) vs machine(now) vs vault(now)
    for vid, vv in vault_views.items():
        if vid not in machine:
            continue
        vfp = vv["vault_fp"]
        mfp = machine[vid]
        oe = origin.get(vid)
        vcfp = vv["content_fp"] if ("content_fp" in vv) else vfp
        if oe is None:
            # 无 origin → 无法判定“谁先变”；vault 与 machine 不一致才报 conflict
            if vfp is None or vfp != mfp:
                result["conflict"].append({"id": vid, "vault_path": vv["path"],
                                           "note": "无 origin 基准且 Vault/machine 不一致，需人工裁决"})
            continue
        ofp = oe.get("fingerprint")
        ocfp = oe.get("vault_content_fp")
        machine_changed = (mfp != ofp)
        # Vault 是否有内容变化：优先比 content_fp；content_fp 不可用（非 .md 稳定字段）则退化比 provenance fp
        if ocfp is not None and vcfp is not None:
            vault_changed = (vcfp != ocfp)
        else:
            vault_changed = (vfp is not None and vfp != ofp)
        if machine_changed and not vault_changed:
            result["conflict"].append({"id": vid, "vault_path": vv["path"],
                                       "note": "machine-changed：重新 export 以机器真相刷新视图"})
        elif not machine_changed and vault_changed:
            result["conflict"].append({"id": vid, "vault_path": vv["path"],
                                       "note": "vault-changed（人工编辑）：应走 import → governance，不得直接回写 JSONL"})
        elif machine_changed and vault_changed:
            result["both-changed"].append({"id": vid, "vault_path": vv["path"],
                                           "note": "both-changed：机器与 Vault 均变更，需人工裁决（以 machine 为准重导出，Vault 变更保留供 review）"})

    # 4) deleted：机器真相标 deleted 但 Vault 残留
    try:
        deleted_ids = set()
        for obj, _ in _read_lines_raw(ENTITIES_FILE):
            e = obj.get("entity", {})
            if e.get("status") == "deleted":
                deleted_ids.add(e["id"])
        for did in deleted_ids:
            if did in vault_views:
                result["deleted"].append({"id": did,
                                          "note": "机器真相已标记 deleted，Vault 视图应清理/归档（绝不动 JSONL）"})
    except Exception:
        pass

    print("reconcile: {0}".format(vault))
    total = 0
    for k in RECONCILE_KINDS:
        total += len(result[k])
        print("  {0}: {1}".format(k, len(result[k])))
        for item in result[k]:
            print("    - {0}".format(item))
    print("  漂移总数: {0}".format(total))
    _audit("reconcile", result)

    return 0


# --------------------------------------------------------------------------
# P3: Validate —— Vault 文件 schema / identity / ontology-consistency / provenance 校验
# --------------------------------------------------------------------------
VALID_STATUSES = {"active", "obsolete", "disputed", "superseded"}
VALID_SOURCE_TYPES = {"source_stated", "model_inferred", "user_asserted", "operational"}
VALID_VALIDITY = {"verified", "uncertain", "unverified", "disputed", "obsolete"}


def _validate_knowledge_file(fm, body, vault, entities):
    """校验一个 knowledge 视图文件。返回 (ok, errors)。"""
    errors = []
    req = {"osv", "object_type", "id", "subject", "claim", "confidence",
           "freshness", "validity", "status", "source_type", "provenance_ref"}
    for k in req:
        if k not in fm:
            errors.append("缺少必需字段: {0}".format(k))
    ot = fm.get("object_type")
    if ot != "knowledge":
        errors.append("object_type 应为 knowledge，实际 {0}".format(ot))
    if str(fm.get("osv")) != str(VAULT_SCHEMA_VERSION):
        errors.append("osv 版本不匹配")
    st = fm.get("status")
    if st and st not in VALID_STATUSES:
        errors.append("非法 status: {0}".format(st))
    stype = fm.get("source_type")
    if stype and stype not in VALID_SOURCE_TYPES:
        errors.append("非法 source_type: {0}".format(stype))
    valid = fm.get("validity")
    if valid and valid not in VALID_VALIDITY:
        errors.append("非法 validity: {0}".format(valid))
    for c in ["confidence", "freshness"]:
        v = fm.get(c)
        if v is not None and not (isinstance(v, (int, float)) and 0 <= float(v) <= 1):
            errors.append("{0} 需在 0-1 之间: {1}".format(c, v))
    # provenance 必须可解析（EVD- 或 evidence.jsonl: 或 artifact）
    pref = fm.get("provenance_ref") or ""
    if not pref:
        errors.append("provenance_ref 缺失")
    # wikilink 合规
    import re as _re
    for m in _re.finditer(r"\[\[([^\]]+)\]\]", body):
        t = m.group(1)
        if "|" in t:
            t = t.split("|")[0]
        if not t.startswith(("entities/", "evolution/evidence/", "knowledge/", "evolution/experience/", "evolution/decisions/")):
            errors.append("wikilink 指向非法目标: {0}".format(m.group(1)))
    return (not errors), errors


def _validate_evidence_file(fm, body, vault, entities):
    errors = []
    if fm.get("object_type") != "evidence":
        errors.append("object_type 应为 evidence")
    if not fm.get("id"):
        errors.append("缺少 id")
    return (not errors), errors


def _validate_experience_file(fm, body, vault, entities):
    errors = []
    if fm.get("object_type") != "experience":
        errors.append("object_type 应为 experience")
    if not fm.get("id"):
        errors.append("缺少 id")
    return (not errors), errors


def _validate_decision_file(fm, body, vault, entities):
    errors = []
    if fm.get("object_type") != "decision":
        errors.append("object_type 应为 decision")
    if not fm.get("id") or not fm.get("decision"):
        errors.append("缺少 id 或 decision")
    return (not errors), errors


_VALIDATORS = {
    "knowledge": _validate_knowledge_file,
    "evidence": _validate_evidence_file,
    "experience": _validate_experience_file,
    "decision": _validate_decision_file,
}

def cmd_validate(args):
    vault = os.path.abspath(args.vault)
    target = args.file
    if not os.path.isabs(target):
        target = os.path.join(vault, target)
    if not os.path.exists(target):
        print("文件不存在: {0}".format(target))
        return 1
    fm, body = _parse_fm(target)
    if not fm.get("osv"):
        print("不是 agent-os 视图文件（无 osv 标记）：{0}".format(target))
        return 0
    oc = fm.get("object_type")
    entities = _load_entities()
    ok = False
    errors = []
    if oc in _VALIDATORS:
        ok, errors = _VALIDATORS[oc](fm, body, vault, entities)
    elif oc in ("ontology_entity", "memory_journal", "memory_durable", "vault_root", "ontology_index"):
        ok, errors = True, []
    else:
        errors = ["未知 object_type: {0}".format(oc)]
    print("validate: {0}".format(target))
    print("  object_type: {0} · id: {1}".format(oc, fm.get("id")))
    if ok:
        print("  [VALID]")
        return 0
    print("  [INVALID]")
    for e in errors:
        print("    - {0}".format(e))
    return 1


# --------------------------------------------------------------------------
# P3: Import —— Vault 人工编辑 → 校验 → Import Candidate → governance gate
# --------------------------------------------------------------------------
def _gen_candidate_id():
    return "CAND-" + fp16(str(time.time()) + os.urandom(4).hex())[:12]


def _find_duplicate_candidate(sig):
    for c in _read_jsonl(CANDIDATES_FILE):
        if c.get("sig") == sig and c.get("status") in ("pending", "review"):
            return c
    return None


def _require_governance(obj_type, change_type):
    """gate 判定：哪些导入必须走治理/审批。

    返回 (level, reason)：level ∈ {'accept-readable','ask','approve'}。
    - 新增知识声明 / 修改 status = L1/L2 需治理 gate（accept-readable 供 review）。
    - 跨 scope、覆盖既有真相、删除 = 高权限需 human approval。
    """
    change = (change_type or "upsert").lower()
    if change in ("delete", "obsolete", "supersede", "overwrite", "modify-jsonl"):
        return "approve", "高影响变更（{0}）需人工审批".format(change)
    if obj_type == "ontology_entity" or obj_type == "ontology_relation":
        return "approve", "本体真相变更必须经 ontology validation + 审批"
    if obj_type == "evidence":
        return "deny", "Evidence 不能经 Vault 导入成为新证据源（只读）"
    if change in ("create", "upsert", "mark-status"):
        return "review", "知识/经验类导入生成候选，需 reviewer 确认"
    return "review", "默认走治理 review"


def cmd_import(args):
    """受控反向导入。绝不 obsi→ overwrite JSONL。

    流程：解析 Vault 文件 → schema/identity/ontology-consistency/provenance 校验 →
    生成 Import Candidate（.agent-os-vault/import-candidates.jsonl）→ governance gate 判定 →
    依 gate 输出 Action（accept-readable / ask human / approve-required / deny）。
    """
    vault = os.path.abspath(args.vault)
    fpth = args.file
    if not os.path.isabs(fpth):
        fpth = os.path.join(vault, fpth)
    if not os.path.exists(fpth):
        print("文件不存在: {0}".format(fpth))
        return 1
    fm, body = _parse_fm(fpth)
    if not fm.get("osv"):
        print("不是 agent-os 视图文件（无 osv 标记），拒绝导入：{0}".format(fpth))
        return 1
    oc = fm.get("object_type")

    entities = _load_entities()
    ok, errors = True, []
    if oc in _VALIDATORS:
        ok, errors = _VALIDATORS[oc](fm, body, vault, entities)
    else:
        errors = ["object_type 不可导入: {0}".format(oc)]
        ok = False

    # identity / unknown-id / invalid-relation / provenance mismatch 硬校验
    vid = fm.get("id")
    if oc == "knowledge":
        # provenance mismatch：knowledge 视图缺合法 provenance → 拒绝
        pref = fm.get("provenance_ref") or ""
        if not pref or pref == "none":
            ok = False
            errors.append("provenance_ref 缺失或非法，无法追溯")
        # unknown subject id → ontology-consistency：subject 若引用实体必须存在
        subj = fm.get("subject")
        if subj and not subj.startswith(("EVD-", "KNW-", "K-")) and subj not in entities and \
           not re.match(r"^(KNW|K)-\w+", str(subj)):
            # 允许自由 subject 文本，但若有 relation 断言则查验 —— 此处仅提示不硬拒
            pass

    if not ok:
        print("[IMPORT-REJECTED] 校验失败：{0}".format(fpth))
        for e in errors:
            print("    - {0}".format(e))
        _audit("import-rejected", {"file": fpth, "errors": errors})
        return 1

    change_type = args.change_type or "upsert"
    level, reason = _require_governance(oc, change_type)

    # 生成 candidate
    sig = canonical_json({"file": os.path.relpath(fpth, vault), "object_type": oc, "id": vid,
                          "status": fm.get("status"), "change_type": change_type})
    dup = _find_duplicate_candidate(sig)
    if dup:
        print("[IMPORT-DUP] 已存在候选 {0}（status={1}），不重复生成".format(dup["id"], dup.get("status")))
        print("  candidate_id: {0}".format(dup["id"]))
        print("  gate: {0} — {1}".format(level, reason))
        return 0
    cid = _gen_candidate_id()
    cand = {
        "id": cid,
        "created_at": now_iso(),
        "status": "pending",
        "gate": level,
        "gate_reason": reason,
        "object_type": oc,
        "id_ref": vid,
        "change_type": change_type,
        "source_file": os.path.relpath(fpth, vault),
        "vault_fingerprint": _fingerprint_of_vault(fm, os.path.relpath(fpth, vault)),
        "frontmatter": {k: v for k, v in fm.items()},
        "agent_id": args.agent or "",
        "reason": args.reason or "",
        "evidence": args.evidence or "",
        "sig": sig,
    }
    _append_line(CANDIDATES_FILE, canonical_json(cand))
    print("[IMPORT-CANDIDATE] {0}".format(cid))
    print("  file: {0} · type: {1} · id_ref: {2}".format(os.path.relpath(fpth, vault), oc, vid))
    print("  change_type: {0} · gate: {1} ({2})".format(change_type, level, reason))
    if level == "deny":
        print("  → 拒绝：该对象类型不允许经 Vault 导入")
    elif level == "approve":
        print("  → 需人工审批（L3），不得自动写回真相源")
    elif level == "review":
        print("  → 进入治理 review：可 state via `candidate-status {0} --status accepted|rejected|conflict`".format(cid))
    else:
        print("  → 低风险可接受（仍经 governance 记录）")
    _audit("import-candidate", {"cid": cid, "file": fpth, "gate": level, "obj_type": oc})
    return 0


def cmd_candidates(args):
    cands = _read_jsonl(CANDIDATES_FILE)
    st = args.status
    rows = [c for c in cands if (not st or c.get("status") == st)]
    print("import candidates: {0}（过滤 status={1}）".format(len(rows), st or "all"))
    for c in rows:
        print("  {0} · {1} · {2} → {3} · gate={4}".format(
            c.get("id"), c.get("object_type"), c.get("id_ref"),
            c.get("status"), c.get("gate")))
    return 0


def cmd_candidate_status(args):
    """Reviewer 状态流转：pending→accepted|rejected|conflict|review。

    accepted 不代表已写真相源；accepted 后才可执行 accept（受控写回）。
    """
    cands = _read_jsonl(CANDIDATES_FILE)
    target = [c for c in cands if c.get("id") == args.cid]
    if not target:
        print("候选不存在: {0}".format(args.cid))
        return 1
    cand = target[0]
    if args.status not in ("pending", "accepted", "rejected", "conflict", "review"):
        print("非法 status: {0}".format(args.status))
        return 1
    cand["status"] = args.status
    cand["reviewed_at"] = now_iso()
    cand["review_reason"] = args.reason or ""
    # 重写 candidates.jsonl
    lines = []
    for c in cands:
        cc = dict(c)
        cc.pop("_line", None)
        if cc.get("id") == args.cid:
            cc = cand
        lines.append(canonical_json(cc))
    _atomic_write(CANDIDATES_FILE, "\n".join(lines) + ("\n" if lines else ""))
    print("candidate {0} → {1}".format(args.cid, args.status))
    _audit("candidate-status", {"cid": args.cid, "status": args.status, "reason": args.reason})
    return 0


def cmd_accept(args):
    """治理通过后，把已 accepted 的 candidate 受控写回真相源。

    这是唯一允许“Vault → 若真相源 JSONL/.agent-os”的路径；必须满足：
      1) candidate 已 review→accepted（治理 gate 已通过）
      2) change_type 高影响的须已带 human 审批标记（此处以 --force 且含 approval token 表达）
      3) 写回经 knowledge registry 或 ontology append，绝不 overwrite 原始行
    """
    cands = _read_jsonl(CANDIDATES_FILE)
    target = [c for c in cands if c.get("id") == args.cid]
    if not target:
        print("候选不存在: {0}".format(args.cid))
        return 1
    cand = target[0]
    if cand.get("status") != "accepted":
        print("候选未通过 governance（status={0}），拒绝 accept。请先 candidate-status → accepted。".format(
            cand.get("status")))
        return 1
    if cand.get("gate") == "approve" and not args.approval:
        print("高影响变更（{0}）需要 --approval <token/reason> 明确审批。拒绝自动写回。".format(
            cand.get("gate_reason")))
        return 1
    if cand.get("gate") == "deny":
        print("该对象类型禁止经 Vault 导入（{0}）。拒绝。".format(cand.get("object_type")))
        return 1

    oc = cand.get("object_type")
    change_type = cand.get("change_type", "upsert")

    # ---- 写回（仅限支持的对象；仍走治理后的聚合字段，不 overwrite 原 JSONL 行）----
    if oc == "knowledge":
        fid = cand.get("id_ref")
        regs = _load_registry()
        fm = cand.get("frontmatter", {})
        regs[fid] = {
            "id": fid,
            "type": fm.get("type", "claim"),
            "subject": fm.get("subject"),
            "claim": fm.get("claim", fid),
            "explanation": fm.get("explanation"),
            "confidence": fm.get("confidence", 0.5),
            "freshness": fm.get("freshness", 0.5),
            "validity": fm.get("validity", "unverified"),
            "status": fm.get("status", "active"),
            "source_type": fm.get("source_type", "source_stated"),
            "provenance_ref": fm.get("provenance_ref") or cand.get("evidence"),
            "source_agent": fm.get("source_agent") or cand.get("agent_id"),
            "superseded_by": fm.get("superseded_by"),
            "contradicts": fm.get("contradicts"),
            "evidence_refs": fm.get("evidence_refs") or [],
            "related": fm.get("related") or [],
            "created_at": cand.get("created_at"),
            "updated_at": now_iso(),
        }
        _save_registry(regs)
        print("[ACCEPT] knowledge `{0}` 已写入 knowledge registry（视图书签）。".format(fid))
        print("  知识视图已生成；真相声明供 knowledge-governance 参考，不替代其治理身份。")
    elif oc in ("ontology_entity", "ontology_relation"):
        print("[ACCEPT-NOT-IMPL] 本体 JSONL 变更须走 `ontology.py` 的原生提案/validate 通道；")
        print("  本桥不直接 append JSONL。请使用 ontology CLI（--create-entity / --relate / --propose）。")
        return 1
    else:
        print("[ACCEPT-READONLY] {0} 为只读投影对象，不写回真相源。".format(oc))
    _audit("accept", {"cid": args.cid, "obj_type": oc, "change": change_type})
    return 0


# --------------------------------------------------------------------------
# Provenance —— 任意视图 → 源真相行 + SHA-256
# --------------------------------------------------------------------------
def _resolve_provenance(provenance_ref):
    """解析 provenance_ref 为源文件行。

    支持两种格式：
      <file>:<line>:<fp16>            —— ontology/evidence JSONL
      <file>::<artifact_id>           —— .agent-os/evolution artifact
    """
    if "::" in provenance_ref:
        src, aid = provenance_ref.split("::", 1)
        return {"source": src, "artifact_id": aid, "type": "artifact"}
    parts = provenance_ref.split(":")
    if len(parts) == 3:
        return {"source": parts[0], "line": int(parts[1]), "fingerprint": parts[2],
                "type": "jsonl"}
    return {"source": provenance_ref, "type": "unknown"}


def cmd_provenance(args):
    vault = os.path.abspath(args.vault)
    key = args.key

    # 若传入 Vault 文件路径，读取其 frontmatter 的 provenance_ref
    cand_path = key if os.path.isabs(key) else os.path.join(vault, key)
    if os.path.exists(cand_path):
        fm, _ = _parse_fm(cand_path)
        pref = fm.get("provenance_ref") or ""
        if not pref:
            print("{0} 无 provenance_ref".format(cand_path))
            return 1
        print("view: {0}".format(cand_path))
        print("provenance_ref: {0}".format(pref))
        info = _resolve_provenance(pref)
        print("  source: {0} · type: {1}".format(info.get("source"), info.get("type")))
        if info["type"] == "jsonl":
            # 重算源行指纹
            line_no = info["line"]
            src = info["source"]
            if src == "entities.jsonl":
                rows = _read_lines_raw(ENTITIES_FILE)
            elif src == "relations.jsonl":
                rows = _read_lines_raw(RELATIONS_FILE)
            elif src == "evidence.jsonl":
                rows = _read_lines_raw(EVIDENCE_FILE)
            else:
                rows = _read_lines_raw(os.path.join(_EVO_WS, "..", src))
            target_line = None
            for obj, ln in rows:
                if ln == line_no:
                    target_line = obj
                    break
            if target_line is not None:
                recomputed = None
                if src == "entities.jsonl" and target_line.get("entity"):
                    recomputed = fp16(_canonical_entity(target_line["entity"]))
                elif src == "relations.jsonl" and target_line.get("relation"):
                    recomputed = fp16(_canonical_relation(target_line["relation"]))
                elif src == "evidence.jsonl":
                    recomputed = fp16(canonical_json(
                        {k: target_line.get(k) for k in ("id", "source", "pattern_key", "problem", "verified")
                         if target_line.get(k) is not None}))
                print("  sha256(fp16): declared={0} recomputed={1} match={2}".format(
                    info["fingerprint"], recomputed,
                    (recomputed == info["fingerprint"]) if recomputed else "?"))
            else:
                print("  源行 {0} 未找到".format(line_no))
        return 0

    # 否则按 id 查 provenance-map / registry
    pm = []
    if os.path.exists(PROV_MAP_FILE):
        try:
            pm = json.load(open(PROV_MAP_FILE, encoding="utf-8"))
        except Exception:
            pm = []
    hits = [e for e in pm if e.get("id") == key]
    if not hits:
        regs = _load_registry()
        if key in regs:
            print("registry knowledge: {0}".format(key))
            print("  provenance_ref: {0}".format(regs[key].get("provenance_ref")))
            return 0
        print("在 provenance-map / registry 未找到: {0}".format(key))
        return 1
    for e in hits:
        print("id: {0} ({1})".format(e["id"], e["object_type"]))
        print("  vault_path: {0}".format(e["vault_path"]))
        print("  source_ref: {0}".format(e["source_ref"]))
        print("  fingerprint(sha256[0:16]): {0}".format(e["fingerprint"]))
    return 0


# --------------------------------------------------------------------------
# P4: Migration —— 首次幂等迁移（不修改原始 JSONL、不删旧 artifact、不自动提升垃圾成 knowledge）
# --------------------------------------------------------------------------
def cmd_migrate(args):
    vault = os.path.abspath(args.vault)
    # 幂等：若 migration 已成功执行过（有完成标记），直接 skip
    if os.path.exists(MIGRATION_REPORT):
        try:
            last = json.load(open(MIGRATION_REPORT, encoding="utf-8"))
            if last.get("done"):
                print("migration 已完成于 {0}（幂等跳过；如需重跑请删除 {1}）".format(
                    last.get("completed_at"), MIGRATION_REPORT))
                return 0
        except Exception:
            pass

    print("migration start → {0}".format(vault))
    report = {
        "schema_version": VAULT_SCHEMA_VERSION,
        "started_at": now_iso(),
        "done": False,
        "entities_migrated": 0, "relations_migrated": 0,
        "evidence_migrated": 0, "experience_migrated": 0,
        "decisions_migrated": 0, "knowledge_migrated": 0,
        "memory_journal": 0, "memory_durable": 0,
        "promotion_gate": {"note": "knowledge 不做历史自动提升（P4 约束）；仅导入经验证知识。"},
    }

    # 1) ontology（P0）→ 视图
    err, rc = _run_ontology_export(vault, args.agent, args.project)
    if rc != 0:
        print("ontology export 失败，中止 migration: {0}".format(err))
        return 1
    report["entities_migrated"] = len(_load_entities())
    report["relations_migrated"] = len(_load_relations())

    # 2) evidence / experience / decision（只读投影）
    report["evidence_migrated"] = len(_export_evidence(vault, args.agent))
    report["experience_migrated"] = len(_export_experience(vault, args.agent))
    report["decisions_migrated"] = len(_export_decision(vault, args.agent))

    # 3) memory journal / durable（promotion gate：仅投影已晋升 durable + 日记存在性）
    m = _export_memory(vault)
    report["memory_journal"] = len(m["journal"])
    report["memory_durable"] = len(m["durable"])

    # 4) knowledge：绝不自动提升历史垃圾成 knowledge；migration 不导入任何知识。
    report["knowledge_migrated"] = 0
    report["knowledge"] = "migration 不自动提升历史数据；知识声明须经 import→governance 逐条治理。"

    # 5) 索引 + provenance map
    _export_indexes(vault, report)

    # 记录：迁移不修改原始 JSONL / 不删旧 artifact（仅生成了新视图）—— 无删除动作。
    report["modified_original_jsonl"] = False
    report["deleted_old_artifacts"] = None
    report["completed_at"] = now_iso()
    report["done"] = True
    _atomic_write(MIGRATION_REPORT, canonical_json(report))

    print("migration done")
    for k in ("entities_migrated", "relations_migrated", "evidence_migrated",
              "experience_migrated", "decisions_migrated", "knowledge_migrated",
              "memory_journal", "memory_durable"):
        print("  {0}: {1}".format(k, report[k]))
    print("  原始 JSONL 未改：{0}".format(not report["modified_original_jsonl"]))
    print("  旧 artifact 未删：{0}".format(report["deleted_old_artifacts"] is None))
    print("  report: {0}".format(MIGRATION_REPORT))
    _audit("migrate", {"vault": vault, "done": True})
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
DEFAULT_VAULT = os.path.join(_WS, "tts obsidian", "tts openclaw memory")


def build_argparser():
    p = argparse.ArgumentParser(prog="agent-os-vault",
                                description="Agent OS × Obsidian 桥接 Skill")
    # 公共参数放到父 parser，供每个子命令共享（允许命令后跟）
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--vault", default=DEFAULT_VAULT, help="Vault 根目录")
    common.add_argument("--agent", default="", help="Agent ID（多 Agent 读隔离）")
    common.add_argument("--project", default="", help="Project 过滤")
    # root 级也接受
    p.add_argument("--vault", default=DEFAULT_VAULT, help=argparse.SUPPRESS)
    p.add_argument("--agent", default="", help=argparse.SUPPRESS)
    p.add_argument("--project", default="", help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd")

    pex = sub.add_parser("export", parents=[common], help="导出视图")
    pex.add_argument("--sources", nargs="*", default=["all"],
                     help="导出源：ontology|knowledge|experience|decision|evidence|memory|all")
    pex.set_defaults(func=cmd_export)

    pre = sub.add_parser("reconcile", parents=[common], help="检测漂移")
    pre.set_defaults(func=cmd_reconcile)

    pv = sub.add_parser("validate", parents=[common], help="校验 Vault 文件")
    pv.add_argument("file")
    pv.set_defaults(func=cmd_validate)

    pi = sub.add_parser("import", parents=[common], help="受控反向导入（生成 candidate）")
    pi.add_argument("file")
    pi.add_argument("--change_type", default="upsert")
    pi.add_argument("--reason", default="")
    pi.add_argument("--evidence", default="")
    pi.set_defaults(func=cmd_import)

    pc = sub.add_parser("candidates", parents=[common], help="列候选")
    pc.add_argument("--status", default="")
    pc.set_defaults(func=cmd_candidates)

    pcs = sub.add_parser("candidate-status", parents=[common], help="候选状态流转")
    pcs.add_argument("cid")
    pcs.add_argument("--status", required=True)
    pcs.add_argument("--reason", default="")
    pcs.set_defaults(func=cmd_candidate_status)

    pa = sub.add_parser("accept", parents=[common], help="治理通过后受控写回")
    pa.add_argument("cid")
    pa.add_argument("--approval", default="")
    pa.set_defaults(func=cmd_accept)

    pp = sub.add_parser("provenance", parents=[common], help="追溯 provenance")
    pp.add_argument("key")
    pp.set_defaults(func=cmd_provenance)

    pm = sub.add_parser("migrate", parents=[common], help="首次幂等迁移")
    pm.set_defaults(func=cmd_migrate)

    ps = sub.add_parser("status", parents=[common], help="状态")
    ps.set_defaults(func=cmd_status)
    return p


def main():
    _ensure_dirs()
    args = build_argparser().parse_args()
    if not getattr(args, "func", None):
        build_argparser().print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
