---
name: context-orchestration
description: 上下文编排策略层（Agent OS v1.2 核心模块）。为任务选择最小有用信息：任务类型→所需实体→记忆/知识/本体检索→去噪→紧凑上下文包。不替代 OpenClaw Context Engine。在任务开始、上下文超预算、多来源信息需要去噪组装时触发。
version: 1.2.0
x-agent-os:
  protocol_version: "1.2"
  layer: "core"
---

# Context Orchestration

## Purpose

为当前任务**选择「最小有用」信息**，组装成紧凑上下文包，交给正常的 OpenClaw 执行。不替代 OpenClaw Context Engine；只在其之上做「取什么、去什么、留什么」的策略判断。

## Scope

- 识别任务类型与成功标准
- 识别所需实体，决定要检索哪些记忆/知识/本体/文件
- 去噪、去重、保留矛盾
- 生成紧凑上下文包
- 判断何时需要扩展检索

## Non-Goals

- 不实现上下文组装/注入/压缩的底层机制（OpenClaw Context Engine 拥有）
- 不做总结（走 summarize）
- 不做记忆/知识治理（走对应 governance）
- 不建并行 context engine

## OpenClaw Boundary

只做「选什么信息」的策略层，复用 OpenClaw 原生 Context Engine / prompt assembly / session / workspace 文件。不创建自己的 Scheduler、Context Engine、Memory Runtime。

## When to Activate

- 任务开始时确定要加载哪些上下文
- 上下文接近预算，需降噪、取舍
- 多来源信息（记忆/知识/本体/文件/工具结果）需组装
- 从多个 Agent 交接、需最小交接包时

## Inputs

- 任务目标 + 成功标准
- 可用来源：conversation / goals/tasks / Memory / Knowledge / Ontology / workspace 文件 / 已验证工具结果
- 相关实体（人/项目/任务/工具/概念）
- 上下文预算约束

## Core Procedure

统一执行链：Trigger → Intake → Context → Goal/Task → Decision → Permission → Action → Verification → Evaluation → Writeback → Evolution

1. **识别任务与成功标准**：明确要解决什么、怎么算完成。
2. **识别所需实体**：涉及哪些人/项目/任务/工具/概念/关系。
3. **检索相关内容**：按任务类型检索 memory / knowledge / ontology / 文件 / 工具结果。
4. **本体解析身份/关系**：通过 ontology 解析别名、依赖、作用域。
5. **优先新鲜/已验证信息**：冲突处选 verified ≥ fresh ≥ 推断。
6. **去噪去重**：去掉重复、无关、噪音。
7. **保留实质矛盾**：不因压缩而抹平矛盾。
8. **产出紧凑上下文包**：交给 OpenClaw 正常执行。

## Decision Rules

**最小充分原则**：只取与当前任务相关的上下文，不全量加载世界模型。

**扩展检索触发条件**（满足任一才扩大检索）：
- confidence 低
- 证据冲突
- 缺失关键依赖
- 需要穷尽式研究

**优先级**：fresh/verified 信息优先；需要时间关键信息时优先新鲜度。

**矛盾**：实质矛盾必须保留（下游自行裁决），不静默去重。

**不越权**：只选信息，不加工成结论（总结走 summarize），不改变语义。

## Outputs

- 紧凑上下文包（目标 + 必要事实 + 必要历史 + 约束 + 所需实体/关系）
- 保留的矛盾清单
- 被排除的信息范围说明（可选，用于可追溯）

## Interaction With Agent OS

- 为 **proactive/orchestrator/task-manager** 组装上下文（它们是被服务方）。
- 从 **memory/knowledge/ontology** 检索，从 **summarize** 取压缩结果。
- 作用域/关系解析依赖 **ontology**。

## Permission

只读检索 + 组装 = L0/L1，可自动。不涉及外部副作用。遵守 OpenClaw native policy。

## Verification

- 上下文包是否含完成此任务所需的最小必要信息？
- 是否遗漏关键实体/关系/依赖？
- 是否误删了实质矛盾或关键证据？
- 是否有无关噪音未去除？

## Failure Handling

- 检索不足 → 走扩展检索分支（confidence 低/依赖缺/要穷尽）。
- 上下文超预算 → 提高去噪力度或分层加载，而非盲目截断。
- 来源冲突 → 保留双方 + 标注，交下游。

## Memory / Knowledge Writeback

本模块不直接写记忆/知识；若发现关键信息缺失，提示走 memory/knowledge-governance 补录。若发现本体缺实体/关系，提示 ontology 提案。

## Self-Evolution Feedback

- 反复因「遗漏某类关键上下文」导致任务失败 → 上报检索策略改进 candidate。
- 反复因「去噪过度丢失关键信息」→ 上报去噪阈值改进 candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Context Engine、Memory Runtime；复用 OpenClaw 原生 agent loop / prompt assembly / session。
- 不因压缩而抹平矛盾或删关键证据。
- 不外泄无关上下文（隐私最小化）。

## Examples

- 「研究 AI Agent 方向」→ 取当前项目、相关目标、近期相关 memory、ontology 依赖，排除无关项目历史。
- 交易任务 → 取资金账户约束、行情时间戳知识、相关决策，排除无关社媒上下文。
- 上下文接近预算 → 只保留目标 + 已确认决策 + 冲突点 + 下一步，其余降级检索。
