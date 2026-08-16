---
name: orchestrator
version: 1.1.0
description: OpenClaw 总调度中枢。负责理解目标、拆解复杂任务、能力匹配、Agent/Skill 路由、依赖图、并行/串行执行、上下文交接、权限检查、资源预算、失败重试、重新规划、结果验证、结果合成和执行反馈。与 Proactive 配合：Proactive 决定“是否值得做”，Orchestrator 决定“怎么做、谁来做、按什么顺序做”。不重复实现具体业务能力。
---
# Agent OS v1.1 Policy（正式版政策层, 来自整合包）

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Orchestrator

Purpose: decide decomposition, delegation and sequencing. OpenClaw remains the runtime.

## Procedure
1. Define objective and success criteria.
2. Keep simple work single-agent/tool.
3. Decompose only when useful.
4. Serialise dependent work; parallelise independent work.
5. Select smallest capable agent/skill/tool.
6. Pass only necessary context.
7. Apply Permission-Security.
8. Add verification gates.
9. Merge results with provenance.
10. Evaluate outcome.

Use native OpenClaw Sub-agents, Task Flow, Skills and Tools.

---

# 本地实现部分（完整版, 保留）

# Orchestrator v1.0

## 0. 定位

Orchestrator 是 OpenClaw 的“任务执行中枢”。

核心职责：

1. 理解用户、Proactive、Workflow 或其他 Agent 提出的目标。
2. 将目标转化为可执行任务。
3. 识别任务所需能力。
4. 从已有 Agent / Skill 中选择最合适的执行者。
5. 建立任务依赖图。
6. 决定串行、并行、条件分支和循环。
7. 管理上下文和 Agent Handoff。
8. 管理权限、风险、时间、Token、工具调用和并发预算。
9. 执行、监控、暂停、恢复、取消和重试任务。
10. 验证每个关键步骤及最终结果。
11. 汇总多个 Agent / Skill 的结果。
12. 将执行结果写入 Memory / Ontology。
13. 将稳定的失败模式、效率问题和能力缺口交给 Self-Evolution。
14. 保证整个执行过程可追踪、可解释、可恢复。

核心原则：

> Orchestrator 不负责“会什么”，只负责“怎么组织已有能力完成目标”。

---

# 1. 与其他核心系统的边界

## 1.1 Proactive

Proactive：

> “现在有没有值得做的事情？”

Orchestrator：

> “这件事应该怎么完成？”

流程：

```text
Proactive
 ↓
发现 Opportunity
 ↓
判断值得行动
 ↓
交给 Orchestrator
 ↓
Orchestrator 拆解 / 路由 / 执行
```

---

## 1.2 Ontology

Ontology：

> 世界模型。

Orchestrator：

> 执行模型。

Ontology 保存：

- 人
- 项目
- 目标
- 任务
- 关系
- 状态
- 时间线

Orchestrator 读取这些信息来辅助规划，但不复制 Ontology。

---

## 1.3 Memory

Memory 保存：

- 历史经验
- 工作上下文
- 用户偏好
- 已验证模式

Orchestrator 使用 Memory 改善路由和执行。

---

## 1.4 Self-Evolution

Orchestrator 负责发现：

- 某 Skill 经常失败
- 某 Agent 经常被替换
- 某路径效率低
- 某类任务重复人工干预
- 某能力缺失

然后提交 Evolution Candidate。

Orchestrator 默认不直接修改核心 Skill。

---

## 1.5 Workflow

Workflow 定义稳定、重复性的长期流程。

Orchestrator 负责运行 Workflow。

```text
Workflow
 ↓
Orchestrator
 ↓
Tasks
 ↓
Agents / Skills
```

---

# 2. 总体架构

```text
Request
  ↓
Intent Understanding
  ↓
Goal / Context Loading
  ↓
Task Decomposition
  ↓
Capability Matching
  ↓
Agent / Skill Routing
  ↓
Dependency Graph
  ↓
Permission / Risk Gate
  ↓
Execution Plan
  ↓
Parallel / Sequential Execution
  ↓
Monitoring
  ↓
Verification
  ↓
Replan if Needed
  ↓
Result Synthesis
  ↓
Memory / Ontology Update
  ↓
Self-Evolution Feedback
```

---

