# Ontology 语义模型参考（详细规格）

> 本文档承载 SKILL.md 中「可执行指令」之外的详细数据模型，供实现/审计查阅。SKILL.md 保持精简，这些是唯一真值的细节。

## 1. 存储结构

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

## 2. 实体 ID 前缀

```text
USR-* User    AGT-* Agent    PRJ-* Project   SKL-* Skill
TSK-* Task    LRN-* Learning DEC-* Decision  TOL-* Tool
RES-* Resource DOC-* Document EVT-* Event    CON-* Concept
RUL-* Rule    MET-* Metric   EVD-* Evidence  ONT-* Proposal
```

名称可改，稳定 ID 不变。

## 3. 初始实体类型

```text
User, Agent, Project, Skill, Task, Memory, Learning, Decision,
Tool, Resource, Document, Event, Workflow, Concept, Rule,
Constraint, Metric, Evidence, Proposal, Issue
```

别因新名字出现就新建实体类型。

## 4. 关系词汇

```text
IS_A, INSTANCE_OF, PART_OF, BELONGS_TO, OWNS, USES, DEPENDS_ON,
PROVIDES, REQUIRES, IMPLEMENTS, DERIVED_FROM, SUPPORTS, CONTRADICTS,
SUPERSEDES, VERIFIED_BY, CREATED_BY, USED_BY, APPLIES_TO, SCOPED_TO,
MEMBER_OF, WORKS_ON, LEARNED_FROM, CAUSED_BY, IMPROVES, REPLACES,
RELATED_TO, IS_EXCEPTION_TO
```

## 5. 置信度标尺

```text
0.00–0.30 weak        0.31–0.50 tentative   0.51–0.70 probable
0.71–0.85 strong      0.86–0.95 highly reliable  0.96–1.00 established
```

DERIVED 关系衰减更快；多跳推导不能当作 GLOBAL 强证据。

## 6. 断言层级

```text
ASSERTED（直接观察）
DERIVED（由关系推导，必须记录 derived_from）
HYPOTHESIS（假设，不当事实）
```

## 7. 上下文 / 作用域

关系可限定在特定 project / agent / tool version / environment / time。

作用域模型（与 self-evolution 一致）：

```text
TASK < AGENT < PROJECT < USER < GLOBAL
```

默认：存到最窄有效作用域。

## 8. 治理分级

- 自动应用（低风险）：新别名、低风险元数据、临时假设、安全推导关系
- 需验证：新实体类型、新核心关系、Skill 依赖、Agent 能力、项目依赖、重要约束、级联状态变更
- 显式批准（高风险）：GLOBAL 本体规则、安全/权限关系、财务关系、身份合并、大规模合并、删除、破坏性语义变更

## 9. 与 self-evolution 的受控反馈环

```text
Ontology（语义上下文）
  ↓
Self-Improvement / Learning OS（学习/冲突/新概念）
  ↓
Ontology Proposal（证据 + 治理）
  ↓
Ontology 更新
```

禁止：`Learning → 自动改 Ontology → 自动再学习`（失控自强化）。演化必须走提案 + 证据 + 验证 + 回滚。置信度标尺与 self-evolution 对齐（0.00–1.00）。

## 10. 安全

绝不存储：密码、API key、token、私密凭证、会话密钥。可引用携带凭证的 Tool，但绝不存凭证本身。

## 11. Definition of Done（MVP 判据）

- Agent/Project/Skill/Tool/Learning/Decision 实体可建可查
- 关系可查询
- 溯源/作用域/置信度已记录
- 矛盾可检测
- 影响分析可用（带守卫）
- 提案可生成、可验证
- 变更可回滚
- schema 校验拒绝非法写入
- 别名缓存已加载

## 12. CLI 完整参考

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
