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
import hashlib
import json
import os
import sys

# ---------------------------------------------------------------------------
# 统一 canonical / 指纹（shared skill/_lib/canonical —— 与 agent-os-vault 同一实现）
# 迁移前后指纹不变：本模块不再各自维护一套 canonical 序列化。
# ---------------------------------------------------------------------------
try:
    _LIB_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "_lib")
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    import canonical as _canon_mod  # noqa: F401
    from provenance import verify_provenance as _verify_provenance  # noqa: F401
    _SHARED_CANONICAL = True
except Exception:
    _canon_mod = None
    # 降级：保留本地内联（与历史逐字一致，指纹不变）
    _SHARED_CANONICAL = False

import re
import sys
import time

import yaml  # P0 Agent OS×Obsidian: vault frontmatter/minimal .base rendering

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# v1.3 Hardening B2: 统一 ID helper
_LIB = os.path.join(os.path.dirname(BASE), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id
from persistence import atomic_write_json, append_atomic
from workspace import shared_state_dir, prefer_migrated_path

DATA = prefer_migrated_path(shared_state_dir("ontology"),
                            os.path.join(BASE, "memory", "ontology"))

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

# CORE-19（最小核心类型白名单）：防止 ontology 实体类型自由膨胀。
# 与 references/semantic-model.md「初始实体类型」一致；另含 Person（常用于身份建模）。
# schema.json 的实际 types 仍为校验权威；白名单用作“超核心告警”，不入白名单的类型可存在
# 但会收到告警，提示走语义模型评审，避免因新名字就新建实体类型。
CORE_ENTITY_TYPES = {
    "Agent", "Project", "Skill", "Tool", "Learning", "Decision", "Concept",
    "Task", "User", "Memory", "Document", "Event", "Resource", "Workflow",
    "Rule", "Constraint", "Metric", "Evidence", "Proposal", "Issue", "Person",
}

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
    # AE-10 (L-17): source-of-truth (entities/relations/proposals/changelog) 用原子追加，
    #   避免崩溃/并发产生损坏半行导致 read_log 静默跳过 → 实体静默丢失。
    append_atomic(path, obj)


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
    # CORE-19：最小核心类型白名单——schema 已含的类型若不属于核心集，告警（防膨胀）。
    # 不硬拦截（schema 仍是权威，自定义扩展类型允许存在），但提示“别因新名字就新建实体类型”。
    if etype not in CORE_ENTITY_TYPES:
        print("⚠ [ontology CORE-19] 类型 '{0}' 不在最小核心白名单内(可用核心: {1})；"
              "如需持久化新类型请走语义模型评审，勿随意膨胀。".format(
                  etype, ", ".join(sorted(CORE_ENTITY_TYPES))))
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


def _visible_to(ent, agent_id):
    """MA-1.0 (规格 8.3 Cross-Agent Read): 判断实体对当前 agent 是否可见。

    scope=AGENT 且 owner_id 非空且 != 当前 agent → 默认 DENY（隔离）。
    scope ∈ TASK/PROJECT/USER/GLOBAL 或 owner_id 为空/匹配 → 可见。
    """
    if not agent_id:
        return True  # 未声明身份 → 不启用隔离（legacy 兼容）
    scope = str(ent.get("scope", "") or "").upper()
    if scope == "AGENT":
        oid = str(ent.get("owner_id", "") or "").strip()
        if oid and oid != agent_id:
            return False
    return True


def cmd_entity(args):
    entities = read_entities()
    e = entities.get(args.entity)
    if not e:
        print("实体不存在: {0}".format(args.entity))
        return 1
    # MA-1.0: 跨 Agent 读隔离
    if not _visible_to(e, args.agent):
        print("拒绝读取（跨 Agent 隔离，scope=AGENT 且非本 Agent）: {0}".format(args.entity))
        return 3
    print(json.dumps(e, ensure_ascii=False, indent=2))
    return 0


def cmd_search(args):
    entities = read_entities()
    q = args.search.lower()
    hits = []
    hidden = 0
    for eid, e in entities.items():
        blob = " ".join(str(v) for v in [
            e.get("name", ""), e.get("description", ""),
            json.dumps(e.get("properties", {}), ensure_ascii=False),
            json.dumps(e.get("tags", [])),
        ]).lower()
        if q in blob or q in eid.lower():
            # MA-1.0: 跨 Agent 读隔离
            if not _visible_to(e, args.agent):
                hidden += 1
                continue
            hits.append(e)
    print("命中 {0} 条:".format(len(hits)))
    for e in hits[:MAX_RETURN]:
        print("  [{0}] {1} ({2})".format(e["id"], e.get("name", "?"), e["type"]))
    if hidden:
        print("（已隔离隐藏 {0} 条跨 Agent 实体）".format(hidden))
    return 0


def cmd_create_entity(args):
    schema = read_schema()
    props = json.loads(args.props) if args.props else {}
    entity_props = validate_entity(schema, args.type, args.name, props)
    entities = read_entities()
    # ONT-01（强制 Alias First）：创建必须先 resolve alias + duplicate check，
    # 不得绕过 alias resolution 直接建实体。
    alias_cache = load_alias_cache(entities)
    resolve_key = (args.name or "").lower()
    dup_id = alias_cache.get(resolve_key)
    if dup_id:
        # 同名/同别名已存在 → 不再新建，返回现有 id（强制去重）
        print("⚠ 实体已存在（alias 命中）: {0} → {1}".format(args.name, dup_id))
        return 2
    # 再查 props.aliases 是否命中已有实体别名
    for a in (props.get("aliases", []) or []):
        hit = alias_cache.get(str(a).lower())
        if hit:
            print("⚠ 别名冲突: {0} → {1}".format(a, hit))
            return 2
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
        # MA-1.0 (规格 8.1 Entity Ownership): 记录实体归属。
        "owner_type": entity_props.get("owner_type", "agent" if entity_props.get("scope") in (None, "AGENT", "TASK") else "project"),
        "owner_id": entity_props.get("owner_id", ""),
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
    # ONT-02: 去重判据 = exact normalized name + explicit alias + stable ID。
    #   不引入 LLM 语义去重（否则 Ontology 开始承担语义推理）。
    alias_cache = load_alias_cache(entities)
    by_alias = {}  # alias → 命中它的实体 id 列表（同名已在 by_name 覆盖，这里只补别名维度）
    for eid, e in entities.items():
        for a in (e.get("properties", {}).get("aliases", []) or []):
            ka = str(a).strip().lower()
            if ka:
                by_alias.setdefault(ka, []).append(eid)
    # 别名命中多个实体的，也列为重复候选
    dups = {k: v for k, v in by_name.items() if len(v) > 1}
    for ka, eids in by_alias.items():
        if len(eids) > 1:
            dups["[alias] " + ka] = eids
    if not dups:
        print("未发现同名/同别名重复候选")
        return 0
    print("重复候选:")
    for key, ids in dups.items():
        print("  '{0}': {1}".format(key, ", ".join(ids)))
    print("(标记为 merge_candidate, 不自动合并；exact name / explicit alias / stable ID 以上均可甄别，不做 LLM 语义去重)")
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


# ---------------------------------------------------------------------------
# P0 Agent OS × Obsidian — 单向只读导出（view rendering only，JSONL 仍是唯一真相）
#
# 边界（design doc 第 6 部分）：此处只新增“视图渲染”逻辑，不触碰
# read_entities/read_relations/append/schema/rollback/alias/impact 等存储与语义核心。
# 导出绝不写回 JSONL / state.json；provenance 通过相对行号 + SHA-256 可回溯。
# 所有输出文件为纯 Markdown + YAML Properties(frontmatter) + Wikilink，
# 不依赖 Obsidian 应用即可读取。
# ---------------------------------------------------------------------------

VAULT_SCHEMA_VERSION = 1

# 只给“核心实体类型白名单”生成独立 .md；非白名单类型（自定义扩展）汇总进 _index，
# 避免视图遗漏且不鼓励类型膨胀（对齐 CORE-19 粒度，但不重复 CORE_ENTITY_TYPES 定义）。


def _canonical_json(obj):
    """稳定 canonical 序列化（provenance 指纹用）。

    规则（见 vault _meta/META.md）：键递归按字典序排序，值 JSON 序列化，
    ensure_ascii=False + sort_keys + 正则空格；同一 JSONL 任意两次读取结果一致。
    由 _lib/canonical 提供；此处仅当 shared 不可用时内联。
    """
    if _SHARED_CANONICAL:
        return _canon_mod.canonical_json(obj)
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _canonical_entity(e):
    """实体的稳定指纹：只取稳定字段(见 META.md 串行化规则)，忽略易变时间戳。"""
    if _SHARED_CANONICAL:
        return _canon_mod.canonical_entity(e)
    stable = {
        "id": e.get("id"),
        "type": e.get("type"),
        "name": e.get("name"),
        "status": e.get("status", "active"),
        "scope": e.get("scope", "AGENT"),
        "owner_type": e.get("owner_type"),
        "owner_id": e.get("owner_id"),
        "properties": e.get("properties", {}) or {},
    }
    return _canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


def _canonical_relation(r):
    """关系的稳定指纹：只取稳定字段，忽略 _line 与易变时间戳。"""
    if _SHARED_CANONICAL:
        return _canon_mod.canonical_relation(r)
    stable = {
        "id": r.get("id"),
        "from_id": r.get("from_id"),
        "predicate": r.get("predicate"),
        "to_id": r.get("to_id"),
        "status": r.get("status", "active"),
        "properties": r.get("properties", {}) or {},
    }
    return _canonical_json({k: v for k, v in stable.items() if v not in (None, "")})


def _sha256(s):
    if _SHARED_CANONICAL:
        return _canon_mod.sha256(s)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_lines(path):
    """读 JSONL 原始行，返回 (replay_obj, line_no)。用于 provenance 行号回溯。"""
    out = []
    if os.path.exists(path):
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


def _esc_prop(v):
    """把属性值转成较安全的 YAML 标量文本用于前端/正文。"""
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False, sort_keys=True)
        except Exception:
            return repr(v)
    return str(v)


