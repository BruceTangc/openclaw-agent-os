# Architecture (v1.3)

> v1.3 执行模型：**Fast Path / Full Path 分流** + **Mandatory 链 / Conditional 节点** +
> Self-Evolution 作为独立反馈循环（不是主链普通步骤）。

## 1. 执行模型总图

```
┌─────────────────────┐
│  OpenClaw Trigger   │  (user / heartbeat / cron / hook / background task)
└──────────┬──────────┘
           ▼
        INTAKE        (条件性: 非用户直接指令时摄入信号)
           ▼
  CONTEXT ORCHESTRATION  (Mandatory: 最小必要上下文)
           ▼
   ┌───────┴────────┐
   │                │
 Direct Task      Autonomous /
  (Simple)         Proactive     (条件性: 仅自主决策任务)
   │                │
   │           PROACTIVE DECISION (决策词汇表)
   │                │
   └───────┬────────┘
           ▼
      GOAL / TASK     (task-manager; 简单任务可最简化)
           ▼
   ┌───────┴────────┐
   │                │
 FAST PATH        FULL PATH
 (Direct Skill)   (Orchestrator: 拆解/路由/DAG)
   │                │
   └───────┬────────┘
           ▼
   PERMISSION GATE   (Mandatory: L2+ 无授权阻断; Fast Path 仅 L0-L1)
           ▼
   OPENCLAW EXECUTION (agent loop / tools / sub-agents / task flow)
           ▼
      VERIFICATION    (V0-V4; 工具成功 ≠ 任务成功)
           ▼
       EVALUATION     (PASS / PARTIAL / FAIL / UNKNOWN)
           ▼
   ┌───────┴────────┐
   │                │
  COMPLETE          FAIL
   │                │
   ▼                ▼
WRITEBACK IF    FAILURE LOOP
 NEEDED         (diagnose→repair→retry→re-verify, 预算内)
(条件性)         │
   │            ├─ 修复 → 回到 Orchestrator 重调度 (闭环)
   │            └─ 连续失败≥3 / 超预算 → ESCALATE (人工)
   ▼                ▼
EXECUTION      EVOLUTION  ◄───────┘ (仅限可授权变更)
 RECORD
 (Full Path / L2+ 任务生成协议执行证明,
  见 schemas/execution-record.md)
```

## 2. 两类路径定义

**Fast Path**（简单 / 低风险 / 单能力任务）
```
Trigger → Context → Goal/Task Semantics → Direct Skill → Permission Gate → Execution → Verification
```
- 适用：总结、搜索、查资料、简单计算、查询状态、文件整理、单次 API 调用。
- 约束：**Permission Gate 永远存在**——L0/L1 自动 ALLOW（无额外交互），L2+ 自动升级 ASK/policy/Full Path。
- 不需要：proactive 决策、task-manager 完整状态机、orchestrator DAG、强制 writeback。

**Full Path**（复杂 / 自主 / 多步骤 / 有副作用任务）
```
Trigger → Intake → Context → Goal/Task → Decision(如自主) → Orchestrator
  → Permission → Execution → Verification → Evaluation → Writeback(如需要) → Evolution(如证据)
```
- 适用：自动经营项目、多 Agent 研究、自动报价/交易分析、长期任务、主动发现问题、多步骤外部操作。

## 3. Mandatory 链与 Conditional 节点

- **Mandatory（所有任务必经）**：Context → Goal/Task Semantics → Permission Gate → Execution → Verification → Evaluation。
- **Conditional（按任务类型进入）**：
  - Intake / Proactive Decision：仅自主决策任务（heartbeat/cron/hook/风险/机会/目标漂移）。
  - Task Manager 状态机：仅 Full Path / 长任务（Goal/Task Semantics 本身 Mandatory）。
  - Orchestrator：仅 Full Path。
  - Writeback：有持久化价值才写；无价值 → NONE。
  - Evolution：有证据的重复失败/重复纠正才触发。
- 判定依据：任务类型 + Skill 的 Protocol Contract（`entry_mode` + `requires` 矩阵，见 SKILL-INTEGRATION.md）。

## 4. 失败闭环（Verification 之后的反馈回路）

```
Verification (V0-V4)
  ├─ PASS ───────────────→ Evaluation → COMPLETE → Writeback(如需要)
  └─ FAIL / PARTIAL ─────→ Failure Loop
                              │
                              ├─ diagnose → repair → retry within budget
                              │     ├─ 瞬时错误 → 预算内重试 (backoff)
                              │     ├─ 确定性错误 → 修复后 re-verify
                              │     ├─ 可换路径 → orchestrator 重路由 / 换 Skill
                              │     ├─ 可分解 → 拆子任务重调度
                              │     └─ 全部重试仍失败 / 连续失败 ≥3
                              │            └─→ ESCALATE (上报人工 / 用户确认)
                              ▼
                   回到 Orchestrator 重新调度 (闭环, 带 cycle_id + retry_count 防死循环)
```

- FAIL/PARTIAL 默认先走失败闭环（预算内），不直接丢给用户；预算用尽才 ESCALATE。
- 每次重试携带 `cycle_id / retry_count / action_signature / last_action_time`，相同动作无新证据 → NOOP（anti-loop）。
- 资金 / 不可逆操作失败 → 不自动重试，直接 ESCALATE。

## 5. Self-Evolution：第二条独立循环

Self-Evolution 不是主链的普通步骤，而是**从主链证据触发的独立反馈循环**：

```
                ┌─────────────────────────────┐
                │      SELF-EVOLUTION          │
                │  Evidence → Candidate →      │
                │  Classify → G1-G6 → Govern → │
                │  Proposal/Approval → Apply → │
                │  Regression check → Observe  │
                └──────────────▲──────────────┘
                               │ Evidence
                               │ (重复失败 / 重复纠正 / 评估弱点 / 低效 / 新需求)
Context → Decision → Action → Verification → Evaluation → Writeback
                 │                                          │
                 └──────────────────────────────────────────┘
                        (主链反馈信号)
```

- 触发条件：已验证失败（≥2 可复现）、重复用户纠正、重复评估弱点、反复低效、稳定新需求。
- 最小单位 G1-G6：G1 指令措辞 → G2 示例模板 → G3 工作流 → G4 评估标准 → G5 协议 → G6 安全/权限/Runtime。
- 审批：G1-G2 走授权策略；G3-G6 进 review queue；G5-G6 必须人工显式批准（详见 EVOLUTION-PROTOCOL.md）。
- 边界：安全规则永不自行修改；不为提高完成率削弱安全。

## 6. Ownership

OpenClaw owns runtime, sessions, context engine, memory storage/recall, goals, automation/heartbeat, background tasks, task flow, hooks, standing orders, sub-agents, tools and native policy/approval.

Agent OS owns policy, semantic models, decision procedures, governance, verification/evaluation and controlled evolution.
