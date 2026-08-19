---
name: orchestrator
description: 决定任务如何分解、按什么顺序、由谁执行并生成执行计划；执行走 OpenClaw 原生。拆分或路由任务时触发。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.3", "layer": "core" } }
version: 1.3.0
---


# Orchestrator

## Purpose

决定「怎么组织已有能力完成目标」：拆解、委派、排序、路由、执行、验证。核心原则：目标优先而非工具优先、能力复用而非重复造轮子、最简单路径优先。OpenClaw 仍是运行时。

## Scope

- 意图理解 + Goal 建模 + 成功条件
- 任务拆解（DAG）+ 依赖 / 并行 / 条件 / 循环
- 能力匹配 + Agent/Skill 路由
- 权限门 + 风险门 + 资源预算
- 执行计划控制 / 执行状态协调 / 重试策略 / 重新规划 / checkpoint / fallback
- 结果验证 + 合成（围绕用户目标）
- 反馈（Memory/Ontology/Self-Evolution）

## Non-Goals

- 不「会什么」（具体能力由 Skill/Agent 提供），只负责组织和调度
- 不保存任务生命周期状态（走 task-manager）
- 不复制 Ontology / Memory / 业务 Skill
- 不建并行 task runtime / scheduler

## OpenClaw Boundary

复用 OpenClaw 原生 Sub-agents / Task Flow / Skills / Tools / agent loop。**不创建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime、Agent Runtime**。scripts/orchestrator.py 是纯函数逻辑层（parse/goal/decompose/dag/route/plan/verify/evol），不持久化状态。

## When to Activate

- 收到 orchestration_request（user/proactive/workflow/event/agent）
- 任务需要拆解、路由、多 Agent 协作、结果合成

## Inputs

```yaml
orchestration_request:
  id: "req_xxx"
  source: "user|proactive|workflow|event|agent"
  objective: "..."
  context: {}
  constraints: []
  deadline: null
  priority: 0
  risk_level: "low|medium|high|critical"
  requested_output: {}
  permissions: []
```

## Core Procedure

本 Skill 只负责生命周期中的 **Decision→Action 之间的编排** 节点：决定怎么拆、谁做、什么顺序。实际执行走 OpenClaw 原生。

1. **意图理解**：识别 Goal/Scope/Constraints/期望输出/Deadline/优先级/风险/成功条件。
2. **Goal 建模**：目标不清晰 → ASK（不猜重大目标）。
3. **复杂度路由**：L0 单 Skill 直调 → 不够才拆（No-Overengineering）。
4. **拆解**：`decompose` 生成 Task；建 DAG（`dag` + 环检测）。
5. **能力匹配**：`route` 按 capability/reliability/output/permission/风险/成本/延迟选择执行者。
6. **权限/风险门**：逐 Task 权限门 + Risk Gate；L2+ 走 permission-security。
7. **预算**：设 max_runtime/tool_calls/parallel/retries/iterations；超限 STOP+REPORT+ASK/REPLAN。
8. **执行**：有依赖串行，独立并行（冲突→SERIALIZE）；检查幂等/去重/并发控制。
9. **验证**：`verify` V0–V4；高风险优先 V3/V4。
10. **失败处理**：分类→重试/backoff/replan/fallback/escalate。
11. **结果合成**：围绕用户目标，非机械拼接；冲突解决按来源/时间/证据/置信度。
12. **Writeback / Evolution**：更新 Memory/Ontology，稳定失败→Evolution Candidate。

## Decision Rules

**复杂度路由**：L0 单 Skill；L1 单任务+验证；L2 2–3 任务；L3 多任务 DAG；L4 多 Agent+多阶段+Replan；L5 长期 autonomous workflow。简单任务（如「总结文本」）直接 Summarize，不建复杂 DAG。

**路由优先级**：1 能完成任务 2 权限满足 3 输出匹配 4 历史成功率 5 可靠性 6 风险 7 成本 8 延迟。高风险优先可靠性，低风险探索可优先成本/速度。不因省钱选明显不可靠能力。

