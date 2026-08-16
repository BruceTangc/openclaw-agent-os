---
name: memory-governance
version: 1.1.0
description: 内存治理策略层（Agent OS v1.1）。决定什么该成为持久记忆：稳定/有用/确定/可溯源/非冗余；晋升路径 observation→candidate→validate→promote→review；用户事实>已验证外部事实>Agent推断。OpenClaw 拥有存储/索引/召回，本模块只提供治理政策。
---

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Memory Governance

Purpose: decide what should become durable memory. OpenClaw owns storage/indexing/recall.

## Write criteria
Prefer durable writes when information is stable, useful later, sufficiently certain, attributable, non-redundant and allowed to store.

## Promotion
observation -> candidate -> validate -> promote -> review

## Priority
Explicit user-provided facts > verified external facts > agent inference.

Never silently overwrite important contradictions. Deduplicate stale operational notes. Distinguish fact from inference. Do not build a parallel memory database.
