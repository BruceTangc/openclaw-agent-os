# Task Manager 任务模型参考

> 任务结构、优先级、依赖、checkpoint、幂等、扫描的详细定义。

## 1. Task ID 与来源

Task ID 唯一，建议 `task_<date>_<random>` 或 UUID。同一外部请求绑定 request_id 防重复创建。来源：user / proactive / orchestrator / workflow / event / agent / system。

## 2. Task 类型

action / research / search / analysis / decision / writing / review / communication / followup / maintenance / scheduled / workflow / proactive / verification / waiting。允许扩展但别为每个业务建新类型。

## 3. 优先级

P0=紧急/关键/高影响；P1=高；P2=正常；P3=低；P4=Backlog。不单纯按「用户说得急不急」。

```text
priority_score = impact + urgency + goal_alignment + deadline_pressure
                 + dependency_impact + proactive_confidence − effort − risk
```

## 4. 截止时间

支持 due_at / start_at / soft_deadline / hard_deadline。超期标 OVERDUE（派生），不直接 FAILED。

## 5. 停滞（Stale）

除 deadline 外检测停滞（如 14 天未更新），依据 last_activity_at / expected_progress / task_type / priority 判定 STALE。

## 6. Parent / Child

Parent 完成条件可为 all children completed 或 required children completed（不默认全部）。

## 7. 依赖类型

hard_dependency / soft_dependency / data_dependency / approval_dependency / time_dependency / resource_dependency。通过 depends_on / blocks / blocked_by 表达。

## 8. Ready Queue 入队条件

status=READY + 依赖满足 + 权限可用 + 未暂停 + 预算可用。

## 9. Waiting 结构

```yaml
waiting:
  reason: "等待客户回复"
  waiting_for: "customer"
  expected_at: null
  followup_at: "ISO-8601"
```

## 10. Follow-up 结构

```yaml
followup:
  task_id: "task_xxx"
  next_at: "ISO-8601"
  max_attempts: 3
```

外部发送必须过 Permission Gate。

## 11. Checkpoint

```yaml
checkpoint:
  task_id: "task_xxx"
  progress: 0.55
  completed_steps: ["xxx"]
  current_step: ["xxx"]
  pending_steps: ["xxx"]
  artifacts: ["xxx"]
  next_action: ["xxx"]
  updated_at: "ISO-8601"
```

恢复时读 checkpoint → 验证外部状态 → 检查已发生副作用 → 安全位置继续，不默认从头。

## 12. 递归任务

frequency daily/weekly/monthly/custom/event-based；recurring_definition → 生成 task instance。错过多次默认 latest_only（也可 catch_up / skip_missed）。

## 13. 任务上下文分层

task_context / project_context / goal_context / memory_context / execution_context，只加载必要。

## 14. 历史与审计

每次状态变化记录 history_event（timestamp/actor/action/from/to/reason），不可覆盖。重要操作（创建/修改/分配/执行/权限/重试/失败/完成/取消/删除）走审计。

## 15. Task Lock

READY→LOCK→RUNNING，lock 含 owner/timestamp/ttl，防两 Agent 并发执行同一任务，超时可恢复。

## 16. Task 来源元数据

Proactive 创建任务须带 proactive_metadata（opportunity_id/reason/confidence/expected_value/urgency）；Agent 任务须带 parent task/objective/context/required_output/permission/risk/verification，不建无来源孤立任务。

## 17. 指标

Completion Rate / On-time Rate / Overdue Rate / Stale Rate / Retry Rate / Failure Rate / Manual Intervention Rate / Average Cycle Time / Average Waiting Time / Average Execution Time / Duplicate Rate / Replan Rate。

## 18. Task Health

health = progress + activity + dependency_health + deadline_health + execution_health → HEALTHY / AT_RISK / STALE / BLOCKED / OVERDUE / FAILED。

## 19. 任务模板

```yaml
task_template:
  id: "weekly_research"
  title: "每周研究"
  type: "research"
  required_capabilities: ["web_research"]
  verification_level: "V2"
  recurrence: { frequency: "weekly" }
```
