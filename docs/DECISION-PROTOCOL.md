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

> **两层决策词汇（v1.6 冻结补）**：上述为 **Proactive 决策层**（被唤醒后判断“是否值得做”）。
> 任务执行中的 **Autonomy Decision 层** 顶层标准词为 `Continue / Complete / Change Strategy / Ask / Stop`
> （见 FOUNDATION-ARCHITECTURE.md §5/§17/§25）。映射关系：
> - `EXECUTE` intent → `Continue`
> - `ESCALATE` → `Stop(Ask)`
> - `WARN / NOOP` → `Continue`（继续但需留意）
> - `UNKNOWN` → 是状态不是决策，按上下文拆为 `WAIT/VERIFY/ASK/RECOVER` 再映射
> - `IGNORE / OBSERVE / QUEUE` → `Stop(Block)`（待核实）
> - `DENY` → `Stop(Block)`

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

三层防御：OpenClaw Runtime 管 tool-call loop；Agent OS 管业务循环；Execution Record 跨模块判断“有没有进展”。

### 5.1 Proactive 局部防循环

每次 cycle 携带：

```
cycle_id
parent_task_id
retry_count
action_signature
last_action_time
escalation_state
```

`action_signature` 由代码确定性生成（不依赖 LLM）：
```
hash(goal_id + task_id + action_type + normalized_target)
```

### 5.2 Progress Gate（Execution Record）

相同 action 本身不等于 loop。只有：

```
same action + same result + no new evidence + no new state
```

才进入 no-progress 计数：

| consecutive_no_progress | decision |
|---|---|
| 1 | WARN |
| 2 | NOOP |
| >=3 | ESCALATE |

同 action 但 result/evidence/state 有变化 → CONTINUE（正常执行）。

### 5.3 Wake Cooldown

`state --op wake` 内置 60 秒 cooldown：

- cooldown 内 → `NO_ACTION`
- cooldown 外 → 正常 wake

### 5.4 Signal Fingerprint

Signal 使用稳定 fingerprint（`hash(type + subject + source)`），不使用 timestamp 作为唯一 identity。

### 5.5 边界

- OpenClaw Runtime 负责 runtime/tool-call loop
- Agent OS 负责 business/control-plane loop
- Self-Evolution 只接收结果，不负责 retry/loop detection/runtime stop