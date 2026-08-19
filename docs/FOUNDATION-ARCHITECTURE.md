# Agent OS — Final Foundation Architecture (冻结版)

> **状态：已冻结 (2026-08-19)。** 本文档是 Agent OS 后续所有开发的**唯一底层基线**。
> 除非爸爸显式重新解冻，否则**不再重新设计底层**。遇到新需求，只按 §27 的判定
> 路由到 OpenClaw / Agent OS / Skill / Self-Evolution，不再新增底层架构。

---

## 定位

> Agent OS 是运行在 **OpenClaw Runtime 之上**的 **Autonomous Control Plane**（自主控制平面）。

## 核心原则

> OpenClaw 负责"怎么运行 Agent"；
> Agent OS 负责"Agent **为什么**运行、**能不能**运行、运行得**怎么样**、**是否应该继续**运行"。

---

## 1. 总体架构（三层）

```
┌─────────────────────────────────────────────┐
│ OpenClaw  Native Agent Runtime             │
│  Model / Agent Loop / Prompt / Tool Calling │
│  Session / Gateway / Workspace / Skills     │
│  Native Permissions                         │
└──────────────────────┬──────────────────────┘
                       │ Runtime Interface
                       ▼
┌─────────────────────────────────────────────┐
│ Agent OS  Autonomous Control Plane          │
│  ┌───────────────────────────────────────┐  │
│  │ Autonomy Control:                     │  │
│  │  Goal / Progress / Decision /         │  │
│  │  Continue / Stop                      │  │
│  └──────────────────┬────────────────────┘  │
│                     │                       │
│  Goal → Task → Execution → Action           │
│                     │                       │
│                     ▼                       │
│  Observation → Evidence → Verification      │
│                     │                       │
│                     ▼                       │
│            Transition Gate                  │
│            Continue  Complete  Stop         │
│  ────────────────────────────────────────   │
│  Permission │ Anti-Loop │ Recovery │         │
│  Governance │ Identity  │ Persistence │      │
│  Audit                                      │
│  ────────────────────────────────────────   │
│  Ontology / Evidence                        │
│  ────────────────────────────────────────   │
│  Self-Evolution                             │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Capabilities                                │
│  Skills / Tools / Specialized Agents /      │
│  External Services                          │
└─────────────────────────────────────────────┘
```

## 2-4. 三层必须严格区分

| 层 | 负责 | 不负责 |
|---|---|---|
| **Layer 1 · OpenClaw Runtime** | Agent Loop, Model, Prompt, Tool Calling, Session, Gateway, Workspace, Skill Loading, Native Execution, Native Approval/Policy | Goal 治理 |
| **Layer 2 · Agent OS Control Plane** | Goal, Task, Execution, Governance, Verification, Progress, Autonomy, Recovery, Evidence, Audit, Self-Evolution | 重复实现 Runtime |
| **Layer 3 · Capabilities** | 具体能力 (Browser/Search/Finance/...) | 自己决定系统级治理 |

> 未来增加 100 个 Skill，也不改变 Agent OS 底层架构。

## 5. 核心执行闭环（最重要的协议）

```
Goal → Task → Execution → Action → Observation → Evidence
  → Verification → Progress → Decision
Decision → Continue | Complete | Stop
Continue → Next Task ; Stop → Ask / Block
```

## 6. Goal 层

Goal = 最终想达到的状态。必须含：`goal_id / objective / success_criteria /
progress_signal / current_state / created_at / updated_at`。
> Goal 不能只写自然语言；必须尽量有 Success Criteria + Progress Signal，否则无法判断"有没有进步"。

## 7. Task 层

Task = 为 Goal 完成的一项工作。关系 `Goal ├── Task A/B/C`。
必须可追溯 `goal_id → task_id`；自主产生的 Task 必须有 Goal provenance。

## 8. Execution 层（重要概念）

> **Task 是意图，Execution 是一次实际尝试。** 不能把多次执行覆盖成一个状态。

