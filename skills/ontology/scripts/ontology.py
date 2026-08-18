#!/usr/bin/env python3
"""Ontology Skill — 语义知识层 for OpenClaw.

Append-only JSONL 存储 + schema 校验 + 影响分析(深度/环守卫) + 提案治理。

命令：
  --status                    状态/统计
  --entity <id>               查实体
  --search "<query>"          搜索(名称/别名/描述/标签)
  --relations <id>            查实体的关系
  --impact <id> [--depth N]   影响分析(BFS, 带环守卫)
  --create-entity --type T --name N [--id ID] [--props '{...}']
  --relate --from A --pred P --to B [--props '{...}']
  --validate                  全量校验
  --orphans                   孤立实体
  --duplicates                重复候选
  --contradictions            矛盾关系
  --propose --change_type X --subject S [--object O] [--pred P] [--reason R] [--evidence E]
  --proposals                 列出提案
  --verify <proposal_id>      批准并应用提案
  --rollback <change_id>      回滚一个变更
  --rebuild-index             重建别名索引
  --reload-alias-cache        重载别名缓存
  --export-md [--project X]   导出 markdown 概览
"""

import argparse
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "memory", "ontology")

# v1.3 Hardening B2: 统一 ID helper
_LIB = os.path.join(os.path.dirname(BASE), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id
from persistence import atomic_write_json

SCHEMA_FILE = os.path.join(DATA, "schema.json")
ENTITIES_FILE = os.path.join(DATA, "entities.jsonl")
RELATIONS_FILE = os.path.join(DATA, "relations.jsonl")
PROPOSALS_FILE = os.path.join(DATA, "proposals.jsonl")
CHANGELOG_FILE = os.path.join(DATA, "changelog.jsonl")
STATE_FILE = os.path.join(DATA, "state.json")

PREDICATES = [
    "IS_A", "INSTANCE_OF", "PART_OF", "BELONGS_TO", "OWNS", "USES",
    "DEPENDS_ON", "PROVIDES", "REQUIRES", "IMPLEMENTS", "DERIVED_FROM",
    "SUPPORTS", "CONTRADICTS", "SUPERSEDES", "VERIFIED_BY", "CREATED_BY",
    "USED_BY", "APPLIES_TO", "SCOPED_TO", "MEMBER_OF", "WORKS_ON",
    "LEARNED_FROM", "CAUSED_BY", "IMPROVES", "REPLACES", "RELATED_TO",
    "IS_EXCEPTION_TO", "HAS_AGENT", "HAS_DECISION", "HAS_LEARNING",
    "HAS_TASK", "HAS_SKILL", "HAS_TOOL", "ABOUT", "DISCOVERED_BY",
]


# 高频通用中文 2-gram，参与 bigram 匹配会制造大量噪声（V4 Pro 审查发现）。
# 这些词过于通用，无法区分实体，匹配时一律剔除。
STOP_BIGRAMS = {
    "系统", "数据", "核算", "分析", "管理", "操作", "功能", "信息",
    "相关", "内容", "方法", "使用", "开发", "测试", "项目", "产品",
    "用户", "服务", "支持", "处理", "生成", "存在", "方案", "改进",
    "同步", "延迟", "联合", "提出", "之间", "发现", "需要", "进行",
    "可以", "应该", "必须", "以及", "通过", "关于", "对于", "因为",
    "所以", "但是", "如果", "虽然", "同时", "此外", "主要", "重要",
    "当前", "现在", "问题", "情况", "时候", "方面", "部分", "方式",
    "过程", "结果", "影响", "作用", "意义", "目的", "目标", "要求",
    "标准", "规定", "政策", "制度", "体系", "结构", "类型", "种类",
    "数量", "质量", "程度", "水平", "范围", "领域", "方向", "趋势",
    "状况", "状态", "条件", "环境", "因素", "原因", "效果", "效率",
    "成本", "收益", "风险", "机会", "挑战", "优势", "劣势", "特点",
    "特征", "属性", "参数", "指标", "我们", "你们", "他们", "认为",
    "表示", "说明", "指出", "强调", "建议", "希望", "计划", "开始",
    "结束", "完成", "实现", "达到", "超过", "低于", "高于", "增加",
    "减少", "提高", "降低", "改善", "优化", "加强", "促进", "推动",
    "负责", "参与", "配合", "协调", "组织", "安排", "部署", "执行",
    "实施", "落实", "跟进", "跟踪", "监控", "监督", "检查", "审核",
    "评估", "评价", "考核", "反馈", "总结", "记录", "保存", "提交",
    "上报", "审批", "批准", "同意", "拒绝", "接受", "采纳", "采用",
    "应用", "利用", "借助", "依靠", "凭借", "基于", "依据", "根据",
    "按照", "遵循", "遵守", "符合", "满足", "突破", "创新", "研发",
    "设计", "规划", "策略", "战略", "机制", "体制", "架构", "框架",
    "平台", "工具", "设备", "装置", "仪器", "材料", "资源", "资金",
    "资产", "费用", "支出", "收入", "利润", "回报", "投资", "融资",
    "贷款", "债务", "股权", "市值", "营收", "净利", "毛利", "增长",
    "下降", "波动", "震荡", "反弹", "回调", "突破", "支撑", "压力",
    "阻力", "报错", "失败", "错误", "成功", "正常", "异常", "修复",
    "排查", "定位", "解决", "覆盖", "丢失", "污染", "兼容", "稳定",
    "可靠", "准确", "及时", "最新", "权威", "官方", "真实", "完整",
}

SCOPES = ["TASK", "AGENT", "PROJECT", "USER", "GLOBAL"]
DEFAULT_DEPTH = 3
MAX_DEPTH = 6
MAX_RETURN = 20

FORBIDDEN_KEYS = ["password", "secret", "token", "api_key", "apikey", "credential", "private_key"]

DEFAULT_SCHEMA = {
    "types": {
        "Agent": {"required": ["name"]},
        "Project": {"required": ["name"]},
        "Skill": {"required": ["name"]},
        "Tool": {"required": ["name"]},
        "Learning": {"required": ["content"]},
        "Decision": {"required": ["title"]},
        "Concept": {"required": ["name"]},
        "Task": {"required": ["title"]},
        "User": {"required": ["name"]},
        "Memory": {"required": ["content"]},
        "Document": {"required": ["title"]},
        "Event": {"required": ["title"]},
        "Resource": {"required": ["name"]},
        "Workflow": {"required": ["name"]},
        "Rule": {"required": ["content"]},
        "Constraint": {"required": ["content"]},
        "Metric": {"required": ["name"]},
        "Evidence": {"required": ["content"]},
        "Proposal": {"required": ["content"]},
        "Issue": {"required": ["title"]},
    },
    "relation_types": {
        "WORKS_ON": {"from": ["Agent"], "to": ["Project"]},
        "USES": {"from": ["Agent", "Project", "Skill"], "to": ["Skill", "Tool"]},
        "REQUIRES": {"from": ["Skill", "Project"], "to": ["Tool", "Skill"]},
        "ABOUT": {"from": ["Learning", "Decision", "Memory"], "to": ["Concept", "Tool", "Skill", "Project"]},
        "SUPPORTS": {"from": ["Learning", "Evidence"], "to": ["Skill", "Learning", "Decision", "Rule"]},
        "APPLIES_TO": {"from": ["Learning", "Rule", "Skill"], "to": ["Project", "Tool"]},
        "SUPERSEDES": {"from": ["Decision", "Learning", "Rule"], "to": ["Decision", "Learning", "Rule"]},
        "CONTRADICTS": {"from": ["Learning", "Rule", "Decision"], "to": ["Learning", "Rule", "Decision"]},
        "DEPENDS_ON": {"from": ["Skill", "Project", "Tool"], "to": ["Tool", "Skill"]},
        "LEARNED_FROM": {"from": ["Learning"], "to": ["Agent", "Event", "Document"]},
        "DISCOVERED_BY": {"from": ["Learning"], "to": ["Agent"]},
        "VERIFIED_BY": {"from": ["Learning", "Skill", "Rule"], "to": ["Evidence", "Event"]},
        "CREATED_BY": {"from": [], "to": ["Agent"]},
        "USED_BY": {"from": ["Skill", "Tool"], "to": ["Agent", "Project"]},
        "BELONGS_TO": {"from": [], "to": []},
        "PART_OF": {"from": [], "to": []},
        "HAS_AGENT": {"from": ["Project"], "to": ["Agent"]},
        "HAS_DECISION": {"from": ["Project"], "to": ["Decision"]},
        "HAS_LEARNING": {"from": ["Project"], "to": ["Learning"]},
        "HAS_TASK": {"from": ["Project"], "to": ["Task"]},
        "HAS_SKILL": {"from": ["Project", "Agent"], "to": ["Skill"]},
        "HAS_TOOL": {"from": ["Project", "Agent"], "to": ["Tool"]},
        "MEMBER_OF": {"from": ["Agent"], "to": ["Project"]},
        "RELATED_TO": {"from": [], "to": []},
        "IMPROVES": {"from": ["Skill", "Learning"], "to": ["Skill", "Workflow"]},
        "CAUSED_BY": {"from": [], "to": []},
        "DERIVED_FROM": {"from": [], "to": []},
        "REPLACES": {"from": [], "to": []},
        "IS_EXCEPTION_TO": {"from": [], "to": []},
        "IS_A": {"from": [], "to": []},
        "INSTANCE_OF": {"from": [], "to": []},
        "OWNS": {"from": [], "to": []},
        "PROVIDES": {"from": [], "to": []},
        "IMPLEMENTS": {"from": [], "to": []},
        "SCOPED_TO": {"from": [], "to": []},
    },
}


def ensure_dirs():
    os.makedirs(DATA, exist_ok=True)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def read_schema():
    if os.path.exists(SCHEMA_FILE):
        with open(SCHEMA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_SCHEMA))


