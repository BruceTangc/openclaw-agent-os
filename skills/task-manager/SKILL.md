---
name: task-manager
version: 1.1.0
description: OpenClaw Agent Task Operating System。统一管理用户任务、Agent任务、Proactive产生的任务和Workflow任务，负责任务生命周期、优先级、依赖、分解、分配、状态、等待、阻塞、重试、超期、Follow-up、去重、Checkpoint、验证、归档、指标，并与 Proactive、Orchestrator、Ontology、Memory、Self-Evolution 协同。不是普通 Todo Skill。
---
# Agent OS v1.1 Policy（正式版政策层, 来自整合包）

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Task Manager

Purpose: manage goal/task semantics while OpenClaw owns task runtime.

Goal = desired outcome.
Task = concrete work.
Step = component.
Runtime task = OpenClaw execution record.

## Procedure
1. Parse outcome.
2. Define success criteria.
3. Identify constraints/dependencies.
4. Break into useful tasks.
5. Set priority and due conditions.
6. Choose native Task Flow/sub-agent execution when useful.
7. Track planned/ready/active/waiting/blocked/completed/failed/cancelled.
8. Verify consequential completion.
9. Send durable lessons through memory/knowledge governance.

Never create a parallel task database/runtime.

---


---

# 存储架构说明（Agent OS v1.1 对齐）

> `memory/tasks.json` 是**任务语义索引/缓存**（state representation），不是执行运行时。
> 真正执行仍走 OpenClaw 原生：Background Tasks / Task Flow / Sub-agents / Cron。
> 不建并行 task database/runtime（v1.1 policy §Never create a parallel task database/runtime）。

# 本地实现部分（完整版, 保留）

# Task Manager v1.0

## 0. 定位

Task Manager 是 OpenClaw 的统一任务状态层。

核心回答：

> 现在有哪些任务？为什么存在？谁负责？做到哪了？下一步是什么？什么时候需要继续？什么时候算完成？

职责：

1. 接收用户、Proactive、Orchestrator、Workflow、Event 创建的任务。
2. 标准化任务结构。
3. 管理完整生命周期。
4. 管理优先级、截止时间和依赖。
5. 管理 Parent/Child Task。
6. 管理 Agent/Skill Owner。
7. 管理 Waiting / Blocked / Failed。
8. 管理 Retry / Follow-up。
9. 自动发现超期、停滞和重复任务。
10. 为 Orchestrator 提供可执行任务。
11. 为 Proactive 提供任务状态和主动跟进依据。
12. 将重要任务关系同步到 Ontology。
13. 将任务经验写入 Memory。
14. 将稳定问题反馈给 Self-Evolution。
15. 保证任务可追踪、可恢复、可验证。

核心原则：

> Task Manager 管“任务是什么以及处于什么状态”；Orchestrator 管“任务怎么执行”。

---

# 1. 与核心系统边界

## Proactive

Proactive：

> 发现值得做的事情。

Task Manager：

> 把值得做的事情变成可管理任务。

---

## Orchestrator

Orchestrator：

> 拆解、路由、执行。

Task Manager：

> 保存任务、状态、依赖、截止时间和执行历史。

---

## Ontology

Ontology：

> 世界模型。

Task Manager：

> 任务运行模型。

任务涉及：

- Project
- Goal
- Person
- Event
- Resource

时，应通过 Ontology 建立关系。

---

## Memory

Memory：

> 经验与历史。

Task Manager：

> 当前任务状态。

不要把所有任务状态都复制到长期 Memory。

---

## Self-Evolution

Task Manager 负责提供：

- 失败率
- 超期率
- 重试率
- 人工接管率
- 完成时间
- 路由表现

供 Self-Evolution 分析。

---

# 2. 总体架构

```text
User
Proactive
Workflow
Event
Agent
   ↓
Task Manager
   ↓
Normalize
   ↓
Deduplicate
   ↓
Prioritize
   ↓
Dependency Check
   ↓
Ready Queue
   ↓
Orchestrator
   ↓
Execution
   ↓
Verification
   ↓
Task Manager
   ↓
Done / Failed / Waiting / Blocked
   ↓
Follow-up
   ↓
Memory / Ontology / Self-Evolution
```

---

# 3. Task 来源

支持：

