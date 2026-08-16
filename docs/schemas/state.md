# State Model

Canonical semantic states（唯一真值，与 task-manager 生命周期一致；大写、含完整流转）：

```
INBOX → PLANNED → READY → RUNNING ←→ (WAITING / BLOCKED / PAUSED / RETRYING)
                          │
                          ├──→ FAILED（可 → READY 重规划）
                          └──→ COMPLETED → REVIEW → ARCHIVED
CANCELLED（任意非终态可取消）
```

状态定义（与 `task-manager/SKILL.md` 及其 `references/lifecycle-model.md` 对齐）：

| 状态 | 含义 |
|:--|:--|
| `INBOX` | 刚创建，尚未规划 |
| `PLANNED` | 已明确目标与执行方式 |
| `READY` | 依赖满足，可执行 |
| `RUNNING` | 执行中 |
| `WAITING` | 为已知条件故意暂停 |
| `BLOCKED` | 依赖外部条件/决策才能推进 |
| `PAUSED` | 用户/系统主动暂停 |
| `RETRYING` | 重试中 |
| `FAILED` | 执行失败且暂无继续策略 |
| `COMPLETED` | 满足完成条件（后果性工作需验证） |
| `REVIEW` | 需复盘/验收/人工确认 |
| `ARCHIVED` | 历史任务，不再参与调度 |
| `CANCELLED` | 明确取消 |

> 小写简化视图（planned/ready/blocked/completed…）仅作文档里的人类速记，不使用于状态机；状态机一律使用上表大写值。

Rules:
- `COMPLETED` requires verification for consequential work.
- `FAILED` requires evidence of failure.
- `BLOCKED` means progress requires an external dependency/decision.
- `WAITING` means work is intentionally paused for a known condition.
- 状态跳转遵循 task-manager 生命周期规则，禁止任意跳转（FAILED→COMPLETED 须先重执行或人工确认）。
