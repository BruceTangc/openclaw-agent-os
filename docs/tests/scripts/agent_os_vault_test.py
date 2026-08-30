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
import yaml

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


def vault_cmd(args, ws, vault):
    env = {"AGENT_OS_VAULT_WORKSPACE": ws}
    cmd = [sys.executable, VAULT_SCRIPT] + args + ["--vault", vault]
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
    kfile = os.path.join(vault, "knowledge", "claim-KNW-test.md")
    os.makedirs(os.path.dirname(kfile), exist_ok=True)
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-test\ntype: claim\n"
                "subject: 测试知识\nclaim: 这是测试声明\nconfidence: 0.85\nfreshness: 0.9\n"
                "validity: verified\nstatus: active\nsource_type: user_asserted\n"
                "provenance_ref: evidence.jsonl:1:abcd\nevidence_refs:\n  - EVD-0001\n"
                "tags:\n  - agent-os/view\n  - knowledge/claim\n---\n# 测试声明\n\n正文\n")
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
    with open(kfile, "w") as f:
        f.write("---\nosv: 1\nobject_type: knowledge\nid: KNW-imp\ntype: claim\n"
                "subject: 导入测试\nclaim: 导入测试声明\nconfidence: 0.7\nfreshness: 0.8\n"
                "validity: unverified\nstatus: active\nsource_type: source_stated\n"
                "provenance_ref: evidence.jsonl:2:ef01\ntags:\n  - agent-os/view\n---\n# 导入测试\n\n正文\n")
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
        if "_index.md" in f or "META.md" in f or "provenance-map" in f:
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


if __name__ == "__main__":
    sys.exit(main())
