# Proactive 信号与机会模型参考

> 详细数据模型，供 SKILL.md 之外查阅。字段为推荐结构，非强制 schema。

## 1. Signal（信号）

所有主动性首先转化为 Signal，尽量基于证据，不得因「感觉可能有事」创建高优先级行动。

```yaml
signal:
  id: "sig_xxx"
  timestamp: "ISO-8601"
  source: "cron|event|skill|browser|ontology|system|user"
  type: "change|anomaly|deadline|opportunity|risk|goal_drift|followup|failure"
  subject: "xxx"
  summary: "发生了什么"
  evidence: ["证据1", "证据2"]
  confidence: 0.0
  freshness: 0.0
  novelty: 0.0
```

## 2. Cheap Filter 条件

```text
是否重复？是否已经处理？是否过期？是否低价值？
是否没有行动空间？是否超出用户关注范围？是否只是普通信息？是否只是噪音？
```

命中 `novelty < threshold AND value < threshold AND no_action_possible = true` → 直接 IGNORE。

## 3. Context Enrichment 读取项

当前目标、当前项目、相关任务、最近历史、Ontology 关系、最近类似事件、用户最近意图、已有 Skill、权限、最近主动提醒记录。只读相关，不全量。

## 4. Opportunity（机会）

```yaml
opportunity:
  id: "opp_xxx"
  title: "xxx"
  source_signal: "sig_xxx"
  value: 0.0
  urgency: 0.0
  confidence: 0.0
  novelty: 0.0
  effort: 0.0
  risk: 0.0
  interruption_cost: 0.0
  reason: ["xxx"]
  recommended_action:
    type: "research|execute|prepare|ask|monitor"
    target_skill: "xxx"
  expires_at: "ISO-8601|null"
```

## 5. Risk（风险，优先级高于普通机会）

风险类型：system_risk / financial_risk / security_risk / privacy_risk / operational_risk / reputation_risk / deadline_risk / data_quality_risk / goal_risk / automation_risk。

## 6. Goal Drift（目标偏移）

```yaml
goal_drift:
  goal: "..."
  current_activity: "..."
  drift_score: 0.78
  evidence: ["..."]
  recommendation: "..."
```

Goal Drift 是建议，不自作主张改变用户目标。

## 7. Follow-up 检查

上次任务是否完成/失败、是否需要确认、是否有新下一步、外部条件是否变化、用户是否长期未处理、是否需要复盘。任务完成后自然产生下一步 → 创建 Follow-up。

## 8. Actionability（可行动性）

高价值但无可执行动作也不强制行动。判断：有明确动作？有 Skill？有权限？有数据？外部条件满足？否则 OBSERVE 或 ASK。

## 9. Priority Score（优先级）

```text
priority = value × urgency_factor × confidence × novelty
           × goal_alignment × actionability
           ÷ (effort_factor × risk_factor × interruption_factor)
```

归一化 0–100。映射见 SKILL.md Decision Rules。

## 10. Proactive Queue

P0 Critical / P1 Important / P2 Opportunity / P3 Research / P4 Watch。

```yaml
queue_item:
  id: "q_xxx"
  type: "risk|opportunity|task|followup|research"
  priority: 0
  status: "queued|running|waiting|done|dismissed|expired"
  created_at: "ISO-8601"
  next_review_at: "ISO-8601"
  owner: "proactive"
```

## 11. Autonomy Gate 检查清单

1. 是否属于已授权动作？2. 风险是否可接受？3. 是否需要用户确认？4. 是否涉钱？5. 是否外发？6. 是否删除？7. 是否涉账号权限？8. 是否涉隐私/敏感？9. 是否改关键系统状态？10. 是否超预算？

## 12. Action Router（能力路由示例）

```text
发现行业变化 → Agent Browser
大量信息压缩 → Summarize
知识关系更新 → Ontology
Skill 长期失败 → Self-Evolution
财务异常 → 财务 Skill
交易机会 → 交易 Skill
```

优先复用已有能力；禁止为一次主动任务临时复制 Skill。

## 13. 多 Agent 路由

判断任务类型 → 选最合适 Agent → 传 context/objective/constraints/expected_output/deadline/risk → 执行 → 返回 → verification。不让多 Agent 无意义并行。

## 14. Outcome（结果/反馈）

```yaml
outcome:
  action_id: "act_xxx"
  result: "success|partial|failure|rejected"
  user_feedback: "accepted|ignored|rejected|corrected|unknown"
  actual_value: 0.0
  cost: 0.0
  lesson: ["xxx"]
```

## 15. Self-Evolution Candidate 触发

同类任务连续失败 ≥3、同类建议连续被拒 ≥3、重复人工纠正 ≥3、能力缺失、流程冗余、明显可自动化模式。

## 16. 用户反馈解读

立即采纳→增强权重；连续拒绝→降权；反复纠正→Evolution Candidate；主动追问→提升优先级；明确「以后不用提醒」→更新偏好。一次拒绝≠永久偏好，需重复行为建立稳定结论。
