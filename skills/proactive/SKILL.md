---
name: proactive
description: 在 Heartbeat/Cron/Hook 或事件唤醒后判断是否有值得主动处理的事项，并在授权范围内采取行动或提醒。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.2", "layer": "core" } }
version: 1.2.0
---


# Proactive

## Purpose

被 OpenClaw 唤醒后（Heartbeat / Cron / Hook / 事件 / 用户消息），决定「现在是否值得做、做什么」。是**主动决策层**，不是定时触发机制。核心原则：主动但不骚扰，自主但不越权，NO_ACTION 是合法结果。

## Scope

- 感知环境/任务/项目/目标/系统状态变化，转为 Signal
- Cheap Filter（低成本过滤）+ Context Enrichment
- 发现 Opportunity / Risk / Anomaly / Goal Drift / Follow-up
- 计算优先级 + Autonomy Gate + Risk Gate → Decision
- Action Router（调用已有 Skill/Agent，不自己实现业务）
- 验证 + 结果记录 + 反馈学习 + 每日/每周复盘

## Non-Goals

- 不建 Scheduler（Cron/Heartbeat 是 OpenClaw 的）
- 不重复实现业务 Skill（财务/交易/搜索/总结/文件…）
- 不自己执行高风险动作（默认 ASK）
- 不为「显得主动」而制造任务

## OpenClaw Boundary

复用 OpenClaw 原生 agent loop / Heartbeat / Automation(Cron) / Hooks / Standing Orders / Tasks / Task Flow / Sub-agents。**不创建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime、Context Engine 或 Agent Runtime**。Cron 只唤醒，决策在本模块。

## When to Activate

- Heartbeat / Cron / Hook / 事件唤醒、用户消息、Watch 到期（next_review_at）
- 需要判断「有没有值得做的事」时

## Inputs

- 当前 Proactive State、Ontology（目标/项目/未完成任务/最近事件）、Queue（P0–P4）、最近失败、最近新增信息
- 新 Signal（id/source/type/subject/evidence/confidence/freshness/novelty）

## Core Procedure

本 Skill 只负责生命周期中的 **Decision（决策）** 节点：被唤醒后判断是否值得做。系统其余环节由其他 Skill / OpenClaw 承担，本 Skill 不自行跑完整生命周期。

1. **唤醒打点**：`state --op wake`（单实例锁，过近且无新 Signal → NO_ACTION）。
2. **读检查源**：按 OpenClaw heartbeat prompt，读工作区 `HEARTBEAT.md`（每轮该检查什么）+ `proactive-registry.yaml`（当前启用的主动关注项），只筛 `enabled: true` 且本轮条件满足的项目；不因项目存在就全部执行。
2. **读状态**：State + Ontology + Queue + 最近失败（只读相关，不全量）。
3. **Intake**：摄入新 Signal（`signal --json`）。
4. **Cheap Filter**：重复?已处理?过期?低价值?无行动空间?超出关注范围?普通信息?噪音? → 直接 IGNORE。
5. **Context Enrichment**：高价值 Signal 读相关目标/任务/历史/关系/最近事件。
6. **判断类型**：Risk / Opportunity / Goal Drift / Follow-up / Anomaly。
7. **评分**：priority = value×urgency×confidence×novelty×goal_alignment×actionability ÷ (effort×risk×interruption)。
8. **Decision**（统一词汇表）：IGNORE/OBSERVE/QUEUE/SUGGEST/PREPARE/EXECUTE/ASK/ESCALATE。
9. **Autonomy Gate**：已授权?风险可接受?需确认?涉钱/外发/删除/权限/敏感/系统状态/超预算?
10. **Permission Gate**：副作用前走 permission-security。
11. **执行/入队**：Action Router 调用现有 Skill/Agent 或入 Queue。
12. **Verification**：不把工具成功当任务成功。
13. **记录 Outcome**：写 semantic state + candidate bump（更新注意力/队列，供下次唤醒参考）。

**State/Queue/Bus 边界定义**（防隐性 Runtime）：
- **State** = Proactive 的**语义状态**（上次唤醒时点、注意力预算、目标对齐），不是执行运行时状态机。
- **Queue** = **语义候选集合**（哪些事值得关注/入列），不是实际执行队列；实际调度由 OpenClaw Heartbeat/Cron/Task Flow 驱动。
- **Bus/输入通道** = 复用 OpenClaw 的 event/input channel，Proactive 自己**不能成为事件总线**。
14. **产出 Writeback/Evolution candidate**：识别应写入 Ontology/Memory 或应建议改进的点，产出 memory/knowledge/ontology/evolution 候选交给对应治理层，**不直接负责治理写入**；低频经验不打扰、不裸写。
15. **无价值 → NO_ACTION**。