def write_schema(schema):
    ensure_dirs()
    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)


def read_log(path):
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return lines


def append_log(path, obj):
    ensure_dirs()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + chr(10))


def append_changelog(change):
    append_log(CHANGELOG_FILE, change)


def read_entities():
    """重放 entities.jsonl → {id: entity}
    [#18/append-only]: rollback_entity 事件标记删除，历史永远保留。
    """
    entities = {}
    for op in read_log(ENTITIES_FILE):
        if op.get("op") == "create":
            e = op["entity"]
            entities[e["id"]] = e
        elif op.get("op") == "update" and op.get("id") in entities:
            entities[op["id"]].update(op.get("changes", {}))
            entities[op["id"]]["updated_at"] = op.get("at", now_iso())
        elif op.get("op") in ("delete", "rollback_entity") and op.get("id") in entities:
            # 追加式删除: 不物理删除 create 记录，仅从当前状态移除
            entities[op["id"]]["status"] = "deleted"
            entities[op["id"]]["deleted_at"] = op.get("at", now_iso())
    return {k: v for k, v in entities.items() if v.get("status") != "deleted"}


def read_relations():
    """重放 relations.jsonl → active relations 列表"""
    relations = []
    for op in read_log(RELATIONS_FILE):
        if op.get("op") == "relate":
            r = op["relation"]
            r.setdefault("status", "active")
            r["_line"] = op.get("_line")
            relations.append(r)
        elif op.get("op") == "expire":
            rid = op.get("relation_id")
            for r in relations:
                if r.get("id") == rid and r.get("status") == "active":
                    r["status"] = "expired"
                    r["valid_until"] = op.get("at", now_iso())
        elif op.get("op") in ("remove", "rollback_relation") and op.get("relation_id"):
            # [#18/append-only]: 追加式删除关系，不物理删除 relate 记录
            rid = op.get("relation_id")
            for r in relations:
                if r.get("id") == rid and r.get("status") == "active":
                    r["status"] = "expired"
                    r["valid_until"] = op.get("at", now_iso())
    return [r for r in relations if r.get("status") == "active"]