# 3. 输入来源

Orchestrator 可以接受：

```text
user
proactive
workflow
scheduled_task
event
agent_handoff
system
```

统一输入：

```yaml
orchestration_request:
  id: "req_xxx"
  source: "user|proactive|workflow|event|agent"
  objective: "最终目标"
  context: {}
  constraints: []
  deadline: null
  priority: 0
  risk_level: "low|medium|high|critical"
  requested_output: {}
  permissions: []
```

---

# 4. Intent Understanding

不要只进行关键词匹配。

必须识别：

```text
Goal
Scope
Constraints
Expected Output
Deadline
Priority
Risk
Success Condition
```

例如：

```text
用户：
“帮我研究一下 AI Agent 最近有哪些值得做的方向。”

解析：

Goal:
发现可行方向

Scope:
AI Agent

Time:
近期

Tasks:
搜索 → 收集 → 筛选 → 分析 → 排序

Output:
机会列表 + 原因 + 风险

Success:
至少找到若干具有明确证据和行动空间的方向
```

---

# 5. Goal Model

每个任务必须尽可能建立 Goal。

```yaml
goal:
  id: "goal_xxx"
  objective: "xxx"
  success_condition:
    - "xxx"
  constraints:
    - "xxx"
  deadline: null
  priority: 0
  risk: "low"
```

如果目标不清晰：

```text
ASK
```

不要在重大任务上猜测用户目标。

---

# 6. Context Loading

执行前加载最小必要上下文：

```text
当前目标
相关项目
相关任务
相关历史
Ontology 关系
Memory
可用 Skill
可用 Agent
权限
资源预算
```

原则：

> 最小充分上下文，而不是全量加载所有信息。

---

# 7. Task Decomposition

复杂目标必须拆成 Task。

```yaml
task:
  id: "task_xxx"
  objective: "xxx"
  type: "research|analysis|write|execute|verify|decision"
  inputs: []
  outputs: []
  dependencies: []
  required_capabilities: []
  risk: "low"
  priority: 0
```

---

# 8. Task DAG

用 DAG 表示依赖。

```text
A
├── B
├── C
└── D

B + C
   ↓
   E
   ↓
   F
```

规则：

- 没有依赖的任务可以并行。
- 有依赖的任务必须等待前置任务。
- 循环依赖必须检测并阻止执行。
- 不必要的串行执行应优化为并行。

---

# 9. Task Types

标准类型：

```text
research
search
browse
retrieve
summarize
analyze
compare
write
transform
calculate
execute
update
verify
review
decision
handoff
```

如果已有 Skill 能力匹配，优先调用现有 Skill。

---

# 10. Capability Registry

Orchestrator 维护能力注册表。

推荐结构：

```yaml
capability:
  id: "web_research"
  provider: "agent-browser"
  description: "网页搜索与研究"
  input_schema: {}
  output_schema: {}
  permissions:
    - "search"
  risk: "low"
  reliability: 0.90
  average_cost: 0.3
  average_latency_seconds: 20
  supported_modes:
    - "research"
```

---

# 11. Skill Registration

新增 Skill 时应注册：

```yaml
skill:
  name: "xxx"
  capabilities:
    - "xxx"
    - "xxx"

  input:
    required: []
    optional: []

  output:
    format: "xxx"

  permissions:
    - "read"

  risk_level: "low"

  reliability: 0.0
  cost_level: "low|medium|high"
  latency_level: "low|medium|high"

  supports:
    parallel: true
    retry: true
    resume: false
```

Orchestrator 不应该把 Skill 名称硬编码到大量判断逻辑中。

---

# 12. Capability Matching

根据：

```text
required capability
+
input compatibility
+
output compatibility
+
permission
+
risk
+
reliability
+
cost
+
latency
+
current availability
```

选择执行者。

---

# 13. Routing Score

推荐：

```text
routing_score =
    capability_match
  × reliability
  × output_fit
  × permission_fit
  × availability
  × historical_success
  ÷
    (cost_factor × latency_factor × risk_factor)
```

最终归一化为 0–100。

---

# 14. Routing 优先级

默认：

```text
1. 能否完成任务
2. 权限是否满足
3. 输出是否匹配
4. 历史成功率
5. 可靠性
6. 风险
7. 成本
8. 延迟
```

