# OpenClaw Agent OS v2

**Adaptive Nervous System for OpenClaw — zero-config Skill edition**

Agent OS v2 is one OpenClaw Skill with four learning semantics: **Verification, Experience, Evolution, Governance**. It uses OpenClaw's native runtime instead of rebuilding it.

## Install

```bash
openclaw skills install git:BruceTangc/openclaw-agent-os@agent-os-v2
```

That is the complete Agent OS setup. Git Skill installation expects `SKILL.md` at the repository root, which this branch provides. No Agent OS config file, Python runtime, heartbeat, cron, database, agent id, memory path, or post-install script is required.

Check it with:

```bash
openclaw skills info agent-os
openclaw skills check
```

Git installs are refreshed by reinstalling the Git source (OpenClaw's `skills update` tracks ClawHub installs, not unmanaged Git installs).

## What happens automatically

When OpenClaw selects Agent OS for substantive work, the current agent preserves the user's goal, executes through native OpenClaw, verifies the real outcome, derives only useful verified lessons, uses native memory/user-memory for durable writeback when available, and routes reusable improvement candidates through native self-learning/Skill Workshop when available.

It stays quiet by default; it does not print an Agent OS report after every task. Automatic coverage is not omniscient: hidden events not exposed to the Skill are never claimed as observed.

## Multi-agent

Agent OS does not orchestrate agents. OpenClaw does. Agent OS learns from native agent/session/task/delegation provenance. Permanent agents may own AGENT-scoped experience; ephemeral subagents contribute evidence but do not become permanent learning identities by default. TEAM and SHARED promotion is explicit and governed.

## Hard invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`.

## Native-first

OpenClaw owns runtime, sessions, tasks, routing, subagents, tools, memory, context, automation, approvals and Workshop application. Agent OS owns the learning semantics only. If OpenClaw gets a stronger native equivalent, Agent OS delegates to it and gets thinner.

## Status

`2.0.0-rc.3` is the current release candidate. The repository package has static architecture/schema/legacy-reference gates and A1-A30 acceptance specifications. Runtime-dependent acceptance still requires a real OpenClaw installation; absence of a native capability must degrade safely rather than fabricate persistence or bypass governance.