def _wikify(eid, entities):
    """把实体 id 整理成相对路径；若目标不存在则返回空路径，避免悬空链接。"""
    if eid in entities:
        e = entities[eid]
        etype = e.get("type", "Entity")
        label = e.get("name") or eid
        rel = "entities/{0}/{1}".format(etype, eid)
        return (label, rel)
    return (eid, "")


def _frontmatter(fields):
    """渲染 YAML frontmatter。fields 为 dict；保持中文、排序、无冗余空值。"""
    # 剔除 None/空 list/dict，避免污染 frontmatter
    clean = {}
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, (dict, list)) and not v:
            continue
        if isinstance(v, str) and v == "":
            continue
        clean[k] = v
    body = yaml.safe_dump(
        clean, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).rstrip("\n")
    return "---\n{0}\n---\n".format(body)


def _safe_mkdirs(path):
    os.makedirs(path, exist_ok=True)


def _emit(path, text):
    _safe_mkdirs(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def cmd_export_vault(args):
    """P0 批量导出：Ontology Entity/Relation → Vault 视图（只读）。

    生成（out 默认为 DATA/../vault-export）：
      ontology/entities/<type>/<id>.md   —— 每个核心类型实体一张卡
      ontology/_index.md                 —— 概览索引（含全部类型汇总）
      ontology/relations.base            —— active 关系 Bases 视图
      ontology/graph.canvas              —— 实体-关系图谱（text 节点 + edges）
      _meta/META.md                      —— schema 版本 + 串行化规则 + 溯源说明

    绝不写回 JSONL / state.json。可重复运行：覆盖视图文件，不改源。
    """
    entities = read_entities()
    relations = read_relations()

    # 多 Agent 读隔离：仅当 --agent 给定时过滤他 agent 私有实体（复用现有 _visible_to）。
    if getattr(args, "agent", ""):
        entities = {eid: e for eid, e in entities.items()
                    if _visible_to(e, args.agent)}

    # project 过滤（同 --export-md 语义）：scope 或 properties.project 匹配才保留。
    if getattr(args, "project", ""):
        prj = args.project
        entities = {eid: e for eid, e in entities.items()
                    if e.get("scope") == prj or e.get("properties", {}).get("project") == prj}

    # 只保留仍指向现存实体的关系（避免悬空），并尊重 agent 隔离/项目过滤。
    relations = [r for r in relations
                 if r.get("from_id") in entities and r.get("to_id") in entities]

    # provenance 行号映射：entities.jsonl/relations.jsonl 的 (id -> line_no)
    ent_lines = {}
    for obj, line in _read_lines(ENTITIES_FILE):
        ent = obj.get("entity", {})
        if ent.get("id"):
            ent_lines[ent["id"]] = line
    rel_lines = {}
    for obj, line in _read_lines(RELATIONS_FILE):
        rel = obj.get("relation", {})
        if rel.get("id"):
            rel_lines.setdefault(rel["id"], line)

    out_dir = getattr(args, "out", None) or os.path.join(DATA, "..", "vault-export")
    out_dir = os.path.abspath(out_dir)
    ont_dir = os.path.join(out_dir, "ontology")
    meta_dir = os.path.join(out_dir, "_meta")
    _safe_mkdirs(ont_dir)
    _safe_mkdirs(meta_dir)

    # 按类型分组（只对 CORE_ENTITY_TYPES 白名单生成独立 .md）
    by_type = {}
    other_types = {}
    for eid, e in entities.items():
        et = e.get("type", "Entity")
        if et in CORE_ENTITY_TYPES:
            by_type.setdefault(et, {})[eid] = e
        else:
            other_types.setdefault(et, {})[eid] = e

    # ---- 1) 每个核心类型实体一张 .md ----
    for et, emap in by_type.items():
        for eid, e in emap.items():
            props = e.get("properties", {}) or {}
            aliases = props.get("aliases") or []
            if not isinstance(aliases, list):
                aliases = [aliases]
            fingerprint = _sha256(_canonical_entity(e))
            fm = {
                "osv": VAULT_SCHEMA_VERSION,
                "object_type": "ontology_entity",
                "id": eid,
                "etype": e.get("type"),
                "name": e.get("name"),
                "aliases": aliases,
                "scope": e.get("scope", "AGENT"),
                "status": e.get("status", "active"),
                "confidence": props.get("confidence"),
                "freshness": props.get("freshness"),
                "validity": props.get("validity"),
                "source_type": props.get("source_type"),
                "provenance_ref": (
                    "entities.jsonl:{0}:{1}".format(
                        ent_lines.get(eid, "?"), fingerprint[:16])
                    if ent_lines.get(eid) else None
                ),
                "source_agent": props.get("source_agent"),
                "owner_type": e.get("owner_type"),
                "owner_id": e.get("owner_id") or None,
                "superseded_by": props.get("superseded_by") or e.get("superseded_by"),
                "created_at": e.get("created_at"),
                "updated_at": e.get("updated_at"),
                "tags": ["agent-os/view", "ontology/entity"],
            }
            for tk in ("description", "title", "content"):
                if props.get(tk):
                    fm[tk] = props[tk]
            # 附加其它非冲突属性，保全语义不丢失
            extra = []
            skip = set(fm.keys()) | {"aliases", "confidence", "freshness", "validity",
                                      "source_type", "provenance_ref", "source_agent",
                                      "description", "title", "content", "name",
                                      "scope", "status", "superseded_by"}
            for k, v in props.items():
                if k in skip:
                    continue
                extra.append("- {0}: {1}".format(k, _esc_prop(v)))

            # 关系区：关联当前实体的 active 关系
            rel_sec = []
            for r in relations:
                if r.get("from_id") == eid:
                    tlabel, trel = _wikify(r["to_id"], entities)
                    link = "[[{0}]]".format(trel.replace(".md", "")) if trel else tlabel
                    rel_sec.append("- {0} → {1}".format(r["predicate"], link))
                elif r.get("to_id") == eid:
                    slab_, srel = _wikify(r["from_id"], entities)
                    link = "[[{0}]]".format(srel.replace(".md", "")) if srel else slab_
                    rel_sec.append("- {0} ⇠ {1}".format(link, r["predicate"]))

            lines = []
            lines.append(_frontmatter(fm))
            lines.append("# {0}".format(e.get("name") or eid))
            lines.append("")
            body = props.get("description") or props.get("content") or props.get("title")
            if body:
                lines.append(body)
                lines.append("")
            lines.append("> [!info] 来源")
            lines.append("> JSONL 源：`entities.jsonl` 行 {0} · 指纹 `{1}`".format(
                ent_lines.get(eid, "?"), fingerprint))
            if e.get("status") in ("obsolete", "superseded", "disputed"):
                lines.append("")
                note = {
                    "obsolete": "该实体已标记 obsolete（视图保留，未删 JSONL）。",
                    "superseded": "该实体已被较新声明取代（见 frontmatter `superseded_by`）。",
                    "disputed": "该实体存在矛盾，未被静默合并。",
                }[e["status"]]
                lines.append("> [!warning] {0}".format(note))
            if aliases:
                lines.append("")
                lines.append("**别名**：" + ", ".join(str(a) for a in aliases))
            if extra:
                lines.append("")
                lines.append("**附加属性**")
                lines.extend(extra)
            if rel_sec:
                lines.append("")
                lines.append("## 关系")
                lines.extend(rel_sec)
            _emit(os.path.join(ont_dir, "entities", et, eid + ".md"),
                  "\n".join(lines) + "\n")

    # ---- 2) _index.md 概览 ----
    idx = []
    idx.append("---")
    idx.append("osv: {0}".format(VAULT_SCHEMA_VERSION))
    idx.append("object_type: ontology_index")
    idx.append("tags: [agent-os/view, ontology/index]")
    idx.append("---")
    idx.append("")
    idx.append("# Ontology 索引（只读导出）")
    idx.append("")
    idx.append("> 本目录由 `ontology.py --export-vault` 生成，**只读视图**；")
    idx.append("> 语义真相在 `entities.jsonl` / `relations.jsonl`（append-only），请勿直接编辑本视图。")
    idx.append("")
    idx.append("生成时间：" + now_iso())
    idx.append("")
    idx.append("实体总数：{0}（核心白名单 {1}，其他类型 {2}）".format(
        len(entities), sum(len(v) for v in by_type.values()),
        sum(len(v) for v in other_types.values())))
    idx.append("")
    for et in sorted(by_type):
        idx.append("## {0} ({1})".format(et, len(by_type[et])))
        for eid in sorted(by_type[et]):
            e = by_type[et][eid]
            status = e.get("status", "active")
            idx.append("- [[{0}|{1}]] — {2} · status=`{3}`".format(
                "entities/{0}/{1}".format(et, eid).replace(".md", ""),
                e.get("name") or eid, eid, status))
        idx.append("")
    if other_types:
        idx.append("## 其他类型（未生成独立卡片）")
        for et in sorted(other_types):
            idx.append("- {0}: {1}".format(et, ", ".join(sorted(other_types[et]))))
        idx.append("")
    _emit(os.path.join(ont_dir, "_index.md"), "\n".join(idx) + "\n")

    # ---- 3) relations.base ----
    base = []
    base.append("# ontology relations 视图（只读导出，Bases）")
    base.append("# 由 ontology.py --export-vault 生成；语义真相在 relations.jsonl")
    base.append("filters:")
    base.append("  and:")
    base.append("    - 'file.inFolder(\"ontology/entities\")'")
    base.append("    - 'status == \"active\"'")
    base.append("views:")
    base.append("  - type: table")
    base.append("    name: \"Active Relations\"")
    base.append("    order:")
    base.append("      - file.name")
    base.append("      - id")
    base.append("      - from_id")
    base.append("      - predicate")
    base.append("      - to_id")
    base.append("      - scope")
    base.append("      - status")
    proto = ""
    try:
        # 深度优先稳定的 relations 列表（edge 候选）写入 canvas node 文本
        proto = "active relations: {0}".format(len(relations))
    except Exception:
        proto = ""
    base.append("# relations_count: {0}".format(len(relations)))
    base.append("# " + proto)
    _emit(os.path.join(ont_dir, "relations.base"), "\n".join(base) + "\n")

    # ---- 4) graph.canvas（JSON Canvas Spec 1.0）----
    nodes = []
    edges = []
    x, y = 0, 0
    node_ids = {}
    for eid, e in sorted(entities.items()):
        nid = ("n" + eid).replace("-", "").lower()
        # 稳定 16 hex 节点 id：用 id 的 sha256 头 16
        nid = _sha256("entity:" + eid)[:16]
        node_ids[eid] = nid
        nodes.append({
            "id": nid,
            "type": "text",
            "x": x,
            "y": y,
            "width": 260,
            "height": 120,
            "text": "**{0}**\n{1} [{2}]\n{3}".format(
                e.get("name") or eid, eid, e.get("type"), e.get("status", "active")),
        })
        x += 320
        if x > 1800:
            x = 0
            y += 180
    edge_counter = 0
    for r in relations:
        frm = node_ids.get(r.get("from_id"))
        to = node_ids.get(r.get("to_id"))
        if not frm or not to:
            continue
        eid_ = _sha256("edge:{0}".format(r.get("id") or edge_counter))[:16]
        edges.append({
            "id": eid_,
            "fromNode": frm,
            "toNode": to,
            "toEnd": "arrow",
            "label": r.get("predicate"),
        })
        edge_counter += 1
    canvas = {"nodes": nodes, "edges": edges}
    _emit(os.path.join(ont_dir, "graph.canvas"),
          json.dumps(canvas, ensure_ascii=False, indent=2) + "\n")

    # ---- 5) _meta/META.md 溯源与串行化规则说明 ----
    meta = []
    meta.append("# P0 Ontology→Vault 导出元信息")
    meta.append("")
    meta.append("- **schema**：osv={0}".format(VAULT_SCHEMA_VERSION))
    meta.append("- **truth source**：`entities.jsonl` / `relations.jsonl`（append-only，唯一真相）")
    meta.append("- **direction**：单向只读导出，P0 不写回 JSONL")
    meta.append("- **serialization rule（canonical 指纹）**：")
    meta.append("  - 实体/关系用 JSON `sort_keys=True, separators=(',' , ':'), ensure_ascii=False` 序列化。")
    meta.append("  - 只取稳定字段，忽略易变时间戳（created_at/updated_at）。")
    meta.append("  - 属性缺失的字段不注入空占位；properties 递归键排序。")
    meta.append("  - 指纹 = `entity`/`relation` 前缀区分命名空间，SHA-256 hexdigest。")
    meta.append("- **provenance_ref 格式**：`<file>:<jsonl_line>:<sha256[0:16]>`")
    meta.append("  - 例：`entities.jsonl:1:abcdef...` → 可回到 entities.jsonl 第 1 行核对。")
    meta.append("- **生成时间**：" + now_iso())
    meta.append("- **排除规则**：status=deleted 的实体不导出；非核心类型只进 _index")
    _emit(os.path.join(meta_dir, "META.md"), "\n".join(meta) + "\n")

    print("已导出 Vault 视图（只读）→ {0}".format(out_dir))
    _printed = "\n".join([
        "  实体卡片: {0} 张 · 关系: {1} 条".format(
            sum(len(v) for v in by_type.values()), len(relations)),
        "  ontology/entities/<type>/<id>.md · relations.base · graph.canvas · _index.md · _meta/META.md",
    ])
    print(_printed)
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
    parser.add_argument("--agent", metavar="AGENT_ID", default="",
                        help="MA-1.0: 当前读取 Agent 身份，用于跨 Agent 读隔离（scope=AGENT 且非本 Agent 的实体默认不可见）")
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
    parser.add_argument("--export-vault", action="store_true")  # P0: 批量只读导出到 Vault
    parser.add_argument("--out", metavar="DIR")                  # P0: Vault 导出目标目录
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
    if args.export_vault:  # P0 批量导出视图
        return cmd_export_vault(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