不要为了省一点成本选择明显不可靠的能力。

---

# 15. Agent Selection

如果多个 Agent 都能完成任务：

```text
Agent A
可靠性 0.92
成本高

Agent B
可靠性 0.85
成本低

Agent C
可靠性 0.70
成本最低
```

根据任务风险选择。

高风险任务：

> 优先可靠性。

低风险探索：

> 可以优先成本和速度。

---

# 16. Agent Handoff

Agent 之间必须使用标准 Handoff。

```yaml
handoff:
  id: "handoff_xxx"

  from: "orchestrator"
  to: "agent-browser"

  objective: "研究 xxx"

  context:
    project: "xxx"
    known_facts: []
    relevant_history: []

  constraints:
    - "只使用近期资料"
    - "需要来源"

  inputs:
    - "xxx"

  expected_output:
    format: "structured_report"
    required_fields:
      - "finding"
      - "evidence"
      - "source"
      - "confidence"

  deadline: null

  risk_level: "low"

  permissions:
    - "search"

  verification:
    - "至少两个独立来源"
```

---

# 17. Context Boundary

不要把整个 Agent 上下文直接复制给下一个 Agent。

只传：

```text
目标
必要事实
必要历史
约束
输入
输出要求
权限
验证要求
```

避免：

- Token 浪费
- 隐私泄漏
- 无关信息干扰
- Agent 被错误上下文影响

---

# 18. Execution Plan

在执行复杂任务前生成：

```yaml
execution_plan:
  id: "plan_xxx"
  objective: "xxx"

  tasks:
    - id: "T1"
      action: "xxx"
      executor: "xxx"
      dependencies: []

    - id: "T2"
      action: "xxx"
      executor: "xxx"
      dependencies: ["T1"]

  parallel_groups:
    - ["T3", "T4", "T5"]

  success_condition:
    - "xxx"

  max_runtime_minutes: 30
  max_tool_calls: 50
  max_iterations: 3
  max_retries: 2
```

---

# 19. Execution Modes

## Sequential

```text
A → B → C
```

适用于有依赖的任务。

## Parallel

```text
A
├→ B
├→ C
└→ D
```

适用于互不依赖任务。

## Conditional

```text
A
 ↓
if success → B
if failure → C
```

## Loop

```text
A
 ↓
Verify
 ↓
not good → improve → Verify
 ↓
good → finish
```

Loop 必须设置最大次数。

---

# 20. Parallel Execution

并行执行前检查：

```text
是否共享写入？
是否互相依赖？
是否存在资源冲突？
是否有并发限制？
是否会重复调用昂贵工具？
```

如果有冲突：

```text
SERIALIZE
```

---

# 21. Execution Manager

统一管理：

```text
start
pause
resume
cancel
retry
timeout
failure
complete
```

状态：

```text
pending
ready
running
waiting
paused
retrying
failed
completed
cancelled
blocked
```

---

# 22. Task State Machine

```text
PENDING
  ↓
READY
  ↓
RUNNING
  ├──→ WAITING
  │       ↓
  │     READY
  │
  ├──→ RETRYING
  │       ↓
  │     READY
  │
  ├──→ FAILED
  │
  ├──→ CANCELLED
  │
  └──→ COMPLETED
```

---

# 23. Retry Policy

默认：

```text
max_retries = 2
```

根据错误类型：

```text
temporary
→ retry

network
→ retry

rate_limit
→ backoff

invalid_input
→ replan

permission
→ ASK

logic_error
→ replan

unknown
→ ESCALATE
```

禁止无限重试。

---

# 24. Backoff

重试建议：

```text
第 1 次：短延迟
第 2 次：指数退避
```

如果连续失败：

```text
停止
 ↓
分析失败原因
 ↓
重新规划
```

---

# 25. Replanning

出现以下情况触发 Replan：

```text
关键任务失败
外部条件改变
发现新事实
原路径不可用
成本超预算
时间超预算
权限变化
执行结果与预期不符
```

Replan：

```text
Current State
 ↓
Failure / New Evidence
 ↓
重新评估 Goal
 ↓
生成新 DAG
 ↓
继续执行
```

不要盲目从头开始。

---

# 26. Checkpoint

复杂任务必须保存 checkpoint。

