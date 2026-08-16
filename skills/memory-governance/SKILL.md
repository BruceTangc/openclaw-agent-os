---
name: memory-governance
description: 决定什么该写进持久记忆、如何分层/晋升/清理；存储与召回由 OpenClaw 原生 memory 承担。记忆写入或复盘时触发。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.2", "layer": "core" } }
version: 1.2.0
---


# Memory Governance

## Purpose

决定「什么该成为持久记忆、存到哪一层、什么时候该清理」。OpenClaw 拥有存储 / 索引 / 召回能力，本模块只提供**治理政策**（写入筛选、分层、晋升、优先级、矛盾处理、清理），不负责物理存储。

核心区分：Memory 存经验/事件，Knowledge 存可复用声明，Ontology 存意义/关系。本模块只管 Memory。

## Scope

- 写入前判稳（是否值得持久化）
- 记忆分层（session / daily / durable / user-profile）
- 晋升路径与晋升条件
- 来源优先级与事实/推断区分
- 矛盾处理、去重、过期清理、敏感信息拦截

## Non-Goals

- 不实现存储、索引、向量召回（OpenClaw 拥有）
- 不管理知识声明（走 knowledge-governance）
- 不管理实体/关系（走 ontology）
- 不决定是否执行某动作（走 proactive/permission）
- 不建并行 memory database / runtime

## OpenClaw Boundary

只做治理政策判断，**复用 OpenClaw 原生 Memory Runtime / session / workspace 文件**。不创建自己的 Scheduler、Event Bus、Memory Runtime。写入动作由 OpenClaw 的 agent loop / 文件系统完成。

## When to Activate

- 会话收尾、复盘、总结时要决定「哪些值得记下来」
- 收到「记住这个 / 以后记住 / 别忘了」等指令时
- 周期性 memory 维护（合并、去重、清理过期条目）
- 检测到矛盾信息、敏感信息、重复操作笔记时

## Inputs

- 待判断的信息片段（observation）及其来源、时间、类型
- 用户明确表达的事实/偏好/约束
- 现有 memory 分层（session/daily/durable/user-profile）当前状态
- 冲突信号（同一主题出现不同说法）

## Core Procedure

本 Skill 只负责生命周期中的 **Writeback（记忆写入）** 节点：判定写什么、怎么分层晋升。存储/召回由 OpenClaw 原生 memory 承担。

1. **Intake**：确认信息片段 + 来源 + 时间 + 类型（事实/推断/偏好/事件）。
2. **写入判定（7 问）**，逐项 YES 才考虑持久化：
   - 稳定吗？（排除一次性噪音）
   - 以后有用吗？
   - 足够确定吗？
   - 来源可溯吗？
   - 冗余吗？（重复则跳过或合并）
   - 允许存吗？（Secret/敏感不存）
   - 会过期吗？（易过期 → daily 层，不进 durable）
3. **分层决策**：判定写入 session / daily / durable / user-profile 哪一层。
4. **晋升判定**（见 Decision Rules）。
5. **矛盾检查**：与现有条目冲突时保留、标注，不静默覆盖。
6. **写后检查**：可溯源？重复？敏感？需回写 ontology/knowledge？
7. **Writeback / Evolution**：长期清理/合并后，若有重复失败或治理缺陷，上报 evolution candidate。

## Decision Rules

**写入判定核心**：只有「稳定 ∧ 有用 ∧ 确定 ∧ 可溯源 ∧ 非冗余 ∧ 允许存」才持久化；否则留在 session 或丢弃。

**分层表**：

| 层 | 用途 | 特点 |
|:--|:--|:--|
| session context | 会话内 | 不持久 |
| daily memory | 日记层 | 高频更新，可定期清理 |
| durable memory | 长期（MEMORY.md） | 精选，人工/治理审核 |
| user-profile | 用户事实/长期偏好指令 | 最稳定 |

**晋升路径**：`observation → candidate → validate → promote → review`

- 观察→候选：出现且有复用价值
- 候选→验证：跨多次（≥ 独立会话）确认有效
- 验证→晋升：写入 durable memory
- 晋升→回顾：定期检查是否过时

**优先级（来源可信度）**：
`用户明确事实 > 已验证外部事实 > Agent 推断`

- 事实与推断必须分开标记；推断不得伪装成事实。

**矛盾处理**：重要矛盾**保留**，不静默覆盖，标注 disputed/unresolved 直到解决。

**敏感信息**：API key / token / 凭证 / 证件号 **绝不写入普通 memory**，只走 secret store。

**不建并行 runtime**：任何时候发现自己在实现存储/索引逻辑 = 跑偏，改用 OpenClaw 原生。

## Outputs

- 写入/不写入的决策 + 目标分层
- 晋升/降级/合并的候选动作
- 待解决矛盾清单
- 需清理的过期/重复条目清单
- （仅结构化时）memory_candidates 结构

## Interaction With Agent OS

- 收 **task-manager** 的复盘、**summarize** 的 memory_candidates、**self-evolution** 的沉淀经验，给它们写入判定。
- 为 **proactive / orchestrator** 提供历史经验检索依据。
- 结构化事实需要成为可复用声明时，转 **knowledge-governance**；需要语义关系时转 **ontology**。

## Permission

写入/清理普通 memory 文件属 L1（可逆本地写入），可自动。涉及删除历史、修改 user-profile 偏好、覆盖长期条目属 L2/L3，需确认/审批。遵守 OpenClaw native policy。

## Verification

- 写入是否可溯源（有来源/时间）？
- 是否与现有条目重复？
- 是否含敏感信息？
- 是否应回写 ontology/knowledge 做结构化？
- 晋升是否有 ≥2 独立会话的证据支撑？

## Failure Handling

- 判定不清 → 保守：留 session / daily，不晋升 durable。
- 矛盾无解 → 标记 Unresolved，保留双方，交人工。
- 清理误删风险 → 归档/trash 优先，不直接 delete。

## Memory / Knowledge Writeback

本模块自身即治理层：将「稳定偏好/约束」写入 user-profile，将「可复用事实」转 knowledge-governance，将「经验」记录到 daily/durable。写后记录治理决策便于追溯。

## Self-Evolution Feedback

- 反复出现「本应持久化但未记」或「误将噪音持久化」→ 上报 selection-criteria 改进 candidate。
- 矛盾频繁且无法自动解析 → 上报 contradiction-handling 改进 candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Memory Runtime、Context Engine；复用 OpenClaw 原生。
- 不静默覆盖重要矛盾；不把推断当事实；不存 Secret。
- 同一信息反复触发写入判断 → 去重，不重复写入。

## Examples

- 「以后都给我完整方案」（用户明确偏好、跨会话稳定）→ user-profile 候选。
- 一次对话里的临时变量 → 仅 session，不持久。
- 某 API 反复超时（跨 3 次独立会话，已验证）→ durable lesson。
- 用户 A 说「喜欢详细」，用户 B 上下文说「要结论」→ 保留矛盾并按作用域区分，不覆盖。
