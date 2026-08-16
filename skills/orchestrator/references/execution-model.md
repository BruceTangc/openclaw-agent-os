# Orchestrator 执行模型参考

> 拆解、DAG、路由、执行、重试、checkpoint 的详细数据模型。

## 1. Goal Model

```yaml
goal:
  id: "goal_xxx"
  objective: "xxx"
  success_condition: ["xxx"]
  constraints: ["xxx"]
  deadline: null
  priority: 0
  risk: "low"
```

目标不清晰 → ASK。

## 2. Task 结构

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

## 3. Task 类型

research / search / browse / retrieve / summarize / analyze / compare / write / transform / calculate / execute / update / verify / review / decision / handoff。

## 4. DAG 规则

无依赖可并行；有依赖等前置；循环依赖检测并阻止；不必要串行优化为并行。

## 5. Capability Registry

```yaml
capability:
  id: "web_research"
  provider: "agent-browser"
  description: "网页搜索与研究"
  input_schema: {}
  output_schema: {}
  permissions: ["search"]
  risk: "low"
  reliability: 0.90
  average_cost: 0.3
  average_latency_seconds: 20
  supported_modes: ["research"]
```

## 6. Skill Registration（新增 Skill 注册字段）

```yaml
skill:
  name: "xxx"
  capabilities: ["xxx"]
  input: { required: [], optional: [] }
  output: { format: "xxx" }
  permissions: ["read"]
  risk_level: "low"
  reliability: 0.0
  cost_level: "low|medium|high"
  latency_level: "low|medium|high"
  supports: { parallel: true, retry: true, resume: false }
```

不把 Skill 名硬编码进大量判断逻辑。

## 7. Routing Score

```text
routing_score = capability_match × reliability × output_fit
                × permission_fit × availability × historical_success
                ÷ (cost_factor × latency_factor × risk_factor)
```

## 8. Agent Handoff

```yaml
handoff:
  id: "handoff_xxx"
  from: "orchestrator"
  to: "agent-browser"
  objective: "研究 xxx"
  context: { project: "xxx", known_facts: [], relevant_history: [] }
  constraints: ["只使用近期资料", "需要来源"]
  inputs: ["xxx"]
  expected_output: { format: "structured_report", required_fields: [finding, evidence, source, confidence] }
  deadline: null
  risk_level: "low"
  permissions: ["search"]
  verification: ["至少两个独立来源"]
```

## 9. Context Boundary

只传目标/必要事实/必要历史/约束/输入/输出要求/权限/验证要求。避免 Token 浪费、隐私泄漏、无关信息干扰、错误上下文影响。不把整个 Agent 上下文复制给下一个。

## 10. Execution Plan

```yaml
execution_plan:
  id: "plan_xxx"
  objective: "xxx"
  tasks:
    - { id: "T1", action: "xxx", executor: "xxx", dependencies: [] }
    - { id: "T2", action: "xxx", executor: "xxx", dependencies: ["T1"] }
  parallel_groups: [["T3", "T4", "T5"]]
  success_condition: ["xxx"]
  max_runtime_minutes: 30
  max_tool_calls: 50
  max_iterations: 3
  max_retries: 2
```

## 11. Task State Machine

PENDING → READY → RUNNING →（WAITING→READY / RETRYING→READY / FAILED / CANCELLED / COMPLETED）。

## 12. Checkpoint

```yaml
checkpoint:
  plan_id: "plan_xxx"
  completed_tasks: ["T1", "T2"]
  running_tasks: []
  pending_tasks: ["T4"]
  artifacts: ["xxx"]
  current_state: ["xxx"]
  next_action: ["T4"]
```

## 13. Task Result

```yaml
task_result:
  task_id: "T1"
  status: "success|partial|failure"
  summary: "xxx"
  outputs: ["xxx"]
  evidence: ["xxx"]
  confidence: 0.0
  artifacts: ["xxx"]
  side_effects: ["xxx"]
  errors: []
  next_recommendation: null
```

## 14. Artifact

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

## 15. Evolution Candidate（orchestrator 上报）

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

## 16. 三方职责

```text
Scheduler (Cron/Event)   → 什么时候唤醒
Proactive               → 是否值得做
Orchestrator            → 怎么做、谁来做、按什么顺序
Agents / Skills         → 具体执行
```

## 17. Action Router 首选 Provider（参考）

| Task Type | 首选 Provider |
|---|---|
| search/browse/research | agent-browser |
| summarize/compare/write | summarize |
| retrieve/update ontology | ontology |
| research(社媒) | social-search |
| decision/analyze | proactive |
| analyze/update(学习) | self-evolution |
