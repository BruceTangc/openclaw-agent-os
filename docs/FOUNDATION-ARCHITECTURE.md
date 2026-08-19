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

> **决策词汇（V4-Pro 复核 A-1 统一）**：Control Plane 的**唯一标准决策词**为
> `Continue / Complete / Stop`（及由此派生的 Stop 动作 `Ask / Block`）。各实现层
> 的子词汇（如 transition 推理的 `CONTINUE/WARN/NOOP/ESCALATE/UNKNOWN`、
> Proactive 的 `IGNORE/SUGGEST/.../DENY`）只是其**语义子映射**，必须能归一到
> 这套标准词；不允许第三种并列的顶层层级词汇。`Complete` 与 `Stop` 是必须由
> Transition Gate 实现的顶层决策，不得长期空缺。

## 6. Goal 层

Goal = 最终想达到的状态。必须含：`goal_id / objective / success_criteria /
progress_signal / current_state / created_at / updated_at`。
> Goal 不能只写自然语言；必须尽量有 Success Criteria + Progress Signal，否则无法判断"有没有进步"。

> **所有权切分（Architecture Contract v1.4）**：Goal/Task 存在**两个正交的所有权**，
> 必须严格分开，不允许混为一谈：
>
> | 维度 | 归属 | 负责 |
> |---|---|---|
> | **Goal/Task Runtime Ownership** | **OpenClaw Runtime** | Task object / Task 持久化 / Task 生命周期运行 / Task 调度与流程 / Task 执行（agent loop） |
> | **Goal/Task Governance Semantics** | **Agent OS Control Plane** | objective 语义 / success criteria / progress 语义 / 风险分级 / governance / verification 要求 / autonomy 决策 |
>
> 一句话：**OpenClaw 拥有 "Task 怎么跑"，Agent OS 拥有 "这个 Task 该不该跑、跑得好不好、要不要继续"**。
> Agent OS 只应作为 Control Plane 读取/判定 Goal/Task 的**语义**，绝不因提供 `task-manager` 语义就
> 声称自建 Task Runtime。文档里不许出现"Agent OS Task Manager owns task runtime"这类表述，
> 以免误读为 Agent OS 自建 Runtime（违反 §27 路由 + 禁止自建 Runtime 原则）。

## 7. Task 层

Task = 为 Goal 完成的一项工作。关系 `Goal ├── Task A/B/C`。
必须可追溯 `goal_id → task_id`；自主产生的 Task 必须有 Goal provenance。
> 归属同上：Task 的**运行生命周期**归 OpenClaw，Task 的**语义判定**（意图、成功标准、风险、
> 验证要求、是否继续）归 Agent OS。`goal_id → task_id` 溯源链是 Agent OS 的语义记录，
> 不构成对 Task 持久化存储的所有权声明。

## 8. Execution 层（重要概念）

> **Task 是意图，Execution 是一次实际尝试。** 不能把多次执行覆盖成一个状态。

```
Task T1 ├── Execution E1 → FAILED
        ├── Execution E2 → UNKNOWN
        └── Execution E3 → SUCCESS
```

保留每次执行，才能做 Retry / Recovery / Anti-loop / Cost / Evolution / Audit。

> **三个概念必须分开（Architecture Contract v1.4）**：
> 1. **Task**："我要做什么"（意图）。
> 2. **Execution**："我实际尝试做了哪一次"（一次有状态的尝试实体，有自己独立的执行状态）。
> 3. **Execution Record**："这次实际执行经过了哪些 Agent OS Protocol"（可观测性/审计记录）。
>
> Execution 不是 Task 的子标签，Execution Record 也不是 Execution 本身。
> Execution 状态机独立存在：`UNKNOWN / FAILED / RETRYING / SUCCEEDED`（以及 RUNNING）。
> 只有把 Task / Execution / Execution Record 三者切开，才能真正可靠地处理：
> retry / recovery / 重复副作用（duplicate side effect）/ crash recovery / anti-loop（L2）/ 执行核算。
>
> **Execution Record 的来源原则（Architecture Contract v1.4）**：
> Execution Record 是 **Control Plane 的语义/审计记录**，**不是 Runtime，也不是 Agent 自己随意填写的日志**。
> - 底层事实（before/after tool call、session/run 元数据）**应尽量取自 OpenClaw Runtime boundary**
>   （native hooks / tool adapters / runtime facade / plugin boundary），而不是完全依赖 Agent 自报。
> - 原因：Agent 自己创建自己的审计记录不可靠——若 Action 已发生但 Agent 中途崩溃，
>   "Action 已发生而 Record 未写"会丢失追踪；Agent 也可能错误记录。
> - 不因此自建 Agent OS Event Bus / Runtime（违反 §27）。当 OpenClaw 提供 runtime boundary
>   事件/hook 时，Agent OS 应**消费这些 native 边界**来补全 Execution Record 的底层事实。
> - Agent OS 负责的，是从这些底层事实推导**语义层判定**（进度、验证要求、是否继续/停止）。

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
示例：`RUNNING → Verification PASS→COMPLETED | Verified Failure→FAILED |
Unknown Outcome→FAILED/BLOCKED（task 层无 UNKNOWN——无法证明时按不可继续暂停，不留未知态）|
Governance Deny→BLOCKED`。
> 注：`UNKNOWN` 只允许存在于 **execution** 层（一次实际尝试结果未知），
> 不进入 task/goal 状态机 —— 未知的尝试必须通过 #18 Recovery 核实副作用后再降级，
> 不能把整个任务悬置在未知态。