```text
user
proactive
orchestrator
workflow
event
agent
system
```

所有来源统一进入 Task Manager。

---

# 4. Task 标准结构

```yaml
task:
  id: "task_xxx"

  title: "任务标题"

  description: "任务描述"

  source:
    type: "user|proactive|workflow|event|agent|system"
    id: null

  goal_id: null
  project_id: null
  parent_task_id: null

  type:
    - "research"

  status: "inbox"

  priority:
    level: "P0|P1|P2|P3|P4"
    score: 0

  owner:
    type: "user|agent|skill"
    id: null

  assignee:
    type: "agent|skill|user"
    id: null

  dependencies: []

  blocked_by: []

  due_at: null
  start_at: null

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
  updated_at: "ISO-8601"
  completed_at: null
```

---

# 5. Task ID

Task ID 必须唯一。

建议：

```text
task_<date>_<random>
```

或者使用系统 UUID。

同一个外部请求必须尽可能绑定：

```text
request_id
```

防止重复创建。

---

# 6. Task 类型

标准：

```text
action
research
search
analysis
decision
writing
review
communication
followup
maintenance
scheduled
workflow
proactive
verification
waiting
```

允许扩展，但不要为了每个业务创建新的类型。

---

# 7. 生命周期

标准状态：

```text
INBOX
 ↓
PLANNED
 ↓
READY
 ↓
RUNNING
 ├── WAITING
 ├── BLOCKED
 ├── PAUSED
 ├── RETRYING
 ├── FAILED
 └── COMPLETED
        ↓
      REVIEW
        ↓
     ARCHIVED
```

取消：

```text
CANCELLED
```

---

# 8. 状态定义

## INBOX

刚创建，尚未规划。

## PLANNED

已明确目标和执行方式。

## READY

依赖满足，可以执行。

## RUNNING

正在执行。

## WAITING

等待外部条件、人、时间或资源。

## BLOCKED

存在阻塞原因。

## PAUSED

用户或系统主动暂停。

## RETRYING

正在重试。

## FAILED

执行失败且暂时没有继续策略。

## COMPLETED

满足完成条件。

## REVIEW

需要复盘、验收或人工确认。

## ARCHIVED

历史任务，不再参与主动调度。

## CANCELLED

任务被明确取消。

---

# 9. 状态转换规则

```text
INBOX → PLANNED
PLANNED → READY
READY → RUNNING
RUNNING → COMPLETED
RUNNING → WAITING
RUNNING → BLOCKED
RUNNING → RETRYING
RUNNING → FAILED
RUNNING → PAUSED
RUNNING → CANCELLED

WAITING → READY
BLOCKED → READY
PAUSED → READY
RETRYING → READY

COMPLETED → REVIEW
REVIEW → ARCHIVED
REVIEW → READY
```

禁止任意跳转。

例如：

```text
FAILED → COMPLETED
```

必须先有重新执行或人工确认。

---

# 10. Inbox

所有新任务先进入 Inbox，除非来源明确要求立即执行。

Inbox 处理：

```text
识别
↓
去重
↓
补充信息
↓
分类
↓
优先级
↓
依赖
↓
规划
```

---

# 11. Task Normalization

将不同来源统一成标准 Task。

例如：

```text
Proactive:
“发现项目 B 14 天没有推进”
```

转换：

```yaml
title: "跟进项目 B"
source:
  type: "proactive"

type:
  - "followup"

priority:
  level: "P1"

goal_id: "xxx"

success_conditions:
  - "确定项目 B 下一步行动"
```

---

# 12. Deduplication

创建任务前检查：

```text
request_id
source_id
goal_id
project_id
title similarity
semantic similarity
active task
recent completed task
```

如果已有相同活跃任务：

```text
MERGE
```

而不是创建重复任务。

---

# 13. Merge Policy

重复任务合并时：

保留：

```text
最早创建时间
最高优先级
最严格 deadline
最完整上下文
所有来源引用
```

新增信息追加到：

```text
context
history
source_refs
```

---

# 14. Priority

推荐：

```text
P0 = 紧急 / 关键 / 高影响
P1 = 高优先级
P2 = 正常
P3 = 低优先级
P4 = Backlog
```

不要单纯根据“用户说得急不急”。

---

# 15. Priority Score

可以综合：

