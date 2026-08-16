---
name: ontology
version: 1.1.0
description: >
  Ontology and Semantic Knowledge Layer for OpenClaw. Provides controlled
  semantic modeling for Agents, Projects, Skills, Memories, Learnings,
  Decisions, Tasks, Tools, Resources and their relationships. Designed to
  work bidirectionally with self-evolution V3.2+. Includes alias cache,
  traversal guards, cascading status proposals, schema enforcement and
  impact analysis.
---
# Agent OS v1.1 Policy（正式版政策层, 来自整合包）

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Ontology

Purpose: provide a minimal semantic model of entities, relations, attributes and states.

Entity: stable identity, type, aliases, attributes, current state, provenance.
Relation: subject, predicate, object, validity, confidence, provenance.

Rules:
- Memory = experiences/events.
- Knowledge = durable claims.
- Ontology = semantic structure.
- Resolve aliases before creating entities.
- Separate current state from history.
- Never convert guesses to facts.
- Preserve contradictions.
- Keep the ontology minimal and useful.

---

# 本地实现部分（完整版, 保留）

# Ontology Skill V1.0.0 — 语义知识层

## 1. 定位

Ontology 是 OpenClaw 的语义层。它**不替代** Memory / Learning OS / Agent Registry / Project State / Skills。

核心原则：

> Memory 存经验。Learning 存变化。Ontology 存意义与关系。

Ontology 回答：

- 这是什么？什么类型？
- 它和什么相关？
- 它依赖什么？谁依赖它？
- 它适用于哪里？证据是什么？
- 什么变了？

## 2. 与 self-evolution 的关系

两个系统构成受控反馈环：

```text
Ontology
 ↓ 语义上下文
Self-Improvement / Learning OS
 ↓ 学习 / 冲突 / 新概念
Ontology Proposal
 ↓ 证据 + 治理
Ontology 更新
```

**禁止**：

```text
Learning → 自动改 Ontology → 自动再学习
```

会产生失控的自强化循环。Ontology 演化必须走提案 + 证据 + 验证 + 回滚。

置信度标尺与 self-improvement 对齐（0.00–1.00）。

## 3. 职责与边界

Ontology 提供：实体类型化、稳定 ID、规范名/别名、关系、上下文、依赖、溯源、语义检索、矛盾上下文、影响分析（带深度/环守卫）、Agent/Skill/Project 匹配、演化提案、别名解析缓存、级联状态提案。

边界：

| 系统 | 职责 |
|---|---|
| Memory | 经验 / 内容 |
| Learning OS | 学习 / 变化 |
| **Ontology** | **意义 / 关系** |
| Agent Registry | 运营 Agent 身份 |
| Skill | 可执行能力 |
| Project State | 当前项目状态 |
| Decision Memory | 重要决策 |

## 4. 存储

```text
memory/ontology/
├── schema.json       # 类型 + 关系定义
├── entities.jsonl    # append-only 实体日志
├── relations.jsonl   # append-only 关系日志
├── proposals.jsonl   # append-only 提案日志
├── changelog.jsonl   # 变更日志
└── state.json        # 别名缓存 / 索引状态
```

Append-only：已有数据只追加/合并，不覆盖（保留历史，防 clobber）。

## 5. 实体模型

稳定实体 ID，前缀：

```text
USR-* User    AGT-* Agent    PRJ-* Project   SKL-* Skill
TSK-* Task    LRN-* Learning DEC-* Decision  TOL-* Tool
RES-* Resource DOC-* Document EVT-* Event    CON-* Concept
RUL-* Rule    MET-* Metric   EVD-* Evidence  ONT-* Proposal
```

名称可改，稳定 ID 不变。

## 6. 初始实体类型

```text
User, Agent, Project, Skill, Task, Memory, Learning, Decision,
Tool, Resource, Document, Event, Workflow, Concept, Rule,
Constraint, Metric, Evidence, Proposal, Issue
```

别因为新名字出现就新建实体类型。

## 7. 初始关系词汇

```text
IS_A, INSTANCE_OF, PART_OF, BELONGS_TO, OWNS, USES, DEPENDS_ON,
PROVIDES, REQUIRES, IMPLEMENTS, DERIVED_FROM, SUPPORTS, CONTRADICTS,
SUPERSEDES, VERIFIED_BY, CREATED_BY, USED_BY, APPLIES_TO, SCOPED_TO,
MEMBER_OF, WORKS_ON, LEARNED_FROM, CAUSED_BY, IMPROVES, REPLACES,
RELATED_TO, IS_EXCEPTION_TO
```

## 8. 置信度标尺

