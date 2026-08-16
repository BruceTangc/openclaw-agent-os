---
name: context-orchestration
version: 1.1.0
description: 上下文编排策略层（Agent OS v1.1）。为任务选择最小有用信息：任务类型→所需实体→记忆/知识/本体检索→去噪→紧凑上下文包。不替代 OpenClaw Context Engine。
---

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Context Orchestration

Purpose: select the minimum useful information for a task. It does not replace OpenClaw Context Engine.

## Sources
conversation, goals/tasks, Memory, Knowledge, Ontology, workspace files, verified tool results.

## Procedure
1. Identify task and success criteria.
2. Identify required entities.
3. Retrieve relevant memory/knowledge.
4. Resolve identity/relationships through ontology.
5. Prefer fresh/verified information where needed.
6. Remove duplicate/noise.
7. Preserve material contradictions.
8. Produce a compact context package for normal OpenClaw execution.

Expand retrieval only when confidence is low, evidence conflicts, dependencies are missing, or exhaustive research is required.