```text
priority_score =
    impact
  + urgency
  + goal_alignment
  + deadline_pressure
  + dependency_impact
  + proactive_confidence
  - effort
  - risk
```

最终映射到 P0–P4。

---

# 16. Goal Alignment

任务如果关联长期 Goal：

```text
Goal
 ↓
Project
 ↓
Task
```

应提高其长期价值评分。

没有 Goal 的任务不代表无价值，但长期任务不能因为日常杂事而无限被挤压。

---

# 17. Deadline

支持：

```text
due_at
start_at
soft_deadline
hard_deadline
```

超期状态不应直接改成 FAILED。

应该：

```text
OVERDUE
```

作为状态标记/派生属性。

---

# 18. Overdue Detection

定期扫描：

```text
due_at < now
AND status not in COMPLETED / ARCHIVED / CANCELLED
```

标记：

```text
overdue = true
```

然后：

```text
重新评分
 ↓
判断是否需要 Proactive Follow-up
```

不要每个超期任务都立即打扰用户。

---

# 19. Stale Task

除了 deadline，还要检测停滞。

例如：

```text
14 天没有更新
```

即使没有 deadline，也可能属于：

```text
STALE
```

判断依据：

```text
last_activity_at
expected_progress
task_type
priority
```

---

# 20. Parent / Child

复杂任务：

```text
Parent
├── Child A
├── Child B
└── Child C
```

Parent 完成条件可以是：

```text
all children completed
```

或者：

```text
required children completed
```

不要默认所有子任务都必须完成。

---

# 21. Dependency

支持：

```text
depends_on
blocks
blocked_by
```

例如：

```text
T1 搜索资料
 ↓
T2 总结
 ↓
T3 决策
```

T2 在 T1 未完成前：

```text
BLOCKED
```

---

# 22. Dependency Types

支持：

```text
hard_dependency
soft_dependency
data_dependency
approval_dependency
time_dependency
resource_dependency
```

---

# 23. Ready Queue

只有：

```text
status = READY
AND dependencies satisfied
AND permission available
AND not paused
AND budget available
```

才能进入 Ready Queue。

---

# 24. Assignment

任务可以分配给：

```text
user
agent
skill
workflow
```

例如：

```yaml
assignee:
  type: "agent"
  id: "research-agent"
```

---

# 25. Owner vs Assignee

必须区分：

```text
Owner:
谁对任务负责。

Assignee:
当前谁在执行。
```

例如：

```text
Owner = user
Assignee = Orchestrator
Executor = Agent Browser
```

---

# 26. Agent Task

Agent 任务必须记录：

```text
parent task
objective
context
required output
permission
risk
verification
```

Agent 不应该创建没有来源的孤立任务。

---

# 27. Proactive Task

Proactive 创建任务时必须提供：

```yaml
proactive_metadata:
  opportunity_id: "opp_xxx"
  reason: "xxx"
  confidence: 0.86
  expected_value: 82
  urgency: 61
```

Task Manager 根据这些信息计算优先级。

---

# 28. Orchestrator 接口

Task Manager 给 Orchestrator：

```yaml
execution_request:
  task_id: "task_xxx"

  objective: "xxx"

  inputs: []

  context: {}

  dependencies_satisfied: true

  required_capabilities:
    - "research"

  permissions:
    - "search"

  risk_level: "low"

  success_conditions:
    - "xxx"

  verification_level: "V2"

  budget:
    max_runtime_minutes: 20
    max_tool_calls: 30
    max_retries: 2
```

---

# 29. Execution Result

Orchestrator 返回：

```yaml
execution_result:
  task_id: "task_xxx"

  status: "success|partial|failure"

  summary: "xxx"

  outputs: []

  artifacts: []

  evidence: []

  confidence: 0.87

  side_effects: []

  errors: []

  next_action: null
```

Task Manager 根据结果更新状态。

---

# 30. Completion

任务只有满足：

```text
success_conditions
+
verification
```

才可以标记：

```text
COMPLETED
```

不要因为 Agent 说“完成了”就直接完成。

---

# 31. Partial Completion

如果只完成一部分：

```text
status = RUNNING
```

或者：

```text
status = REVIEW
```

不要误标为 COMPLETED。

---

# 32. Waiting

适用于：

```text
等待用户回复
等待客户
等待第三方
等待日期
等待数据
等待审批
等待另一个任务
```

