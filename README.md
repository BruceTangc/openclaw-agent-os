# OpenClaw Agent OS v2 — Architecture Preview

> Active v2 development branch. v1.3 remains the stable baseline on `main` until v2 acceptance is complete.

**Agent OS is OpenClaw's adaptive learning nervous system.** It learns from verified real work and user feedback without rebuilding OpenClaw's runtime.

## Architecture Freeze

One Skill, four stable core capabilities:

- **Verification** — did reality satisfy the goal?
- **Experience** — what reusable lesson follows from verified evidence?
- **Evolution** — what future behavior should improve and why?
- **Governance** — what may be learned, promoted or changed?

OpenClaw owns agent runtime, sessions, workspaces, tasks/task flow, subagents/A2A, routing, tools, memory persistence/recall, context, automation, sandbox/approval and actual Workshop skill mutation.

## Multi-agent native

Agent OS does not orchestrate agents. It learns from OpenClaw's native work graph. It preserves agent/requester/parent/root/session/task/delegation provenance and isolates durable learning into `AGENT -> TEAM -> SHARED` scopes.

Ephemeral subagents can produce Evidence but do not become permanent learning identities by default.

## Core invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`

Local PASS never proves global PASS.

## Native-first

Core protocols depend on stable capabilities, not OpenClaw version strings. Resolution order:

1. OpenClaw native
2. official OpenClaw plugin
3. Agent OS adapter
4. minimal Agent OS fallback

When OpenClaw adds a FULL equivalent capability, the fallback is deprecated and removed after compatibility validation. **OpenClaw gets stronger; Agent OS gets thinner.**

## v2 structure

```text
SKILL.md                         single skill entry
protocols/                       Verification / Experience / Evolution / Governance / Multi-Agent / Native-first
schemas/                         stable Evidence / Experience / Candidate / Identity contracts
native/                          capability registry + adapter boundary
docs/ARCHITECTURE-V2.md          frozen architecture
docs/CONTRACTS-V2.md             contract specification
docs/OPENCLAW-CAPABILITY-MATRIX-V2.md
docs/V1.3-TO-V2-MIGRATION.md
tests/acceptance-v2.md           architecture acceptance A1-A8
scripts/validate_v2.py           dependency-free architecture gate
```

Run the static gate with:

```bash
python scripts/validate_v2.py
```

## v1.3 migration

The old 11-Skill control-plane model is not carried forward as 11 v2 Skills. Native-overlapping modules retire; useful semantics are absorbed into the four core protocols. See `docs/V1.3-TO-V2-MIGRATION.md`.

## Status

`2.0.0-dev`: architecture/contracts/protocols/capability boundary frozen on this branch. Runtime integration must continue to use OpenClaw native facilities and pass A1-A8 before v1.3 is removed from the stable branch.