## 14. Permission / Governance

```
Agent OS Permission → OpenClaw Native Policy/Approval → Tool Execution
```

> Agent OS Permission **不是** OpenClaw 权限系统的替代品，它是更高层的 Governance。
>
> **信任边界（V4-Pro 复核 B 补）**：Agent OS 返回的 `native_policy_final=True` 是
> **声明而非强制**——它只是告诉调用方"最终拦截应交给 OpenClaw Native Policy"，
> 并不保证 Native Policy 真的被调用。真正的强制边界只能在 **OpenClaw 侧**（Native
> Approval/Policy 作为 action-level 拦截）实现，Agent OS 无法替 OpenClaw 强制。
> 所以 Agent OS 侧的 Permission **必须 fail-closed**（拿不准就拒绝/ask），把剩余信任
> 交给 Native Policy；不能在 Agent OS 侧因为"有 native_policy_final=True"就放行。

## 15. Permission 必须绑定 Action

```
Task → Action → Action Fingerprint → Permission → OpenClaw Policy → Execute
```

批准"修改 foo.py"后若 Action 变成"删除 production.db"，必须**重新判断**。

## 16. Anti-Loop（三层，非简单 retry>3）

- **L1 Action Loop**：检测重复 Action (A/A/A)
- **L2 Execution Loop**：Retry→Failure→Recovery→Retry→Failure，检测 Retry Storm
- **L3 Goal Loop**：Task 都不同但 Goal Progress=0 → STALL/LOOP → STOP

> **三层必须全部落地（Architecture Contract v1.4）**：Anti-loop 不是只做 L1 Action 去重。
> 当前代码已实现 cycle_id / retry_count / action_signature / last_action_time（覆盖 L1 + 部分 L2），
> **但 L3 Goal Progress Loop 必须补齐**——它检测的是"Action/Execution 每次都不一样、
> 但 Goal Progress 始终为 0"的模式（A→B→C→D→A' 或 A→B→C 但零进展）。没有 L3，
> 仅靠 Action 级 anti-loop 检测不到"换着动作无效空转"。L1/L2/L3 是**三层叠加**，不是可选项。

