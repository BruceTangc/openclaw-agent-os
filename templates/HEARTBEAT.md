# Heartbeat Checklist

Heartbeat 唤醒后，运行 Proactive Skill 判断是否有值得主动处理/提醒的事项。

## 运行

- 调用 Proactive Skill（`skills/proactive/`）执行主动检查：
  - 读当前状态 / 信号，按 Proactive 决策流程判断
  - 有值得处理的事 → 判断优先级 → 行动或提醒
  - 无值得处理的事 → 回复 `HEARTBEAT_OK`，保持安静
- Proactive Skill 负责"该不该做、做什么"；Heartbeat 只负责唤醒。

## 边界

- 周期性精确任务（如"每天9点看行情"）用 OpenClaw cron，不写进 HEARTBEAT.md。
- 不为了显示活跃而发送消息；无实质价值就 HEARTBEAT_OK。
