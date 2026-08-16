---
name: task-manager
description: 任务操作系统（Agent OS v1.2 核心模块）。统一管理用户/Agent/Proactive/Workflow 任务：生命周期、优先级、依赖、分解、分配、状态、等待、阻塞、重试、超期、Follow-up、去重、Checkpoint、验证、归档、指标。与 Proactive、Orchestrator、Ontology、Memory、Self-Evolution 协同。管「任务是什么及其状态」，Orchestrator 管「怎么执行」。不是普通 Todo Skill。在任务创建、状态流转、跟进、复盘时触发。
version: 1.2.0
x-agent-os:
  protocol_version: "1.2"
  layer: "core"
---

# Task Manager

## Purpose

管理「任务是什么 + 处于什么状态 + 下一步是什么」。核心区分：Goal=期望结果，Task=具体工作，Step=组件，Runtime task=OpenClaw 执行记录。`memory/tasks.json` 是任务语义索引/缓存，不是执行运行时；真正执行走 OpenClaw 原生 Background Tasks / Task Flow / Sub-agents / Cron。

## Scope

- 任务标准化（normalize）+ 去重 + 优先级重算
- 完整生命周期状态机 + 状态转换校验
- 优先级 P0–P4 / 截止 / 依赖 / Parent-Child / Owner-Assignee
- Waiting/Blocked/Retry/Follow-up/超期/停滞检测
- Checkpoint / 幂等 / 崩溃恢复 / 归档 / 指标
- 联动 Proactive/Orchestrator/Ontology/Memory/Self-Evolution

## Non-Goals

- 不执行具体业务（走 orchestrator）
- 不拆解/路由（走 orchestrator）
- 不建并行 task database / runtime（tasks.json 只是索引）
- 不保存世界关系（走 ontology）、不存历史经验（走 memory）

## OpenClaw Boundary

复用 OpenClaw 原生 Task/Automation runtime、Background Tasks、Task Flow、Sub-agents、Cron。**不创建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime**。scripts/task_manager.py 提供创建/查询/状态机校验，scripts/link.py 提供跨模块联动。

## When to Activate

- 创建/修改/分配/暂停/恢复/取消/重试/完成/归档任务
- 扫描超期/停滞/阻塞/等待/目标偏移
- 每日/每周任务复盘
- 需要把 Proactive 信号转任务、把 READY 任务交 Orchestrator

## Inputs

```yaml
task:
  id: "task_xxx"
  title: "..."
  description: "..."
  source: { type: "user|proactive|workflow|event|agent|system", id: null }
  goal_id: null
  project_id: null
  parent_task_id: null
  type: ["research"]
  status: "inbox"
  priority: { level: "P0|P1|P2|P3|P4", score: 0 }
  owner: { type: "user|agent|skill", id: null }
  assignee: { type: "agent|skill|user", id: null }
  dependencies: []
  blocked_by: []
  due_at: null
  recurrence: null
  risk_level: "low"
  required_permissions: []
  success_conditions: []
  verification_level: "V1"
  inputs: []
  outputs: []
  context: {}
  tags: []
  metadata: {}
  created_at: "ISO-8601"
  completed_at: null
```

## Core Procedure

统一执行链：Trigger → Intake → Context → Goal/Task → Decision → Permission → Action → Verification → Evaluation → Writeback → Evolution

1. **接收任务**（user/proactive/orchestrator/workflow/event/agent/system）。
2. **Normalize**：统一成标准 task 结构。
3. **Deduplicate**：request_id/source_id/goal_id/标题/语义相似/活跃任务 → 有则 MERGE。
4. **优先级重算**：不盲信 priority_hint；P0 紧急关键 / P1 高 / P2 正常 / P3 低 / P4 backlog。
5. **关联 goal/project + 依赖检查**。
6. **入 Ready Queue**（READY + 依赖满足 + 权限 + 未暂停 + 预算）。
7. **交 Orchestrator**（get_ready_tasks → execution_request）。
8. **收结果回写**（result-to-task：状态机中转）。**完成须满足 success_conditions + verification**，不因 Agent 说「完成」就完成。
9. **Waiting/Blocked/超期 → Follow-up**，外部发送过 Permission Gate。
10. **failed → retry/replan**；completed → review → archived。
11. **扫描**（overdue/stale/blocked/waiting/goal_drift）交 Proactive。
12. **Writeback / Evolution**：同步 ontology、写 memory、失败模式上报 evolution。

