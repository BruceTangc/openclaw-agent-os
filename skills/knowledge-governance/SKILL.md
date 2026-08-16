---
name: knowledge-governance
version: 1.1.0
description: 知识治理策略层（Agent OS v1.1）。管理可复用知识为带来源/新鲜度/不确定性的持久声明（subject/claim/evidence/confidence/freshness/validity/status）；矛盾保留不静默覆盖；历史标记 obsolete/disputed。
---

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Knowledge Governance

Purpose: manage reusable knowledge as durable claims with provenance, freshness and uncertainty.

## Claim
subject / claim / evidence / confidence / freshness / validity / status.

## Intake
source -> extract -> normalize -> provenance -> contradiction check -> confidence -> retain/publish.

When knowledge changes, preserve history where practical and mark obsolete/disputed claims instead of silently replacing them.

Use OpenClaw's existing knowledge/memory facilities where possible. No second knowledge runtime.
