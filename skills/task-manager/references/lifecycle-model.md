# Task Manager 生命周期与联动参考

## 1. 生命周期状态机

```text
INBOX → PLANNED → READY → RUNNING
  ├── WAITING → READY
  ├── BLOCKED → READY
  ├── PAUSED → READY
  ├── RETRYING → READY
  ├── FAILED
  └── COMPLETED → REVIEW → ARCHIVED
CANCELLED
```

禁止任意跳转（如 FAILED→COMPLETED 须先重执行或人工确认）。

## 2. 状态定义

- INBOX：刚创建未规划
- PLANNED：已明确目标和执行方式
- READY：依赖满足可执行
- RUNNING：执行中
- WAITING：等外部条件/人/时间/资源
- BLOCKED：有阻塞原因
- PAUSED：主动暂停
- RETRYING：重试中
- FAILED：失败且暂时无策略
- COMPLETED：满足完成条件
- REVIEW：需复盘/验收/人工确认
- ARCHIVED：历史，不参与主动调度
- CANCELLED：被明确取消

## 3. 状态转换规则

INBOX→PLANNED→READY→RUNNING；RUNNING→{COMPLETED, WAITING, BLOCKED, RETRYING, FAILED, PAUSED, CANCELLED}；{WAITING, BLOCKED, PAUSED, RETRYING}→READY；COMPLETED→REVIEW→{ARCHIVED, READY}。

## 4. Task Lock 与崩溃恢复

崩溃后：扫描 RUNNING → 查 lock → 查 checkpoint → 查外部副作用 → 判断 resume/retry/wait/fail。不简单把所有 RUNNING 变 FAILED。

## 5. 与 Proactive 接口

Task Manager 提供：overdue/stale/blocked/waiting/goal_drift/high_value_unfinished 信号；Proactive 判断是否提醒/行动。

proactive-to-task：把 proactive 信号转标准任务；scan-to-proactive：把 scan 结果反馈 proactive。

## 6. 与 Orchestrator 接口

execution_request（task_id/objective/inputs/context/required_capabilities/permissions/risk/success_conditions/verification_level/budget）；execution_result（task_id/status/summary/outputs/artifacts/evidence/confidence/side_effects/errors/next_action）回写状态。

## 7. 典型闭环

```text
Proactive 发现信号
  → link.py proactive-to-task      (INBOX)
  → task_manager.py update --status READY
  → link.py tasks-to-orchestrator  (交 Orchestrator)
  → Orchestrator 执行
  → link.py result-to-task         (回写 COMPLETED/FAILED)
  → link.py all                    (scan + Ontology + 失败学习)
```

## 8. Notification Policy

silent / digest / normal / urgent / critical。默认：低价值→silent；一般→digest；重要→normal；紧急→urgent；真正不可等待→critical。Digest 合并低优先级任务。

## 9. 打扰预算

```yaml
interruption_budget:
  max_high_priority_notifications: 3
  max_normal_notifications: 5
  used: 0
```

超预算 → QUEUE，除非真正紧急。

## 10. Escalation 触发

关键任务失败 / 连续重试失败 / 高风险 / 权限不足 / 超预算 / 接近硬截止 / 重要外部依赖失效。处置：ask_user / notify / create_review / pause。

## 11. 每日 / 每周复盘

- Daily：扫 overdue/stale/blocked/waiting/high priority/goal drift/重复/backlog → digest → 供 Proactive。
- Weekly：完成率/超期率/失败率/重复率/平均周期/长期积压/Goal Progress/Agent Performance，找「为什么做不完/为何反复失败/哪些无价值/哪些该自动化」→ Self-Evolution。

## 12. 命令接口

task list/show/create/update/assign/pause/resume/cancel/retry/complete/review/archive/search/overdue/blocked/waiting。自然语言同样支持。
