# Proactive 优先级 / 自主性 / 决策模型参考

> 决策与优先级细节，供 SKILL.md 之外查阅。

## 1. 决策引擎（8 决策，唯一真值）

- **IGNORE**：没有价值或无行动空间。
- **OBSERVE**：值得关注，但现在不行动。
- **QUEUE**：等待合适时间。
- **SUGGEST**：告诉用户建议。
- **PREPARE**：主动准备资料，但不执行关键动作。
- **EXECUTE**：在授权范围内执行。
- **ASK**：需要用户确认。
- **ESCALATE**：高风险或超出能力边界，交用户或更高权限 Agent。

（DENY 由 permission-security 输出，非 proactive 输出。）

## 2. 评分→默认策略映射

| 分数 | 默认策略 |
|---|---|
| 0–20 | IGNORE |
| 20–40 | OBSERVE |
| 40–60 | QUEUE |
| 60–75 | SUGGEST |
| 75–90 | PREPARE / 低风险 EXECUTE |
| 90–100 | 高优先级处理 |

评分非绝对，Risk Gate 与用户授权优先。

## 3. 优先级覆盖顺序

```text
Safety
> User Explicit Instruction
> Permission
> Critical Risk
> Deadline
> Goal Alignment
> High Value Opportunity
> Routine Optimization
> Low Value Information
```

## 4. 主动性六层模型

- **L0 Reactive**：只响应用户明确请求。
- **L1 Remind**：主动提醒明确时间/期限/待办。
- **L2 Suggest**：主动发现问题并建议，不执行。
- **L3 Prepare**：主动准备信息/草稿/分析/计划。
- **L4 Execute**：低风险任务自动执行（搜索/整理/总结/分类/建内部任务/更新可自动维护数据/生成报告/研究计划）。
- **L5 Autonomous Loop**：授权范围内 发现→分析→规划→执行→验证→继续，但受权限/风险/预算/最大循环数/最大 Token/最大执行时间约束。

## 5. 自主循环（L5）默认上限

max_iterations = 3（除非明确授权更高）；max_steps = 10；max_runtime_minutes = 30。风险增加 → stop_and_ask；无进展 → stop_and_escalate；超预算 → stop。

## 6. 计划结构

```yaml
plan:
  objective: "xxx"
  success_condition: "xxx"
  steps:
    - { id: "1", action: "xxx", dependency: [] }
    - { id: "2", action: "xxx", dependency: ["1"] }
  max_steps: 10
  max_runtime_minutes: 30
  max_iterations: 3
```

## 7. 失败分类与策略

| 分类 | 策略 |
|---|---|
| temporary | retry |
| tool | retry with adjusted parameters |
| data | collect more data |
| permission | ASK |
| logic | replan |
| external | WAIT |
| unknown | ESCALATE |

## 8. 长期学习统计指标

主动建议接受率 / 主动执行成功率 / 用户拒绝率 / 误报率 / 重复提醒率 / 平均价值 / 平均成本 / 平均打扰次数。

## 9. Proactive Health Score

```text
health = acceptance_rate + execution_success + goal_alignment + verified_value
         − false_positive − interruption_cost − failure_rate
```

目标不是「主动次数越多」，而是「更少的主动行为，产生更高的实际价值」。