## Decision Rules

**生命周期状态**：INBOX→PLANNED→READY→RUNNING→（WAITING/BLOCKED/PAUSED/RETRYING→READY，FAILED，COMPLETED→REVIEW→ARCHIVED，CANCELLED）。禁止任意跳转（FAILED→COMPLETED 须先重执行或人工确认）。

**去重/MERGE**：保留最早创建时间、最高优先级、最严 deadline、最完整上下文、所有来源引用；新信息追加到 context/history/source_refs。

**优先级分数**：`impact + urgency + goal_alignment + deadline_pressure + dependency_impact + proactive_confidence − effort − risk` → 映射 P0–P4。

**Owner/Assignee 区分**：Owner=谁负责，Assignee=谁在执行，Executor=实际执行者（如 Agent Browser）。

**超期 ≠ 失败**：超期标 OVERDUE（派生属性），重新评分交 Proactive，不立即打扰用户。

**完成判定**：success_conditions + verification 都满足 → COMPLETED；部分满足 → RUNNING/REVIEW，不误标完成。

**递归任务防爆**：错过多次运行默认 latest_only（不一次补执行几十次）。

**公平性**：低优先级积压任务获 aging bonus（避免 backlog 永久不处理）。

**Safe Defaults**：低风险任务自动创建/执行允许；外部沟通/资金/删除/无限重试/无限通知默认禁止。

**简单任务不复杂化**：直接调用能力，不建复杂 DAG。

## Outputs

- 标准 task + 状态
- scan 信号（overdue/stale/blocked/waiting/goal_drift）
- execution_request（交 orchestrator）
- digest 摘要报告

## Interaction With Agent OS

- 收 **proactive** 的 create_task / task_query，返回 task_signals。
- 给 **orchestrator** READY 任务，收执行结果回写状态。
- 重要任务关系同步 **ontology**；经验写 **memory**；失败/阻塞模式上报 **self-evolution**。
- 验证走 **verification-evaluation**，权限走 **permission-security**。

## Permission

创建/更新普通任务 = L1（本地可逆）可自动；外部沟通/资金/删除/权限变更 = L2/L3 过 permission-security。遵守 OpenClaw native policy。

## Verification

- 状态转换是否合法（状态机校验，stats）？
- 完成是否满足 success_conditions + verification_level？
- 是否有重复任务（去重）？
- 幂等：副作用任务是否带 operation_id 防重复？

## Failure Handling

temporary/network→retry；rate_limit→backoff；invalid_input/logic_error→replan；permission→ask；unknown→escalate。max_retries=2，不无限重试。崩溃恢复：扫 RUNNING→查 lock→查 checkpoint→查副作用→resume/retry/wait/fail，不简单全 FAILED。

## Memory / Knowledge Writeback

重要经验/稳定模式/用户反馈/重大结果/失败原因→memory-governance；普通状态变化/临时变量/重复日志不存。任务关系同步 ontology。

## Self-Evolution Feedback

统计 task 成功率/失败率/重试率/超期率/人工接管率/平均周期/路由成功率；异常模式 → evolution_candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime；复用 OpenClaw 原生。
- 同一事件不无限创建、同任务不无限 Follow-up、同失败不无限 Retry（source_id/request_id/dedup_key/cooldown/max_attempts）。
- 超期≠失败；Waiting≠Done；Agent 不无限制造任务；Proactive 不无限打扰。

## Examples

```bash
python3 scripts/task_manager.py create --json '{...}' [--merge]
python3 scripts/task_manager.py list [--status X] [--priority P] [--limit N]
python3 scripts/task_manager.py scan                # overdue/stale/blocked/waiting/goal_drift
python3 scripts/task_manager.py metrics
python3 scripts/link.py proactive-to-task --signal '{...}'
python3 scripts/link.py tasks-to-orchestrator [--limit 10]
python3 scripts/link.py result-to-task --json '{...}' [--verify]
python3 scripts/link.py all [--min-level P1]
```

详细模型（状态机/优先级/依赖/checkpoint/联动/指标）见 `references/task-model.md`、`references/lifecycle-model.md`。
