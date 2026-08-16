# OpenClaw Agent OS v1.1

Governance, decision and workflow policy layer around OpenClaw's native runtime.

> **Design rule:** OpenClaw native runtime first. These skills must **not** create
> parallel runtimes for memory, context, tasks, scheduling, events, agents or permissions.
> Skills provide policy, reasoning procedures and workflows; OpenClaw owns the runtime.

## Modules (11)

| Module | Type | Purpose |
|---|---|---|
| `proactive` | adjusted | Decide whether something useful should happen after wakeup |
| `task-manager` | adjusted | Goal/task semantics; OpenClaw owns task runtime |
| `orchestrator` | adjusted | Decomposition/delegation/sequencing policy; OpenClaw remains runtime |
| `ontology` | adjusted | Minimal semantic model of entities, relations, attributes, states |
| `summarize` | adjusted | Transform large/noisy material into decision-useful information |
| `self-evolution` | adjusted | Controlled, evidence-based improvement loop |
| `memory-governance` | new | What becomes durable memory; promotion path |
| `knowledge-governance` | new | Durable claims with provenance, freshness, uncertainty |
| `context-orchestration` | new | Select minimum useful information for a task |
| `verification-evaluation` | new | Prove task success vs. tool success; PASS/PARTIAL/FAIL/UNKNOWN |
| `permission-security` | new | L0-L4 risk/authority policy above native policy/approval |

## Architecture

```
Trigger (user / heartbeat / automation / hook)
 -> Context Orchestration
 -> Goal / Task semantics
 -> Proactive Decision
 -> Orchestrator
 -> Permission Security
 -> OpenClaw execution (native)
 -> Verification
 -> Evaluation
 -> Memory / Knowledge writeback
 -> Self-Evolution candidate
```

## Explicitly do NOT build

- scheduler runtime
- event bus runtime
- task database/runtime
- memory database/runtime
- context engine
- agent runtime
- parallel permission enforcement runtime

## Install

1. Back up existing same-named skills.
2. Copy each directory under `skills/` into your OpenClaw skills directory.
3. Read `docs/INSTALL.md`.
4. Run the smoke tests in `docs/tests/`.

Target baseline: OpenClaw 2026.7.1-2.

## Docs

- `docs/ARCHITECTURE.md`
- `docs/INSTALL.md`
- `docs/COMPATIBILITY.md`
- `docs/OPERATIONS.md`
- `docs/schemas/` — decision / evidence / state / task models
- `docs/tests/` — smoke test cases

## License

MIT