# Evolution Model — Self-Evolution v2

Self-Evolution v2 是一个 **Evidence-driven 的进化控制器**，不是并行 Runtime、也不是自造的 Scheduler。

## 唯一核心职责

解决 Agent 在长期运行中，如何从真实 Evidence 中发现可重复问题、形成改进方案、
经治理与验证后安全改变自身行为、并证明改变有效。

```
Evidence
 ↓
Discover      （发现可重复问题 → 判定是否够格成为 Candidate）
 ↓
Candidate     （只回答"什么问题值得解决"，不改任何文件）
 ↓
Diagnose      （找根因/可复现性/是否外部因素/是否已有方案/目标/级别/置信度）
 ↓
Proposal      （描述"准备如何最小修改"，可执行，不模糊）
 ↓
Governance    （Apply 前的安全闸门：全过才 REJECT 以外放行）
 ↓
Test          （Apply 前测试：已知失败/正常/边界用例）
 ↓
Apply         （笨：Approval → Snapshot → Apply exact change → Change Record → Regression）
 ↓
Regression    （最终裁判：Before vs After → IMPROVED/NO_CHANGE/REGRESSED/UNKNOWN）
 ↓
Promotion / Rollback
```

三层关系固定不变：

```
OpenClaw      → Agent Runtime / Session / Context / Tools / Skills / Workspace / Heartbeat / Cron
Agent OS      → Goal/Task / Execution / Verification / Evaluation / Evidence / Permission / Governance
Self-Evolution→ Discover / Candidate / Diagnose / Proposal / Governance / Test / Apply / Regression / Promotion / Rollback
```

## 十二项核心设计原则（写入 SKILL.md）

1. Evidence before Evolution
2. Repeated evidence before Candidate
3. Diagnosis before Proposal
4. Proposal before Apply
5. Test before Apply
6. Regression before Promotion
7. Rollback before continuing a failed evolution
8. Smallest effective change
9. Never invent evidence
10. Security and authority changes require human approval
11. Regression failure never automatically becomes a new Candidate
12. Self-Evolution never becomes a parallel Agent Runtime

## Evidence 边界

Self-Evolution **不重新建立** Verification / Evaluation / Execution Record。
这些来自 Agent OS，Self-Evolution 只消费。

```
Execution → Verification → Evaluation → Evidence
```

禁止把自我制造的循环失败当成新 Candidate：恶化时先 Rollback，再人工评估。

## 状态机

合法跳转：

```
CANDIDATE → DIAGNOSED → PROPOSED → APPROVED → APPLIED → REGRESSION → PROMOTED
失败路径：CANDIDATE→REJECTED / DIAGNOSED→UNRESOLVED / PROPOSED→REJECTED
        / APPLIED→REGRESSED→ROLLED_BACK
```

非法跳转由 `skills/_lib/transitions.py` 中央门强制拒绝（`_core.assert_transition` 为薄封装转发，Code = Enforcement）。
