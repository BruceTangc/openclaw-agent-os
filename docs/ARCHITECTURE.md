# Architecture

## 主链路（正常路径）

```
Trigger (OpenClaw: user / heartbeat / cron / hook / background task)
  → Context Orchestration (最小必要上下文)
  → Goal / Task semantics (task-manager)
  → Proactive Decision (决策词汇表: IGNORE…EXECUTE/ASK)
  → Orchestrator (拆解 / 路由 / 调度)
  → Permission Security (L0-L4 门, L2+ 无授权阻断)
  → OpenClaw Native Execution (agent loop / tools / sub-agents / task flow)
  → Verification (V0-V4)
  → Evaluation (PASS / PARTIAL / FAIL / UNKNOWN)
  → Memory / Knowledge writeback (governance)
  → Self-Evolution candidate (有证据才进化)
```

## 失败闭环（Verification 之后的反馈回路）

```
Verification (V0-V4)
  ├─ PASS ───────────────→ Evaluation → writeback → Evolution candidate
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

**规则：**
- FAIL/PARTIAL 默认先走失败闭环（预算内），不直接丢给用户；预算用尽才 ESCALATE。
- 每次重试携带 `cycle_id / retry_count / action_signature / last_action_time`，
  相同动作无新证据 → NOOP/IGNORE（anti-loop）。
- 失败闭环的出口有两个：修复后重新进入 Orchestrator（闭环），或 ESCALATE（人工）。
- 资金 / 不可逆操作失败 → 不自动重试，直接 ESCALATE。

## Ownership

OpenClaw owns runtime, sessions, context engine, memory storage/recall, goals, automation/heartbeat, background tasks, task flow, hooks, standing orders, sub-agents, tools and native policy/approval.

Agent OS owns policy, semantic models, decision procedures, governance, verification/evaluation and controlled evolution.