def read_proposals():
    return read_log(PROPOSALS_FILE)


def gen_id(etype, prefix_map=None):
    mapping = {
        "User": "USR", "Agent": "AGT", "Project": "PRJ", "Skill": "SKL",
        "Task": "TSK", "Learning": "LRN", "Decision": "DEC", "Tool": "TOL",
        "Resource": "RES", "Document": "DOC", "Event": "EVT", "Concept": "CON",
        "Rule": "RUL", "Metric": "MET", "Evidence": "EVD", "Proposal": "ONT",
        "Issue": "ISS", "Memory": "MEM", "Workflow": "WF", "Constraint": "CST",
    }
    prefix = mapping.get(etype, "ENT")
    # v1.3: UUID 取代 int(time.time()*1000) 碰撞, 保留大写前缀格式 (USR-<hex>)
    return "{0}-{1}".format(prefix, generate_id("id").split("_", 1)[1])


def check_forbidden(props):
    bad = []
    for k in props:
        kl = k.lower()
        for fk in FORBIDDEN_KEYS:
            if fk in kl:
                bad.append(k)
                break
    if bad:
        raise ValueError("禁止存储敏感字段: {0}".format(", ".join(bad)))


def validate_entity(schema, etype, name, props):
    types = schema.get("types", {})
    if etype not in types:
        raise ValueError("未知实体类型: {0} (可用: {1})".format(etype, ", ".join(sorted(types))))
    required = types[etype].get("required", [])
    entity_props = {"name": name} if name else {}
    entity_props.update(props or {})
    for req in required:
        if not entity_props.get(req):
            raise ValueError("类型 {0} 缺少必填字段: {1}".format(etype, req))
    check_forbidden(entity_props)
    scope = entity_props.get("scope")
    if scope and scope not in SCOPES:
        raise ValueError("非法 scope: {0} (可用: {1})".format(scope, ", ".join(SCOPES)))
    return entity_props


def validate_relation(schema, from_id, pred, to_id, entities, props=None):
    if pred not in PREDICATES:
        raise ValueError("非法关系词: {0} (可用见 PREDICATES)".format(pred))
    if from_id not in entities:
        raise ValueError("from 实体不存在: {0}".format(from_id))
    if to_id not in entities:
        raise ValueError("to 实体不存在: {0}".format(to_id))
    rt = schema.get("relation_types", {}).get(pred, {})
    if rt:
        ftypes = rt.get("from", [])
        ttypes = rt.get("to", [])
        if ftypes and entities[from_id]["type"] not in ftypes:
            raise ValueError("关系 {0} 的 from 类型 {1} 不在允许范围 {2}".format(pred, entities[from_id]["type"], ftypes))
        if ttypes and entities[to_id]["type"] not in ttypes:
            raise ValueError("关系 {0} 的 to 类型 {1} 不在允许范围 {2}".format(pred, entities[to_id]["type"], ttypes))
    check_forbidden(props or {})
    return True


def load_alias_cache(entities):
    """name → id 别名映射 (含 properties.aliases)"""
    cache = {}
    for eid, e in entities.items():
        cache[e.get("name", "").lower()] = eid
        cache[eid.lower()] = eid
        for a in (e.get("properties", {}).get("aliases", []) or []):
            cache[str(a).lower()] = eid
    return cache


def build_state(entities, relations, proposals):
    state = {
        "entities": len(entities),
        "relations": len(relations),
        "proposals": len(proposals),
        "alias_cache_size": 0,
        "built_at": now_iso(),
    }
    cache = load_alias_cache(entities)
    state["alias_cache_size"] = len(cache)
    return state


def write_state(state):
    ensure_dirs()
    atomic_write_json(STATE_FILE, state)


def cmd_status(args):
    # [#24/修复]: --status 默认只读，不做任何写盘副作用。
    #   状态计算是纯函数；持久化(写 state.json)只属于 --rebuild-index。
    entities = read_entities()
    relations = read_relations()
    proposals = read_proposals()
    state = build_state(entities, relations, proposals)
    print("Ontology Status:")
    print("  Entities:  {0}".format(state["entities"]))
    print("  Relations: {0}".format(state["relations"]))
    print("  Proposals: {0}".format(state["proposals"]))
    print("  Alias cache: {0} entries".format(state["alias_cache_size"]))
    types = {}
    for e in entities.values():
        types[e["type"]] = types.get(e["type"], 0) + 1
    if types:
        print("  By type:   {0}".format(", ".join("{0}={1}".format(k, v) for k, v in sorted(types.items()))))


