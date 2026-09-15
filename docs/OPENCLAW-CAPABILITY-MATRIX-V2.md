# OpenClaw Capability Matrix for Agent OS v2

This matrix is a semantic ownership/boundary document, not a copy of OpenClaw implementation and not runtime capability detection. Re-audit it on OpenClaw upgrades that materially affect these surfaces.

| Capability domain | Owner | Agent OS RC3 action |
|---|---|---|
| Agent runtime / loop / reasoning wiring | OpenClaw | consume only |
| Workspace / bootstrap / persona files | OpenClaw | consume exposed identity/context; do not replace |
| Sessions / main session / session tools | OpenClaw | consume exposed provenance/results |
| Tasks / background tasks / task flow | OpenClaw | consume exposed task graph/results; do not manage state machine |
| Multi-agent bindings/routing | OpenClaw | consume exposed agent identity; do not route |
| Subagents / ACP / A2A | OpenClaw | consume exposed requester/child provenance; do not spawn as OS runtime |
| Tools / browser / shell / plugins | OpenClaw | treat exposed outputs as evidence sources |
| Memory persistence/search/user model | OpenClaw | use only when the native turn exposes a suitable facility; otherwise do not claim persistence/recall |
| Context assembly/compaction | OpenClaw | no parallel context engine |
| Automation/heartbeat/cron/hooks | OpenClaw | exposed results may become evidence; no Agent OS scheduler/hook runtime |
| Sandbox/tool policy/approval | OpenClaw | Governance supplies semantics; enforcement remains native |
| Skills / Workshop / self-learning apply | OpenClaw | Evolution proposes; apply only through an actually exposed native facility |
| Outcome verification semantics | Agent OS | semantic core |
| Experience extraction/scoping | Agent OS | semantic core unless native supersedes |
| Evolution candidate reasoning | Agent OS | semantic core unless native supersedes |
| Learning/change governance | Agent OS | semantic core; enforcement native |

## RC3 implementation note

Agent OS RC3 is a prompt/instruction Skill. It does not ship an executable Native Adapter or capability detector. `native/capability-registry.json` records expected ownership and integration boundaries only. `EXPECTED` and `CONDITIONAL` in that registry are not the `Capability.support` enum used by serialized capability observations in `schemas/capability.schema.json`.

## Upgrade procedure
1. Read current official OpenClaw documentation/release notes for materially changed surfaces.
2. Inspect what the running OpenClaw turn actually exposes; do not infer availability from this matrix.
3. Diff semantic ownership/expectations against the registry.
4. Classify any observed capability using the frozen Capability contract (`FULL | PARTIAL | NONE`) only when there is evidence to do so.
5. A FULL native equivalent supersedes a real Agent OS fallback/adapter if one exists.
6. Run the relevant acceptance scenarios; for a broad architecture change run the full A1-A30 suite.
7. Update instructions/contracts/matrix and any real adapter. The four core semantics remain stable unless the learning problem itself changes.