必须记录：

```yaml
waiting:
  reason: "等待客户回复"
  waiting_for: "customer"
  expected_at: null
  followup_at: "ISO-8601"
```

---

# 33. Waiting Follow-up

Waiting 不应该无限等待。

如果：

```text
followup_at <= now
```

触发：

```text
Follow-up Evaluation
```

判断：

```text
自动跟进
提醒用户
继续等待
取消任务
升级
```

---

# 34. Follow-up

每个 Follow-up 必须有：

```text
target
reason
last_contact
next_followup
max_attempts
channel
permission
```

例如：

```yaml
followup:
  task_id: "task_xxx"
  next_at: "2026-08-20T10:00:00"
  max_attempts: 3
```

外部发送必须经过 Permission Gate。

---

# 35. Retry

默认：

```text
max_retries = 2
```

错误分类：

```text
temporary → retry
network → retry
rate_limit → backoff
invalid_input → replan
permission → ask
logic_error → replan
unknown → escalate
```

每次 Retry 必须记录：

```text
attempt
reason
executor
result
```

---

# 36. Replan

如果失败不是简单重试：

```text
FAILED
 ↓
Orchestrator Replan
 ↓
生成新执行计划
 ↓
Task 回到 READY
```

原始失败记录必须保留。

---

# 37. Task Checkpoint

长任务必须支持：

```yaml
checkpoint:
  task_id: "task_xxx"

  progress: 0.55

  completed_steps:
    - "xxx"

  current_step:
    - "xxx"

  pending_steps:
    - "xxx"

  artifacts:
    - "xxx"

  next_action:
    - "xxx"

  updated_at: "ISO-8601"
```

---

# 38. Resume

恢复任务时：

```text
读取 checkpoint
 ↓
验证外部状态
 ↓
检查已有副作用
 ↓
从安全位置继续
```

不要默认从头执行。

---

# 39. Idempotency

可能产生副作用的任务：

```text
发送
创建
写入
修改
删除
交易
```

必须检查：

```text
request_id
operation_id
existing result
external state
```

避免重复执行。

---

# 40. Recurring Task

支持：

```text
daily
weekly
monthly
custom
event-based
```

Recurring Task 不应该复制全部历史。

应该：

```text
recurring_definition
      ↓
生成 task instance
```

例如：

```yaml
recurrence:
  frequency: "weekly"
  interval: 1
  next_run: "2026-08-23"
```

---

# 41. Recurring Task 防爆

如果系统错过多次运行：

不要一次补执行几十次。

根据任务策略：

```text
latest_only
catch_up
skip_missed
```

默认：

```text
latest_only
```

---

# 42. Task Context

任务上下文分层：

```text
task_context
project_context
goal_context
memory_context
execution_context
```

只加载必要上下文。

---

# 43. Task History

每次状态变化记录：

```yaml
history_event:
  timestamp: "ISO-8601"
  actor: "user|agent|system"
  action: "status_changed"
  from: "running"
  to: "waiting"
  reason: "xxx"
```

历史不可覆盖。

---

# 44. Task Audit

重要操作记录：

```text
创建
修改
分配
执行
权限
重试
失败
完成
取消
删除
```

用于追踪和 Debug。

---

# 45. User Task vs Agent Task

## User Task

用户明确要求。

优先级通常高于 Agent 自己产生的建议。

## Agent Task

由 Proactive / Workflow / Agent 自动产生。

必须有：

```text
source
reason
confidence
expected_value
```

Agent 任务不得无限挤占用户任务。

---

# 46. Task Queue

建议队列：

```text
P0
P1
P2
P3
P4
WAITING
BLOCKED
REVIEW
```

调度时考虑：

```text
priority
deadline
goal alignment
dependency impact
age
estimated effort
```

---

# 47. Fairness

不能永远只执行高优先级任务。

低优先级但长期积压的任务应获得 Aging Bonus。

例如：

```text
priority_score += aging_bonus
```

避免 Backlog 永久不被处理。

---

# 48. Interruption Budget

Proactive 创建任务不能无限打扰用户。

每天维护：

```yaml
interruption_budget:
  max_high_priority_notifications: 3
  max_normal_notifications: 5
  used: 0
```

超过预算：

