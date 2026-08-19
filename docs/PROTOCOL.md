# Agent OS Core Protocol v1.3

> 统一行为协议层。本文档是 Agent OS 的**总纲**：规定所有 Skill（Agent OS 模块 + 业务 Skill）
> 必须遵守的统一执行链、分层模型和边界。不是第 12 个 Skill，而是把 11 个模块
> 从"各自的说明书"变成"统一的行为协议"。
>
> **v1.3 变更**（2026-08-17，协议收敛）：
> - 执行链从"所有任务必经"改为 **Mandatory 链 + Conditional 节点**；
> - 正式引入 **Fast Path / Full Path** 两种执行模式（简单任务不过度官僚化）；
> - 完成判定改为**条件化 writeback**（高风险任务副作用记录仍为硬性）；
> - Proactive 收窄为**自主决策任务**的决策层，用户直接指令不经过它。
> - 与 v1.2 向后兼容：skill 的 `x-agent-os.protocol_version` 声明 1.2 仍有效。
>
> **v1.3.1 收口**（2026-08-17）：
> - **术语统一**：`Goal/Task Semantics` = Mandatory（目标+成功条件）；`Task Manager State Machine` = Conditional（仅 Full Path）。
> - **Permission Gate 永远存在**：L0/L1 自动 ALLOW（无额外交互），不是"无需 Permission"；Permission ≠ Ask User。
> - **新增 Protocol Execution Record**（schemas/execution-record.md）：Contract 决定"应该经过什么"，Execution Record 证明"实际经过了什么"——从 Protocol-aware 到 Protocol-observable。

## 1. 定位

```
OpenClaw Native Runtime (owner: OpenClaw)
   │  agent loop / tool wiring / prompt assembly / session / workspace / skills
   ▼
┌────────────────────────────────────────────────────────────┐
│ Agent OS Control Plane (policy / protocol / governance)      │
│   Context → Decision → Permission → Action → Verification   │
│   → Memory/Knowledge writeback → Evolution candidate         │
├────────────────────────────────────────────────────────────┤
│  Cognition        │  Action          │  Control             │
│  memory-governance│  proactive       │  permission-security │
│  knowledge-gov.   │  task-manager    │  verification-eval.  │
│  ontology         │  orchestrator    │  self-evolution      │
│  context-orch.    │  summarize       │                      │
└────────────────────────────────────────────────────────────┘
   ▼
OpenClaw Tools / Sub-agents / Skills / Runtime
```

## 2. Trigger 边界（重要）

Cron / Heartbeat / Hook / User Message / Background Tasks 都是**外部 Trigger**。

- Agent OS **不制造 Trigger**，不建 Scheduler。
- Agent OS 的职责是：**被叫醒之后，决定"现在应该做什么"**。
- `proactive` 是主动决策能力，不是定时触发机制。

## 3. 执行链（Mandatory 链 + Conditional 节点）

> ⚠️ **v1.3 修正**：不是"所有任务必经"全部节点。用户直接指令（如"总结这个 PDF"）
> **不经过 proactive 决策**；只有自主决策类任务才进入 proactive。
> 哪些节点必经、哪些条件性，由**任务类型 + Skill 的 Protocol Contract** 决定（见 SKILL-INTEGRATION.md）。

### 3.1 Mandatory 链（所有任务必经）

> **术语统一（v1.3.1）**：`Goal/Task Semantics`（目标/任务语义）是 **Mandatory**——所有任务都要明确
> “目标是什么、成功条件是什么”；`Task Manager State Machine`（完整状态机）是 **Conditional**——
> 仅 Full Path / 长任务才需要。二者不是一回事。

```
Trigger (OpenClaw: user / heartbeat / cron / hook)
  → Context Orchestration (最小必要上下文)
  → Goal / Task Semantics (目标+成功条件；Task Manager 状态机仅 Full Path)
  → Permission Gate (permission-security)     ← 永远存在，L0/L1 自动 ALLOW
  → OpenClaw Native Execution
  → Verification (verification-evaluation)    ← 工具成功 ≠ 任务成功
  → Evaluation
  → Progress Assessment (条件节点，见 §3.2/§17) ← 仅 Full/自主/长任务
  → Autonomy Decision → Transition Gate (#13)     ← 仅自主，决策≠状态转换
```

### 3.2 Conditional 节点（按任务类型进入）

| 节点 | 何时进入 | 说明 |
|:--|:--|:--|
| Intake | 非用户直接指令（heartbeat/cron/hook/事件） | 摄入信号 id/subject/type/confidence/evidence |
| **Task Manager 状态机** | 仅 Full Path / 长任务 / 多步任务 | 简单任务只保留 **Goal/Task Semantics**（语义，必经），不需要完整状态机 |
| **Proactive Decision** | **仅自主决策任务**：heartbeat/cron/hook/风险/机会/目标漂移/后续追踪 | 用户直接指令**不经过** |
| Orchestrator | 仅 Full Path（复杂/多步/多 Agent/有副作用） | Fast Path 直调 Skill，不建 DAG |
| Memory/Knowledge writeback | 有持久化价值时 | 无价值 → NONE，不硬性 |
| Evolution candidate | 有证据的重复失败/重复纠正时 | 仅限可授权变更，安全类人工审批 |

