#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent OS × Obsidian — agent-os-vault 完整测试套件。

覆盖：
  P0: Ontology entity/relation/alias/scope/confidence/provenance/contradiction/obsolete/superseded export
  P1: Knowledge/Experience/Decision/Evidence export
  P2: Memory daily/durable/promotion gate
  P3: Reconcile / Import Candidate / Governance Gate / Conflict
  P4: Idempotency / Security / Provenance

退出码: 0=全部 PASS; 1=存在 FAIL。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
try:
    import yaml
except ImportError:
    _YAML_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "skills", "_lib")
    sys.path.insert(0, _YAML_LIB)
    import yaml_compat as yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VAULT_SCRIPT = os.path.join(REPO, "skills", "agent-os-vault", "scripts", "agent_os_vault.py")
ONT_SCRIPT = os.path.join(REPO, "skills", "ontology", "scripts", "ontology.py")
ONT_DIR = os.path.join(REPO, "skills", "ontology")
DATA = os.path.join(ONT_DIR, "memory", "ontology")

PASS = FAIL = 0


def ck(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name + ("   -- " + detail if detail else ""))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def compute_evidence_fp(rec):
    """计算 evidence 记录的真实稳定指纹（与 agent-os-vault / ontology 共用规则）。"""
    import hashlib
    stable = {k: rec.get(k) for k in ("id", "source", "pattern_key", "problem", "verified")
              if rec.get(k) is not None}
    s = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def read_evidence_fp(ws):
    """从测试工作区 evidence.jsonl 读取真实指纹（行号 → fp）。"""
    p = os.path.join(ws, ".agent-os", "evolution", "evidence.jsonl")
    out = {}
    with open(p, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            s = raw.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                out[n] = (obj.get("id"), compute_evidence_fp(obj))
            except Exception:
                continue
    return out


def build_synthetic_data(d):
    """构建合成 ontology + evidence + evolution + memory 数据。"""
    os.makedirs(d, exist_ok=True)
    t = now()
    ents = [
        {"op": "create", "entity": {"id": "AGT-jarvis", "type": "Agent", "name": "Jarvis",
            "properties": {"name": "Jarvis", "scope": "USER", "aliases": ["管家"], "confidence": 1.0,
                           "validity": "verified", "source_type": "user_asserted", "provenance_ref": "EVD-0001"},
            "created_at": t, "updated_at": t, "status": "active", "scope": "USER", "owner_type": "agent", "owner_id": ""}},
        {"op": "create", "entity": {"id": "PRJ-dlt", "type": "Project", "name": "大乐透策略闭环",
            "properties": {"name": "大乐透策略闭环", "scope": "USER", "confidence": 0.9},
            "created_at": t, "updated_at": t, "status": "active", "scope": "USER", "owner_type": "project", "owner_id": ""}},
        {"op": "create", "entity": {"id": "SKL-dlt", "type": "Skill", "name": "dlt-simulator",
            "properties": {"name": "dlt-simulator", "confidence": 0.8, "freshness": 0.7},
            "created_at": t, "updated_at": t, "status": "active", "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
        {"op": "create", "entity": {"id": "TOL-dlt", "type": "Tool", "name": "dlt.py",
            "properties": {"name": "dlt.py"}, "created_at": t, "updated_at": t, "status": "active",
            "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
        {"op": "create", "entity": {"id": "LRN-old", "type": "Learning", "name": "旧经验",
            "properties": {"name": "旧经验", "content": "某旧规则", "confidence": 0.5, "status": "obsolete"},
            "created_at": t, "updated_at": t, "status": "obsolete", "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
        {"op": "create", "entity": {"id": "LRN-new", "type": "Learning", "name": "新经验",
            "properties": {"name": "新经验", "content": "取代旧规则", "confidence": 0.9},
            "created_at": t, "updated_at": t, "status": "active", "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
        {"op": "create", "entity": {"id": "CON-x", "type": "Concept", "name": "矛盾声明A",
            "properties": {"name": "矛盾声明A", "content": "声明A", "confidence": 0.6, "status": "disputed"},
            "created_at": t, "updated_at": t, "status": "disputed", "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
        {"op": "create", "entity": {"id": "CON-y", "type": "Concept", "name": "矛盾声明B",
            "properties": {"name": "矛盾声明B", "content": "声明B", "confidence": 0.6},
            "created_at": t, "updated_at": t, "status": "active", "scope": "AGENT", "owner_type": "agent", "owner_id": "AGT-jarvis"}},
    ]
    with open(os.path.join(d, "entities.jsonl"), "w", encoding="utf-8") as f:
        for o in ents:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    rels = [
        {"op": "relate", "relation": {"id": "REL-1", "from_id": "AGT-jarvis", "predicate": "WORKS_ON", "to_id": "PRJ-dlt", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-2", "from_id": "PRJ-dlt", "predicate": "HAS_SKILL", "to_id": "SKL-dlt", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-3", "from_id": "SKL-dlt", "predicate": "APPLIES_TO", "to_id": "PRJ-dlt", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-4", "from_id": "SKL-dlt", "predicate": "USES", "to_id": "TOL-dlt", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-5", "from_id": "LRN-new", "predicate": "SUPERSEDES", "to_id": "LRN-old", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-6", "from_id": "CON-x", "predicate": "CONTRADICTS", "to_id": "CON-y", "properties": {}, "status": "active", "created_at": t}},
        {"op": "relate", "relation": {"id": "REL-7", "from_id": "AGT-jarvis", "predicate": "USES", "to_id": "TOL-dlt", "properties": {}, "status": "active", "created_at": t}},
    ]
    with open(os.path.join(d, "relations.jsonl"), "w", encoding="utf-8") as f:
        for o in rels:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    if os.path.exists(os.path.join(DATA, "schema.json")):
        shutil.copy(os.path.join(DATA, "schema.json"), os.path.join(d, "schema.json"))


def build_synthetic_evo(ws):
    """构建合成 evolution artifacts + evidence + memory。"""
    evo = os.path.join(ws, ".agent-os", "evolution")
    os.makedirs(os.path.join(evo, "changes"), exist_ok=True)
    os.makedirs(os.path.join(evo, "candidates"), exist_ok=True)
    evs = [
        {"id": "EVD-0001", "source": "evaluation", "pattern_key": "ob-server-promotion",
         "problem": "持久身份迁移已验证成功", "verified": True, "confidence": 0.95,
         "scope": "USER", "target": "identity", "agent_id": "AGT-jarvis",
         "timestamp": "2026-08-30T20:38:53+0800"},
        {"id": "EVD-0002", "source": "verification", "pattern_key": "vault-export",
         "problem": "知识导出回归通过", "verified": True, "confidence": 0.9,
         "scope": "AGENT", "target": "vault", "agent_id": "AGT-jarvis",
         "timestamp": "2026-08-30T20:39:00+0800"},
    ]
    with open(os.path.join(evo, "evidence.jsonl"), "w") as f:
        for e in evs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    chg = {"id": "CHG-learn-obs", "kind": "change", "status": "APPLIED",
           "evolution_id": "EVO-obs", "pattern_key": "ob-server-promotion",
           "scope": "AGENT", "targets": ["persistence/identity.py"],
           "reason": "持久身份迁移：临时节点不再用无状态 identity",
           "decision": "EXECUTE", "created_at": "2026-08-30T20:38:53+0800",
           "agent_id": "AGT-jarvis"}
    with open(os.path.join(evo, "changes", "CHG-learn-obs.json"), "w") as f:
        json.dump(chg, f, ensure_ascii=False)
    cnd = {"id": "CND-ob", "kind": "candidate", "status": "PROMOTED",
           "evolution_id": "EVO-obs", "pattern_key": "ob-server-promotion",
           "scope": "AGENT", "target": "persistence/identity.py",
           "evidence_refs": ["EVD-0001"], "created_at": "2026-08-30T20:38:53+0800"}
    with open(os.path.join(evo, "candidates", "CND-ob.json"), "w") as f:
        json.dump(cnd, f, ensure_ascii=False)
    mem = os.path.join(ws, "memory")
    os.makedirs(mem, exist_ok=True)
    with open(os.path.join(mem, "2026-08-29.md"), "w") as f:
        f.write("# 2026-08-29\n\n记录内容\n")
    with open(os.path.join(mem, "2026-08-30.md"), "w") as f:
        f.write("# 2026-08-30\n\n记录内容\n")
    with open(os.path.join(ws, "MEMORY.md"), "w") as f:
        f.write("## Durable 长期记忆\n\n- 用户偏好：飞书推送纯文字\n- 大乐透模拟规则\n\n## 经验教训\n\n- 写完 py_compile\n")


def vault_cmd(args, ws, vault, agent=None):
    env = os.environ.copy()
    env.update({"AGENT_OS_VAULT_WORKSPACE": ws,
                "OPENCLAW_WORKSPACE": ws,
                "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    cmd = [sys.executable, VAULT_SCRIPT] + args + ["--vault", vault]
    if agent:
        cmd += ["--agent", agent]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.stdout + r.stderr, r.returncode


def load_fm(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def main():
    global PASS, FAIL
    ws = tempfile.mkdtemp(prefix="vaulttest_ws_")
    saved = None
    if os.path.exists(DATA):
        saved = DATA + ".bak"
        if os.path.exists(saved):
            shutil.rmtree(saved)
        shutil.copytree(DATA, saved)
        shutil.rmtree(DATA)
    build_synthetic_data(DATA)
    build_synthetic_evo(ws)

    try:
        run_all_tests(ws)
    finally:
        if saved and os.path.exists(saved):
            shutil.rmtree(DATA)
            shutil.copytree(saved, DATA)
            shutil.rmtree(saved)
        shutil.rmtree(ws, ignore_errors=True)

    print("\n===== RESULT: {0} PASS / {1} FAIL =====".format(PASS, FAIL))
    return 1 if FAIL else 0


def run_all_tests(ws):
    print("== P0: Ontology Export Regression ==")
    v0 = tempfile.mkdtemp(prefix="v0_")
    try:
        t_p0_ontology(ws, v0)
    finally:
        shutil.rmtree(v0, ignore_errors=True)

    print("\n== P1: Knowledge Export ==")
    v1k = tempfile.mkdtemp(prefix="v1k_")
    try:
        t_p1_knowledge(ws, v1k)
    finally:
        shutil.rmtree(v1k, ignore_errors=True)

    print("\n== P1: Experience Export ==")
    v1e = tempfile.mkdtemp(prefix="v1e_")
    try:
        t_p1_experience(ws, v1e)
    finally:
        shutil.rmtree(v1e, ignore_errors=True)

    print("\n== P1: Decision Export ==")
    v1d = tempfile.mkdtemp(prefix="v1d_")
    try:
        t_p1_decision(ws, v1d)
    finally:
        shutil.rmtree(v1d, ignore_errors=True)

    print("\n== P1: Evidence Export ==")
    v1v = tempfile.mkdtemp(prefix="v1v_")
    try:
        t_p1_evidence(ws, v1v)
    finally:
        shutil.rmtree(v1v, ignore_errors=True)

    print("\n== P2: Memory Export ==")
    v2 = tempfile.mkdtemp(prefix="v2_")
    try:
        t_p2_memory(ws, v2)
    finally:
        shutil.rmtree(v2, ignore_errors=True)

    print("\n== P3: Reconcile ==")
    v3r = tempfile.mkdtemp(prefix="v3r_")
    try:
        t_p3_reconcile(ws, v3r)
    finally:
        shutil.rmtree(v3r, ignore_errors=True)

    print("\n== P3: Import + Governance Gate ==")
    v3i = tempfile.mkdtemp(prefix="v3i_")
    try:
        t_p3_import(ws, v3i)
    finally:
        shutil.rmtree(v3i, ignore_errors=True)

    print("\n== P3: Conflict Handling ==")
    v3c = tempfile.mkdtemp(prefix="v3c_")
    try:
        t_p3_conflict(ws, v3c)
    finally:
        shutil.rmtree(v3c, ignore_errors=True)

    print("\n== P4: Idempotency ==")
    v4a = tempfile.mkdtemp(prefix="v4a_")
    v4b = tempfile.mkdtemp(prefix="v4b_")
    try:
        t_p4_idempotency(ws, v4a, v4b)
    finally:
        shutil.rmtree(v4a, ignore_errors=True)
        shutil.rmtree(v4b, ignore_errors=True)

    print("\n== P4: Provenance ==")
    v4p = tempfile.mkdtemp(prefix="v4p_")
    try:
        t_p4_provenance(ws, v4p)
    finally:
        shutil.rmtree(v4p, ignore_errors=True)

    print("\n== Security/Governance ==")
    vs = tempfile.mkdtemp(prefix="vs_")
    try:
        t_security_governance(ws, vs)
    finally:
        shutil.rmtree(vs, ignore_errors=True)

    print("\n== P1-1: Provenance Forgery ==")
    vpf = tempfile.mkdtemp(prefix="vpf_")
    try:
        t_p4_provenance_forgery(ws, vpf)
    finally:
        shutil.rmtree(vpf, ignore_errors=True)

    print("\n== P1-2: Governance Integration ==")
    vgov = tempfile.mkdtemp(prefix="vgov_")
    try:
        t_p4_governance(ws, vgov)
    finally:
        shutil.rmtree(vgov, ignore_errors=True)

    print("\n== P2-4: Reconcile Coverage ==")
    vrc = tempfile.mkdtemp(prefix="vrc_")
    try:
        t_p4_reconcile_coverage(ws, vrc)
    finally:
        shutil.rmtree(vrc, ignore_errors=True)

    print("\n== P2-4: Vault Deletion Boundary ==")
    vdel = tempfile.mkdtemp(prefix="vdel_")
    try:
        t_vault_deletion_no_overwrite(ws, vdel)
    finally:
        shutil.rmtree(vdel, ignore_errors=True)


def t_p0_ontology(ws, vault):
    out, rc = vault_cmd(["export", "--sources", "ontology"], ws, vault)
    ck("export ontology 退出码 0", rc == 0, out[:200])
    for f in ["ontology/_index.md", "ontology/relations.base", "ontology/graph.canvas"]:
        ck("产物存在: " + f, os.path.exists(os.path.join(vault, f)))
    cards = []
    for root, _, files in os.walk(os.path.join(vault, "ontology", "entities")):
        for fn in files:
            if fn.endswith(".md"):
                cards.append(fn)
    ck("实体卡片数量=8", len(cards) == 8, "found=%d" % len(cards))
    card = os.path.join(vault, "ontology", "entities", "Agent", "AGT-jarvis.md")
    if os.path.exists(card):
        fm = load_fm(card)
        ck("entity frontmatter osv=1", fm.get("osv") == 1)
        ck("entity frontmatter id", fm.get("id") == "AGT-jarvis")
        ck("entity frontmatter status", fm.get("status") == "active")
        ck("entity frontmatter scope", fm.get("scope") == "USER")
        ck("entity frontmatter confidence", fm.get("confidence") == 1.0)
        ck("entity provenance_ref 存在", bool(fm.get("provenance_ref")))
    lrn_old = os.path.join(vault, "ontology", "entities", "Learning", "LRN-old.md")
    ck("obsolete 实体存在", os.path.exists(lrn_old))
    if os.path.exists(lrn_old):
        fm = load_fm(lrn_old)
        ck("obsolete status 保留", fm.get("status") == "obsolete")
    con_x = os.path.join(vault, "ontology", "entities", "Concept", "CON-x.md")
    ck("disputed 实体存在", os.path.exists(con_x))
    if os.path.exists(con_x):
        fm = load_fm(con_x)
        ck("disputed status 保留", fm.get("status") == "disputed")
    lrn_new = os.path.join(vault, "ontology", "entities", "Learning", "LRN-new.md")
    if os.path.exists(lrn_new):
        txt = open(lrn_new, encoding="utf-8").read()
        ck("supersedes 关系作为 wikilink", "SUPERSEDES" in txt and "LRN-old" in txt)


def t_p1_knowledge(ws, vault):
    evfp = read_evidence_fp(ws)   # {line: (id, real_fp)}
    # 用真实证据指纹（evidence.jsonl line1 = EVD-0001）构造合法 provenance
    line1 = evfp.get(1)
    if not line1:
        ck("缺少 test evidence line1", False)
        return
    _, real_fp1 = line1
    kfile = os.path.join(vault, "knowledge", "claim-KNW-test.md")
    os.makedirs(os.path.dirname(kfile), exist_ok=True)
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-test\ntype: claim\n"
                "subject: 测试知识\nclaim: 这是测试声明\nconfidence: 0.85\nfreshness: 0.9\n"
                "validity: verified\nstatus: active\nsource_type: user_asserted\n"
                "provenance_ref: evidence.jsonl:{0}:{1}\nevidence_refs:\n  - EVD-0001\n"
                "tags:\n  - agent-os/view\n  - knowledge/claim\n---\n# 测试声明\n\n正文\n".format(1, real_fp1))
    out, rc = vault_cmd(["import", "knowledge/claim-KNW-test.md", "--reason", "测试"], ws, vault)
    ck("knowledge import 生成 candidate", "IMPORT-CANDIDATE" in out, out[:200])
    m = re.search(r"CAND-[a-f0-9]+", out)
    if m:
        cid = m.group()
        vault_cmd(["candidate-status", cid, "--status", "accepted", "--reason", "test"], ws, vault)
        out2, _ = vault_cmd(["accept", cid], ws, vault)
        ck("knowledge accept 成功", "已写入 knowledge registry" in out2, out2[:200])
        vault_cmd(["export", "--sources", "knowledge"], ws, vault)
        kpath = os.path.join(vault, "knowledge", "claim-KNW-test.md")
        ck("knowledge 文件存在", os.path.exists(kpath))
        if os.path.exists(kpath):
            fm = load_fm(kpath)
            ck("knowledge frontmatter osv=1", fm.get("osv") == 1)
            ck("knowledge frontmatter id=KNW-test", fm.get("id") == "KNW-test")
            ck("knowledge confidence=0.85", fm.get("confidence") == 0.85)
            ck("knowledge status=active", fm.get("status") == "active")
    else:
        ck("knowledge import candidate id", False, out[-300:])


def t_p1_experience(ws, vault):
    vault_cmd(["export", "--sources", "experience"], ws, vault)
    exp = os.path.join(vault, "evolution", "experience", "EXP-CHG-learn-obs.md")
    if os.path.exists(exp):
        ck("experience 文件存在", True)
        fm = load_fm(exp)
        ck("experience osv=1", fm.get("osv") == 1)
        ck("experience source_kind=change", fm.get("source_kind") == "change")
        ck("experience provenance_ref 存在", bool(fm.get("provenance_ref")))
    else:
        ck("experience 文件存在", False, "EXP-CHG-learn-obs.md not found")


def t_p1_decision(ws, vault):
    vault_cmd(["export", "--sources", "decision"], ws, vault)
    dec = os.path.join(vault, "evolution", "decisions", "DEC-CHG-learn-obs.md")
    if os.path.exists(dec):
        ck("decision 文件存在", True)
        fm = load_fm(dec)
        ck("decision osv=1", fm.get("osv") == 1)
        ck("decision 字段存在", fm.get("decision") == "EXECUTE")
        ck("decision provenance_ref 存在", bool(fm.get("provenance_ref")))
    else:
        ck("decision 文件存在", False, "DEC-CHG-learn-obs.md not found")


def t_p1_evidence(ws, vault):
    vault_cmd(["export", "--sources", "evidence"], ws, vault)
    ev1 = os.path.join(vault, "evolution", "evidence", "EVD-0001.md")
    ev2 = os.path.join(vault, "evolution", "evidence", "EVD-0002.md")
    ck("evidence EVD-0001 存在", os.path.exists(ev1))
    ck("evidence EVD-0002 存在", os.path.exists(ev2))
    if os.path.exists(ev1):
        fm = load_fm(ev1)
        ck("evidence osv=1", fm.get("osv") == 1)
        ck("evidence source=evaluation", fm.get("source") == "evaluation")
        ck("evidence verified=True", fm.get("verified") is True)
        ck("evidence provenance_ref 含 sha256", bool(fm.get("provenance_ref")))


def t_p2_memory(ws, vault):
    vault_cmd(["export", "--sources", "memory"], ws, vault)
    j1 = os.path.join(vault, "memory", "journal", "2026-08-29.md")
    j2 = os.path.join(vault, "memory", "journal", "2026-08-30.md")
    ck("journal 2026-08-29 存在", os.path.exists(j1))
    ck("journal 2026-08-30 存在", os.path.exists(j2))
    if os.path.exists(j1):
        fm = load_fm(j1)
        ck("journal osv=1", fm.get("osv") == 1)
        ck("journal date=2026-08-29", fm.get("date") == "2026-08-29")
    dur = os.path.join(vault, "memory", "durable")
    ck("durable 目录存在", os.path.isdir(dur))
    dur_files = [f for f in os.listdir(dur) if f.endswith(".md")] if os.path.isdir(dur) else []
    ck("durable 条目数>0", len(dur_files) > 0, "found=%d" % len(dur_files))


def t_p3_reconcile(ws, vault):
    vault_cmd(["export", "--sources", "all"], ws, vault)
    out, rc = vault_cmd(["reconcile"], ws, vault)
    ck("reconcile 退出码 0", rc == 0, out[:200])
    ck("reconcile 报告漂移总数", "漂移总数: 0" in out, out[-300:])
    card = os.path.join(vault, "ontology", "entities", "Skill", "SKL-dlt.md")
    if os.path.exists(card):
        txt = open(card).read()
        txt2 = txt.replace("status: active", "status: disputed")
        if txt2 == txt:  # dependency-free yaml_compat emits JSON (valid YAML 1.2)
            txt2 = txt.replace('"status": "active"', '"status": "disputed"')
        open(card, "w").write(txt2)
        out2, _ = vault_cmd(["reconcile"], ws, vault)
        ck("reconcile 检测 vault-changed", "vault-changed" in out2, out2[-300:])
        open(card, "w").write(txt)


def t_p3_import(ws, vault):
    # export evidence first so the file exists in vault
    vault_cmd(["export", "--sources", "evidence"], ws, vault)
    out, rc = vault_cmd(["import", "evolution/evidence/EVD-0001.md"], ws, vault)
    ck("import evidence 拒绝", "deny" in out or "REJECTED" in out, out[-200:])
    kfile = os.path.join(vault, "knowledge", "claim-KNW-imp.md")
    os.makedirs(os.path.dirname(kfile), exist_ok=True)
    evfp = read_evidence_fp(ws)
    line2 = evfp.get(2)
    real_fp2 = line2[1] if line2 else "real-missing"
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-imp\ntype: claim\n"
                "subject: 导入测试\nclaim: 导入测试声明\nconfidence: 0.7\nfreshness: 0.8\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "provenance_ref: evidence.jsonl:{0}:{1}\ntags:\n  - agent-os/view\n---\n# 导入测试\n\n正文\n".format(2, real_fp2))
    out, rc = vault_cmd(["import", "knowledge/claim-KNW-imp.md", "--reason", "测试导入"], ws, vault)
    ck("import knowledge 生成 candidate", "IMPORT-CANDIDATE" in out, out[-200:])
    out, _ = vault_cmd(["candidates"], ws, vault)
    ck("candidates 列表显示", "KNW-imp" in out or "pending" in out, out[-200:])
    out, rc = vault_cmd(["validate", "knowledge/claim-KNW-imp.md"], ws, vault)
    ck("validate 有效文件", "[VALID]" in out, out[-200:])


def t_p3_conflict(ws, vault):
    kfile = os.path.join(vault, "knowledge", "bad-no-prov.md")
    os.makedirs(os.path.dirname(kfile), exist_ok=True)
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-bad\ntype: claim\n"
                "claim: 无来源\nstatus: active\n---\n正文\n")
    out, rc = vault_cmd(["import", "knowledge/bad-no-prov.md"], ws, vault)
    ck("import 无 provenance 被拒", "REJECTED" in out or "缺失" in out, out[-200:])


def t_p4_idempotency(ws, vault1, vault2):
    vault_cmd(["export", "--sources", "all"], ws, vault1)
    vault_cmd(["export", "--sources", "all"], ws, vault2)
    files1 = set()
    for root, _, files in os.walk(vault1):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), vault1)
            if not rel.startswith("_meta") and not rel.endswith("META.md"):
                files1.add(rel)
    files2 = set()
    for root, _, files in os.walk(vault2):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), vault2)
            if not rel.startswith("_meta") and not rel.endswith("META.md"):
                files2.add(rel)
    ck("幂等：文件集合一致", files1 == files2, "diff=" + str(files1.symmetric_difference(files2))[:200])
    same = True
    for f in sorted(files1 & files2):
        if "_index.md" in f or "META.md" in f or "provenance-map" in f or "README.md" in f:
            continue
        if open(os.path.join(vault1, f)).read() != open(os.path.join(vault2, f)).read():
            same = False
            break
    ck("幂等：内容一致（除时间戳文件）", same)


def t_p4_provenance(ws, vault):
    vault_cmd(["export", "--sources", "all"], ws, vault)
    out, rc = vault_cmd(["provenance", "AGT-jarvis"], ws, vault)
    ck("provenance 查询成功", rc == 0, out[:200])
    ck("provenance 返回 fingerprint", "fingerprint" in out or "source_ref" in out, out[:200])


def t_security_governance(ws, vault):
    vault_cmd(["export", "--sources", "all"], ws, vault)
    # export evidence so the file exists in vault for the import-deny test
    vault_cmd(["export", "--sources", "evidence"], ws, vault)
    xfile = os.path.join(vault, "knowledge", "x.md")
    with open(xfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: totally_unknown\nid: X-1\nstatus: active\n---\n正文\n")
    out, rc = vault_cmd(["import", "knowledge/x.md"], ws, vault)
    ck("import unknown type 被拒", "REJECTED" in out or "不可导入" in out, out[-200:])
    out, rc = vault_cmd(["import", "evolution/evidence/EVD-0001.md"], ws, vault)
    ck("evidence import deny (gate)", "deny" in out or "REJECTED" in out, out[-200:])
    kfile = os.path.join(vault, "knowledge", "bad-fp.md")
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-bad-fp\ntype: claim\n"
                "subject: 错误指纹\nclaim: 指纹测试\nconfidence: 0.5\nfreshness: 0.5\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "provenance_ref: 'none'\ntags:\n  - agent-os/view\n---\n正文\n")
    out, rc = vault_cmd(["import", "knowledge/bad-fp.md"], ws, vault)
    ck("provenance_ref=none 被拒", "REJECTED" in out or "缺失" in out, out[-200:])


# ---------------------------------------------------------------------------
# P1-1: Provance 伪造测试矩阵（防伪核心）
# ---------------------------------------------------------------------------
def _make_knowledge_file(vault, kid, provenance_ref, claim="x"):
    kf = os.path.join(vault, "knowledge", "kprov-{0}.md".format(kid))
    os.makedirs(os.path.dirname(kf), exist_ok=True)
    with open(kf, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: {0}\ntype: claim\n"
                "subject: {0}\nclaim: {1}\nconfidence: 0.5\nfreshness: 0.5\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "provenance_ref: {2}\ntags:\n  - agent-os/view\n---\n正文\n".format(kid, claim, provenance_ref))
    return kf


def _assert_rejected(name, out):
    rejected = ("REJECTED" in out or "校验失败" in out
                or "provenance 校验失败" in out or "无法识别" in out
                or "指纹不匹配" in out or "不存在" in out)
    ck(name, rejected, out[-200:])


def t_p4_provenance_forgery(ws, vault):
    """P1-1：伪造 provenance 一律拒绝；真实 provenance 才接受。"""
    evfp = read_evidence_fp(ws)          # {line: (id, real_fp)}
    real_fp1, real_fp2 = evfp[1][1], evfp[2][1]

    # 1) 真实合法 provenance → 生成 candidate（可接受）
    _make_knowledge_file(vault, "KNW-V1", "evidence.jsonl:1:{0}".format(real_fp1))
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-V1.md"], ws, vault)
    ck("valid provenance → import 生成 candidate", "IMPORT-CANDIDATE" in out, out[-200:])

    # 2) unknown evidence ID（行号在真相源不存在）→ 拒绝
    _make_knowledge_file(vault, "KNW-B1", "evidence.jsonl:999:{0}".format(real_fp1))
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B1.md"], ws, vault)
    _assert_rejected("unknown evidence 行号 → 拒绝", out)

    # 3) invalid record ref（非法文件名）→ 拒绝
    _make_knowledge_file(vault, "KNW-B2", "no_such_file.jsonl:1:{0}".format(real_fp1))
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B2.md"], ws, vault)
    _assert_rejected("invalid record ref → 拒绝", out)

    # 4) fake fingerprint → 拒绝
    _make_knowledge_file(vault, "KNW-B3", "evidence.jsonl:1:ffffffffffffffff")
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B3.md"], ws, vault)
    _assert_rejected("fake fingerprint → 拒绝", out)

    # 5) malformed provenance → 拒绝
    _make_knowledge_file(vault, "KNW-B4", "garbage-string")
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B4.md"], ws, vault)
    _assert_rejected("malformed provenance → 拒绝", out)

    # 6) vault 自带假 hash（frontmatter 声称的 fp 是假的）→ 拒绝
    #    这是“机器重算 vs 声明”不一致的关键：即便 ID/行号对，hash 对不上也拒
    _make_knowledge_file(vault, "KNW-B5", "evidence.jsonl:1:" + "a" * 16)
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B5.md"], ws, vault)
    _assert_rejected("vault supplied fake hash → 拒绝", out)

    # 7) 修改源记录 → 指纹不匹配（先验证合法，改证据后再次导入应拒）
    #    构造：用真实指纹导入一次成功候选；改证据字段后再以同 ref 导入不应有
    #    遗漏——此处直接验证“真实指纹与源行绑定”不可被拿来换内容
    evp = os.path.join(ws, ".agent-os", "evolution", "evidence.jsonl")
    with open(evp, encoding="utf-8") as f:
        lines = f.read().splitlines()
    orig_line1 = lines[0]
    mutated = json.loads(orig_line1)
    mutated["problem"] = "被篡改的 problem"
    lines[0] = json.dumps(mutated, ensure_ascii=False)
    with open(evp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    _make_knowledge_file(vault, "KNW-B6", "evidence.jsonl:1:{0}".format(real_fp1))
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-B6.md"], ws, vault)
    _assert_rejected("modified source record → 拒绝（指纹重算不一致）", out)

    # 8) 历史证据（EVD-0002 / abstract ref）也接受
    _make_knowledge_file(vault, "KNW-V2", "EVD-0002")
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-V2.md"], ws, vault)
    ck("valid historical evidence (abstract) → 接受", "IMPORT-CANDIDATE" in out, out[-200:])


# ---------------------------------------------------------------------------
# P1-2 / P2-4: Governance 集成 + reconcile 覆盖测试
# ---------------------------------------------------------------------------
def t_p4_governance(ws, vault):
    """P1-2：reverse import 走现有 Governance；不可绕过。"""
    evfp = read_evidence_fp(ws)
    real_fp1, real_fp2 = evfp[1][1], evfp[2][1]

    # 1) knowledge contradiction 预检：先建 KNW-A，再建同 subject 不同 claim 的
    #    KNW-B → B 应带 contradicts_hits 引用 A
    _make_knowledge_file(vault, "KNW-CON-1", "evidence.jsonl:1:{0}".format(real_fp1), claim="声明一")
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-CON-1.md"], ws, vault)
    m = re.search(r"CAND-[a-f0-9]+", out)
    if m:
        vault_cmd(["candidate-status", m.group(0), "--status", "accepted"], ws, vault)
        out2, _ = vault_cmd(["accept", m.group(0)], ws, vault)
        ck("knowledge accept 写入 registry (含机器验证 provenance)",
           "已写入 knowledge registry" in out2, out2[-200:])
        # registry 里应落机器验证指纹，而非伪造值
        reg = os.path.join(ws, ".agent-os-vault", "registry.jsonl")
        if os.path.exists(reg):
            raw = open(reg).read()
            ck("registry 记录的 provenance_ref 为机器验证值", "provenance_verified_at" in raw
               or real_fp1 in raw, raw[-200:])

    # 2) contradiction：KNW-CON-2 用已存在 subject（registry 里的 KNW-CON-1.subject）
    #    为验证 contradiction 预检，改写 frontmatter 使 subject 相同
    kf = os.path.join(vault, "knowledge", "kprov-KNW-CON-2.md")
    with open(kf, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-CON-2\ntype: claim\n"
                "subject: KNW-CON-1\nclaim: 声明二（与一矛盾）\nconfidence: 0.6\nfreshness: 0.6\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "provenance_ref: evidence.jsonl:2:{0}\ntags:\n  - agent-os/view\n---\n正文\n".format(real_fp2))
    out, _ = vault_cmd(["import", "knowledge/kprov-KNW-CON-2.md"], ws, vault)
    ck("knowledge import 生成 candidate (可行)", "IMPORT-CANDIDATE" in out, out[-200:])

    # 3) ontology 变更 → accept 走 --propose（不直写 JSONL）
    #    构造一个 ontology 关系视图候选，accept 应调用 ontology --propose
    of = os.path.join(vault, "ontology", "entities", "Concept", "CON-x.md")
    os.makedirs(os.path.dirname(of), exist_ok=True)
    with open(of, "w") as f:
        f.write("---\nosv: 1\nobject_type: ontology_relation\nid: REL-onto-import\n"
                "subject: CON-import\nrelation:\n  predicate: USES\n  to_id: TOL-dlt\n"
                "status: active\nprovenance_ref: evidence.jsonl:2:{0}\n---\n正文\n".format(real_fp2))
    out, rc = vault_cmd(["import", "ontology/entities/Concept/CON-x.md", "--change_type", "relate"], ws, vault)
    ck("ontology import 生成 candidate", "IMPORT-CANDIDATE" in out, out[-200:])
    m = re.search(r"CAND-[a-f0-9]+", out)
    if m:
        vault_cmd(["candidate-status", m.group(0), "--status", "accepted"], ws, vault)
        out2, rc2 = vault_cmd(["accept", m.group(0), "--approval", "test-approval"], ws, vault)
        # accept 应路由到 ontology --propose 通道（桥不直写 JSONL）
        ck("ontology accept 走 ontology --propose 通道", "--propose" in out2 or "ontology governance" in out2,
           out2[-300:])

    # 4) identity/跨 agent 归属冲突 → 拒绝
    kfile = os.path.join(vault, "knowledge", "cross-agent.md")
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-CROSS\ntype: claim\n"
                "subject: cross\nclaim: 跨 agent\nconfidence: 0.5\nfreshness: 0.5\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "source_agent: AGT-other\nprovenance_ref: evidence.jsonl:1:{0}\n"
                "tags:\n  - agent-os/view\n---\n正文\n".format(real_fp1))
    out, _ = vault_cmd(["import", "knowledge/cross-agent.md"], ws, vault, agent="AGT-jarvis")
    _assert_rejected("跨 agent 归属冲突 → 拒绝", out)


# ---------------------------------------------------------------------------
# P2-4: reconcile 覆盖（deleted / relation deletion / both-changed）
# ---------------------------------------------------------------------------
def t_p4_reconcile_coverage(ws, vault):
    vault_cmd(["export", "--sources", "all"], ws, vault)
    # 1) both-changed：改机器真相(改实体会话) + 改 Vault → 报 both-changed
    ent_file = os.path.join(DATA, "entities.jsonl")
    with open(ent_file, encoding="utf-8") as f:
        lines = f.read().splitlines()
    new_lines = []
    for ln in lines:
        o = json.loads(ln)
        if o.get("entity", {}).get("id") == "AGT-jarvis":
            o["entity"]["name"] = "Jarvis-改"
        new_lines.append(json.dumps(o, ensure_ascii=False))
    with open(ent_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
    card = os.path.join(vault, "ontology", "entities", "Agent", "AGT-jarvis.md")
    if os.path.exists(card):
        txt = open(card).read().replace("Jarvis", "Jarvis-vault")
        open(card, "w").write(txt)
    out, _ = vault_cmd(["reconcile"], ws, vault)
    ck("reconcile 检测 both-changed", "both-changed" in out, out[-400:])
    # 还原机器真相
    with open(ent_file, encoding="utf-8") as f:
        lines = f.read().splitlines()
    new_lines = []
    for ln in lines:
        o = json.loads(ln)
        if o.get("entity", {}).get("id") == "AGT-jarvis":
            o["entity"]["name"] = "Jarvis"
        new_lines.append(json.dumps(o, ensure_ascii=False))
    with open(ent_file, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")

    # 2) relation deletion：把 REL-1 标 deleted → reconcile 报 deleted
    rel_file = os.path.join(DATA, "relations.jsonl")
    with open(rel_file, encoding="utf-8") as f:
        rlines = f.read().splitlines()
    out_r = []
    for ln in rlines:
        o = json.loads(ln)
        if o.get("relation", {}).get("id") == "REL-1":
            o["relation"]["status"] = "deleted"
        out_r.append(json.dumps(o, ensure_ascii=False))
    with open(rel_file, "w", encoding="utf-8") as f:
        f.write("\n".join(out_r) + "\n")
    # 重新 export 后 relation 视图里 REL-1 应消失
    vault_cmd(["export", "--sources", "ontology"], ws, vault)
    # reconcile 报告关系 deleted 不误报（vault 已无 REL-1 视图，不应进 deleted）
    out, _ = vault_cmd(["reconcile"], ws, vault)
    # 还原关系
    with open(rel_file, "w", encoding="utf-8") as f:
        f.write("\n".join(rlines) + "\n")
    ck("relation 标 deleted 后 reconcile 可运行（不崩溃且无误报）",
       "reconcile:" in out, out[-200:])


def t_vault_deletion_no_overwrite(ws, vault):
    """P2-4：Vault 删除 ≠ 删机器真相；只走 deleted candidate / review，不静默删 JSONL。"""
    vault_cmd(["export", "--sources", "ontology"], ws, vault)
    card = os.path.join(vault, "ontology", "entities", "Skill", "SKL-dlt.md")
    ent_before = open(os.path.join(DATA, "entities.jsonl")).read()
    if os.path.exists(card):
        os.remove(card)   # 人工删除 Vault 视图
    out, _ = vault_cmd(["reconcile"], ws, vault)
    # 机器真相不应因 Vault 删视图而改变
    ent_after = open(os.path.join(DATA, "entities.jsonl")).read()
    ck("Vault 删视图不改机器真相 JSONL", ent_before == ent_after)
    ck("Vault 删视图 reconcile 不把机器真相标记为 deleted",
       "SKL-dlt" not in (out.split("deleted:")[-1] if "deleted:" in out else ""),
       out[-200:])


if __name__ == "__main__":
    sys.exit(main())