def cmd_entity(args):
    entities = read_entities()
    e = entities.get(args.entity)
    if not e:
        print("实体不存在: {0}".format(args.entity))
        return 1
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


def cmd_search(args):
    entities = read_entities()
    q = args.search.lower()
    hits = []
    for eid, e in entities.items():
        blob = " ".join(str(v) for v in [
            e.get("name", ""), e.get("description", ""),
            json.dumps(e.get("properties", {}), ensure_ascii=False),
            json.dumps(e.get("tags", [])),
        ]).lower()
        if q in blob or q in eid.lower():
            hits.append(e)
    print("命中 {0} 条:".format(len(hits)))
    for e in hits[:MAX_RETURN]:
        print("  [{0}] {1} ({2})".format(e["id"], e.get("name", "?"), e["type"]))
    return 0


def cmd_create_entity(args):
    schema = read_schema()
    props = json.loads(args.props) if args.props else {}
    entity_props = validate_entity(schema, args.type, args.name, props)
    entities = read_entities()
    if args.id:
        if args.id in entities:
            print("实体已存在: {0}".format(args.id))
            return 1
        eid = args.id
    else:
        eid = gen_id(args.type)
    entity = {
        "id": eid,
        "type": args.type,
        "name": args.name or entity_props.get("title") or entity_props.get("content", "")[:40],
        "properties": entity_props,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": entity_props.get("status", "active"),
        "scope": entity_props.get("scope", "AGENT"),
    }
    append_log(ENTITIES_FILE, {"op": "create", "entity": entity})
    change = {
        "change_id": "CHG-" + generate_id("id").split("_", 1)[1],
        "action": "create_entity",
        "entity_id": eid,
        "at": now_iso(),
    }
    append_changelog(change)
    print("已创建实体: {0} [{1}]".format(eid, args.type))
    print("change_id: {0}".format(change["change_id"]))
    return 0


def cmd_relate(args):
    schema = read_schema()
    entities = read_entities()
    props = json.loads(args.props) if args.props else {}
    validate_relation(schema, args.from_id, args.pred, args.to, entities, props)
    # 重复关系检查：同 from+pred+to 且 active 的已存在则拒绝（防 verify 建重复）
    existing = read_relations()
    for r in existing:
        if (r["from_id"] == args.from_id and r["predicate"] == args.pred
                and r["to_id"] == args.to):
            print("⚠ 重复关系已存在: {0} -{1}-> {2} (relation_id: {3})".format(
                args.from_id, args.pred, args.to, r["id"]))
            return 2
    rid = "REL-" + generate_id("relation").split("_", 1)[1]
    relation = {
        "id": rid,
        "from_id": args.from_id,
        "predicate": args.pred,
        "to_id": args.to,
        "properties": props or {},
        "status": "active",
        "created_at": now_iso(),
    }
    append_log(RELATIONS_FILE, {"op": "relate", "relation": relation})
    change = {
        "change_id": "CHG-" + generate_id("id").split("_", 1)[1],
        "action": "add_relation",
        "relation_id": rid,
        "at": now_iso(),
    }
    append_changelog(change)
    print("已建立关系: {0} -{1}-> {2}".format(args.from_id, args.pred, args.to))
    print("relation_id: {0}  change_id: {1}".format(rid, change["change_id"]))
    return 0


def cmd_relations(args):
    relations = read_relations()
    out = []
    for r in relations:
        if r["from_id"] == args.relations or r["to_id"] == args.relations:
            out.append(r)
    if not out:
        print("无关系")
        return 0
    for r in out:
        arrow = "->" if r["from_id"] == args.relations else "<-"
        print("  {0} {1} {2} [{3}]".format(r["from_id"], arrow, r["to_id"], r["predicate"]))
    return 0


def cmd_impact(args):
    entities = read_entities()
    relations = read_relations()
    if args.impact not in entities:
        print("实体不存在: {0}".format(args.impact))
        return 1
    depth = args.depth or DEFAULT_DEPTH
    if depth > MAX_DEPTH:
        depth = MAX_DEPTH
    # 构建邻接表 (含入/出)
    adj = {}
    for r in relations:
        adj.setdefault(r["from_id"], []).append((r["to_id"], r["predicate"], "out"))
        adj.setdefault(r["to_id"], []).append((r["from_id"], r["predicate"], "in"))
    visited = set([args.impact])
    queue = [(args.impact, 0)]
    levels = {}
    while queue:
        node, d = queue.pop(0)
        if d >= depth:
            continue
        for nbr, pred, direction in adj.get(node, []):
            if nbr in visited:
                continue  # 环守卫
            visited.add(nbr)
            levels.setdefault(d + 1, []).append((nbr, pred, direction))
            queue.append((nbr, d + 1))
    print("影响分析: {0} (depth<= {1}, 共 {2} 个关联实体)".format(args.impact, depth, len(visited) - 1))
    for d in sorted(levels):
        print("  depth {0}:".format(d))
        for nid, pred, direction in levels[d][:MAX_RETURN]:
            name = entities.get(nid, {}).get("name", "?")
            print("    {0} {1} {2} ({3})".format(nid, pred, direction, name))
    return 0


