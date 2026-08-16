# Proactive 注意力 / 打扰预算 / 状态模型参考

> 注意力预算、冷却、状态持久化细节。

## 1. 打扰预算（Interruption Budget）

```yaml
attention_budget:
  period: "day"
  critical: { limit: null }        # 不设限，可突破普通预算
  important: { limit: 3 }
  recommendation: { limit: 5 }
  low_priority: { limit: 0 }
```

规则：Critical 可突破普通预算；Important/Recommendation 达预算后进 Queue；Low 默认不打扰；同主题短时间不重复提醒。

## 2. 注意力冷却（Attention Cooldown）

同 Signal/Opportunity 刚提醒过且无新证据 → 不重复提醒。

| 级别 | 冷却 |
|---|---|
| Critical | 15 min |
| Important | 6 h |
| Recommendation | 24 h |
| Low | 72 h |

明显新变化可提前唤醒。

## 3. 唤醒预算（Wake Budget）

```yaml
wake_budget:
  max_llm_calls: 5
  max_tool_calls: 20
  max_runtime_minutes: 5
  max_new_opportunities: 10
```

## 4. 唤醒策略

- **Scheduled Wake**：Cron 定期（早晨/午间/晚间/每日复盘），每次先判断必要性。
- **Event Wake**：任务完成/失败、外部数据变化、用户输入、Skill 返回异常。
- **Opportunity Wake**：Watch 条目到达 next_review_at。

## 5. Proactive State（持久化）

```yaml
proactive_state:
  last_wake_at: "ISO-8601"
  attention: { important_used: 0, recommendation_used: 0 }
  queues: { p0: 0, p1: 0, p2: 0, p3: 0, p4: 0 }
  metrics:
    signals_today: 0
    opportunities_today: 0
    actions_today: 0
    successful_actions_today: 0
    rejected_today: 0
    false_positive_today: 0
  current_goal: { id: "xxx", alignment: 0.0 }
  active_plan: { id: null }
```

存 `skills/proactive/memory/state.json` 与 `queue.json`，由 scripts/proactive.py 读写。

## 6. 反骚扰（Anti-Spam）禁止

1. 同一信息重复提醒；2. 无新证据重复分析；3. 低价值信息打扰；4. Cron 唤醒就执行任务；5. 为用 Skill 而制造任务；6. 为表现主动而主动；7. 把普通变化夸大为异常；8. 未授权执行高风险。

## 7. 用户交互格式

- 主动提醒（【主动发现】发现/为什么值得关注/建议/风险/我可以…）
- 主动完成（【主动处理完成】我发现/已完成/结果/下一步）
- 需确认（【需要你确认】原因/计划/风险/是否执行）

## 8. 每日 / 每周复盘

- Daily：最多一条汇总（风险/机会/Goal Drift/自动完成/待确认/明日观察），除非 Critical。
- Weekly：统计主动行为数、有效率、接受率、误报率、重复提醒、成功率、新机会、新缺口 → Proactive Health Score。