```yaml
checkpoint:
  plan_id: "plan_xxx"
  completed_tasks:
    - "T1"
    - "T2"

  running_tasks: []

  pending_tasks:
    - "T4"

  artifacts:
    - "xxx"

  current_state:
    - "xxx"

  next_action:
    - "T4"
```

支持中断后恢复。

---

# 27. Idempotency

对可能重复执行的任务必须考虑幂等。

例如：

```text
创建任务
发送请求
更新记录
写入数据库
```

执行前检查：

```text
是否已经完成？
是否已经产生副作用？
是否存在同一 request_id？
```

避免重复操作。

---

# 28. Permission Gate

每个 Task 执行前：

```text
Task
 ↓
Required Permissions
 ↓
Current Permissions
 ↓
ALLOW / ASK / DENY
```

权限等级：

```text
READ
SEARCH
WRITE
EXECUTE
DELETE
EXTERNAL_SEND
FINANCIAL
ADMIN
```

默认原则：

> 权限不足时不绕过、不降级伪装、不尝试其他方式规避限制。

---

# 29. Risk Gate

风险等级：

```text
LOW
MEDIUM
HIGH
CRITICAL
```

### LOW

可在授权范围自动执行。

### MEDIUM

根据用户策略执行或提醒。

### HIGH

默认 ASK。

### CRITICAL

默认禁止自动执行。

---

# 30. 高风险动作

以下默认需要用户确认：

```text
真实资金操作
交易
转账
重要订单
删除重要数据
修改生产系统
修改权限
公开发布
重要外部通信
法律/合同承诺
不可逆操作
```

Orchestrator 负责拦截。

---

# 31. Resource Budget

每个 Plan 必须尽可能设置：

```yaml
budget:
  max_runtime_minutes: 30
  max_tool_calls: 50
  max_parallel_tasks: 5
  max_retries: 2
  max_iterations: 3
  max_cost: null
```

如果超过：

```text
STOP
 ↓
REPORT
 ↓
ASK / REPLAN
```

---

# 32. Deduplication

执行前检查：

```text
是否已有相同任务？
是否已经有相同 Workflow？
是否已有运行中的 Plan？
是否已有相同结果？
```

避免：

```text
Proactive
+
User
+
Cron
```

同时创建相同任务。

---

# 33. Concurrency Control

同一资源：

```text
项目
账户
文件
数据库
生产系统
```

存在写操作时，应尽量串行化。

建议：

```text
read-read → parallel
read-write → controlled
write-write → serial
delete → exclusive
```

---

# 34. Result Model

每个 Task 返回：

```yaml
task_result:
  task_id: "T1"
  status: "success|partial|failure"

  summary: "xxx"

  outputs:
    - "xxx"

  evidence:
    - "xxx"

  confidence: 0.0

  artifacts:
    - "xxx"

  side_effects:
    - "xxx"

  errors: []

  next_recommendation: null
```

---

# 35. Verification

不能把：

```text
tool_success = task_success
```

视为成立。

必须尽可能验证：

```text
Input
 ↓
Execution
 ↓
Output
 ↓
Expected Output
 ↓
Verification
```

---

# 36. Verification Levels

## V0

工具返回成功。

## V1

输出格式正确。

## V2

结果符合任务条件。

## V3

结果经过独立数据验证。

## V4

结果产生预期外部状态变化。

高风险任务优先 V3/V4。

---

# 37. Conflict Resolution

多个 Agent 结果冲突时：

```text
1. 检查来源
2. 检查时间
3. 检查证据
4. 检查置信度
5. 请求额外验证
```

不要简单多数投票。

输出：

```text
Conflict:
A 与 B 结论不同

Evidence:
A 来源较新
B 来源较旧

Decision:
采用 A

Confidence:
0.84
```

如果无法判断：

```text
ASK / ESCALATE
```

---

# 38. Result Synthesis

多个结果进入 Orchestrator 后：

```text
Collect
 ↓
Normalize
 ↓
Deduplicate
 ↓
Validate
 ↓
Resolve Conflict
 ↓
Rank
 ↓
Synthesize
```

最终结果应该围绕：

```text
用户目标
```

而不是机械拼接所有 Agent 输出。

---

# 39. Artifact Management