```
Task T1 ├── Execution E1 → FAILED
        ├── Execution E2 → UNKNOWN
        └── Execution E3 → SUCCESS
```

保留每次执行，才能做 Retry / Recovery / Anti-loop / Cost / Evolution / Audit。

## 9. Action 层

Execution 可含多个 Action。Action 必须含：
`action_id / execution_id / tool / parameters / fingerprint / timestamp`。
> **Permission 最终必须落到 Action。**

## 10. Observation

Action 执行后产生 Observation。关系必须 `Action → Observation`，不把所有结果
混成一个 Execution Result。

## 11. Evidence

Observation ≠ Evidence。Evidence 必须可追溯：
`evidence_id / action_id / execution_id / source / timestamp / content|reference`。
例：Observation "pytest exit 0" → Evidence "tests_passed"。

## 12. Verification

> **LLM 自己宣布成功不能直接改变任务状态。**

```
Action → Observation → Evidence → Verification → PASS → Task: COMPLETED
```

Verification 是 Control Plane 最重要的可信度层之一。

## 13. Transition Gate

所有关键状态变化必须经过 **Transition Gate**：
`transition(entity, target_state, reason, evidence)`。
禁止 `task["status"] = "COMPLETED"` 直接修改。
示例：`RUNNING → Verification PASS→COMPLETED | Verified Failure→FAILED | Unknown→UNKNOWN | Governance Deny→BLOCKED`。

## 14. Permission / Governance

```
Agent OS Permission → OpenClaw Native Policy/Approval → Tool Execution
```

> Agent OS Permission **不是** OpenClaw 权限系统的替代品，它是更高层的 Governance。

## 15. Permission 必须绑定 Action

```
Task → Action → Action Fingerprint → Permission → OpenClaw Policy → Execute
```

批准"修改 foo.py"后若 Action 变成"删除 production.db"，必须**重新判断**。

## 16. Anti-Loop（三层，非简单 retry>3）

- **L1 Action Loop**：检测重复 Action (A/A/A)
- **L2 Execution Loop**：Retry→Failure→Recovery→Retry→Failure，检测 Retry Storm
- **L3 Goal Loop**：Task 都不同但 Goal Progress=0 → STALL/LOOP → STOP

## 17. Progress Gate

不能"Action changed"就认为"Goal progressed"。须比较 current vs previous progress。
无 Progress → STALL_DETECTED → Stop / Change Strategy / Ask（而非无限运行）。

## 18. Recovery

处理 Crash/Timeout/Gateway Disconnect/UNKNOWN/Corrupt/Partial Apply/Stale Execution。
**UNKNOWN 不能直接 Retry**，必须 `UNKNOWN → Verify Side Effect → Known Outcome → Continue/Retry`，
否则可能产生重复副作用。

## 19. Persistence

```
Source of Truth → Atomic Write → Derived Index
```

> **Corrupt ≠ Empty。** state.json 损坏绝不能变成 `{}` 覆盖原数据，应该
> `CORRUPTED → STOP → RECOVERY`。

## 20. Identity / Traceability

```
goal_id → task_id → execution_id → action_id → observation_id
       → evidence_id → verification_id
+ agent_id / session_id（连接 OpenClaw Runtime）
```

最终回答：哪个 Agent、在哪个 Session、为哪个 Goal、执行哪个 Task、
哪次 Execution、调什么 Action、产什么 Evidence、为何最终变状态。

## 21. Proactive

Proactive **不是 Runtime**，只是自主控制的**触发机制**。
`Heartbeat → Proactive → Eligibility Check → 有没有该做的 → YES → Goal/Task → 正常 Control Plane`。
必须经过 Permission/Eligibility/Cooldown/Dependency/Ownership/Goal State/Anti-loop，
禁止直接 `Heartbeat → Execute`。

## 22. Ontology / Evidence Store

事实与关系层，记录 Goal/Task/Execution/Action/Observation/Evidence/Verification/
Decision/Change/Outcome。**不是** Memory Runtime，也不是 Vector Context Engine。
解决"Control Plane 对过去发生的事实有什么可追溯记录"。

