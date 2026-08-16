---
name: ontology
description: 维护实体/关系/属性的语义索引（含别名/状态/来源/置信度）供检索与一致性；不替代 OpenClaw runtime。语义建模时触发。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.2", "layer": "core" } }
version: 1.2.0
---


# Ontology

## Purpose

提供最小有用的**语义模型**（实体、关系、属性、状态），回答：这是什么类型、和什么相关、依赖什么、适用于哪里、证据是什么、什么变了。核心区分：Memory 存经验，Learning 存变化，**Ontology 存意义与关系**。

## Scope

- 实体类型化 + 稳定 ID + 规范名/别名
- 关系建模（谓词词汇 + 置信度 + 作用域）
- 溯源 / 上下文 / 断言层级（ASSERTED/DERIVED/HYPOTHESIS）
- 影响分析（带深度/环守卫）
- 别名解析缓存、级联状态提案、schema 校验、回滚

## Non-Goals

- 不存经验/内容（走 memory-governance）
- 不存学习/变化（走 self-evolution）
- 不替代 Agent Registry / Project State / Skill / Decision Memory
- 不存 Secret / 凭证（只引用，不存本体）
- 不建独立图数据库（用 JSON append-only）

## OpenClaw Boundary

只做语义建模，复用 OpenClaw 原生文件系统/session/memory 设施。不创建自己的 Scheduler、Event Bus、Agent Runtime、Memory Runtime。存储用 `memory/ontology/` 下的 append-only JSONL，只是语义索引，不是并行运行时。

## When to Activate

- 新实体/关系需要建模、查询、搜索
- 需要解析别名、判断依赖/作用域
- 需要影响分析（改一个实体会影响谁）
- 级联状态变化需要提案
- 需要检测矛盾/孤儿/重复实体

## Inputs

- 实体信息（类型/名称/别名/属性/作用域）
- 关系信息（subject/predicate/object/置信度/作用域）
- 待解析的别名/待查询的实体
- 待验证的提案

## Core Procedure

本 Skill 只负责生命周期中的 **Context/Writeback 辅助** 节点：维护实体/关系语义索引供检索。不替代 OpenClaw runtime。

1. **解析别名**：创建实体前先解析别名，避免重复实体。
2. **建实体/关系**：走 scripts/ontology.py 的 create-entity / relate。
3. **记录溯源**：记录 provenance、scope（TASK<AGENT<PROJECT<USER<GLOBAL，默认最窄有效）、confidence、断言层级。
4. **校验**：schema 校验拒绝非法写入。
5. **查询/影响分析**：搜索 + impact（带深度/环守卫）。
6. **演化提案**：新语义结构 → 走 --propose（证据+治理），验证后应用。
7. **维护**：validate/orphans/duplicates/contradictions 定期检查。
8. **回滚**：变更可 rollback，历史 append-only。

详细模型（实体前缀、类型、关系词汇、置信度标尺、断言层级、存储结构、治理分级）见 `references/semantic-model.md`。

## Decision Rules

**别名先于建实体**：名称可改，稳定 ID 不变；先解析别名再创建。

**断言层级**：ASSERTED（直接观察）> DERIVED（由关系推导，须记 derived_from）> HYPOTHESIS（假设，不当事实）。多跳推导不能当 GLOBAL 强证据。

**作用域**：默认存最窄有效 scope；DERIVED 关系衰减更快。

**矛盾**：保留矛盾，不把猜测转事实。

**治理分级**：
- 自动应用（低风险）：新别名、低风险元数据、临时假设、安全推导关系。
- 需验证：新实体类型、新核心关系、Skill/Agent/项目依赖、重要约束、级联状态变更。
- 显式批准（高风险）：GLOBAL 规则、安全/权限/财务关系、身份合并、删除、破坏性语义变更。

**反模式（禁止）**：每条 Memory→实体；每条 Learning→永久关系；Ontology 自动改写 Skill；Learning↔Ontology 自动互相扩（失控自强化）；静默级联变更；无界图遍历。

## Outputs

- 实体/关系记录（含 provenance/scope/confidence）
- 查询/搜索/影响分析结果
- 提案 + 待验证项
- 矛盾/孤儿/重复检测结果

## Interaction With Agent OS

- 被 **context-orchestration** 用来解析身份/关系/作用域。
- 接收 **self-evolution** 发现的新概念/实体/关系 → 走 Proposal，不静默改本体。
- 辅助 **orchestrator / task-manager / proactive** 的世界模型读取。
- 与 self-evolution 构成受控反馈环（禁止自动互相扩）。

## Permission

读/查询 = L0；建实体/关系（本地 append） = L1 可自动；级联状态变更/删除/身份合并/GLOBAL 规则 = L2/L3 需审批。遵守 OpenClaw native policy。

## Verification

- schema 校验是否通过（--validate）？
- 别名是否已解析（无重复实体）？
- 溯源/scope/confidence 是否记录？
- 影响分析是否有深度/环守卫（不无限遍历）？
- 提案是否有证据 + 回滚路径？

## Failure Handling

- 非法写入 → schema 拒绝。
- 重复/孤儿实体 → --duplicates / --orphans 检测并合并/清理。
- 冲突关系 → --contradictions 保留并标记，交人工。
- 误变更 → --rollback 回滚（历史 append-only 保证可恢复）。

## Memory / Knowledge Writeback

本体变更若产生经验（如某建模决策），转 memory-governance；若形成可复用声明，转 knowledge-governance。通过 --export-md 导出结构化语义。

## Self-Evolution Feedback

- Self-Evolution 发现新概念/关系 → 创建 Ontology Proposal（不静默改动）。
- Ontology 发现模型缺口/矛盾高发 → 反馈 self-evolution 作为改进 candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Agent Runtime、Context Engine；复用 OpenClaw 原生。
- 不存 Secret/凭证（只引用工具，不存凭证本身）。
- 禁止 Learning↔Ontology 自动互相扩的失控循环；演化必须提案+证据+验证+回滚。

## Examples

```bash
python3 scripts/ontology.py --create-entity --type Agent --name "短线交易员" --id AGT-short-term-trader --props '{"scope":"PROJECT"}'
python3 scripts/ontology.py --relate --from AGT-short-term-trader --pred WORKS_ON --to PRJ-a-share-paper-trading
python3 scripts/ontology.py --impact AGT-short-term-trader --depth 3
python3 scripts/ontology.py --propose --change_type create_entity --subject "CON-market-data-freshness" --reason "..." --evidence "..."
```
