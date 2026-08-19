---
name: self-evolution
description: 受控、有证据、可验证、可回滚的自我进化控制器。从真实 Evidence 发现可重复问题→Diagnose→Proposal→Governance→Test→Apply→Regression→Promote/Rollback。发现重复失败或重复纠正后触发；绝不自改权限/安全/Runtime。
metadata:
  openclaw:
    emoji: "🧬"
  agent_os:
    protocol_version: "1.3"
    layer: "core"
version: 2.0.0
---

# Self-Evolution (v2)

> Evidence-driven 自我进化控制器。**不是另一个 Agent，不是并行 Runtime。**

## Purpose

OpenClaw Agent 在长期运行中，如何从**真实 Evidence** 中发现可重复问题、形成改进方案、
经治理与验证后**安全改变自身行为**、并**证明改变有效**。

三层关系固定：

```
OpenClaw       → Agent Runtime / Session / Context / Tools / Skills / Workspace / Heartbeat / Cron
Agent OS       → Goal/Task / Execution / Verification / Evaluation / Evidence / Permission / Governance
Self-Evolution → Discover / Candidate / Diagnose / Proposal / Governance / Test / Apply / Regression / Promotion / Rollback
```

**Self-Evolution 只消费 Evidence，不重新建立 Verification/Evaluation/Execution Record。**

## 生命周期（固定，不得设计第二套）

```
Evidence → Discover → Candidate → Diagnose → Proposal → Governance → Test → Apply → Regression → Promote/Rollback
```

## 十二项核心设计原则

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

## OpenClaw Boundary（绝不越界）

- **不创建**：Agent Runtime / Session Runtime / Context Runtime / Scheduler / Heartbeat / Cron / Event Bus / Permission Runtime / Memory Runtime
- **不重新实现**：Verification / Evaluation / Execution Record（来自 Agent OS）
- **不建**：Knowledge Graph / Vector DB / Embedding DB / PageRank / TF-IDF / Message Bus / Agent Registry / SQLite / Redis / 独立 Scheduler
- 存储用简单 workspace artifact：`.agent-os/evolution/`（候选/诊断/提案/变更/回归/索引）——是治理 artifact，不是 Runtime

## When to Activate（何时使用本 Skill）

**使用（发现系统性、可证明可重复的问题）：**
- 发现重复失败（同类任务连续 FAIL/PARTIAL）
- 发现重复人工纠正（用户/Agent 多次修正同一问题）
- 发现稳定行为缺陷（可复现）
- 发现可验证的效率问题（长期重复劳动）
- 发现系统性 workflow gap
- 发现已有 Evidence 支持的改进机会（recurrence>=3 且 sessions>=2）

**不使用：**
- 单次失败 / 临时 API 故障 / 随机网络失败 / 第三方服务异常 / 单次工具故障
- 用户一次性要求
- 普通 Memory 写入、普通 Knowledge 更新、普通 Ontology 更新、普通任务执行

## Evolution State（心跳巡检）

Self-Evolution **不自己创建 cron/heartbeat/scheduler**。
OpenClaw Heartbeat 唤醒 Agent → `Proactive` → 检查 Evolution State：

```
pending candidates / pending diagnoses / pending proposals / pending approvals / pending regressions / rollback required
```

无 → `NOOP`。有 → 只处理**当前最优先事项**，不每次跑完整 Pipeline。

## Commands（脚本目录 scripts/）

| 阶段 | 命令 | 说明 |
|:--|:--|:--|
| Discover | `python3 scripts/discover.py --evidence '<json>'` | Evidence → Candidate（门槛/幂等/禁止外部环境） |
| Diagnose | `python3 scripts/diagnose.py --candidate CAND-xxx --root_cause workflow_gap ...` | Candidate → Diagnosis（valid/reproducible/external/level） |
| Propose | `python3 scripts/propose.py --candidate --diagnosis --change ...` | Diagnosis → Proposal（最小可执行修改） |
| Apply | `python3 scripts/apply.py --proposal PRP-xxx --approve --approver ...` | Governance → Snapshot → Apply → Change Record |
| Regression | `python3 scripts/regression.py --change CHG-xxx --result IMPROVED ...` | 最终裁判 Before vs After → Promote/Rollback |
| Rollback | `python3 scripts/rollback.py --change CHG-xxx --reason ...` | REGRESSED → 恢复 Snapshot → ROLLED_BACK |
| Migrate | `python3 scripts/migrate.py --dry-run` | 一次性从旧版迁移（迁移后归档） |

> **Apply 契约**：`apply.py` 负责 **Governance 校验 / Permission 拦截 / Snapshot 建立 / Change Record 生成**，
> 它**不代为判断如何改文件**。真实写入 target 由调用方 Agent 严格按 proposal.change 的精确修改方案执行
> （写完后才允许 regression）。这样保持 Apply “笨”，只做 Enforcement。

> **MA-1.0 Integration#5（Skill 变更接 OpenClaw Workshop）**：
> Skill 作为 live capability 的实际创建/修改默认走 **OpenClaw Skill Workshop**（Agent 只能生成
> PROPOSAL.md，apply 才写入；更新绑定目标当前 hash，目标被改后 proposal 变 stale；apply 前重新安全扫描）。
> Agent OS self-evolution **不直接用 apply_patch 写 Skill**——它负责到 Proposal/治理边界为止；真实 Skill
> 写入由 OpenClaw Workshop 执行（Proposal → Review → Security Scan → Apply）。apply_patch 仅保留用于
> 非 Skill 的 governance 类变更（如配置文件/脚本的非 skill 修改），且仍受 protected targets 硬约束。
> 这样不新建 Skill Update Runtime，Agent OS 负责治理，OpenClaw 负责 Skill 实际生命周期。

> **MA-1.0 Integration#6（Apply 后 Verification/Record）**：
> Workshop/apply_patch 的写入**不代表进化完成**。Apply 后必须回到 Agent OS 做 validate_applied_files
> （指纹一致）、regression（behavior test）、security 检查；全部通过 → VERIFIED → Execution Record；
> 任一失败 → ROLLBACK（恢复 snapshot）。见 `apply.py _apply_change_locked` 的 apply→verify→regression 链路。

## 状态机（非法跳转被 Core 强制拒绝）

```
CANDIDATE → DIAGNOSED → PROPOSED → APPROVED → APPLIED → REGRESSION → PROMOTED
失败路径：CANDIDATE→REJECTED / DIAGNOSED→UNRESOLVED / PROPOSED→REJECTED / APPLIED→REGRESSED→ROLLED_BACK
```

## 幂等 / 可追溯 / 安全

- **幂等**：同 scope+target+pattern_key → 不重复建 Candidate；同 Proposal 不重复 Apply；同 Change 不重复 Regression
- **可追溯**：regression_id ↔ change_id ↔ proposal_id ↔ diagnosis_id ↔ candidate_id ↔ evidence_ids（`_core` evidence_chain）
- **保护目标**：Permission/Security/Credentials/Secrets/Auth/Approval Rules/Runtime/Infrastructure/Global Authority/AGENTS.md/SOUL.md —— 永不自动修改，即使显式 --approve 也被拦截
- **审批**：G1-G2 可走授权策略；G3 review；G4 review+人工；G5/G6 必须人工（强制）

## References

- `references/evolution-model.md` — 核心模型、三层关系、状态机、十二原则
- `references/candidate-policy.md` — Candidate 门槛、禁止错误学习、去重
- `references/governance.md` — Apply 前安全闸门、Change Level、审批流、保护目标
- `references/regression-policy.md` — Before/After 裁判、Promotion/Rollback、防死循环