```text
QUEUE
```

除非属于真正紧急事项。

---

# 49. Proactive Follow-up

Task Manager 定期向 Proactive 提供：

```text
overdue tasks
stale tasks
waiting tasks
blocked tasks
high priority unfinished
goal drift tasks
repeated failures
```

Proactive 再判断是否主动提醒或行动。

---

# 50. Task Aging

任务长期未处理：

```text
age = now - created_at
```

结合：

```text
priority
deadline
goal alignment
activity
```

生成：

```text
aging_score
```

---

# 51. Goal Drift

如果：

```text
Goal
 ↓
大量相关任务长期未推进
```

Task Manager 提供信号：

```yaml
goal_drift_signal:
  goal_id: "xxx"
  unfinished_tasks: 8
  stale_tasks: 4
  overdue_tasks: 2
  last_progress_at: "ISO-8601"
  drift_score: 0.81
```

由 Proactive 判断是否干预。

---

# 52. Task Health

每个活跃任务可计算：

```text
health =
  progress
  + activity
  + dependency_health
  + deadline_health
  + execution_health
```

分类：

```text
HEALTHY
AT_RISK
STALE
BLOCKED
OVERDUE
FAILED
```

---

# 53. Task Risk

风险来源：

```text
side_effect
financial
external_communication
data_loss
production
permission
irreversibility
```

Task Risk 高时：

```text
更严格验证
更高权限要求
更高人工确认等级
```

---

# 54. Verification Policy

不同任务：

```text
简单阅读 → V1
研究 → V2/V3
数据分析 → V2/V3
外部写入 → V3
资金相关 → V4 + 人工确认
不可逆操作 → V4 + 人工确认
```

---

# 55. Archive

任务完成后：

```text
COMPLETED
 ↓
REVIEW
 ↓
ARCHIVED
```

Review 可记录：

```text
结果
问题
用户反馈
经验
是否值得进入 Memory
```

---

# 56. Memory 联动

进入 Memory 的内容：

```text
重要经验
稳定执行模式
用户明确反馈
长期偏好
重大项目结果
失败原因
```

不要保存：

```text
普通状态变化
短期临时变量
重复日志
```

---

# 57. Ontology 联动

当任务状态变化影响：

```text
Goal
Project
Person
Event
Relationship
```

同步 Ontology。

例如：

```text
Task Completed
 ↓
Project Progress
 ↓
Goal Progress
```

---

# 58. Self-Evolution 联动

统计：

```text
task success rate
task failure rate
retry rate
average completion time
overdue rate
manual intervention rate
executor success rate
routing success rate
```

异常模式形成 Evolution Candidate。

---

# 59. Metrics

核心指标：

```text
Completion Rate
On-time Rate
Overdue Rate
Stale Rate
Retry Rate
Failure Rate
Manual Intervention Rate
Average Cycle Time
Average Waiting Time
Average Execution Time
Duplicate Rate
Replan Rate
```

---

# 60. Task Value

长期运行后计算：

```text
task_value =
  goal_impact
  + user_value
  + urgency
  + learning_value
  - effort
  - risk
```

帮助 Proactive 判断哪些任务值得主动推进。

---

# 61. 自动清理

长期运行必须定期：

```text
archive completed
merge duplicates
close stale low-value tasks
remove expired reminders
compress old history
```

但：

```text
不要自动删除重要历史。
```

---

# 62. Task Review

每日 Review：

```text
完成了什么？
失败了什么？
哪些超期？
哪些停滞？
哪些等待？
哪些任务价值下降？
明天最重要的是什么？
```

每周 Review：

```text
Goal Progress
Project Progress
Backlog
Failure Patterns
Recurring Tasks
Proactive Tasks
Execution Efficiency
```

---

# 63. 与 Scheduler 的接口

Scheduler 只负责：

```text
什么时候唤醒
```

Task Manager 负责：

```text
有什么任务需要检查
```

例如：

```text
Scheduler
 ↓
Task Health Scan
 ↓
Overdue
Stale
Waiting
Recurring
Follow-up
```

---

# 64. 与 Proactive 的标准接口

Proactive 可以请求：

```yaml
task_query:
  filters:
    status:
      - "running"
      - "waiting"
      - "blocked"

    priority:
      - "P0"
      - "P1"

  include:
    - "overdue"
    - "stale"
    - "goal_drift"
```

