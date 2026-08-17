# Agent OS Protocol Checklist

> Agent OS v1.3 Core Protocol 之一。逐文件审计清单：判定一个 Skill / 一个任务 / 整个
> Agent OS 是否真正遵守 Core Protocol。用于爸爸的架构审计和自我回归。

## 1. 系统性检查（防止跑偏）

- [ ] **无并行 Runtime**：无自定义 Scheduler / Event Bus / Task Runtime / Memory Runtime / Context Engine / Agent Runtime / Permission Runtime。
- [ ] **Trigger 边界**：Heartbeat/Cron/Hook/User Message 都是外部 Trigger；Proactive 是决策层不是定时器。
- [ ] **OpenClaw 原生优先**：复用 agent loop / tool wiring / prompt assembly / session / skills，不重复造。
- [ ] **统一执行链**：Mandatory（Context → Goal/Task → Permission → Action → Verification → Evaluation）+ Conditional（Proactive 仅自主任务、Orchestrator 仅 Full Path、Writeback 有条件）。
- [ ] **统一决策词汇表**：IGNORE/OBSERVE/QUEUE/SUGGEST/PREPARE/EXECUTE/ASK/ESCALATE/DENY。
- [ ] **统一权限分级**：L0-L4（permission-security 治理 Skill）。
  - 注意：不建立独立 permission Runtime；OpenClaw native policy / approval / sandbox 才是最终执行边界。

## 2. 单 Skill 检查

- [ ] 声明 `x-agent-os` 接入块（protocol_version/layer/permissions/verification/memory_write/evolution_feedback）。
- [ ] frontmatter 有 name + description + version。
- [ ] 归类到 4 层之一（Cognition/Action/Control/Business）。
- [ ] 副作用动作过 Permission Gate。
- [ ] 后果性工作完成有验证证据。

## 3. 任务执行链检查

- [ ] **Fast/Full Path**：简单任务 Fast Path（Direct Skill），复杂任务 Full Path（Orchestrator）；不无谓 DAG。
- [ ] **Execution Record**：Full Path / L2+ 任务结束生成协议执行证明（见 schemas/execution-record.md）。

```
Intake      — 信号被正确摄入（id/subject/type/confidence…）
Context     — 只取最小必要上下文（context-orchestration）
Goal/Task   — 目标/任务语义清晰（task-manager）
Decision    — proactive 决策，词汇统一
Permission  — L2+ 无授权被阻断（permission-security）
Action      — 幂等 operation_id，actual ≤ authorized
Verification— tool success ≠ task success，PASS/PARTIAL/FAIL/UNKNOWN
Evaluation  — 目标达成评估（verification-evaluation）
Writeback   — 经验走 memory/knowledge-governance
Evolution   — 有证据才进化，安全规则需人工审批
```

## 4. 验证独立检查

- [ ] 不因工具返回成功就写 COMPLETED。
- [ ] V 等级与任务重要性匹配（资金/不可逆 → V4）。
- [ ] 外部状态改变有独立证据（state_changed）。
- [ ] 验证失败 → 修复 → 预算内重试 → 升级，而非放行。

## 5. Self-Evolution 安全检查

- [ ] 权限/安全/凭证/外部副作用/Runtime 变更 → 人工审批。
- [ ] 单次未验证失败不触发修改。
- [ ] 不为提高完成率削弱安全。
- [ ] 不自动批准自己的变更。

---

**用法**：审计者逐项打勾。任一系统项 ✅ 未满足 → Agent OS 跑偏，需回退到已冻结架构。