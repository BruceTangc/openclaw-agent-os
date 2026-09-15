# OpenClaw Agent OS v2

**Adaptive Nervous System for OpenClaw**

Agent OS v2 makes OpenClaw learn from verified real work without duplicating OpenClaw runtime capabilities.

## Architecture Freeze

One Skill. Four stable core capabilities:

1. Verification — did reality satisfy the goal?
2. Experience — what reusable lesson follows from verified evidence?
3. Evolution — what future behavior should improve and why?
4. Governance — what may be learned, promoted or changed?

OpenClaw owns runtime, sessions, workspaces, tasks, subagents, multi-agent routing, tools, memory persistence/recall, context, automation, sandbox/approval and actual Workshop skill mutation.

## Multi-agent native

Agent OS learns across OpenClaw's native work graph without orchestrating it. It preserves agent/requester/parent/root/session/task/delegation provenance and separates local execution evidence from durable AGENT, TEAM and SHARED learning.

Ephemeral subagents produce evidence but do not become permanent learning identities by default.

## Core invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`.

## Upgrade invariant

Core code consumes stable capability contracts, not OpenClaw version numbers. Native capability wins. When OpenClaw supersedes a fallback, delegate to native, deprecate fallback, then remove it.

## Layout

- `SKILL.md` — single skill entry
- `protocols/` — four core, multi-agent and native-first protocols
- `schemas/` — stable data contracts
- `native/capability-registry.json` — capability ownership map
- `docs/ARCHITECTURE-V2.md` — frozen architecture
- `docs/CONTRACTS-V2.md` — contract specification
- `docs/V1.3-TO-V2-MIGRATION.md` — migration plan
- `tests/acceptance-v2.md` — architecture acceptance scenarios

v1.3 remains intact on `main` until v2 acceptance and implementation compatibility are proven.