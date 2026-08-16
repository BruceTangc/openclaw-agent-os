# OpenClaw Agent OS v1.1 Production

Target baseline: OpenClaw 2026.7.1-2.

This package provides the governance, decision and workflow layer around OpenClaw's native runtime.

## Install
1. Back up existing versions of any same-named Skills.
2. Copy each directory under `skills/` into the OpenClaw skills directory you use.
3. Read `INSTALL.md`.
4. Enable/verify Skills according to your OpenClaw installation.
5. Run the smoke tests in `tests/`.

## Design rule
OpenClaw native runtime first. These Skills must not create parallel runtimes for memory, context, tasks, scheduling, events, agents or permissions.

## Modules
proactive
memory-governance
knowledge-governance
ontology
context-orchestration
task-manager
orchestrator
permission-security
verification-evaluation
self-evolution
summarize

## Safety
High-risk external actions remain subject to OpenClaw native policy/approval. Self-evolution cannot silently weaken security.
