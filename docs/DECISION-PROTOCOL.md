# Decision Protocol

> Agent OS v1.3 Core Protocol 之一。统一决策模型与词汇表。

## 1. 决策词汇表（唯一真值）

与 `skills/proactive/scripts/proactive.py` 的 `DECISIONS` 实现一致：

```
IGNORE    — 无行动价值，不打扰
OBSERVE   — 继续观察，暂不行动
QUEUE     — 有价值但当前不宜执行，入队
SUGGEST   — 建议给用户/上游，不自动执行
PREPARE   — 准备（草稿/计划/环境），可逆
EXECUTE   — 执行（低风险可逆/已授权）
ASK       — 需要用户确认（L2+ 或中高风险无授权）
ESCALATE  — 升级（连续失败/超预算/权限不足/高风险）
DENY      — 拒绝（由 permission-security 输出，非 proactive 输出）
```

## 2. 决策输入（Opportunity/Signal schema）

```yaml
id: "sig_xxx"
subject: "一句话主题"
summary: "补充说明"
type: "change|anomaly|deadline|opportunity|risk|goal_drift|followup|failure"
confidence: 0.0-1.0
freshness: 0.0-1.0
novelty: 0.0-1.0
expected_value: 0-100     # 期望价值
urgency: 0-100            # 紧急性
priority_hint: "P0-P4"    # 参考，需重算
evidence: []
```

## 3. 决策输出

```yaml
decision: "IGNORE|OBSERVE|QUEUE|SUGGEST|PREPARE|EXECUTE|ASK|ESCALATE"
score: 0-100
reason: "决策理由"
```

## 4. 评分要点

- 综合：impact + urgency + goal_alignment + deadline_pressure + dependency_impact + confidence − effort − risk
- 明确无行动空间 → IGNORE
- 任何风险类型都不得随意 EXECUTE（风险优先）
- 连续失败 ≥3 → ESCALATE
- 决策结果必须在模块间标准传递（同一词汇表）

## 5. Anti-loop（防死循环）

每次 cycle 携带：

```
cycle_id
parent_task_id
retry_count
action_signature
last_action_time
escalation_state
```

相同 action_signature 且无新证据/紧急性 → NOOP/IGNORE，不重复提醒。