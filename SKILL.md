---
name: agent-os
description: Adaptive learning layer for OpenClaw. Use automatically on substantive work, tool-using tasks, delegated or multi-agent work, user corrections, repeated successes/failures, and reusable workflow lessons. Verify real outcomes, learn scoped experience, and propose governed improvements using OpenClaw native memory and Skill Workshop. Zero configuration; do not create a parallel runtime.
version: 2.0.0-rc.1
protocol_version: "2.0"
user-invocable: true
---

# Agent OS v2

Agent OS is OpenClaw's adaptive learning nervous system. It is an operating protocol executed by the current OpenClaw agent with the native tools/capabilities already available in that turn. Do not require setup, an Agent OS daemon, cron, database, profile, fixed agent id, or a separate runtime.

## Automatic operating loop

For every substantive task where this skill is eligible:

1. **Goal** — preserve the user's original goal and explicit constraints. Infer success criteria only when needed; do not make the user configure them.
2. **Native execution** — use OpenClaw's existing agent/session/task/subagent/tool flow. Do not replace routing, task management, context, memory, approvals, or orchestration.
3. **Verification** — before claiming completion, compare observable results with the original goal. Tool success is evidence only. Use PASS, PARTIAL, FAIL, or UNKNOWN internally; surface caveats when the outcome is not PASS.
4. **Experience** — when the episode contains a reusable success, failure, correction, preference, tool lesson, workflow lesson, or delegation lesson, derive the narrowest useful lesson from verified evidence.
5. **Native writeback** — if the lesson is durable and the current OpenClaw environment exposes an appropriate native memory/user-memory mechanism, use that mechanism. Do not create Agent OS-owned memory files or databases. Do not write transient/noisy facts merely to prove learning occurred.
6. **Evolution** — when repeated or strong evidence indicates a reusable behavior/skill improvement, form a narrow change hypothesis. Use OpenClaw native self-learning/Skill Workshop proposal flow when available. Do not directly mutate user-owned/shared skills when native governance expects a proposal or approval.
7. **Governance** — preserve evidence/provenance, choose the narrowest valid scope, and obey all native approval/security restrictions. Never silently promote an agent-specific lesson to TEAM or SHARED.
8. **Close the loop** — after an improvement is applied by OpenClaw, verify future outcomes; failed improvements become new evidence.

Do not narrate this loop on every response. It should improve work without adding user friction. Mention verification/learning only when useful, requested, uncertain, risky, or when an approval/proposal needs attention.

## Zero-configuration rules

- Never ask the user to configure `agent_id`, main/root agent, team membership, memory paths, Workshop paths, cron, heartbeat, or Agent OS storage just to use this skill.
- Resolve identity and delegation from native session/task context when available. If identity is ambiguous, keep learning local and do not promote scope.
- Never treat literal `agent_id == "main"` as semantic proof of root ownership.
- If a native capability is unavailable, degrade safely: verify the current outcome and keep the lesson in current reasoning; do not invent a replacement runtime or claim persistence occurred.
- Installation itself is sufficient activation when OpenClaw marks this skill eligible. No post-install configuration is required by Agent OS.

## Verification invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`.

For delegated work, verify child output, parent integration, and final user outcome separately. Local PASS does not imply global PASS.

## Learning scope

Execution evidence scopes: `RUN`, `SESSION`, `TASK`, `DELEGATION`.

Durable learning scopes: `AGENT`, `TEAM`, `SHARED`.

Default durable owner is the permanent agent doing/owning the work. Ephemeral subagents may produce evidence but do not receive permanent learning identities by default; attribute durable lessons to the requester/owning permanent agent unless governance supports broader promotion.

## Native-first boundary

OpenClaw owns agent runtime, sessions, workspaces, tasks, task flow, subagents/A2A, routing, tools, skills, memory persistence/recall, context, automation, sandboxing, approvals, and Workshop application.

Agent OS owns only the semantics of **Verification -> Experience -> Evolution -> Governance**.

Capability preference: OpenClaw Native -> official OpenClaw plugin -> thin Agent OS adapter -> minimal fallback only when unavoidable. If OpenClaw adds an equivalent native capability, use it and retire the fallback.

## Supporting protocols

Read `{baseDir}/protocols/VERIFICATION.md`, `EXPERIENCE.md`, `EVOLUTION.md`, `GOVERNANCE.md`, and `MULTI-AGENT.md` when the task requires the detailed contract. Read `{baseDir}/protocols/NATIVE-FIRST.md` when adapting to a changed OpenClaw capability.
