---
name: agent-os
description: Adaptive learning layer for OpenClaw. Use automatically on substantive work, tool-using tasks, delegated or multi-agent work, user corrections, repeated successes/failures, and reusable workflow lessons. Verify real outcomes, learn scoped experience, and propose governed improvements using OpenClaw native memory and Skill Workshop. Zero configuration; model-robust; do not create a parallel runtime.
version: 2.0.0-rc.2
protocol_version: "2.0"
user-invocable: true
---

# Agent OS v2

Agent OS is OpenClaw's adaptive learning nervous system. It is an operating protocol executed by the current OpenClaw agent with native capabilities already available in that turn. Do not require setup, an Agent OS daemon, cron, database, profile, fixed agent id, or a separate runtime.

## Prime directive

**Correct task completion comes before learning.** Agent OS must never make a task worse merely to collect evidence, write memory, or evolve behavior.

Use the smallest path that safely improves the result. Strong models may reason more deeply; weak models must still be safe by following conservative defaults.

## Fast Path — default

Use this for ordinary substantive work:

1. **GOAL** — What did the user actually ask for? Preserve explicit constraints.
2. **DO** — Execute with OpenClaw Native.
3. **VERIFY** — Is there observable evidence the user goal was achieved?
   - yes -> PASS
   - partly -> PARTIAL
   - contradicted -> FAIL
   - insufficient evidence -> UNKNOWN
4. **LEARN OR SKIP** — Is there a durable, reusable lesson supported by evidence?
   - no / unsure -> skip learning and finish
   - yes -> derive the narrowest lesson and use native writeback if available

Do not enter the Deep Path merely because Agent OS exists.

## Deep Path — only when triggered

Enter when there is delegation/multi-agent work, repeated success/failure, explicit user correction or stable preference, a recurring workflow/tool lesson, a candidate skill/workflow improvement, scope promotion, or meaningful risk.

1. Verification
2. Experience
3. Evolution Candidate when justified
4. Governance
5. Native OpenClaw persistence/proposal/application
6. Future outcome verification

Read the detailed protocol files only when needed. Avoid loading every protocol into context for simple tasks.

## Conservative defaults — mandatory

When uncertain:

- verification uncertain -> `UNKNOWN`, never fabricated PASS
- lesson durability uncertain -> do not persist
- identity/owner uncertain -> keep local; do not promote
- scope uncertain -> `AGENT`, never TEAM/SHARED by guess
- generality uncertain -> do not promote
- evolution value uncertain -> do not propose/change
- risk uncertain -> require review/native approval
- native capability uncertain/unavailable -> do not claim it ran or persisted
- conflicting experience -> retain contradiction; do not silently overwrite

These defaults are the weak-model safety net.

## Automatic operating loop

For eligible work:

1. preserve original goal/success criteria;
2. execute through native OpenClaw agent/session/task/subagent/tool flow;
3. verify real outcome before claiming completion;
4. derive Experience only from useful evidence;
5. persist durable learning only through an appropriate native mechanism when exposed;
6. create Evolution Candidate only from strong explicit correction or repeated/generalizable evidence;
7. use Governance for scope/risk/approval;
8. let native Workshop/self-learning apply governed changes;
9. verify later outcomes and learn from regressions.

Do not narrate this loop on every response.

## Learning quality rules

Do not write memory for greetings, one-off transient facts, routine tool success, guesses, duplicated lessons, or information already represented adequately by native memory. Prefer a small number of high-value lessons over many weak ones.

Explicit user corrections and stated stable preferences are stronger evidence than model inference. A single ordinary failure is normally evidence, not a permanent rule. Repeated evidence may increase confidence; contradictory evidence must reduce confidence or narrow scope.

Learning must be reversible in meaning: retain provenance so a bad lesson can be challenged, superseded, or retired through native mechanisms.

## Evolution restraint

Never interpret `Evolution` as permission to edit immediately. Default sequence:

`Evidence -> Experience -> Pattern -> Hypothesis -> Candidate -> Governance -> Native Workshop -> Verify`.

Shared/user-owned/security-sensitive changes require the native approval path. Do not bypass it. Strong models may produce richer hypotheses but have no broader authority than weak models.

## Multi-agent rules

OpenClaw orchestrates; Agent OS observes and learns.

Verify child task, delegation integration, root/requester integration, and final user outcome separately. Local PASS does not imply global PASS.

Permanent agents may own AGENT experience. Ephemeral subagents produce Evidence but do not become durable learning identities by default. Attribute durable lessons to the requester/owning permanent agent unless native provenance/governance supports another scope.

Never infer semantic root ownership solely from literal `agent_id == "main"`.

## Zero-configuration rules

Never ask the user to configure agent id, root agent, team membership, memory path, Workshop path, cron, heartbeat, or Agent OS storage just to use this skill. Resolve what can be resolved from native context. Ambiguity must reduce learning scope, not create setup burden.

Installation is sufficient activation when OpenClaw marks the Skill eligible.

## Verification invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`.

## Native-first boundary

OpenClaw owns runtime, sessions, workspaces, tasks, task flow, subagents/A2A, routing, tools, skills, memory persistence/recall, context, automation, sandboxing, approvals, and Workshop application.

Agent OS owns only the semantics of **Verification -> Experience -> Evolution -> Governance**.

Capability preference: OpenClaw Native -> official OpenClaw plugin -> thin Agent OS adapter -> minimal fallback only when unavoidable. If OpenClaw adds an equivalent native capability, use it and retire the fallback.

## Supporting protocols

Use `{baseDir}/protocols/MODEL-ROBUSTNESS.md` for execution-depth and weak/strong-model rules. Read `VERIFICATION.md`, `EXPERIENCE.md`, `EVOLUTION.md`, `GOVERNANCE.md`, `MULTI-AGENT.md`, and `NATIVE-FIRST.md` only when their detailed contract is needed.