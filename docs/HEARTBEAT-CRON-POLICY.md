# Heartbeat / Cron Policy

> Agent OS v1.3 Core Protocol 之一。明确 Heartbeat、Cron、Hook、Background Tasks 的定位：
> 它们都是**外部 Trigger**，不是 Agent OS 的一部分，不建自己的调度器。

## 1. 定位

| 机制 | 归属 | 作用 |
|:--|:--|:--|
| Heartbeat | OpenClaw | 周期性唤醒 agent（巡检、兜底检查） |
| Cron / Automation | OpenClaw | 精确时间触发（定时任务） |
| Hooks | OpenClaw | 事件触发（gateway:startup 等） |
| User Message | 外部 | 用户主动发起 |
| Background Tasks / Task Flow | OpenClaw | 持久化运行编排 |

**Agent OS 不制造任何 Trigger，不建 Scheduler。**

## 2. Proactive ≠ Cron

- **Cron = 定时触发机制**：负责"什么时候唤醒"。
- **Proactive = 主动决策能力**：负责"被唤醒之后，现在是否值得做、做什么"。

正确姿势：
```
Cron/Heartbeat/Hook  (OpenClaw 唤醒)
  → Proactive  (Agent OS 决策：该不该做)
  → Permission Gate  (高危拦截)
  → 执行
  → Verification
```

## 3. 每小时/每日唤醒建议

- Heartbeat 承担"是否有值得做的事"的低成本巡检。
- 无价值候选 → 保持安静（NOOP/IGNORE），不打扰用户。
- 有价值候选 → 按价值/紧急度 ≤ 预算内行动或排队。
- 相同信号未变化 → 不重复提醒（anti-loop）。

## 4. 禁止

- 用自定义 scheduler 替代 Cron/Heartbeat。
- 把 heartbeat 当成任务账本（任务状态归 task-manager）。
- 每个唤醒都重复执行相同动作（无新证据则 NOOP）。