返回：

```yaml
task_signals:
  overdue: []
  stale: []
  blocked: []
  waiting: []
  goal_drift: []
  high_value_unfinished: []
```

---

# 65. Proactive 创建任务接口

```yaml
create_task:
  source:
    type: "proactive"
    id: "opp_xxx"

  title: "xxx"

  objective: "xxx"

  reason: "xxx"

  confidence: 0.88

  expected_value: 82

  priority_hint: "P1"

  risk_level: "low"

  suggested_executor:
    type: "orchestrator"
```

Task Manager 不应盲目接受 Priority Hint，必须重新计算。

---

# 66. Orchestrator 获取任务

Orchestrator 请求：

```yaml
get_ready_tasks:
  limit: 5
  priority_min: "P2"
```

Task Manager 返回：

```yaml
tasks:
  - task_id: "xxx"
    objective: "xxx"
    dependencies_satisfied: true
    permissions: []
    risk_level: "low"
    budget: {}
```

---

# 67. Task Lock

执行前获取 Lock：

```text
READY
 ↓
LOCK
 ↓
RUNNING
```

防止两个 Agent 同时执行同一任务。

Lock 必须：

```text
owner
timestamp
ttl
```

超时可恢复。

---

# 68. Crash Recovery

系统崩溃后：

```text
扫描 RUNNING
 ↓
检查 lock
 ↓
检查 checkpoint
 ↓
检查外部副作用
 ↓
判断：
  resume
  retry
  wait
  fail
```

不要简单把所有 RUNNING 变成 FAILED。

---

# 69. Safe Defaults

默认：

```text
自动创建低风险任务：允许
自动执行低风险任务：视权限允许
自动外部沟通：禁止
自动资金操作：禁止
自动删除：禁止
无限重试：禁止
无限通知：禁止
```

---

# 70. 简单任务策略

例如：

> “总结这段文字。”

不要过度编排：

```text
Task Manager
 ↓
直接调用 Summarize
```

可以记录轻量 Task，但不要制造复杂 DAG。

---

# 71. 复杂任务策略

例如：

> “帮我研究一个 AI Agent 创业机会。”

应：

```text
Task
 ↓
Orchestrator
 ↓
Research
 ├── Browser
 ├── Social Search
 ├── GitHub
 └── Market Data
 ↓
Summarize
 ↓
Verification
 ↓
Result
```

---

# 72. Long-running Project

项目级任务：

```text
Project
 ↓
Epic / Parent Task
 ↓
Milestones
 ↓
Tasks
 ↓
Subtasks
```

Task Manager 负责状态，不负责项目知识模型。

---

# 73. Task Templates

重复任务可定义模板：

```yaml
task_template:
  id: "weekly_research"

  title: "每周研究"

  type: "research"

  required_capabilities:
    - "web_research"

  verification_level: "V2"

  recurrence:
    frequency: "weekly"
```

生成实例时：

```text
Template
 ↓
Task Instance
```

---

# 74. Smart Task Creation

用户一句：

> “这个以后每周帮我做。”

不要直接创建无限任务。

应该：

```text
识别 recurring intent
 ↓
创建 recurring definition
 ↓
确认关键时间 / 范围
 ↓
生成下一实例
```

如果信息充分，可以直接创建。

---

# 75. User Clarification

只有缺失信息影响正确执行时才询问。

例如：

```text
“明天提醒我处理这个。”
```

如果系统无法确定“明天几点”且确实影响执行：

```text
ASK
```

不要对每个小问题都打断用户。

---

# 76. Notification Policy

通知分：

```text
silent
digest
normal
urgent
critical
```

默认：

```text
低价值 → silent
一般 → digest
重要 → normal
紧急 → urgent
真正不可等待 → critical
```

---

# 77. Digest

可以把多个低优先级任务合并：

```text
今日任务摘要：

3 个待处理
2 个超期
1 个等待回复
1 个建议任务
```

减少通知噪音。

---

# 78. Task Compression

历史任务过多时：

```text
详细历史
 ↓
摘要
 ↓
保留关键事件
```

原始审计记录按系统策略保存。

---

# 79. No Action

如果扫描后：

```text
没有值得处理的任务
```

返回：

```text
NO_ACTION
```