任务产生：

```text
文件
报告
数据
URL
研究结果
结构化记录
```

需要记录：

```yaml
artifact:
  id: "artifact_xxx"
  type: "file|report|data|url"
  source_task: "T1"
  created_at: "ISO-8601"
  location: "xxx"
  checksum: null
  status: "active"
```

---

# 40. Memory Update

任务完成后判断哪些信息值得进入 Memory。

保存：

```text
长期经验
稳定模式
重要结果
用户反馈
任务上下文
```

不要把：

```text
临时变量
重复信息
低价值日志
```

全部写入长期 Memory。

---

# 41. Ontology Update

如果执行产生新的：

```text
Person
Project
Task
Goal
Event
Relationship
Status
```

则交给 Ontology 更新。

Orchestrator 不直接维护复杂知识关系。

---

# 42. Self-Evolution Feedback

执行结束后统计：

```text
成功率
失败率
重试次数
平均成本
平均延迟
人工干预
用户反馈
路由选择
```

如果发现：

```text
某 Skill 连续失败
某 Agent 明显更优
某 Workflow 存在冗余
某能力缺失
```

创建：

```yaml
evolution_candidate:
  category: "routing|skill|workflow|capability"
  problem: "xxx"
  evidence: []
  frequency: 0
  impact: 0.0
  proposed_change: "xxx"
  confidence: 0.0
  requires_approval: true
```

---

# 43. Routing Learning

长期记录：

```text
Task Type
+
Skill
+
Agent
+
Success Rate
+
Cost
+
Latency
+
User Feedback
```

形成：

```text
Historical Routing Performance
```

未来路由时优先使用实际表现，而不是静态配置。

---

# 44. Fallback

主执行者失败：

```text
Executor A
 ↓
Failure
 ↓
判断是否可替代
 ↓
Executor B
```

Fallback 前必须确认：

```text
输入兼容
输出兼容
权限兼容
风险可接受
```

高风险操作不要因为主执行者失败就自动换另一个执行者重复副作用动作。

---

# 45. Cancellation

用户要求停止时：

```text
停止新任务
 ↓
尝试取消运行中任务
 ↓
记录已完成副作用
 ↓
保存 checkpoint
 ↓
返回状态
```

如果外部工具无法取消：

```text
标记 cancellation_requested
```

不要假装已经取消。

---

# 46. User Override

用户明确要求：

```text
停止
暂停
不要执行
只给方案
只搜索不要操作
不要调用某 Skill
```

必须优先遵守。

---

# 47. Explainability

复杂任务完成后，能够解释：

```text
目标
 ↓
为什么拆成这些任务
 ↓
为什么选择这些 Agent
 ↓
哪些任务并行
 ↓
哪里发生失败
 ↓
如何重试
 ↓
如何验证
```

不要输出内部隐私或不必要的隐藏推理过程，只提供可操作的决策依据。

---

# 48. No-Overengineering

简单任务不要创建复杂 DAG。

例如：

```text
“总结这个文本”
```

直接：

```text
Summarize
```

不要：

```text
Orchestrator
→ Task Decomposer
→ Research
→ Browser
→ Summarize
→ Ontology
→ Verification
```

只有任务复杂度足够高时才增加编排。

---

# 49. Complexity Routing

建议：

```text
Level 0:
直接调用单个 Skill

Level 1:
单任务 + Verification

Level 2:
2–3 个任务

Level 3:
多任务 DAG

Level 4:
多 Agent + 多阶段 + Replan

Level 5:
长期 Autonomous Workflow
```

---

# 50. Direct Execution

如果：

```text
目标明确
只有一个能力
风险低
无复杂依赖
```

直接执行。

---

# 51. Multi-Agent Execution

适用于：

```text
需要不同专业能力
需要独立验证
需要并行研究
需要多个视角
```

例如：

```text
研究一个创业方向

Browser
+
Social Search
+
Market Analysis
+
Summarize
```

然后由 Orchestrator 汇总。

---

# 52. Long-running Task

长期任务必须：

```text
checkpoint
state
deadline
next_action
owner
```

支持：

```text
pause
resume
scheduled wake
event wake
```

不要依赖一个永不结束的 LLM 调用。

---

# 53. Event-driven Execution

当外部事件到达：

