# Governance — Self-Evolution v2

Governance 是 **Apply 前的安全闸门**。Apply 前必须逐项检查，任一不满足 → **REJECT**，不得 Apply。

## 检查清单（Code = Enforcement，`apply.py` governance_check）

| # | 检查项 | 说明 |
|:--|:--|:--|
| 1 | Proposal 是否存在 | 状态须为 PROPOSED 或已 APPROVED |
| 2 | Diagnosis 是否有效 | diagnostic status == DIAGNOSED |
| 3 | Evidence 是否存在 | proposal.evidence_refs 非空 |
| 4 | Target 与 Proposal 一致 | 不得扩大/漂移 |
| 5 | Change Level | 取值 G1-G6 |
| 6 | 是否需要人工审批 | G5/G6 → human；G4 → review_human |
| 7 | 是否有 Regression Plan | test_plan 非空 |
| 8 | 是否有 Rollback Plan | targets 存在（snapshot 可回滚） |

任一不满足 → **REJECT**，不 Apply。

## Change Level（遵循 Agent OS EVOLUTION-PROTOCOL）

| 级别 | 含义 | 审批 |
|:--|:--|:--|
| G1 | Prompt 指令措辞 | 低风险，可走授权策略 |
| G2 | 示例/模板 | 低风险，可走授权策略 |
| G3 | 工作流/流程 | 需 review |
| G4 | 评估标准/验证等级 | review + 人工 |
| G5 | 协议/策略定义 | **必须人工** |
| G6 | 安全/权限/Runtime | **禁止自动，强制人工** |

## 永远不得自动修改的目标

以下**任何情况**都不得由 Self-Evolution 自动修改（即使显式 --approve 也被 `_core.is_protected_target` 拦截）：

```
Permission
Security
Credentials
Secrets
Authentication
Approval Rules
Runtime
Infrastructure
Global Authority
AGENTS.md
SOUL.md
```

## 审批流

```
G1-G2 （低风险指令/示例）
  → 已有授权策略 或 用户确认
  → Apply → Regression

G3-G6
  → 变更候选（问题/证据/提议变更/预期影响/回归检查）
  → review queue（人工）
  → 多级审批（技术复核 → 用户/管理员批准，G5/G6 强制）
  → Apply（含 Snapshot）→ Regression check → 记录
```

被拒的候选**保留记录（含拒绝原因），不静默丢弃**。
