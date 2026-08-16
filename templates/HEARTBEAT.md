<!--
Heartbeat checklist for the Proactive agent.

DO NOT delete this file while heartbeat is enabled. It tells the agent
what to check each time it wakes. If nothing needs attention, reply HEARTBEAT_OK.
-->

# Heartbeat Checklist

Heartbeat 被触发后，**不要默认执行任务**。按下面顺序检查，判断是否有值得行动的事项。

## 1. 高优先级事项

检查：
- 用户明确要求后续跟进的事项
- 已到期 / 临近到期的任务
- 等待用户确认的任务
- 失败或中断、需要恢复的任务
- 子 Agent 是否有重要结果返回

## 2. Proactive Registry

读取 `proactive-registry.yaml`（当前启用的主动关注项）。

只检查：
- `enabled: true` 的项目
- 当前时间 / 条件满足检查规则的项目
- 本轮确实需要检查的项目

**不要因为项目存在就每次执行。**

## 3. 外部事件

若存在已接入事件源，只检查：
- 新事件
- 状态变化
- 异常
- 用户真正关心的变化

**不要重复处理已经确认过的事件。**

## 4. 决策

- 无值得用户知道 / 需要 Agent 行动的事 → `HEARTBEAT_OK`（保持安静）
- 有需要处理的事：
  1. 判断优先级
  2. 调用对应 Skill / Tool / Agent
  3. 完成验证
  4. 必要时通知用户

## 5. 成本控制（不要）

- 每次运行所有 Skill
- 重复查询没有变化的数据
- 执行与当前时间无关的任务
- 为了"证明自己工作了"而发送消息

## 原则

> 醒来 ≠ 干活。
> 醒来 → 检查 → 判断 → 必要时行动（否则 HEARTBEAT_OK）。