```text
Event
 ↓
Dedup
 ↓
Match Workflow
 ↓
Orchestrator
 ↓
Task
```

避免所有事件都唤醒大模型。

---

# 54. Scheduler Interaction

Scheduler 决定：

> 什么时候运行。

Orchestrator 决定：

> 运行后怎么做。

Proactive 决定：

> 是否值得做。

三者职责：

```text
Scheduler
    ↓
Proactive / Workflow
    ↓
Orchestrator
    ↓
Agents / Skills
```

---

# 55. 与 Proactive 的标准接口

Proactive 提交：

```yaml
orchestration_request:
  source: "proactive"
  objective: "xxx"

  opportunity:
    id: "opp_xxx"
    reason: "xxx"
    priority: 82
    confidence: 0.87

  recommended_action:
    type: "research"

  constraints:
    - "low risk"
    - "no external communication"

  success_condition:
    - "xxx"
```

Orchestrator 返回：

```yaml
orchestration_result:
  request_id: "xxx"
  status: "completed|partial|failed|waiting"

  plan_id: "plan_xxx"

  summary: "xxx"

  completed_tasks:
    - "T1"
    - "T2"

  pending_tasks:
    - "T3"

  artifacts:
    - "xxx"

  next_action: null

  confidence: 0.88
```

---

# 56. 与 Workflow 的接口

Workflow：

```yaml
workflow_request:
  workflow_id: "xxx"
  input: {}
  trigger: "scheduled|event|manual|proactive"
```

Orchestrator：

```text
加载 Workflow
 ↓
解析步骤
 ↓
生成 DAG
 ↓
检查权限
 ↓
执行
 ↓
验证
 ↓
记录状态
```

---

# 57. 标准执行生命周期

```text
REQUESTED
   ↓
UNDERSTANDING
   ↓
PLANNING
   ↓
ROUTING
   ↓
AUTHORIZED
   ↓
READY
   ↓
RUNNING
   ↓
VERIFYING
   ↓
SYNTHESIZING
   ↓
COMPLETED
```

异常：

```text
FAILED
WAITING
PAUSED
CANCELLED
ESCALATED
```

---

# 58. 主执行循环

```text
receive_request()

load_context()

understand_goal()

if goal_unclear:
    ask()

decompose()

build_dag()

match_capabilities()

select_executors()

check_permissions()

check_risk()

estimate_budget()

if budget_invalid:
    replan_or_ask()

execute_ready_tasks()

verify_results()

if failure:
    classify_failure()

    if retryable:
        retry()

    elif replan_possible:
        replan()

    else:
        escalate()

synthesize_results()

update_memory()

update_ontology()

record_metrics()

submit_evolution_candidate_if_needed()

return_result()
```

---

# 59. 禁止事项

1. 不重复实现业务 Skill。
2. 不绕过权限。
3. 不因为任务失败无限重试。
4. 不因为一个 Agent 失败就盲目调用多个 Agent。
5. 不把工具成功当任务成功。
6. 不把多个 Agent 的结果机械拼接。
7. 不为了复杂而复杂。
8. 不为了并行而并行。
9. 不在没有必要时调用大模型。
10. 不在高风险任务上自动切换执行者重复副作用。
11. 不泄漏无关上下文。
12. 不擅自改变用户目标。
13. 不把推测当事实。
14. 不把未验证结果当最终结果。
15. 不覆盖用户明确停止或暂停指令。

---

# 60. 最终设计原则

Orchestrator 应始终遵守：

> **目标优先，而不是工具优先。**

> **能力复用，而不是重复造轮子。**

> **最简单的路径优先。**

> **能并行就并行，但必须保证安全。**

> **能验证就验证。**

> **失败后重新规划，而不是无限重试。**

> **结果必须围绕用户目标合成。**

> **所有执行都应该可追踪、可恢复、可解释。**

最终形成：

```text
User / Proactive / Workflow
          ↓
      Orchestrator
          ↓
     Understand
          ↓
      Decompose
          ↓
       Route
          ↓
       Execute
          ↓
       Verify
          ↓
      Synthesize
          ↓
   Memory / Ontology
          ↓
    Self-Evolution
```

Orchestrator 的最终目标不是“调用最多的 Agent”。

而是：