不要为了显示“主动性”而制造任务。

---

# 80. 主任务循环

```text
receive task

normalize

deduplicate

calculate priority

link goal/project

check dependencies

check risk/permission

place into queue

if ready:
    send to orchestrator

receive result

verify

update state

if waiting:
    schedule follow-up

if failed:
    retry or replan

if completed:
    review

sync ontology

write useful memory

emit evolution signals
```

---

# 81. Daily Task Review

每日运行一次：

```text
1. 扫描 overdue
2. 扫描 stale
3. 扫描 blocked
4. 扫描 waiting
5. 扫描 high priority
6. 扫描 goal drift
7. 检查重复任务
8. 检查长期 backlog
9. 生成 digest
10. 提供给 Proactive
```

---

# 82. Weekly Task Review

每周：

```text
完成率
超期率
失败率
重复率
平均周期
长期积压
Goal Progress
Project Progress
Agent Performance
```

重点找：

```text
为什么任务总是做不完？
为什么某些任务反复失败？
哪些任务实际上没有价值？
哪些任务应该自动化？
```

这些问题进入 Self-Evolution。

---

# 83. Anti-Spam

禁止：

```text
同一事件 → 无限创建任务
同一任务 → 无限 Follow-up
同一失败 → 无限 Retry
同一建议 → 每次 Wake 都重新创建
```

必须使用：

```text
source_id
request_id
dedup_key
cooldown
max_attempts
```

---

# 84. Cooldown

Proactive 任务可以设置：

```yaml
cooldown:
  key: "opportunity_xxx"
  until: "ISO-8601"
```

在 cooldown 内：

```text
不要重复提醒
```

除非出现新证据或风险升级。

---

# 85. Escalation

以下情况升级：

```text
关键任务失败
连续重试失败
高风险
权限不足
超过预算
接近硬截止时间
重要外部依赖失效
```

Escalation 可以：

```text
ask_user
notify
create_review
pause
```

---

# 86. Review Queue

需要人工判断的任务进入：

```text
REVIEW
```

例如：

```text
研究结论冲突
重要合同
高风险执行
重要对外信息
```

用户确认后：

```text
REVIEW → READY
```

---

# 87. Task Command Interface

建议支持：

```text
task list
task show <id>
task create
task update
task assign
task pause
task resume
task cancel
task retry
task complete
task review
task archive
task search
task overdue
task blocked
task waiting
```

自然语言同样支持：

```text
“看看我有哪些超期任务”
“暂停这个任务”
“把这个交给研究 Agent”
“这个以后每周做”
```

---

# 88. 示例：Proactive 发现任务

```text
Proactive
 ↓
发现项目 A 21 天未推进
 ↓
创建 Task
 ↓
Task Manager
 ↓
计算：
P1
health = STALE
goal_alignment = high
 ↓
Ready
 ↓
Orchestrator
 ↓
分析原因
 ↓
返回
 ↓
Task → REVIEW
 ↓
Proactive
 ↓
提醒用户
```

---

# 89. 示例：研究任务

```text
用户：
“帮我研究 AI Agent 市场。”

Task Manager
 ↓
创建 Parent Task
 ↓
Orchestrator
 ↓
拆成：
T1 行业研究
T2 GitHub
T3 社媒
T4 竞品
 ↓
并行
 ↓
T5 汇总
 ↓
T6 验证
 ↓
完成
```

---

# 90. 示例：等待外部回复

```text
发送前经过 Permission Gate
 ↓
等待客户
 ↓
WAITING
 ↓
followup_at
 ↓
Scheduler 唤醒
 ↓
Task Manager
 ↓
交给 Proactive 判断
 ↓
需要跟进？
 ├── 是 → Orchestrator
 └── 否 → WAITING
```

---

# 91. 示例：失败恢复

```text
RUNNING
 ↓
失败
 ↓
classify = network
 ↓
RETRY
 ↓
成功
 ↓
VERIFY
 ↓
COMPLETED
```

如果：

```text
invalid_input
```

则：

```text
REPLAN
```

而不是继续重试。

---

# 92. 最终职责矩阵

