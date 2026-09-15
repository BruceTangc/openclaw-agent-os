# OpenClaw Capability Matrix for Agent OS v2

This matrix is a boundary document, not a copy of OpenClaw implementation. Re-audit it on every OpenClaw upgrade.

| Capability domain | Owner | Agent OS action |
|---|---|---|
| Agent runtime / loop / reasoning wiring | OpenClaw | consume only |
| Workspace / bootstrap / persona files | OpenClaw | consume identity/context; do not replace |
| Sessions / main session / session tools | OpenClaw | consume provenance/results |
| Tasks / background tasks / task flow | OpenClaw | consume task graph; do not manage state machine |
| Multi-agent bindings/routing | OpenClaw | consume agent identity; do not route |
| Subagents / ACP / A2A | OpenClaw | consume requester/child provenance; do not spawn as OS runtime |
| Tools / browser / shell / plugins | OpenClaw | treat outputs as evidence sources |
| Memory persistence/search/promotion/user model | OpenClaw | persist/recall Experience through adapter |
| Context assembly/compaction | OpenClaw | no parallel context engine |
| Automation/heartbeat/cron/hooks | OpenClaw | may trigger learning; no scheduler runtime |
| Sandbox/tool policy/approval | OpenClaw | Governance maps decisions to native controls |
| Skills / Workshop / self-learning apply | OpenClaw | Evolution proposes; native applies |
| Outcome verification semantics | Agent OS | core |
| Experience extraction/scoping | Agent OS | core unless native supersedes |
| Evolution candidate reasoning | Agent OS | core unless native supersedes |
| Learning/change governance | Agent OS | core semantics; enforcement native |

## Upgrade procedure
1. Read release notes and changed official docs.
2. Discover capabilities, not version-number branches.
3. Diff against registry.
4. For overlap classify NONE/PARTIAL/FULL.
5. FULL native equivalent supersedes fallback.
6. Run acceptance A1-A8.
7. Update adapter/matrix; four core semantics remain stable unless the problem itself disappears.