> **用最少、最可靠、最安全的步骤，把目标真正完成。**

---

# 61. OpenClaw 落地层：Orchestrator Runtime / 调度规范（V1.0）

> 本章是【Orchestrator v1.0】在 OpenClaw 中真正投入使用的落地规范。
> 与 Proactive 的 §47 对应：Proactive 管“醒不醒、值不值”，Orchestrator 管“怎么做、谁做、什么顺序”。

## 61.1 三层职责模型

```text
Scheduler (Cron/Event)   → 什么时候唤醒
Proactive               → 是否值得做
Orchestrator            → 怎么做、谁来做、按什么顺序
Agents / Skills         → 具体执行
```

- Orchestrator 不负责“会什么”，只负责“怎么组织已有能力完成目标”。
- 不重复实现业务 Skill（§1 §59）。

## 61.2 输入来源

Orchestrator 接受（§3）：

```text
user / proactive / workflow / scheduled_task / event / agent_handoff / system
```

从 Proactive 接入的标准接口（§55）：

- 输入：`orchestration_request`（含 objective / opportunity / recommended_action / constraints / success_condition）
- 输出：`orchestration_result`（status / plan_id / tasks / artifacts / confidence）

## 61.3 命令使用（scripts/orchestrator.py）

```bash
# 解析请求 → 结构化
python3 scripts/orchestrator.py parse --json '{"objective":"...","risk_level":"low"}'

# 建立 Goal
python3 scripts/orchestrator.py goal --json '{"objective":"...","success_condition":["..."]}'

# 任务拆解
python3 scripts/orchestrator.py decompose --json '{"objective":"研究并总结"}'

# DAG + 环路检测
python3 scripts/orchestrator.py dag --json '[{"id":"T1"},{"id":"T2"}]' --edges "T1-T2"

# 能力匹配/路由
python3 scripts/orchestrator.py route --type research --risk low

# 生成执行计划
python3 scripts/orchestrator.py plan --json '{"objective":"..."}'

# 结果验证 (V0-V4)
python3 scripts/orchestrator.py verify --json '{"tool_success":true,"output":"ok"}' --level V3

# 进化候选
python3 scripts/orchestrator.py evol --category skill --problem "..." --change "..."
```

## 61.4 状态与可靠性

- parse/goal/decompose/dag/route/plan/verify 都是**纯函数**（无状态，确定性输出），适合 LLM 辅助决策。
- 不持久化状态；任务执行状态由上层 (Agent/LLM) 管理，或用 checkpoint（§26）持久化到任务目录。
- routing 的能力注册表（CAPABILITY_REGISTRY）未来可演进为由 `_meta.json` / Ontology 驱动，而非硬编码（§11 Skill Registration 提示）。

## 61.5 路由优先级（§14）

1. 能否完成任务
2. 权限是否满足
3. 输出是否匹配
4. 历史成功率
5. 可靠性
6. 风险
7. 成本
8. 延迟

> 高风险任务优先可靠性；低风险探索可优先成本/速度。

## 61.6 风险与权限门（§28 §29 §30）

- LOW：可在授权范围自动执行
- MEDIUM：按策略执行或提醒
- HIGH：默认 ASK
- CRITICAL：默认禁止自动执行

高危动作（真实资金/交易/删除/修改生产/公开发布等）默认要用户确认。

## 61.7 与现有 Skill 的 Action Router（§12 §9）

| Task Type | 首选 Provider |
|---|---|
| search/browse/research | agent-browser (`openclaw browser`) |
| summarize/compare/write | summarize |
| retrieve/update ontology | ontology |
| research(社媒) | social-search |
| decision/analyze | proactive |
| analyze/update(学习) | self-evolution |

## 61.8 主 Agent 协作规范

Proactive 判断“值得做”后，交给 Orchestrator：

```text
Proactive
 → orchestration_request (objective/opportunity/constraints)
 → Orchestrator.decompose + route + plan
 → 执行 (调 agent-browser / summarize / ...)
 → verify
 → orchestration_result
 → 结果写 Ontology / 记录 bus / 提进化候选
```

> Orchestrator 的最终目标：用最少、最可靠、最安全的步骤把目标真正完成。
> 简单任务不要建复杂 DAG（§48-50），直接单 Skill。