**权限门**：READ/SEARCH/WRITE/EXECUTE/DELETE/EXTERNAL_SEND/FINANCIAL/ADMIN。不足时不绕过、不降级伪装、不换方式规避。

**风险门**：LOW 授权范围自动；MEDIUM 按策略执行/提醒；HIGH 默认 ASK；CRITICAL 默认禁止自动。

**高风险默认确认**：真实资金/交易/转账/重要订单/删重要数据/改生产/改权限/公开发布/重要外发/法律承诺/不可逆。

**重试**：max_retries=2；temporary/network→retry；rate_limit→backoff；invalid_input/logic_error→replan；permission→ASK；unknown→ESCALATE。不无限重试。

**失败后 replan**（不盲目从头）：关键任务失败/外部条件变/新事实/原路径不可用/超预算/权限变/结果不符预期。

**并发**：read-read 并行；read-write 受控；write-write 串行；delete 独占。

## Outputs

```yaml
orchestration_result:
  request_id: "xxx"
  status: "completed|partial|failed|waiting"
  plan_id: "plan_xxx"
  summary: "xxx"
  completed_tasks: ["T1"]
  pending_tasks: ["T3"]
  artifacts: ["xxx"]
  next_action: null
  confidence: 0.88
```

## Interaction With Agent OS

- 接收 **proactive** 的 orchestration_request，返回 orchestration_result。
- 可执行任务由 **task-manager** 提供（get_ready_tasks），结果回写 task-manager。
- 读 **ontology** 世界模型、**memory** 历史经验辅助路由。
- 权限判断走 **permission-security**；验证走 **verification-evaluation**；失败模式提 **self-evolution**。

## Permission

按 Task 权限门 + Risk Gate；副作用走 permission-security。遵守 OpenClaw native policy / sub-agent 权限（不自动继承）。

## Verification

- V0–V4 分级验证，不把 tool_success 当 task_success。
- 高风险任务优先 V3/V4。
- 结果冲突：检查来源/时间/证据/置信度，不简单多数投票；无法判断 → ASK/ESCALATE。

## Failure Handling

重试（有限）→ backoff → replan → fallback（主执行者失败且兼容才换，高风险不因失败自动换执行者重复副作用）→ cancel（记录已发生副作用+checkpoint，不假装取消）→ escalate。

## Memory / Knowledge Writeback

长期经验/稳定模式/重要结果/用户反馈→memory-governance；新 Person/Project/Task/Goal/关系→ontology；不写临时变量/重复/低价值日志。

## Self-Evolution Feedback

成功率/失败率/重试次数/成本/延迟/人工干预/用户反馈/路由选择统计；Skill 连败/Agent 明显更优/工作流冗余/能力缺失 → evolution_candidate（requires_approval=true）。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime、Agent Runtime；复用 OpenClaw 原生。
- 目标优先；不重复造轮子；不复杂化；不无谓并行；不机械拼接；不泄漏无关上下文；不擅自改用户目标；不覆盖用户停止/暂停指令。

## Examples

```bash
python3 scripts/orchestrator.py parse --json '{"objective":"...","risk_level":"low"}'
python3 scripts/orchestrator.py decompose --json '{"objective":"研究并总结"}'
python3 scripts/orchestrator.py dag --json '[{"id":"T1"},{"id":"T2"}]' --edges "T1-T2"
python3 scripts/orchestrator.py route --type research --risk low
python3 scripts/orchestrator.py plan --json '{"objective":"..."}'
python3 scripts/orchestrator.py verify --json '{"tool_success":true,"output":"ok"}' --level V3
python3 scripts/orchestrator.py evol --category skill --problem "..." --change "..."
```

详细模型（Goal/Task/DAG/执行计划/路由/重试/checkpoint）见 `references/execution-model.md`。

## Multi-Agent Contract（PROTOCOL.md §8）

对齐统一 10 项契约，本 Skill 涉及: 1,2,4,6,7,8,9,10（编排/委派须保留 provenance；Child 权限只减不增）。不重写已有机制；跨 Agent 场景以 PROTOCOL.md §8 总规则 + 本 SKILL.md 对应章节为准。