## 23-24. Self-Evolution

受治理的自我修改：Candidate→Diagnosis→Proposal→Approval→Snapshot→Apply→
Verification→Regression→Monitoring→Validation→Promotion。
继承 Agent OS 全部 Control Plane 规则（Permission/Verification/Evidence/
Rollback/Anti-loop），**不能绕过治理层**。
必须保持 `evolution_id` 贯穿全程，`evolution_id mismatch → REJECT`。

## 25. 最终自主模型（压缩）

```
GOAL → TASK → EXECUTION → GOVERN/ANTI-LOOP → ACTION → OPENCLAW RUNTIME
  → OBSERVATION → EVIDENCE → VERIFICATION → TRANSITION GATE → PROGRESS
  → CONTINUE | COMPLETE | STOP → NEXT TASK | ASK/BLOCK
```

外围永远存在：**Permission / Recovery / Persistence / Identity / Audit / Ontology**。
Self-Evolution 运行在整个 Control Plane 之内。

## 27. 冻结判定（唯一路由）

```
它是不是 Runtime？    → 是 → OpenClaw
它是不是 Control Plane？→ 是 → Agent OS
它是不是具体能力？    → 是 → Skill
它是不是修改自身？    → 是 → Self-Evolution
```

> **不再因为新增一个功能就增加一个新的底层架构。**

## 最终一句话

这套 Agent OS 不是要做成"一个比 OpenClaw 功能更多的 Agent"，而是做成：

> **让 OpenClaw Agent 能够长期、自主、可验证、可恢复、可控地运行的 Control Plane。**

---

## 附录 A：V4-Pro 深度核查 ↔ 架构条款对齐（2026-08-19 冻结时验证）

> 爸爸指令：底层冻结前，确认 V4-Pro 核查结果是否按本架构来。结论：**全部对齐，无一条要求推翻架构。**

| V4-Pro 审出 | 对应架构条款 | 判定 |
|---|---|---|
| C-1 execution/action ID 碰撞 | #8 (Execution 多次不覆盖) / #20 (Identity 链) | ✅ 强对齐 |
| C-2 verify_trace 误报短链 | #22 (部分模块只产 Evidence) | ✅ 对齐 |
| C-3 attach 掩盖断裂 | #20 (链可追溯真实) | ✅ 对齐 |
| A-1 双轨制绕过面 | #13/#14 (Transition Gate 强制 + Governance) | ✅ 对齐 |
| A-2 CONSUMED 一次性未消费 | #15 (Permission 绑定 Action) | ✅ 对齐 |
| A-3 授权不持久化 | #19 (Source of Truth) / #22 | ✅ 对齐 |
| B-1 retryable 实例覆写 | #18 (Recovery/UNKNOWN 不盲 retry) / #17 (Progress Gate) | ✅ 对齐 |
| B-2 MRO / except ValueError | #20 | ✅ 无冲突 |
| D-1 permission 硬编码路径 | #13 (Gate 全局强制不静默失效) | ✅ 对齐 |
| D-2 errors import 路径 | #13 | ✅ 对齐 |

**结论**：当前底层与架构兼容；V4-Pro 审出的是缺陷修复、非架构推翻。底层冻结成立。

## 附录 B：C2 授权持久化落地（A-2/A-3，2026-08-19）

- **A-2**：`permission.py` 授权记录支持 `one_time` + `fingerprint`（绑定 Action，架构 #15）；check() 对一次性授权返回 `one_time_consumed` 标记，fingerprint 不匹配 → 授权失效须重新判断。
- **A-3**：授权决策 audit 留痕 —— 复用 `persistence.append_atomic` 写 `.agent-os/permissions/audit.jsonl`（JSONL append-only）；"谁批准"由 OpenClaw Native Approval 承接，Agent OS 只记录决策与依据（架构 #14/#19/#22）。