def cmd_validate(args):
    schema = read_schema()
    entities = read_entities()
    relations = read_relations()
    errors = []
    # 实体引用完整性
    for r in relations:
        if r["from_id"] not in entities:
            errors.append("关系 {0} from 引用缺失: {1}".format(r["id"], r["from_id"]))
        if r["to_id"] not in entities:
            errors.append("关系 {0} to 引用缺失: {1}".format(r["id"], r["to_id"]))
    # 关系类型约束
    for r in relations:
        try:
            validate_relation(schema, r["from_id"], r["predicate"], r["to_id"], entities)
        except ValueError as e:
            errors.append("关系 {0}: {1}".format(r["id"], e))
    if errors:
        print("校验发现 {0} 个问题:".format(len(errors)))
        for e in errors[:40]:
            print("  ✗ {0}".format(e))
        return 1
    print("✓ 校验通过: {0} 实体, {1} 关系, 无违规".format(len(entities), len(relations)))
    return 0


def cmd_orphans(args):
    entities = read_entities()
    relations = read_relations()
    referenced = set()
    for r in relations:
        referenced.add(r["from_id"])
        referenced.add(r["to_id"])
    orphans = [eid for eid in entities if eid not in referenced]
    if not orphans:
        print("无孤立实体")
        return 0
    print("孤立候选 ({0}):".format(len(orphans)))
    for eid in orphans:
        print("  {0} [{1}] {2}".format(eid, entities[eid]["type"], entities[eid].get("name", "?")))
    print("(标记为 orphan_candidate, 不自动删除)")
    return 0


def cmd_duplicates(args):
    entities = read_entities()
    by_name = {}
    for eid, e in entities.items():
        key = e.get("name", "").strip().lower()
        if key:
            by_name.setdefault(key, []).append(eid)
    dups = {k: v for k, v in by_name.items() if len(v) > 1}
    if not dups:
        print("未发现同名重复候选")
        return 0
    print("重复候选:")
    for name, ids in dups.items():
        print("  '{0}': {1}".format(name, ", ".join(ids)))
    print("(标记为 merge_candidate, 不自动合并)")
    return 0


def cmd_contradictions(args):
    relations = read_relations()
    entities = read_entities()
    # 简单检测：CONTRADICTS 关系对，同 scope 且都 active
    found = []
    for r in relations:
        if r["predicate"] == "CONTRADICTS":
            f = entities.get(r["from_id"], {})
            t = entities.get(r["to_id"], {})
            found.append((r["from_id"], r["to_id"], f.get("scope"), t.get("scope")))
    if not found:
        print("未发现 active CONTRADICTS 关系")
        return 0
    print("矛盾关系 ({0}):".format(len(found)))
    for a, b, sa, sb in found:
        print("  {0} CONTRADICTS {1}  (scope: {2} vs {3})".format(a, b, sa, sb))
    print("(按 scope/上下文/时间/证据/置信度处理, 不强制统一)")
    return 0


def cmd_propose(args):
    if not args.change_type:
        print("--change_type 必填")
        return 1
    pid = "ONT-PROP-" + generate_id("proposal").split("_", 1)[1]
    proposal = {
        "id": pid,
        "type": "ontology_proposal",
        "change_type": args.change_type,
        "subject": args.subject,
        "object": args.object,
        "predicate": args.pred,
        "reason": args.reason,
        "evidence": args.evidence,
        "evidence_schema": normalize_evidence(args.evidence),
        "status": "pending",
        "created_at": now_iso(),
    }
    append_log(PROPOSALS_FILE, proposal)
    print("已提交提案: {0} ({1})".format(pid, args.change_type))
    print("  subject: {0}".format(args.subject))
    return 0


def cmd_proposals(args):
    proposals = read_proposals()
    if not proposals:
        print("无提案")
        return 0
    for p in proposals:
        print("  [{0}] {1} | {2} | subject={3} | status={4}".format(
            p["id"], p["change_type"], p.get("created_at", "?"), p.get("subject", "?"), p["status"]))
    return 0


