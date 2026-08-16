# Heartbeat Checklist

Heartbeat 每 2 小时唤醒一次。醒来后判断当前是否有值得主动提醒用户或需要 Agent 行动的事项；有则采取行动并通过 heartbeat 投递（target: last）发到最近渠道，无则回复 HEARTBEAT_OK 保持安静，不要为显示活跃而发送消息。

## 检查

1. **用户承诺 / 待办**
   - 用户明确要求后续跟进的事项
   - 已到期 / 临近到期的事项
   - 等待用户确认的事项

2. **当前任务 / 子 Agent**
   - 进行中任务是否需要继续
   - 失败或中断、需要恢复的任务
   - 子 Agent 是否有重要结果返回（完成 / 失败 / 阻塞）

3. **主动关注（Proactive Registry）**
   读取 `proactive-registry.yaml`：
   - 只看 `enabled: true` 的项目
   - 只检查当前条件满足的项目
   - 不要每次执行所有项目

4. **异常**
   - 最近失败 / 重复失败 / 阻塞
   - 明显风险

## 决策

- 无值得处理的事 → `HEARTBEAT_OK`
- 有值得处理的事 → 交给 Proactive Skill 判断
  （IGNORE / OBSERVE / QUEUE / SUGGEST / PREPARE / EXECUTE / ASK / ESCALATE）

不要因为 Heartbeat 被触发就强行执行任务。周期性确点任务（如"每天9点看行情"）应使用 cron，不要写进 HEARTBEAT.md。
