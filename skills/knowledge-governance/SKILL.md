---
name: knowledge-governance
description: 把可复用知识治理为带来源/新鲜度/置信度的持久声明，处理矛盾保留与历史标记。知识录入或冲突时触发。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.3", "layer": "core" } }
version: 1.3.0
---


# Knowledge Governance

## Purpose

把可复用知识整理为**带来源、新鲜度、不确定性的持久声明（claim）**，并治理其生命周期。与 memory-governance 区别：Memory = 经验/事件；Knowledge = 可复用的「关于世界的声明」（subject/claim/evidence…）。物理持久化使用 OpenClaw native memory/workspace 设施或已安装的 knowledge provider/plugin，本模块只做治理（不把 Agent OS 的 Knowledge 抽象说成 OpenClaw 原生 Knowledge Runtime）。

## Scope

- 声明的标准化（subject / claim / evidence / confidence / freshness / validity / status）
- 知识摄入管线（source → extract → normalize → provenance → contradiction check → confidence → retain/publish）
- 矛盾保留、obsolete/disputed 标记、历史保留
- 新鲜度衰减与失效判定
- 声明升级为 Decision 的建议（走 self-evolution）

## Non-Goals

- 不实现知识检索/向量存储（OpenClaw 拥有）
- 不管经验/事件（走 memory-governance）
- 不管实体/关系建模（走 ontology）
- 不建并行 knowledge runtime / 第二套知识库

## OpenClaw Boundary

只做声明治理政策，复用 OpenClaw 原生 knowledge/memory 设施。不创建自己的 Scheduler、Event Bus、Knowledge Runtime。写入由 OpenClaw agent loop / 文件系统完成。

## When to Activate

- 把零散信息整理成「可复用的声明」时
- 知识更新、出现矛盾、旧知识过时时
- summarize 产出 facts/claims 需要持久化时
- 需要把高置信声明升级为约束（Decision）时

## Inputs

- 来源素材 + 提取出的 fact/claim
- 已有相关声明（用于矛盾/重复检查）
- 来源属性（author/date/type/可信度）

## Core Procedure

本 Skill 只负责生命周期中的 **Writeback（知识写入）** 节点：把可复用知识治理为持久声明。物理持久化用 OpenClaw memory/插件。

1. **Intake**：来源 + 原始信息 + 提取出的声明。
2. **Extract/Normalize**：落地为 subject/claim/evidence 结构。
3. **Provenance**：记录来源、时间、类型（source_stated / model_inferred / user_asserted）。
4. **Contradiction check**：与现有声明比对，检测直接/部分矛盾、supersede、obsolete、scope 例外。
5. **Confidence/freshness**：定 confidence（0-1）与 freshness（0-1）。
6. **Retain/Publish**：决定保留/更新/标记 obsolete/标记 disputed，或发布为可复用声明。
7. **Writeback / Evolution**：更新失败/矛盾高发 → 上报治理改进 candidate。

## Decision Rules

**声明标准字段**（不可省）：
`subject / claim / evidence / confidence / freshness / validity / status`

**状态**：`active / obsolete / disputed / superseded`

**摄入规则**：
- source_stated ≠ model_inferred，后者必须标注，不得伪装成事实。
- 缺证据的声明 confidence 必须压低，validity 标 uncertain。

**矛盾处理**：不静默覆盖；保留历史，旧声明标 `obsolete` 或 `disputed`（附 superseded_by 指向新声明）。

**失效判定**：freshness 低 + 无新证据 + 上下文（工具版本/环境）已变 → 标 obsolete，而非删除。

**升级边界**：高置信且带行动约束力的声明 → 建议升级为 Decision（交 self-evolution governance），本模块只建议，不直接改行为。

**不建第二知识 runtime**：发现自己实现检索/向量 → 跑偏。

## Outputs

- 标准化声明（含 provenance/confidence/freshness/status）
- 矛盾清单与处置结果
- obsolete/disputed 标记结果
- 建议升级为 Decision 的候选

## Interaction With Agent OS

- 收 **summarize** 的 facts/claims、**memory-governance** 转来的可复用事实。
- 为 **ontology** 提供可结构化语义（实体/关系候选）。
- 高置信约束建议交 **self-evolution** 走 Decision 提案。
- 为 **proactive/orchestrator** 提供「关于世界」的知识检索依据。

## Permission

新增/更新普通知识声明 = L1（本地可逆写入）可自动。覆盖既有声明、删除历史、发布为跨作用域规则 = L2/L3 需确认/审批。遵守 OpenClaw native policy。

## Verification

- 每个声明是否有来源/时间/类型？
- 是否与现有声明矛盾（未处理）？
- confidence/freshness 是否有依据？
- 是否把 model_inferred 写成了 source_stated？

## Failure Handling

- 来源不明 → confidence 压低，标 uncertain。
- 矛盾无法解析 → 保留双方 + 标 disputed，交人工。
- 误标 obsolete → 保留历史可回滚，不删除。

## Memory / Knowledge Writeback

本模块是知识治理层本身：把已验证声明写入知识库，把「需要结构化语义」的项转 ontology，把「升级为约束」的项转 self-evolution Decision 提案。写后记录 provenance 与状态变更。

## Self-Evolution Feedback

- 反复出现「model_inferred 被当事实」→ 上报 provenance 改进 candidate。
- 矛盾高发/无法收敛 → 上报 contradiction-resolution 改进 candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Knowledge Runtime、Memory Runtime；复用 OpenClaw 原生。
- 不静默覆盖知识；不删除历史（标 obsolete 代替）。
- 不因减少上下文而删除有用知识。

## Multi-Agent Knowledge Contract（MA-1.0）

多 Agent 横向协作时，知识治理必须保留 Agent 来源并做 scope 隔离（对齐规格第 10 条）。

### 10.1 Knowledge Provenance

每条声明除 subject/claim/evidence 外，跨 Agent 时必须额外保留：
`source_agent_id / source_task_id / source_execution_id / source_evidence / confidence / freshness`。
Agent B 引用 Agent A 的知识时，不得抹掉来源、不得把 A 的声明当成 B 自己验证过的事实。

### 10.2 Agent-local Knowledge

默认 `scope = AGENT`、`owner_id = 当前 agent`。Agent-local 知识不被其它 Agent 隐式读取。

### 10.3 Shared Knowledge 走 Governance

跨 Agent 共享（PROJECT/USER/GLOBAL scope）必须：
`Agent A → Knowledge Candidate → Contradiction Check → Provenance Check → Governance → PROJECT/USER/GLOBAL`。
禁止 Agent A 直接写 GLOBAL。

### 10.4 Conflict 不静默覆盖

Research 声称 X、Trading 声称 Y 时：不得静默 A+B=TRUE，必须 `CONFLICT` + 保留双方
（标 disputed）+ 交上层 resolve 或补证据。

## Examples

- 「API X 返回字段 Y 需校验时间戳」→ 声明（source_stated + evidence）→ active。
- 「用户倾向详细回答」旧声明遇到「要结论」新指令 → 旧标 superseded，新 active。
- 工具版本升级使某知识失效 → 标 obsolete + superseded_by。
- 两来源对同一事实矛盾且都无更强证据 → 都保留 + disputed，交人工。

## Multi-Agent Contract（PROTOCOL.md §8）

对齐统一 10 项契约，本 Skill 涉及: 1,2,3,4,5,6,10（Shared Knowledge 须经 governance，见 SKILL.md §10）。不重写已有机制；跨 Agent 场景以 PROTOCOL.md §8 总规则 + 本 SKILL.md 对应章节为准。