def cmd_verify(args):
    proposals = read_proposals()
    target = None
    for p in proposals:
        if p["id"] == args.verify and p["status"] == "pending":
            target = p
            break
    if not target:
        print("未找到待验证提案: {0}".format(args.verify))
        return 1
    # 应用提案（MVP 支持 create_entity / add_relation / deprecate）
    # [<=#21]: 子操作全部成功才标记 applied；任一失败则 status=FAILED，不全成功
    ct = target["change_type"]
    applied_ok = True
    fail_reason = None
    if ct in ("create_entity", "add_entity"):
        subj = target["subject"]
        parts = subj.split(":", 1)
        etype = parts[0] if len(parts) == 2 else "Concept"
        name = parts[1] if len(parts) == 2 else subj
        try:
            rc = cmd_create_entity(argparse.Namespace(type=etype, name=name, id=None, props=target.get("evidence", "")))
            if rc != 0:
                applied_ok = False; fail_reason = "create_entity 失败 rc=%s" % rc
        except Exception as e:
            applied_ok = False; fail_reason = "create_entity 异常: %s" % e
        if applied_ok:
            target["status"] = "applied"
    elif ct in ("add_relation", "relate"):
        if not target.get("object") or not target.get("predicate"):
            print("提案缺少 object/predicate，无法应用")
            return 1
        # 找到/创建 subject 实体
        subject_id = target["subject"] if target["subject"].startswith(("AGT", "PRJ", "SKL", "TOL", "LRN", "CON", "DEC", "USR")) else "CON-" + target["subject"]
        try:
            rc = cmd_relate(argparse.Namespace(from_id=subject_id, pred=target["predicate"], to=target["object"], props=None))
            if rc != 0:
                applied_ok = False; fail_reason = "add_relation 失败 rc=%s" % rc
        except Exception as e:
            applied_ok = False; fail_reason = "add_relation 异常: %s" % e
        if applied_ok:
            target["status"] = "applied"
    elif ct in ("deprecate", "merge", "split"):
        # MVP: 仅标记实体 deprecated
        target["status"] = "applied"
        print("提案 {0} 已标记 applied（{1} 为高级操作，需人工介入）".format(target["id"], ct))
    else:
        target["status"] = "applied"
        print("提案 {0} 已 applied（change_type={1} 由人工处理）".format(target["id"], ct))
    if not applied_ok:
        target["status"] = "FAILED"
        if fail_reason:
            target.setdefault("context", {})
            target["context"]["apply_error"] = fail_reason
        print("提案 {0} 应用失败 → {1}（不全成功不标 applied）: {2}".format(target["id"], target["status"], fail_reason))
    # 重写 proposals 文件（更新状态）[#23: 原子化写入，防并发损坏]
    ensure_dirs()
    lines = []
    for p in read_log(PROPOSALS_FILE):
        if p["id"] == target["id"]:
            p = target
        lines.append(p)
    atomic_write_jsonlines(PROPOSALS_FILE, lines)
    print("提案已标记: {0} → {1}".format(target["id"], target["status"]))
    return 0




def normalize_evidence(raw):
    """[#22] Evidence 支持 string / object / list，归一化为统一 schema。
    保留事实(distinct from summary)，不把"可能A"当"A"。
    返回: {"values": [...], "source": str, "confidence": float} 兼容存储原样。
    实际使用方决定取哪个字段；此处只保证 string/object/list 都能安全处理。
    """
    if raw is None:
        return {"values": [], "raw": raw}
    if isinstance(raw, str):
        return {"values": [raw], "raw": raw}
    if isinstance(raw, list):
        # 列表元素可能是 str / dict
        vals = []
        for it in raw:
            if isinstance(it, dict):
                vals.append(it.get("content") or it.get("evidence") or it.get("text") or it)
            else:
                vals.append(it)
        return {"values": vals, "raw": raw}
    if isinstance(raw, dict):
        vals = raw.get("values") or raw.get("evidence")
        if not isinstance(vals, list):
            vals = [vals] if vals else []
        return {"values": vals, "raw": raw}
    return {"values": [raw], "raw": raw}

def atomic_write_jsonlines(path, objs):
    """[#23] 原子化写 jsonl：写临时文件→fsync→os.replace。"""
    import tempfile, os as _os
    ensure_dirs()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(o, ensure_ascii=False) for o in objs))
            if objs:
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise

def cmd_rollback(args):
    changes = read_log(CHANGELOG_FILE)
    target = None
    for c in changes:
        if c.get("change_id") == args.rollback:
            target = c
            break
    if not target:
        print("未找到变更: {0}".format(args.rollback))
        return 1
    # #19/修复: 若已被回滚过，拒绝重复回滚（只撤销指定 change 一次）。
    # 必须在任何写盘之前检查并返回，否则重复回滚仍会追加事件。
    already_rolled = any(
        (op.get("op") == "rollback" or op.get("action") == "rollback")
        and op.get("target_change_id") == args.rollback
        for op in read_log(CHANGELOG_FILE)
    )
    if already_rolled:
        print("⚠ 该变更已被回滚过，拒绝重复回滚: {0}".format(args.rollback))
        return 3
    action = target.get("action")

    if action == "create_entity":
        eid = target.get("entity_id")
        entities = read_entities()
        relations = read_relations()
        if eid not in entities:
            print("该实体当前已不存在或已删除: {0}".format(eid))
            return 1
        linked = [r for r in relations if r["from_id"] == eid or r["to_id"] == eid]
        if linked:
            print("⚠ 该实体有 {0} 条关联关系将被一并回滚:".format(len(linked)))
            for r in linked:
                print("    {0} -{1}-> {2}".format(r["from_id"], r["predicate"], r["to_id"]))
        # [#18/append-only]: 不物理删除 create 记录，追加 rollback_entity 事件
        append_log(ENTITIES_FILE, {
            "op": "rollback_entity", "id": eid,
            "target_change_id": args.rollback, "at": now_iso(),
        })
        # 关联关系也追加式回滚（已确认未被回滚，见开头拒绝）
        for r in linked:
            append_log(RELATIONS_FILE, {
                "op": "rollback_relation", "relation_id": r["id"],
                "target_change_id": args.rollback, "at": now_iso(),
            })
        print("已回滚实体创建 (append-only): {0} (含 {1} 条关联关系)".format(eid, len(linked)))
    elif action == "add_relation":
        rid = target.get("relation_id")
        # [#18/append-only]: 追加 rollback_relation 事件
        append_log(RELATIONS_FILE, {
            "op": "rollback_relation", "relation_id": rid,
            "target_change_id": args.rollback, "at": now_iso(),
        })
        print("已回滚关系 (append-only): {0}".format(rid))
    else:
        print("该变更类型不支持自动回滚: {0}".format(action))
        return 1

    # [#20]: changelog 永不删除；追加一条 ROLLBACK 记录标记该 change 已回滚
    append_changelog({
        "change_id": "RB-" + generate_id("id").split("_", 1)[1],
        "action": "rollback",
        "target_change_id": args.rollback,
        "target_action": action,
        "status": "ROLLED_BACK",
        "at": now_iso(),
    })
    return 0