> **L3 与 #17 的分工（V4-Pro 复核 A-3 补）**：`#16 L3 Goal Loop` 与 `#17 Progress
> Gate` 在实现上是同一个 `action/execution` 重复检测计数器，为避免条款重复、混乱，
> 明确分工：**#16 负责「检测」**（识别重复/无进展的行为模式），**#17 负责「决策」**
> （把检测结果映射为 Continue/Stop/Change Strategy/Ask）。二者是「检测器→决策器」
> 关系。应定义接口契约：检测器输出 `loop_type ∈ {ACTION, EXECUTION, GOAL}` +
> `repetition_count` + `progress_delta`；决策器据此产出顶层决策词（归一到
> Continue/Stop，见 #5）。Phase 2 wire 时按此契约落地。

> **Fast Path / Full Path 必须汇入同一套协议（Architecture Contract v1.4，防分叉）**：
> 简单任务走 Fast Path（无需 Orchestrator/Task 状态机/Proactive/Writeback），
> 复杂任务走 Full Path——但**两条路径最终必须汇入同一套** Governance / Execution /
> Verification / Evaluation / Progress / Completion 协议，不能演化成"Fast Path = 一套
> Agent OS、Full Path = 另一套 Agent OS"。二者只是**同一 Control Plane 的两种简化度**
> （Fast Path = 省略非必要的编排层，但 Permission/Verification/Progress/词汇归一 #5 不变），
> 不是两套互不共享的底层。

## 17. Progress Gate

不能"Action changed"就认为"Goal progressed"。须比较 current vs previous progress。
无 Progress → STALL_DETECTED → Stop / Change Strategy / Ask（而非无限运行）。

> **Progress Decision / Autonomy Decision（Architecture Contract v1.4，核心协议）**：
> Control Plane 的顶层决策不是"Evaluation 通过就继续"，而是必须形成一条明确的决策链：
>
> ```
> Verification ──▶ Evaluation ──▶ Progress Assessment ──▶ Autonomy Decision
>  (证据是否可信)     (结果是否达标)    (较上次是否有进展)    (Continue/Complete/
>                                                          Change Strategy/
>                                                          Ask/Stop)
> ```
>
> - **Evaluation ≠ Progress Gate**。Evaluation 判断"这次结果对 Goal 是否有价值/是否达标"；
>   Progress Gate 比较"Goal current vs previous progress"是否真的在逼近 success criteria。
>   二者不可混为一个"过得去就继续"的开关——否则会出现：每次 Task 都不同（Evaluation
>   认为"有产出"），但 Goal Progress = 0 持续很久（换着动作空转），Anti-loop L3 也难检测。
> - **Autonomy Decision 的顶层词汇（归一到 #5 的标准词）**：
>   - `Continue`：有进展，继续下一 Task。
>   - `Complete`：success criteria 达成，Goal 闭环。
>   - `Change Strategy`：确认停滞/低效，换策略而非无限重试（映射到 #5 的 Stop 系：暂时
>     停下当前行动，重新规划后 Continue）。
>   - `Ask`：信息不足/需用户或 Native Approval 推进（#5 Stop(Ask)）。
>   - `Stop`：不可证明有进展、风险过高或触达上限（#5 Stop(Block)，配合 #18 Recovery + Owner）。
> - 决策必须**可溯源**：记录 `progress_signal`（当前 vs 上次）+ `decision` + reason +
>   evidence 引用（对齐 #20），否则无法回答"为什么继续/为什么停在这里"。
> - **这是 Control Plane 区别于"Governance + Verification + Failure Retry"的最后一块**：
>   没有明确的 Progress/Autonomy 决策，系统更像失败重试机；补上后才是真正的 Autonomous
>   Control Plane。Phase 2 wire 时把 #16（检测器）↔ #17（决策器）按此契约落地。

## 18. Recovery

处理 Crash/Timeout/Gateway Disconnect/UNKNOWN/Corrupt/Partial Apply/Stale Execution。
**UNKNOWN 不能直接 Retry**，必须 `UNKNOWN → Verify Side Effect → Known Outcome → Continue/Retry`，
否则可能产生重复副作用。

> **通用副作用验证机制（V4-Pro 复核 A-4，Phase 3 前置）**：目前"Verify Side Effect"
> 仅在 Self-Evolution file_patch 落地一段，**通用 Control-Plane 层的副作用验证机制
> 尚未实现（连设计都没有）**。这是未来自主性的最大前置缺口，必须在 Phase 3
> （Autonomy Safety）实现前补齐：定义"如何判断一次 UNKNOWN 尝试是否产生了副作用、
> 副作用如何幂等回滚/去重重放"的统一接口。落地前，凡 encounter UNKNOWN 一律
> 按 fail-closed 停止（Stop+Block），不自动 retry。

## 19. Persistence

```
Source of Truth → Atomic Write → Derived Index
```

> **Corrupt ≠ Empty。** state.json 损坏绝不能变成 `{}` 覆盖原数据，应该
> `CORRUPTED → STOP → RECOVERY`。

> **STOP 责任人**：`STOP` 不是无人认领的悬空状态。谁检测到 `CORRUPTED`，谁就是该
> 状态的 **Owner** —— 由它执行 Recovery（#18），或把控制交回父级 Goal 的
> 责任 Agent / 触发方（Heartbeat/用户）。Owner 必须在持久化记录里显式写入，
> 否则 Stop 即死锁（见 #25 之后「Stop 的推进」）。

## 20. Identity / Traceability

```
goal_id → task_id → execution_id → action_id → observation_id
       → evidence_id → verification_id
+ agent_id / session_id（连接 OpenClaw Runtime）
```

最终回答：哪个 Agent、在哪个 Session、为哪个 Goal、执行哪个 Task、
哪次 Execution、调什么 Action、产什么 Evidence、为何最终变状态。

> **溯源字段补充（V4-Pro 复核 A-5/6）**：完整链还应纳入 `progress`（当前 vs 上一次）
> 与 `decision`（Continue/Complete/Stop 及依据），否则无法回答"为什么继续/
> 为何停在当前状态"。建议 goal/task 记录携带 `progress_signal` 与最近一次
> `decision`（含 reason + evidence 引用）。

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

> **Stop / BLOCKED / WAITING 的推进（V4-Pro 复核 A-4 补，防死锁）**：
> `STOP` 是决策输出，不是终态。`BLOCKED`/`WAITING` 状态必须有一个**明确的
> Owner + 恢复机制**，否则系统死锁。约定：
> 1. **产生 Stop 的 Agent 会话 = 该状态的 Owner**，写入持久化记录（含 owner_id）。
> 2. 恢复触发方（任一）：父级 Goal 的责任 Agent / 触发方（Heartbeat、用户）/
>    Recovery（#18）在副作用核实后的 Continue。
> 3. `ASK` 时由用户/OpenClaw Native Approval 提供推进；`BLOCK` 时由 Governance
>    （Permission 重新审批 via #14）或父任务解锁。
> 4. 无 Owner 的 Stop 视为架构缺陷——禁止把状态悬空无人推进。
>
> **transition 推理词汇归一（V4-Pro 复核 A-1 落地）**：`transition()` 的推理输出
> `CONTINUE/WARN/NOOP/ESCALATE/UNKNOWN` 均归一到标准词：CONTINUE/`WARN/NOOP` →
> `Continue`、`ESCALATE` → `Stop(Ask)`、`UNKNOWN` → `Stop(Block, 待 #18 核实)`。
> 不新增第三种顶层层级词汇。`Complete`/`Stop` 必须由 Transition Gate 实现（Phase 2 wire 目标）。

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