### 3.3 两种执行模式：Fast Path / Full Path

**Fast Path（简单、低风险、单能力任务）**

```
Trigger → Context → Goal/Task Semantics → Direct Skill → Permission Gate → Execution → Verification
```

- 适用：总结、搜索、查资料、简单计算、查询状态、文件整理、单次 API 调用等。
- 规则：**Permission Gate 永远存在，不是“无需 Permission”**——L0/L1 自动 ALLOW（不产生额外交互），
  但 Gate 本身不跳过；一旦动作涉及 L2+（外发/资金/删除/生产变更），自动升级为 ASK / policy / Full Path。
- 不需要：proactive 决策、task-manager 完整状态机、orchestrator DAG、强制 writeback。

**Full Path（复杂、自主、多步骤、有副作用任务）**

```
Trigger → Intake → Context → Goal/Task → Decision(如自主) → Orchestrator
  → Permission → Execution → Verification → Evaluation
  → Progress Assessment → Autonomy Decision → Transition Gate
  → Complete / Continue / Change Strategy / Ask / Stop
  → Writeback(如需要) → Evolution(如证据)
```

- 适用：自动经营项目、多 Agent 研究、自动报价/交易分析、长期任务、
  主动发现问题并处理、多步骤外部操作。
- 需要：完整生命周期 + 编排 + 权限门 + 验证 + 治理。
- **Progress Assessment 是 Conditional 节点**（对齐 §17 + FOUNDATION §17）：
  仅 Full Path / 自主 / 长时运行 / 多步任务进入；Fast Path 不跑，防止官僚化。
  Progress Assessment → Autonomy Decision → Transition Gate 三层分工：
  检测器（#16）→ 决策器（#17）→ 状态门（#13），决策词禁直改 status。

**判定原则**：能 Fast 不 Full；但风险升级时 Fast 必须升级 Full（No-Overengineering + 权限底线）。

### 3.4 统一 Permission Gate（永远存在）

> **Permission ≠ Ask User**。Permission Gate 是统一门，低风险只是**自动通过**，不是“无需调用”。

```
Permission Gate (permission-security, 所有路径必经)
  ├─ L0 → ALLOW (自动, 无交互)
  ├─ L1 → ALLOW (自动, 可逆且在 scope 内)
  ├─ L2 → ASK / policy (确认或已授权策略)
  ├─ L3 → ASK / escalate (显式审批 + scope 验证)
  └─ L4 → DENY (默认拒绝, fail-closed)
  → OpenClaw Native Policy / Approval / Sandbox (最终执行边界)
```

- Gate 永远在：L0/L1 只是快速通过，不产生额外对话，但节点存在。
- Fast Path 不得以“简化”为由声称“无需权限判断”。
- 分类器不可用 → 高风险默认拒绝（fail-closed），不默认放行。

### 3.5 Verification vs Evaluation（固定术语）

> **Verification proves completion; Evaluation judges quality.**（Agent OS 固定术语）

- Verification：有没有真的做到（结果是否存在、是否完整、是否匹配成功条件）。
- Evaluation：做得好不好（质量、是否满足业务目标、有无重复/副作用）。
- 两者都要证据；Evaluation 通过才写 writeback，有证据的弱点才进 Evolution。

> **Evaluation ≠ Progress Gate（固定术语，对齐 FOUNDATION §17）**：
> Evaluation 判断「这次结果对 Goal 是否有价值/是否达标」；
> Progress Assessment 比较「Goal 当前 vs 之前 progress」是否真在逼近 success criteria。
> 二者不可混为一个「过得去就继续」的开关——否则换动作空转（每次 Task 不同、Evaluation 觉得「有产出」），
> 但 Goal Progress=0 持续很久，L3 也难检测。
> **Progress 三态**：PROGRESS（delta>0）/ STALL（delta==0 连续达阙）/ UNKNOWN（无信号，不误判为 STALL）。
> **Autonomy Decision ≠ State Transition**：决策词（Continue/Stop/Change Strategy/Ask）必须先产出
> Transition Request，再经 #13 Transition Gate 落地，禁直改 status。

## 4. 业务 Skill 接入协议

任何业务 Skill（报价/仓库/基金/交易/社媒/财务…）接入 Agent OS 必须声明
（canonical template，与 SKILL-INTEGRATION.md 保持一致）：