def cmd_rebuild_index(args):
    entities = read_entities()
    relations = read_relations()
    proposals = read_proposals()
    state = build_state(entities, relations, proposals)
    write_state(state)
    print("索引已重建: {0} 实体, {1} 关系, {2} 别名".format(
        state["entities"], state["relations"], state["alias_cache_size"]))
    return 0


def cmd_reload_alias_cache(args):
    entities = read_entities()
    cache = load_alias_cache(entities)
    ensure_dirs()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"alias_cache": cache, "cache_loaded_at": now_iso()}, f, ensure_ascii=False, indent=2)
    print("别名缓存已重载: {0} 条".format(len(cache)))
    return 0


def cmd_export_md(args):
    entities = read_entities()
    relations = read_relations()
    out = ["# Ontology 概览", ""]
    out.append("生成时间: {0}".format(now_iso()))
    out.append("")
    out.append("## 实体 ({0})".format(len(entities)))
    out.append("")
    for eid in sorted(entities):
        e = entities[eid]
        if args.project and e.get("scope") != args.project and e.get("properties", {}).get("project") != args.project:
            continue
        out.append("- **{0}** [{1}] {2} (status={3})".format(e["id"], e["type"], e.get("name", "?"), e.get("status", "?")))
    out.append("")
    out.append("## 关系 ({0})".format(len(relations)))
    out.append("")
    for r in relations:
        out.append("- {0} -{1}-> {2}".format(r["from_id"], r["predicate"], r["to_id"]))
    out.append("")
    md_path = os.path.join(DATA, "INDEX.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(chr(10).join(out))
    print("已导出: {0}".format(md_path))
    return 0



def cmd_resolve(args):
    """--resolve "<text>": 解析文本，匹配实体 + 相关关系。"""
    entities = read_entities()
    relations = read_relations()
    q = (args.resolve or '').strip().lower()
    if not q:
        print("--resolve 需要文本参数")
        return 1
    cache = load_alias_cache(entities)
    # 1) 精确别名/名称匹配
    exact = []
    for name, eid in cache.items():
        if q == name:
            exact.append(eid)
    # 2) 模糊匹配（q 出现在名称/别名/描述/标签中）
    fuzzy = []
    for eid, e in entities.items():
        blob = " ".join(str(v) for v in [
            e.get("name", ""),
            e.get("description", ""),
            json.dumps(e.get("properties", {}), ensure_ascii=False),
            json.dumps(e.get("tags", [])),
        ]).lower()
        if q and (q in blob or q in eid.lower()):
            fuzzy.append(eid)
    # 3) bigram 双向匹配（长句 → 含关键词的实体）：
    #    只对中文（CJK）2-gram 做匹配，忽略纯 ASCII 短词（避免 "API" 的 "pi"
    #    误命中 "Cupid" 这类英文别名的偶然重叠）。
    bigram = []
    if len(q) >= 2:
        # 生成 q 的 CJK 2-gram 集合（要求两个字符都是中文）
        def is_cjk(ch):
            return '一' <= ch <= '鿿'
        q_grams = set(q[i:i+2] for i in range(len(q)-1)
                      if is_cjk(q[i]) and is_cjk(q[i+1]))
        if q_grams:
            for eid, e in entities.items():
                if eid in fuzzy or eid in exact:
                    continue
                ename = str(e.get("name", "")).lower()
                ealias = " ".join(str(a) for a in (e.get("properties", {}).get("aliases", []) or [])).lower()
                etext = ename + " " + ealias
                if not etext:
                    continue
                e_grams = set(etext[i:i+2] for i in range(max(0, len(etext)-1))
                              if is_cjk(etext[i]) and is_cjk(etext[i+1]))
                # 剔除高频通用 bigram（V4 Pro 审查：避免"数据/系统/核算"等制造噪声）
                overlap = (q_grams & e_grams) - STOP_BIGRAMS
                # 至少 1 个非通用中文 2-gram 重叠才命中
                if overlap:
                    bigram.append(eid)
    matched = list(dict.fromkeys(exact + fuzzy + bigram))
    print("实体解析: {0}".format(args.resolve))
    resolved = []
    if matched:
        print("  匹配实体 ({0}):".format(len(matched)))
        for eid in matched[:MAX_RETURN]:
            e = entities[eid]
            conf = e.get("properties", {}).get("confidence", 0.0) or 0.0
            resolved.append({"id": eid, "type": e["type"], "confidence": conf})
            print("    - {0} [{1}] conf={2} ({3})".format(eid, e["type"], conf, e.get("name", "?")))
    else:
        print("  无匹配（status: unresolved）")
        print("  交给 Self-Improvement 处理，不强行绑定")
    # 相关关系
    rels = []
    if matched:
        print("  相关关系:")
        seen = set()
        for r in relations:
            if r["from_id"] in matched and r["to_id"] in matched:
                key = (r["from_id"], r["predicate"], r["to_id"])
                if key not in seen:
                    seen.add(key)
                    rels.append({"subject": r["from_id"], "predicate": r["predicate"], "object": r["to_id"]})
                    print("    - {0} -{1}-> {2}".format(r["from_id"], r["predicate"], r["to_id"]))
        if not seen:
            print("    (无直接关系)")
    return 0


def cmd_context(args):
    """--context <id>: 获取实体的语义上下文（相关 Agent/Skill/Project/Tool/Decision/Learning/矛盾/依赖）。"""
    entities = read_entities()
    relations = read_relations()
    eid = args.context
    if eid not in entities:
        print("实体不存在: {0}".format(eid))
        return 1
    e = entities[eid]
    print("上下文: {0} [{1}] {2}".format(eid, e["type"], e.get("name", "?")))
    # 收集一跳关系
    groups = {}
    for r in relations:
        if r["from_id"] == eid:
            groups.setdefault(r["predicate"], []).append((r["to_id"], "out"))
        elif r["to_id"] == eid:
            groups.setdefault(r["predicate"], []).append((r["from_id"], "in"))
    if not groups:
        print("  无直接关系")
    for pred in sorted(groups):
        print("  - {0}:".format(pred))
        for nid, direction in groups[pred][:MAX_RETURN]:
            ne = entities.get(nid, {})
            print("      {0} {1} {2} [{3}]".format(nid, "<- " if direction == "in" else "->", ne.get("name", "?"), ne.get("type", "?")))
    # 依赖（DEPENDS_ON/REQUIRES 关系，作为 dependencies）
    deps = []
    for r in relations:
        if r["predicate"] in ("DEPENDS_ON", "REQUIRES") and r["from_id"] == eid:
            deps.append(r["to_id"])
        elif r["predicate"] in ("DEPENDS_ON", "REQUIRES") and r["to_id"] == eid:
            deps.append(r["from_id"])
    if deps:
        print("  Dependencies: {0}".format(", ".join(deps)))
    # 矛盾
    contras = []
    for r in relations:
        if r["predicate"] == "CONTRADICTS":
            if r["from_id"] == eid or r["to_id"] == eid:
                other = r["to_id"] if r["from_id"] == eid else r["from_id"]
                contras.append(other)
    if contras:
        print("  Contradictions: {0}".format(", ".join(contras)))
    else:
        print("  Contradictions: none")
    return 0



def main():
    parser = argparse.ArgumentParser(description="Ontology Skill for OpenClaw")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--entity", metavar="ID")
    parser.add_argument("--search", metavar="QUERY")
    parser.add_argument("--relations", metavar="ID")
    parser.add_argument("--impact", metavar="ID")
    parser.add_argument("--depth", type=int)
    parser.add_argument("--create-entity", action="store_true")
    parser.add_argument("--type", metavar="TYPE")
    parser.add_argument("--name", metavar="NAME")
    parser.add_argument("--id", metavar="ID")
    parser.add_argument("--props", metavar="JSON")
    parser.add_argument("--relate", action="store_true")
    parser.add_argument("--from", dest="from_id", metavar="FROM")
    parser.add_argument("--pred", metavar="PREDICATE")
    parser.add_argument("--to", dest="to", metavar="TO")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--orphans", action="store_true")
    parser.add_argument("--duplicates", action="store_true")
    parser.add_argument("--contradictions", action="store_true")
    parser.add_argument("--propose", action="store_true")
    parser.add_argument("--change_type", metavar="TYPE")
    parser.add_argument("--subject", metavar="SUBJECT")
    parser.add_argument("--object", metavar="OBJECT")
    parser.add_argument("--reason", metavar="REASON")
    parser.add_argument("--evidence", metavar="EVIDENCE")
    parser.add_argument("--proposals", action="store_true")
    parser.add_argument("--verify", metavar="PROPOSAL_ID")
    parser.add_argument("--rollback", metavar="CHANGE_ID")
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--reload-alias-cache", action="store_true")
    parser.add_argument("--export-md", action="store_true")
    parser.add_argument("--resolve", metavar="TEXT")
    parser.add_argument("--context", metavar="ID")

    parser.add_argument("--project", metavar="PROJECT")
    args = parser.parse_args()

    ensure_dirs()
    if not os.path.exists(SCHEMA_FILE):
        write_schema(DEFAULT_SCHEMA)

    if args.status:
        return cmd_status(args)
    if args.entity:
        return cmd_entity(args)
    if args.search:
        return cmd_search(args)
    if args.relations:
        return cmd_relations(args)
    if args.impact:
        return cmd_impact(args)
    if args.create_entity:
        return cmd_create_entity(args)
    if args.relate:
        return cmd_relate(args)
    if args.validate:
        return cmd_validate(args)
    if args.orphans:
        return cmd_orphans(args)
    if args.duplicates:
        return cmd_duplicates(args)
    if args.contradictions:
        return cmd_contradictions(args)
    if args.propose:
        return cmd_propose(args)
    if args.proposals:
        return cmd_proposals(args)
    if args.verify:
        return cmd_verify(args)
    if args.rollback:
        return cmd_rollback(args)
    if args.rebuild_index:
        return cmd_rebuild_index(args)
    if args.reload_alias_cache:
        return cmd_reload_alias_cache(args)

    if args.resolve:
        return cmd_resolve(args)
    if args.context:
        return cmd_context(args)
    if args.export_md:
        return cmd_export_md(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
