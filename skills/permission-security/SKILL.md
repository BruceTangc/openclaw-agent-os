---
name: permission-security
version: 1.1.0
description: 权限安全策略层（Agent OS v1.1）。L0 Observe/L1 Prepare/L2 External/L3 High/L4 Prohibited 风险分级；默认 L0自动/L1可逆自动/L2确认/L3显式审批/L4拒绝；位于 OpenClaw 原生 policy/exec/sandbox/approval 之上，never weaken native controls。配套脚本 scripts/permission.py 提供 --classify/--check 确定性接口。
---

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Permission Security

Purpose: risk and authority policy above OpenClaw native policy/exec/sandbox/approval.

L0 Observe: read/search/analyze.
L1 Prepare: drafts/reversible local changes.
L2 External impact: messages/email/publishing/business changes.
L3 High impact: deletion/payments/permissions/sensitive export/dangerous host operations.
L4 Prohibited: bypassing security, credential theft, unauthorized/destructive behavior.

## Default
L0 auto if native policy permits.
L1 auto if reversible/in scope.
L2 confirmation unless explicitly authorized.
L3 explicit approval plus target/scope verification.
L4 deny.

## Gate
authority -> target/scope -> risk -> native policy -> approval -> reversibility -> confirmation -> minimal execution -> verification.

Never weaken or bypass native controls.