## Decision Rules

**决策词汇表（唯一真值）**：IGNORE / OBSERVE / QUEUE / SUGGEST / PREPARE / EXECUTE / ASK / ESCALATE（DENY 由 permission-security 输出）。NOOP≈IGNORE，INFORM≈SUGGEST，ACT≈EXECUTE。

**评分→默认策略**：0–20 IGNORE；20–40 OBSERVE；40–60 QUEUE；60–75 SUGGEST；75–90 PREPARE/低风险 EXECUTE；90–100 高优先级。评分非绝对，Risk Gate 与用户授权优先。

**优先级覆盖**：Safety > 用户明确指令 > Permission > Critical Risk > Deadline > Goal Alignment > 高价值机会 > 常规优化 > 低价值信息。主动性不覆盖用户明确指令。

**Autonomy Gate 默认 ASK**：转账/下单/买卖资产/外发重要消息/删重要数据/改权限/改生产系统/公开发布/重大承诺/任何不可逆高风险。

**反骚扰**：同信号无新证据不重复提醒（冷却见 references/attention-model.md）。

**反幻觉**：证据不足 → confidence↓ 或 OBSERVE/ASK；禁止猜用户意图/外部事实/任务完成/交易结果。

## Outputs

- 决策 + score + reason
- 执行结果 / 入队 / NO_ACTION
- 主动提醒格式（【主动发现】【主动处理完成】【需要你确认】）

## Interaction With Agent OS

- 发现值得做 → 交 **orchestrator** 执行（orchestration_request）。
- 值得做的事 → 交 **task-manager** 创建/管理任务。
- 读 **ontology** 世界模型，读 **summarize** 压缩结果。
- 长期失败/能力缺口 → 提 **self-evolution** candidate。
- 权限判断 → **permission-security**。

## Permission

低风险可逆已授权动作可自动；涉钱/外发/删除/权限/生产/不可逆 → ASK（过 permission-security）。遵守 OpenClaw native policy。

## Verification

- 执行结果是否满足 success_condition（不把工具成功当任务成功）？
- 副作用是否 actual ≤ authorized？
- 主动行为是否可追踪、有 Outcome 记录？

## Failure Handling

- temporary→retry；tool→调参重试；data→补数据；permission→ASK；logic→replan；external→WAIT；unknown→ESCALATE。不无限重试。

## Memory / Knowledge Writeback

短期 Signal/Queue/Plan；中期反馈；长期授权/偏好/已验证策略/被禁行为。不存无价值噪音。长期经验走 memory-governance。

## Self-Evolution Feedback

同类任务连续失败 ≥3 / 同类建议连续被拒 ≥3 / 重复人工纠正 ≥3 / 能力缺口 / 流程冗余 → Evolution Candidate（requires_approval=true）。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime、Context Engine、Agent Runtime；复用 OpenClaw 原生。
- 无新证据不重复提醒（action_signature + cooldown）。
- 不因 Cron 唤醒就必须做事；NO_ACTION 合法。
- 不为主动而主动；不绕过权限；不把推测当事实。

## Examples

- 项目偏离（连续建孤立 Skill，核心调度未推进，drift=0.81）→ SUGGEST。
- 新工具与项目高相关/低风险 → PREPARE（Agent Browser 研究 + Summarize）。
- 自动化任务连败 3 次 → ESCALATE + Self-Evolution candidate。
- 交易机会（涉真实资金/高风险）→ ASK，禁止自动下单，只整理分析。
- 无值得做 → NO_ACTION。

详细模型（Signal/Opportunity/Risk/Goal Drift/优先级/Autonomy/注意力/状态）见 `references/signal-model.md`、`references/priority-model.md`、`references/attention-model.md`。

## Scripts

```bash
python3 scripts/proactive.py state --op show          # 读状态
python3 scripts/proactive.py state --op wake          # 唤醒打点
python3 scripts/proactive.py signal --json '<Signal>' # 摄入信号
python3 scripts/proactive.py filter --json '...'      # Cheap Filter 测试
python3 scripts/proactive.py score --json '...'       # 优先级评分
python3 scripts/proactive.py decision --json '...'    # 决策
python3 scripts/proactive.py queue --op list          # 维护队列
python3 scripts/proactive.py evol --json '...'        # 生成进化候选
python3 scripts/proactive.py noop                    # NO_ACTION 标记
```