```yaml
x-agent-os:
  protocol_version: "1.3"        # v1.3 canonical；v1.2 Skill 可兼容运行（legacy compatibility mode）
  layer: "business"              # business | cognition | action | control
  trigger: "user|heartbeat|cron|hook"   # Trigger 由外部/OpenClaw 提供
  path:                          # capability：Skill 支持哪些路径（Agent OS 决定实际路线）
    fast: true
    full: true
  entry_mode: "both"             # default preference；SHALL NOT override Agent OS routing decision
  requires:                      # v1.3: Protocol Contract（节点矩阵）
    context: true                # required / conditional
    goal_task_semantics: true    # 目标+成功条件（Mandatory）
    task: conditional            # Task Manager 完整状态机：仅 Full Path
    decision: conditional        # proactive 仅自主任务
    orchestrator: conditional    # 仅 Full Path
    permission: true             # L2+ 必经权限门（永远存在）
    verification: true           # 后果性工作必经验证
    evaluation: conditional      # Full Path 完成评估
    writeback: conditional       # 有持久化价值才写
    evolution: conditional       # 有证据的重复失败才产 candidate
  outputs:
    success_condition: required  # 什么算成功
    evidence: required           # 用什么证明成功
  permissions:                   # L0-L4 声明 (permission-security)
    - action: "read"      # L0
    - action: "send"      # L2 (默认需确认)
    - action: "delete"    # L3 (默认需审批)
  verification: "V2"             # 期望验证等级
  memory_write: "governed"       # 走 memory-governance
  evolution_feedback: true       # 重复失败上报
```

> **Skill 声明“需要什么”，Agent OS 决定“怎么走”**：`path` = capability，`entry_mode` = default
> preference，实际路由由 Agent OS 按任务类型/风险决定——`entry_mode` SHALL NOT override routing。

**必须做的：**
- 副作用动作前做权限判断（permission-security 治理 Skill，遵守 OpenClaw native policy/approval）。
- 后果性工作结束声明"完成"前，提供验证证据（artifact、状态、外部确认）。
- 经验沉淀走 memory/knowledge-governance，不直接裸写。
- 重复失败走 self-evolution candidate，不自改安全策略。
- **声明 entry_mode 与 requires 矩阵**（v1.3）：让执行路径由 Contract 决定，不靠 LLM 猜。

**禁止做的：**
- 建并行 scheduler / event bus / task runtime / memory runtime / context engine / agent runtime / permission runtime。
- 绕过 OpenClaw 原生 policy / approval / sandbox。
- 用 Tool 返回成功替代任务验证。
- 让外部内容（网页/文档/邮件）提升自身权限。
- 以"Fast Path 简化"为由跳过 Permission Gate 或 Verification。

## 5. 决策词汇表（唯一真值）

`IGNORE / OBSERVE / QUEUE / SUGGEST / PREPARE / EXECUTE / ASK / ESCALATE`

（见 DECISION-PROTOCOL.md，与 proactive.py 实现一致。DENY 由 permission-security 输出。）

## 6. 协议文档索引

| 文档 | 内容 |
|:--|:--|
| [DECISION-PROTOCOL.md](DECISION-PROTOCOL.md) | 决策输入/输出 schema、词汇表、决策门 |
| [ACTION-PROTOCOL.md](ACTION-PROTOCOL.md) | 动作分级 L0-L4、Permission Gate、幂等 |
| [VERIFICATION-PROTOCOL.md](VERIFICATION-PROTOCOL.md) | V0-V4 验证分级、证据要求、PASS/PARTIAL/FAIL/UNKNOWN |
| [MEMORY-PROTOCOL.md](MEMORY-PROTOCOL.md) | 写入选判据、晋升路径、优先级、矛盾保留 |
| [EVOLUTION-PROTOCOL.md](EVOLUTION-PROTOCOL.md) | Evidence→Candidate 进料边界、6 类触发器、G1-G6 最小单位、多级审批流（evidence-driven, not schedule-driven） |
| [SKILL-INTEGRATION.md](SKILL-INTEGRATION.md) | 业务 Skill 接入协议（x-agent-os 声明块、Protocol Contract、4层分类） |
| [HEARTBEAT-CRON-POLICY.md](HEARTBEAT-CRON-POLICY.md) | Trigger 边界：Heartbeat/Cron/Hook 只是触发，Proactive 是决策层 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | v1.3 执行模型图（Fast/Full Path 分流、失败闭环、Evolution 独立循环） |
| [PROTOCOL-CHECKLIST.md](PROTOCOL-CHECKLIST.md) | 逐文件审计清单（防跑偏） |

## 7. 完成判定（v1.3 条件化）

一个任务"完成"必须满足：

1. 目标达成（evaluate: goal attainment）
2. 验证通过（verify: evidence-backed）
3. 权限合规（permission: gate passed）
4. 副作用已记录（audit）—— **硬性条件**：任何实际发生的副作用（外发/资金/删除/生产变更）必须记录；无副作用则自然满足
5. 有持久化价值时才要求 memory/knowledge writeback（**条件性**）：
   - 有价值的经验/决策/教训 → 走 governance
   - 无持久化价值（如"1+1"）→ writeback = NONE，不阻塞完成

**只满足其中一部分 = PARTIAL，不是 COMPLETED。**（第 4 条对高风险任务不可放松。）