```text
0.00–0.30 weak        0.31–0.50 tentative   0.51–0.70 probable
0.71–0.85 strong      0.86–0.95 highly reliable  0.96–1.00 established
```

DERIVED 关系衰减更快；多跳推导不能当作 GLOBAL 强证据。

## 9. 断言层级

```text
ASSERTED（直接观察）
DERIVED（由关系推导，必须记录 derived_from）
HYPOTHESIS（假设，不当事实）
```

## 10. 上下文 / 作用域

关系可限定在特定 project / agent / tool version / environment / time。

与 self-improvement 同一作用域模型：

```text
TASK < AGENT < PROJECT < USER < GLOBAL
```

默认：存到最窄有效作用域。

## 11. CLI 使用

所有命令在 `skills/ontology/scripts/` 下执行：

```bash
# 状态 / 索引
python3 scripts/ontology.py --status
python3 scripts/ontology.py --rebuild-index
python3 scripts/ontology.py --reload-alias-cache

# 实体
python3 scripts/ontology.py --create-entity --type Agent --name "短线交易员" --id AGT-short-term-trader --props '{"scope":"PROJECT"}'
python3 scripts/ontology.py --entity AGT-short-term-trader
python3 scripts/ontology.py --search "行情时间戳"

# 关系
python3 scripts/ontology.py --relate --from AGT-short-term-trader --pred WORKS_ON --to PRJ-a-share-paper-trading
python3 scripts/ontology.py --relations AGT-short-term-trader

# 影响分析（带深度/环守卫）
python3 scripts/ontology.py --impact AGT-short-term-trader --depth 3

# 校验 / 维护
python3 scripts/ontology.py --validate
python3 scripts/ontology.py --orphans
python3 scripts/ontology.py --duplicates
python3 scripts/ontology.py --contradictions

# 提案 / 治理
python3 scripts/ontology.py --propose --change_type create_entity --subject "CON-market-data-freshness" --reason "..." --evidence "..."
python3 scripts/ontology.py --proposals
python3 scripts/ontology.py --verify <proposal_id>
python3 scripts/ontology.py --rollback <change_id>

# 导出
python3 scripts/ontology.py --export-md [--project PRJ-xxx]
```

## 12. 与 self-improvement 对接（关键流程）

在 Global Learning Cycle 中，Ontology 解析插在 **Bus Drain 之后、Learning Engine 决策之前**：

```text
1. 读 Agent Registry
2. Drain 中央 Learning Bus（Phase 0）
3. Ontology 实体解析 + 别名查找
4. 用关系/上下文/矛盾富化事件
5. 交给 Learning Engine
6. Learning 决定 scope / promotion / demotion
7. 需要新语义结构 → Ontology Proposal
8. 验证并应用已批准的 ontology 变更
9. 更新索引 + 别名缓存
```

**Ontology 绝不自动广播学习。** Self-Improvement 发现新概念/新实体/新关系 → 必须创建 Ontology Proposal，而非静默改动重要本体。

## 13. 治理

### 自动应用（低风险）
新别名、低风险元数据、临时假设、安全推导关系

### 需验证
新实体类型、新核心关系、Skill 依赖、Agent 能力、项目依赖、重要约束、级联状态变更

### 显式批准（高风险）
GLOBAL 本体规则、安全/权限关系、财务关系、身份合并、大规模合并、删除、破坏性语义变更

## 14. 安全

绝不存储：密码、API key、token、私密凭证、会话密钥。

Ontology 可引用携带凭证的 Tool，但绝不存凭证本身。

## 15. 反模式（禁止）

```text
每条 Memory → Ontology 实体
每条 Learning → 永久 ontology 关系
Ontology → 自动改写 Skill
Self-Improvement → 自动扩 Ontology → 自动扩 Self-Improvement
静默级联状态变更
无界图遍历
```

## 16. Definition of Done（MVP 判据）

```text
✓ Agent/Project/Skill/Tool/Learning/Decision 实体可建可查
✓ 关系可查询
✓ 溯源/作用域/置信度已记录
✓ 矛盾可检测
✓ 影响分析可用（带守卫）
✓ 提案可生成、可验证
✓ 变更可回滚
✓ schema 校验拒绝非法写入
✓ 别名缓存已加载
```

---

# Version

## V1.0.0

基于 ClawHub `@oswalpalash/ontology` V1.1.0 文档思想的本地实现，裁剪为 Phase 1 MVP：

- JSON append-only 存储（不引入图数据库，贴合现有 self-improvement 风格）
- 核心类型 + 关系词汇 + schema 校验
- 实体 CRUD / 关系 / 搜索 / 影响分析（深度+环守卫）
- 提案治理 / 回滚 / 维护命令
- 与 self-evolution 的受控双向接口约定