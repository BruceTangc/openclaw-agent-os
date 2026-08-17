#!/usr/bin/env python3
"""
ontology_bridge.py — Ontology × Self-Improvement 桥接层

按集成规范 V1.0 §5/§33，在 Global Learning Cycle 的 Phase 0 (Bus Drain)
之后、Learning Engine 决策之前，对新增 learning entries 做 Ontology 实体
解析与富化（enrichment），把语义上下文写回 trail 的 extra_meta["ontology"]。

职责边界（对齐规范）：
- Ontology 只提供语义上下文，不决定 Learning 是否成立/晋升
- 富化失败不阻断主 cycle（best-effort）
- 只处理本轮新增条目（增量游标），不重扫全部历史

用法：
  python3 scripts/ontology_bridge.py --enrich --limit 20   # 富化最近 entries
  python3 scripts/ontology_bridge.py --status              # 看桥接状态
  python3 scripts/ontology_bridge.py --resolve "<text>"    # 直接调 ontology 解析

规范对齐命令（供 learn.py / 人工调用）：
  python3 scripts/ontology_bridge.py --impact <entity_id>  # 影响分析

> 多 workspace 探测：ONTOLOGY_SCRIPT 不再硬编码单一路径，而是自动探测
> （本 WORKSPACE → ~/.openclaw/workspace-* 按名排序取首命中 → 回退默认），
> 以兼容多 agent/多服务器（如 workspace-jarvis）下 ontology skill 的安装目录。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

WORKSPACE = (
    os.environ.get("OPENCLAW_WORKSPACE")
    or os.environ.get("OPENCLAW_WORKSPACE_DIR")
    or os.path.expanduser("~/.openclaw/workspace")
)
TRAIL_PATH = os.path.join(WORKSPACE, "memory", ".learning-trail.json")


def _probe_ontology_script():
    """自动探测 ontology.py 路径。

    ontology skill 可能装在主 workspace，也可能装在 workspace-*（多 agent
    或多服务器）目录，用硬编码单一路径会在其中一台打 stderr。这里探测：
      1. WORKSPACE 本身
      2. ~/.openclaw/workspace-*（按名称排序，取第一个命中）
    返回实际存在的脚本路径；找不到返回 None（由调用方决定如何降级）。
    """
    import glob
    # 1) WORKSPACE 本身
    if WORKSPACE:
        p = os.path.join(WORKSPACE, "skills", "ontology", "scripts", "ontology.py")
        if os.path.exists(p):
            return p
    # 2) workspace-*（多 agent / 多服务器）目录里探测
    base = os.path.dirname(WORKSPACE) if WORKSPACE else os.path.expanduser("~/.openclaw")
    for ws in sorted(glob.glob(os.path.join(base, "workspace-*"))):
        p = os.path.join(ws, "skills", "ontology", "scripts", "ontology.py")
        if os.path.exists(p):
            return p
    return None


def _resolve_ontology_script():
    """返回 ontology.py 真实路径；探测失败时回退到 WORKSPACE 默认。"""
    found = _probe_ontology_script()
    if found:
        return found
    return os.path.join(WORKSPACE, "skills", "ontology", "scripts", "ontology.py")


ONTOLOGY_SCRIPT = None  # 惰性解析，避免 import 时探测
_ONTOLOGY_CACHE = {"v": None}


def get_ontology_script():
    """带缓存的 ontology.py 路径解析，供 status 等重复调用。"""
    if _ONTOLOGY_CACHE["v"] is None:
        _ONTOLOGY_CACHE["v"] = _resolve_ontology_script()
    return _ONTOLOGY_CACHE["v"]


def ensure_ontology():
    script = get_ontology_script()
    if not os.path.exists(script):
        raise FileNotFoundError("ontology.py 不存在: {0}".format(script))
    return script


def run_ontology(args_list, timeout=30):
    """调用 ontology.py，返回 (ok, stdout)。best-effort，失败不抛异常。"""
    script = ensure_ontology()
    try:
        proc = subprocess.run(
            [sys.executable, script] + args_list,
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode == 0:
            return True, proc.stdout
        return False, proc.stdout + "\n" + proc.stderr
    except Exception as e:
        return False, str(e)


def resolve_text(text, timeout=30):
    """对一段文本做实体解析，返回结构化结果。"""
    ok, out = run_ontology(["--resolve", text], timeout)
    if not ok:
        return {"ok": False, "raw": out}
    # 解析 stdout：匹配实体行 + 相关关系行
    entities = []
    entities_conf = {}
    relations = []
    in_entities = False
    in_relations = False
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("匹配实体"):
            in_entities = True
            in_relations = False
            continue
        if s.startswith("相关关系"):
            in_entities = False
            in_relations = True
            continue
        if s.startswith("无匹配"):
            in_entities = False
            in_relations = False
            continue
        if in_entities and s.startswith("- "):
            # - AGT-xxx [Agent] conf=0.91 (名字)
            m = s[2:]
            id_part = m.split(" ", 1)[0]
            entities.append(id_part)
            # 提取 confidence（若存在）
            conf_m = __import__("re").search(r"conf=([0-9.]+)", m)
            if conf_m:
                entities_conf[id_part] = float(conf_m.group(1))
        elif in_relations and s.startswith("- "):
            # - SKL-xxx -REQUIRES-> TOL-xxx
            m = s[2:]
            relations.append(m)
    return {"ok": True, "entities": entities, "entities_conf": entities_conf,
            "relations": relations, "raw": out}


def load_trail():
    if not os.path.exists(TRAIL_PATH):
        return {"entries": [], "stats": {}}
    try:
        with open(TRAIL_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"entries": [], "stats": {}}


def save_trail(trail):
    with open(TRAIL_PATH, "w", encoding="utf-8") as f:
        json.dump(trail, f, ensure_ascii=False, indent=2)


def cmd_enrich(args):
    """富化最近 N 条尚未 ontology 解析的 entries。"""
    trail = load_trail()
    entries = trail.get("entries", [])
    enriched = 0
    skipped = 0
    # 只处理没有 extra_meta.ontology 的条目（增量）
    candidates = []
    for ent in entries:
        meta = ent.get("extra_meta") or {}
        if not meta.get("ontology"):
            candidates.append(ent)
    # 按时间倒序取最近 limit 条
    candidates = candidates[-args.limit:] if args.limit > 0 else candidates
    print("Ontology Bridge Enrichment:")
    print("  待富化候选: {0} (limit={1})".format(len(candidates), args.limit))
    for ent in candidates:
        content = ent.get("details") or ent.get("summary") or ent.get("content") or ""
        if not content:
            skipped += 1
            continue
        result = resolve_text(content[:500])
        meta = ent.setdefault("extra_meta", {})
        if result.get("ok"):
            meta["ontology"] = {
                "entities": result.get("entities", []),
                "relations": result.get("relations", []),
                "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            enriched += 1
            if result.get("entities"):
                print("  ✓ [{0}] → {1}".format(ent.get("id", "?"), ", ".join(result["entities"][:5])))
            else:
                print("  ○ [{0}] → 无实体匹配 (unresolved)".format(ent.get("id", "?")))
        else:
            meta["ontology"] = {"error": result.get("raw", "?")[:200]}
            skipped += 1
            print("  ✗ [{0}] resolve 失败".format(ent.get("id", "?")))
    save_trail(trail)
    print("完成: {0} enriched, {1} skipped".format(enriched, skipped))
    return 0


def cmd_status(args):
    trail = load_trail()
    entries = trail.get("entries", [])
    done = 0
    for ent in entries:
        meta = ent.get("extra_meta") or {}
        if meta.get("ontology"):
            done += 1
    print("Ontology Bridge Status:")
    print("  entries: {0}".format(len(entries)))
    print("  enriched with ontology: {0}".format(done))
    print("  ontology script: {0}".format(get_ontology_script()))
    print("  available: {0}".format(os.path.exists(get_ontology_script())))
    return 0


def cmd_resolve(args):
    if not args.text:
        print("--resolve 需要文本")
        return 1
    ok, out = run_ontology(["--resolve", args.text])
    print(out)
    return 0 if ok else 1


def cmd_sync_agent(args):
    """--sync-agent <id> [--role R] [--deprecate]：Agent 生命周期同步到 ontology。

    创建/退休 Agent 时，把运行身份同步到 ontology 实体（规范 §22/§23）。
    已存在的跳过，不重复创建；--deprecate 走 proposal 治理，不直接改。
    """
    agent_id = args.agent_id
    if not agent_id:
        print("--sync-agent 需要 agent_id")
        return 1
    eid = "AGT-" + agent_id
    # 是否已存在
    ok, out = run_ontology(["--entity", eid])
    exists = ok and eid in out
    if args.deprecate:
        if exists:
            # 退休：走 proposal（cascade_status），不静默改（规范 §30/§45）
            reason = "Agent 生命周期: {0} 退休".format(agent_id)
            run_ontology(["--propose", "--change_type", "deprecate",
                          "--subject", eid, "--reason", reason, "--evidence", "agents.py --sync-ontology"])
            print("  已提交退休提案: {0}（需 verify 后生效）".format(eid))
        else:
            print("  实体不存在，无需退休: {0}".format(eid))
        return 0
    # 正常同步：缺失则创建
    if exists:
        print("  ✓ 已在 ontology 中: {0}".format(eid))
        return 0
    props = {"scope": "PROJECT"}
    if args.role:
        props["role"] = args.role
    ok2, out2 = run_ontology(["--create-entity", "--type", "Agent",
                              "--name", agent_id, "--id", eid,
                              "--props", json.dumps(props, ensure_ascii=False)])
    if ok2:
        print("  ✓ 已同步 Agent 到 ontology: {0}".format(eid))
        return 0
    print("  ✗ 创建失败: {0}".format(out2.strip()))
    return 1


def cmd_sync_skill(args):
    """--sync-skill <name> [--id SKL-xxx] [--agent AGT-xxx]：Skill 回写 ontology。

    Skill Evolution 后把新 skill 注册进 ontology（规范 §21/§26）。
    可选 --agent 同时建立 Agent USES Skill 关系。
    """
    name = args.skill_name
    if not name:
        print("--sync-skill 需要 skill name")
        return 1
    eid = args.skill_id or ("SKL-" + name)
    ok, out = run_ontology(["--entity", eid])
    exists = ok and eid in out
    if not exists:
        ok2, out2 = run_ontology(["--create-entity", "--type", "Skill",
                                  "--name", name, "--id", eid,
                                  "--props", '{"scope":"GLOBAL"}'])
        if ok2:
            print("  ✓ 已注册 Skill 到 ontology: {0}".format(eid))
        else:
            print("  ✗ 创建失败: {0}".format(out2.strip()))
            return 1
    else:
        print("  ✓ Skill 已存在: {0}".format(eid))
    if args.agent_id:
        run_ontology(["--relate", "--from", args.agent_id, "--pred", "USES", "--to", eid])
        print("  已关联 {0} USES {1}".format(args.agent_id, eid))
    return 0


def cmd_tool_change(args):
    """--tool-change <tool_id>：工具变更传播分析（规范 §24/§49）。

    对 Tool 做影响分析，列出受影响的 Skill/Agent/Project，
    输出重验证建议。返回受影响实体供上层通知。
    """
    tool_id = args.tool_id
    if not tool_id:
        print("--tool-change 需要 tool_id")
        return 1
    ok, out = run_ontology(["--impact", tool_id, "--depth", "3"])
    if not ok:
        print("✗ 影响分析失败: {0}".format(out))
        return 1
    print("🔧 Tool 变更传播分析: {0}".format(tool_id))
    print(out)
    # 解析受影响实体
    affected = []
    for line in out.splitlines():
        s = line.strip()
        # 影响分析输出形如:  SKL-xxx USES in (名字)  或  AGT-xxx REQUIRES out (名字)
        # 特征：中间含 ' in ' 或 ' out '，第一 token 是实体 id
        if (" in " in s or " out " in s) and "->" not in s and "depth" not in s:
            id_part = s.split(" ")[0]
            if id_part and id_part not in (tool_id,):
                affected.append(id_part)
    skills = [a for a in affected if a.startswith("SKL-")]
    agents = [a for a in affected if a.startswith("AGT-")]
    projects = [a for a in affected if a.startswith("PRJ-")]
    print("受影响: {0} Skills, {1} Agents, {2} Projects".format(len(skills), len(agents), len(projects)))
    if skills:
        print("  Skills: {0}".format(", ".join(skills)))
    if agents:
        print("  Agents: {0}".format(", ".join(agents)))
    if projects:
        print("  Projects: {0}".format(", ".join(projects)))
    if affected:
        print("建议: 相关 Agent 应重新验证上述 Skill（规范 §24）")
    return 0


def cmd_impact(args):
    if not args.entity_id:
        print("--impact 需要 entity_id")
        return 1
    ok, out = run_ontology(["--impact", args.entity_id, "--depth", str(args.depth or 3)])
    print(out)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="Ontology × Self-Improvement 桥接层")
    parser.add_argument("--enrich", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--text", metavar="TEXT")
    parser.add_argument("--impact", action="store_true")
    parser.add_argument("--entity_id", metavar="ID")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--sync-agent", action="store_true")
    parser.add_argument("--agent_id", metavar="ID")
    parser.add_argument("--role", metavar="ROLE")
    parser.add_argument("--deprecate", action="store_true")
    parser.add_argument("--sync-skill", action="store_true")
    parser.add_argument("--skill_name", metavar="NAME")
    parser.add_argument("--skill_id", metavar="ID")
    parser.add_argument("--tool-change", action="store_true")
    parser.add_argument("--tool_id", metavar="ID")

    args = parser.parse_args()

    if args.enrich:
        return cmd_enrich(args)
    if args.status:
        return cmd_status(args)
    if args.resolve:
        return cmd_resolve(args)

    if args.sync_agent:
        return cmd_sync_agent(args)
    if args.sync_skill:
        return cmd_sync_skill(args)
    if args.tool_change:
        return cmd_tool_change(args)
    if args.impact:
        return cmd_impact(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