| 能力 | Proactive | Task Manager | Orchestrator | Ontology | Memory | Self-Evolution |
|---|---|---|---|---|---|---|
| 发现机会 | ✓ | | | | | |
| 创建任务 | ✓ | ✓ | | | | |
| 任务状态 | | ✓ | | | | |
| 任务拆解 | | | ✓ | | | |
| Skill 路由 | | | ✓ | | | |
| 世界关系 | | | | ✓ | | |
| 历史经验 | | | | | ✓ | |
| 失败学习 | | 指标 | 指标 | | | ✓ |
| Follow-up | 判断 | 管状态 | 执行 | | | |
| Verification | | 管结果 | 执行验证 | | | |
| 权限 | | 请求 | 执行前检查 | | | |

---

# 93. 生产原则

始终遵守：

> 任务必须有来源。

> 任务必须有明确目标。

> 任务必须有状态。

> 任务必须可追踪。

> 任务必须可恢复。

> 任务完成必须验证。

> 失败必须分类。

> 重试必须有限。

> 重复任务必须合并。

> 超期不等于失败。

> Waiting 不等于 Done。

> Agent 不得无限制造任务。

> Proactive 不得无限打扰用户。

> 高风险任务必须经过权限与风险控制。

> Task Manager 不负责执行具体业务。

> Orchestrator 不负责保存任务生命周期。

最终形成：

```text
              PROACTIVE
                  │
                  │ 发现值得做的事
                  ▼
             TASK MANAGER
                  │
        ┌─────────┼─────────┐
        │         │         │
      Queue    State     Follow-up
        │         │         │
        └─────────┼─────────┘
                  ▼
             ORCHESTRATOR
                  │
          拆解 / 路由 / 执行
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
      Agent     Skill     Workflow
        │         │         │
        └─────────┼─────────┘
                  ▼
              VERIFY
                  │
                  ▼
           TASK MANAGER
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
     Memory   Ontology   Self-Evolution
```

**Task Manager 的最终目标不是“帮你记 Todo”，而是成为 OpenClaw 所有任务的统一生命周期操作系统。**

---

# 附录A: 可运行脚本

## task_manager.py（任务核心, V1.0）

```bash
python3 skills/task-manager/scripts/task_manager.py --help
```

| 命令 | 作用 |
|:--|:--|
| `create --json '{...}' [--merge]` | 创建/合并任务（标准化+去重+优先级重算） |
| `list [--status X] [--priority P] [--limit N]` | 列出任务 |
| `show --id task_x` | 查看单个任务 |
| `update --id task_x --status X [--json '{...}']` | 更新字段/状态（含状态机校验§9） |
| `assign --id task_x --role owner|assignee --to xxx` | 分配 Owner/Assignee |
| `scan` | 健康扫描: overdue/stale/waiting/blocked/goal_drift |
| `queue` | 队列分布 |
| `metrics` | 核心指标 |
| `stats` | 状态机校验+结构统计 |

状态持久化: `skills/task-manager/memory/tasks.json`

## link.py（联动层, V1.1）

```bash
python3 skills/task-manager/scripts/link.py --help
```

| 命令 | 联动方向 |
|:--|:--|
| `proactive-to-task --signal '{...}'` | Proactive Signal → 创建任务 (source=proactive) |
| `scan-to-proactive [--min-level P1]` | 任务 scan 信号 → 反馈 Proactive |
| `tasks-to-orchestrator [--limit 10]` | READY 任务 → orchestration_request |
| `result-to-task --json '{...}' [--verify]` | Orchestrator 结果 → 任务状态回写（自动状态机中转） |
| `sync-ontology [--limit 200]` | 任务实体/关系 → Ontology (Task 类型) |
| `sync-memory` | 任务摘要 → 今日 memory/YYYY-MM-DD.md |
| `sync-evolution` | 失败/阻塞模式 → Learning Bus 进化候选 |
| `all [--min-level P1]` | 一键联动: scan + 反馈Proactive + 同步Ontology + 进化 |

### 典型闭环示例

```text
Proactive 发现信号
  → link.py proactive-to-task    (任务进入 INBOX)
  → task_manager.py update --status READY
  → link.py tasks-to-orchestrator (交给 Orchestrator 拆解路由)
  → Orchestrator 执行
  → link.py result-to-task --json '{task_id,status,summary}'  (回写 COMPLETED/FAILED)
  → link.py all                   (scan 反馈 + Ontology 同步 + 失败学习)
```