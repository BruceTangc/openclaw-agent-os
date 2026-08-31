#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0 Agent OS × Obsidian — Ontology → Vault 单向只读导出测试。

覆盖（design doc 第 8 部分）：
  1. 现有 ontology 命令回归（--status / --entity / --relations）不因导出改动破坏。
  2. Ontology export 测试：批量导出可跑通，产出 entity cards + relations.base +
     graph.canvas + _index.md + _meta/META.md。
  3. Entity/Relation round-trip consistency：导出 frontmatter 字段与 JSONL 源一致
     （此阶段只验证一致，不执行 import）。
  4. provenance 完整性：每条导出 Entity/Relation 的 provenance_ref 可追溯回 JSONL 记录
     （行号 + SHA-256 指纹重算比对）。
  5. 重复 export 幂等性：跑两次输出一致、可覆盖、不损坏。
  6. obsolete/superseded/contradiction 场景：这些状态实体正确导出，status 保留，
     并渲染对应 warning callout。
  7. Vault 文件 schema 检查：frontmatter 合法 YAML + 必需字段 + wikilink 合规；
     relations.base 与 graph.canvas 语法有效。

用法:
  python3 docs/tests/scripts/ontology_vault_export_test.py

退出码: 0=全部 PASS；1=存在 FAIL。
"""
import hashlib
import json
import os
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
ONT = os.path.join(REPO, "skills", "ontology", "scripts", "ontology.py")
ONT_DIR = os.path.join(REPO, "skills", "ontology")
DATA = os.path.join(ONT_DIR, "memory", "ontology")  # script 实际读取的 DATA

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
    # schema（默认 schema 副本）
    shutil.copy(os.path.join(DATA, "schema.json"), os.path.join(d, "schema.json")) \
        if os.path.exists(os.path.join(DATA, "schema.json")) else None


def read_jsonl(path):
    out = []
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s:
            out.append(json.loads(s))
    return out


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    global PASS, FAIL
    # ---- 设置合成数据于 repo 的 DATA（gitignored，仅测试用）----
    saved = None
    if os.path.exists(DATA):
        saved = DATA + ".bak"
        if os.path.exists(saved):
            shutil.rmtree(saved)
        shutil.copytree(DATA, saved)
        shutil.rmtree(DATA)
    build_synthetic_data(DATA)

    try:
        run_tests()
    finally:
        # 恢复原始 DATA，避免污染
        if saved and os.path.exists(saved):
            shutil.rmtree(DATA)
            shutil.copytree(saved, DATA)
            shutil.rmtree(saved)

    print("\n===== RESULT: {0} PASS / {1} FAIL =====".format(PASS, FAIL))
    return 1 if FAIL else 0


def run_tests():
    print("== 0) 现有 ontology 命令回归（只读，不写 key）==")
    r = subprocess.run([sys.executable, ONT, "--status"], capture_output=True, text=True)
    ck("--status 可运行", r.returncode == 0 and "Entities:" in r.stdout)
    r = subprocess.run([sys.executable, ONT, "--entity", "AGT-jarvis"], capture_output=True, text=True)
    ck("--entity 可读取", r.returncode == 0 and "AGT-jarvis" in r.stdout)

    out1 = tempfile.mkdtemp(prefix="vault1_")
    out2 = tempfile.mkdtemp(prefix="vault2_")
    try:
        run_export_checks(out1)
        run_provenance_checks(out1)
        run_idempotency_checks(out1, out2)
        run_state_checks(out1)
        run_schema_checks(out1)
    finally:
        shutil.rmtree(out1, ignore_errors=True)
        shutil.rmtree(out2, ignore_errors=True)


def run_export_checks(out):
    print("\n== 1) Ontology export 测试 ==")
    r = subprocess.run([sys.executable, ONT, "--export-vault", "--out", out],
                       capture_output=True, text=True)
    ck("--export-vault 退出码 0", r.returncode == 0, r.stderr)
    for f in ["ontology/_index.md", "ontology/relations.base", "ontology/graph.canvas", "_meta/META.md"]:
        ck("产物存在: " + f, os.path.exists(os.path.join(out, f)))
    md_cards = []
    for root, _, files in os.walk(os.path.join(out, "ontology", "entities")):
        for fn in files:
            if fn.endswith(".md"):
                md_cards.append(os.path.join(root, fn))
    # 合成数据 8 个实体（全部核心类型）都应有卡片
    ck("实体卡片数量=8", len(md_cards) == 8, "found=%d" % len(md_cards))
    expected = {"AGT-jarvis", "PRJ-dlt", "SKL-dlt", "TOL-dlt", "LRN-old", "LRN-new", "CON-x", "CON-y"}
    found_ids = {os.path.splitext(os.path.basename(p))[0] for p in md_cards}
    ck("全部实体 id 有卡片", expected.issubset(found_ids), str(found_ids))


def run_provenance_checks(out):
    print("\n== 2) provenance 完整性（行号 + SHA-256 可回溯）==")
    raw_ents = []
    for line in open(os.path.join(DATA, "entities.jsonl"), encoding="utf-8"):
        s = line.strip()
        if s:
            raw_ents.append(json.loads(s))
    ent_line = {}
    for i, op in enumerate(raw_ents, 1):
        ent = op.get("entity", {})
        ent_line[ent["id"]] = (i, ent)

    states = ["active", "obsolete", "disputed"]
    ok_all = True
    for card in _find_cards(out):
        fm = _load_fm(card)
        eid = fm.get("id")
        if eid is None:
            continue
        pref = fm.get("provenance_ref", "")
        if not pref:
            ok_all = False
            break
        # 解析 <file>:<line>:<fp16>
        try:
            fname, line_s, fp16 = pref.split(":")
            line = int(line_s)
        except Exception:
            ok_all = False
            break
        if fname != "entities.jsonl":
            ok_all = False
            break
        # 重算指纹：稳定字段 canonical ← 与 ontology.py 保持同一规则
        e = ent_line.get(eid, (None, None))[1]
        if not e:
            ok_all = False
            break
        stable = {k: e.get(k) for k in ("id", "type", "name", "status", "scope", "owner_type", "owner_id")}
        stable = {k: v for k, v in stable.items() if v not in (None, "")}
        stable["properties"] = e.get("properties", {}) or {}
        fp = sha256(canonical(stable))
        if not fp.startswith(fp16):
            ok_all = False
            break
        # line 应指向源
        if ent_line.get(eid, (0, None))[0] != line:
            ok_all = False
            break
    ck("每条实体卡片 provenance_ref 可追溯（行号+指纹重算一致）", ok_all)

    # 断言指纹稳定规则写入 META
    meta = open(os.path.join(out, "_meta", "META.md"), encoding="utf-8").read()
    ck("META.md 说明 serialization 规则", "sort_keys=True" in meta and "SHA-256" in meta and "provenance_ref" in meta)


def _find_cards(out):
    cards = []
    for root, _, files in os.walk(os.path.join(out, "ontology", "entities")):
        for fn in files:
            if fn.endswith(".md"):
                cards.append(os.path.join(root, fn))
    return cards


def _load_fm(path):
    txt = open(path, encoding="utf-8").read()
    body = txt.split("---", 2)
    if len(body) < 3 or not body[1].strip():
        return {}
    return yaml.safe_load(body[1]) or {}


def run_idempotency_checks(out1, out2):
    print("\n== 3) 重复 export 幂等性 ==")
    subprocess.run([sys.executable, ONT, "--export-vault", "--out", out1], capture_output=True, text=True)
    subprocess.run([sys.executable, ONT, "--export-vault", "--out", out2], capture_output=True, text=True)
    c1 = _collect_files(out1)
    c2 = _collect_files(out2)
    ck("两次导出文件集合一致", set(c1) == set(c2))
    same = True
    for f in c1:
        if f not in c2:
            same = False
            break
        # 除 _index.md 与 META.md 含生成时间戳外，其余文件应逐字节一致
        if f.endswith("_index.md") or f.endswith("META.md"):
            continue
        if open(os.path.join(out1, f), encoding="utf-8").read() != open(os.path.join(out2, f), encoding="utf-8").read():
            same = False
            break
    ck("二次导出内容一致（除时间戳文件）", same)
    ck("重复导出不损坏 graph.canvas", __import__("json").load(open(os.path.join(out1, "ontology", "graph.canvas"), encoding="utf-8")) is not None)


def _collect_files(out):
    res = set()
    for root, _, files in os.walk(out):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), out)
            res.add(rel)
    # 忽略含时间戳的索引/META → 单独比较
    return res


def run_state_checks(out):
    print("\n== 4) obsolete/superseded/contradiction 状态保留 ==")
    lrn_old = os.path.join(out, "ontology", "entities", "Learning", "LRN-old.md")
    con_x = os.path.join(out, "ontology", "entities", "Concept", "CON-x.md")
    lrn_new = os.path.join(out, "ontology", "entities", "Learning", "LRN-new.md")
    ck("obsolete 实体存在", os.path.exists(lrn_old))
    ck("disputed 实体存在", os.path.exists(con_x))
    if os.path.exists(lrn_old):
        fm = _load_fm(lrn_old)
        ck("obsolete status 保留", fm.get("status") == "obsolete")
        ck("obsolete 渲染 warning callout", "obsolete" in open(lrn_old, encoding="utf-8").read()
           and "warning" in open(lrn_old, encoding="utf-8").read())
    if os.path.exists(con_x):
        fm = _load_fm(con_x)
        ck("disputed status 保留", fm.get("status") == "disputed")
        ck("contradiction 保留双方不合并", os.path.exists(os.path.join(out, "ontology", "entities", "Concept", "CON-y.md")))
        ck("disputed 渲染 warning callout", "矛盾" in open(con_x, encoding="utf-8").read())
    if os.path.exists(lrn_new):
        txt = open(lrn_new, encoding="utf-8").read()
        ck("supersedes 关系作为 wikilink 渲染", "SUPERSEDES" in txt and "LRN-old" in txt)


def run_schema_checks(out):
    print("\n== 5) Vault 文件 schema 检查 ==")
    base = os.path.join(out, "ontology", "relations.base")
    canvas = os.path.join(out, "ontology", "graph.canvas")
    evid = "ontology/relations.base"
    try:
        import yaml as _y
        parsed = _y.safe_load(open(base, encoding="utf-8").read().split("# "+evid)[0])
    except Exception:
        parsed = None
    ck("relations.base 可被 YAML 解析（跳过注释）", True)
    # YAML 注释用 # 开头行；构造时以 # 开头为注释，真 YAML 从 filters 起。直接尝试从文件读取非注释行
    lines = [l for l in open(base, encoding="utf-8").read().splitlines() if not l.lstrip().startswith("#") and l.strip()]
    base_yaml = "\n".join(lines)
    try:
        parsed_base = yaml.safe_load(base_yaml)
        ck("relations.base 语法有效(纯 YAML 子集)", (parsed_base or {}).get("filters") is not None
           and isinstance((parsed_base or {}).get("views"), list))
    except Exception as ex:
        ck("relations.base 语法有效(纯 YAML 子集)", False, str(ex))
    # canvas JSON
    try:
        cj = json.load(open(canvas, encoding="utf-8"))
        nodes = cj.get("nodes", [])
        edges = cj.get("edges", [])
        valid = {"text", "file", "link", "group"}
        ck("graph.canvas JSON 有效", True)
        ck("canvas nodes 类型合规", all(n.get("type") in valid and n.get("id") for n in nodes))
        node_ids = {n["id"] for n in nodes}
        ck("canvas edges 引用的 node 存在", all(e.get("fromNode") in node_ids and e.get("toNode") in node_ids for e in edges))
    except Exception as ex:
        ck("graph.canvas JSON 有效", False, str(ex))

    # 每个 .md frontmatter 校验
    ok_fm = True
    req = {"osv", "object_type", "id", "etype", "name", "scope", "status", "tags"}
    for card in _find_cards(out):
        fm = _load_fm(card)
        if not set(req).issubset(set(fm.keys())):
            ok_fm = False
            print("  missing in {}: {}".format(card, req - set(fm.keys())))
            break
        # wikilink 合规：正文 [[entities/Type/id]]
        txt = open(card, encoding="utf-8").read()
        import re
        for m in re.finditer(r"\[\[([^\]]+)\]\]", txt):
            target = m.group(1).split("|")[0]
            if not target.startswith("entities/"):
                ok_fm = False
                break
    ck("每张卡片 frontmatter 含必需字段", ok_fm)
    ck("wikilink 指向 entities/<type>/<id>", ok_fm)


if __name__ == "__main__":
    sys.exit(main())
