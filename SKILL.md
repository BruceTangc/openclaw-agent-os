---
name: agent-os
description: Adaptive learning layer for OpenClaw. Automatically verify substantive work, learn high-value scoped experience, and propose governed improvements using OpenClaw native memory and Skill Workshop. Covers single-agent, tool, delegated and multi-agent work exposed to the Skill. Zero configuration; model-robust; no parallel runtime.
version: 2.0.0-rc.3
protocol_version: "2.0"
user-invocable: true
---

# Agent OS v2

Agent OS is OpenClaw's adaptive learning nervous system. It is an operating protocol executed by the current OpenClaw agent with native capabilities available in that turn. No Agent OS daemon, cron, database, profile, fixed agent id, or separate runtime.

## Prime directive

**Correct task completion comes before learning.** Never make work worse merely to collect evidence, write memory, or evolve behavior. Use the smallest safe path. Strong models may reason more deeply; weak models remain safe through conservative defaults.

## Automatic coverage

When this Skill is eligible, classify work automatically; do not ask the user to run Agent OS, summarize experience, organize memory, or perform a separate review.

- **C0 IGNORE** — casual/trivial/transient interaction; no learning overhead.
- **C1 VERIFY** — substantive answer/action/tool/file/code/research task; Fast Path.
- **C2 LEARN** — C1 plus durable correction/preference/reusable success/failure/tool/workflow lesson; verify then derive Experience.
- **C3 DEEP ADAPT** — multi-agent/delegation integration, repeated pattern, contradiction, scope promotion, meaningful risk, or improvement candidate; full four-Core path.

When uncertain choose the lower coverage class. Automatic does not mean omniscient: process only work/provenance/results OpenClaw actually exposes to the Skill. Never claim hidden background/subagent events were observed.

## Fast Path — default

1. **GOAL** — preserve what the user actually asked for and explicit constraints.
2. **DO** — execute with OpenClaw Native.
3. **OBSERVE EVIDENCE** — select factual, provenance-bearing observations. A tool/agent assertion is Evidence at most; it is not a verdict.
4. **VERIFY** — compare Evidence with the goal/criteria and produce a `VerificationResult`: PASS / PARTIAL / FAIL / UNKNOWN.
5. **LEARN OR SKIP** — derive Experience only when the relevant outcome has been evaluated and the lesson is durable, reusable and evidence-backed; otherwise finish without learning overhead.

**Evidence != VerificationResult.** Tool success is evidence only, never proof of run/task/delegation/user-outcome success. `UNKNOWN` must not be silently promoted to PASS or used to justify durable causal/general learning.

## Deep Path — only when triggered

`Evidence -> VerificationResult -> Experience -> Evolution Candidate (if justified) -> Governance -> OpenClaw Native -> Future Verification`

Read detailed protocol files only when needed; do not load every protocol for simple tasks.

## Automatic data lifecycle

For exposed work use:

`Native trajectory -> Evidence selection -> VerificationResult -> Learn? -> Experience -> Deduplicate/Contradiction -> Scope -> Native persistence -> Native recall -> Future verification`

Do **not** archive all raw data. OpenClaw remains source-of-truth for sessions/tasks/memory. Keep/select only evidence needed for trustworthy learning.

Before durable writeback, avoid duplicates when native memory can represent an existing lesson. Repetition should strengthen/narrow an existing lesson rather than create endless copies. Contradictory evidence must not be silently overwritten; weaken, narrow, supersede, or flag the old lesson as appropriate. Current explicit user instruction outranks inferred historical experience.

Do not dump all experience into every prompt. Use OpenClaw native recall/context selection. Recalled experience is evidence/advice, not authority; re-check it against the current request and environment.

## Conservative defaults — mandatory

When uncertain:

- verification -> `UNKNOWN`, never fabricated PASS
- lesson durability -> do not persist
- identity/owner -> keep local; do not promote
- scope -> `AGENT`, never TEAM/SHARED by guess
- generality -> do not promote
- evolution value -> do not propose/change
- risk -> require review/native approval
- native capability -> do not claim it ran/persisted
- conflicting experience -> retain contradiction; do not silently overwrite

## Learning quality

Do not persist greetings, one-off transient facts, routine tool success, guesses, duplicated lessons, or information already adequately represented by native memory. Prefer few high-value lessons.

Explicit user corrections/stated stable preferences are stronger evidence than inference. A single ordinary failure is normally evidence, not a permanent rule. Repetition can increase confidence; contradiction should lower confidence or narrow scope.

Retain meaningful provenance so bad learning can later be challenged, superseded, or retired through native mechanisms.

## Evolution restraint

Evolution is not immediate editing. Default sequence:

`Evidence -> Experience -> Pattern -> Hypothesis -> Candidate -> Governance -> Native Workshop -> Verify`.

Governance authorization and observed runtime state are distinct. **`APPROVED != APPLIED != VERIFIED`.** Governance may authorize a candidate, but `APPROVED` must never be reported as `APPLIED` until native application is directly evidenced. `APPLIED` must never be reported as `VERIFIED` until post-application verification produces PASS. If application or verification cannot be observed, retain the last evidenced state; never advance status by assumption. `REJECT` maps to `REJECTED`; `DEFER` does not advance the candidate unless an explicit review is opened.

Shared, user-owned, security-sensitive, or risky changes follow native approval. Strong models have more reasoning capacity, not more authority.

## Multi-agent

OpenClaw orchestrates; Agent OS observes and learns. Verify child task, delegation integration, requester/root integration, and final user outcome separately. Local PASS does not imply global PASS.

Permanent agents may own AGENT experience. Ephemeral subagents produce Evidence but do not become durable learning identities by default. Attribute durable lessons to the requester/owning permanent agent unless native provenance/governance supports another scope. Never infer semantic root solely from literal `agent_id == "main"`.

## Zero configuration

Never require agent id, root agent, team list, memory path, Workshop path, cron, heartbeat, Agent OS storage, or a setup conversation. Resolve what native context provides. Ambiguity reduces scope; it must not create setup burden.

Installation is sufficient activation when OpenClaw marks the Skill eligible.

## Verification invariant

`Tool success != Run success != Task success != Delegation success != User outcome success`.

## Native-first boundary

OpenClaw owns runtime, sessions, workspaces, tasks, task flow, subagents/A2A, routing, tools, skills, memory persistence/recall, context, automation, sandboxing, approvals, and Workshop application.

Agent OS owns only **Verification -> Experience -> Evolution -> Governance** semantics.

Capability preference: OpenClaw Native -> official OpenClaw plugin -> thin Agent OS adapter -> minimal fallback only when unavoidable. Native FULL equivalents supersede Agent OS fallbacks.
## Cognitive loop

Treat OpenClaw as the execution body and this Skill as the cognitive layer. In each eligible turn, use exposed native context as perception, preserve the goal and criteria as working memory, use native sessions/memory for episodic recall, verify the real outcome, admit only durable lessons, and use the next recall plus user outcome as feedback. Use native approval and sandbox controls as executive inhibition. The loop is: `perceive -> attend -> execute -> verify -> remember -> recall -> learn`.
## Native capability use — operational rule

For every eligible substantive turn, first inspect the OpenClaw capabilities actually exposed in the current context and map the task to them before choosing a fallback:

1. Use native tools for the work itself, native task and subagent facilities for delegation, native memory/user-memory for recall and durable writeback, and native approval/sandbox/Workshop facilities for governed changes when those tools are exposed.
2. Treat a capability as available only after the current turn exposes it and a call succeeds with an observable result. The registry, Skill text, configuration, or tool name alone is not runtime evidence.
3. Record which native facility was selected and verify its real outcome separately from tool success. If the native call is unavailable, fails, or its result cannot be observed, mark that operation UNKNOWN or use the smallest safe fallback; never recreate the facility as an Agent OS runtime.
4. Do not perform duplicate Agent OS work when a native facility fully satisfies the semantic contract. Agent OS adds only the Verification, Experience, Evolution, or Governance decision around the native operation.

## Acceptance truth boundary

Repository/static gate success proves package/contract integrity only. It does **not** prove runtime Agent behavior. Runtime acceptance requires observable execution in real OpenClaw; never report an A-scenario PASS merely because its specification exists or static CI passed.

## Supporting protocols

Use `{baseDir}/protocols/AUTOMATIC-COVERAGE.md` for trigger/data-lifecycle rules and `{baseDir}/protocols/MODEL-ROBUSTNESS.md` for weak/strong-model execution rules. Read `VERIFICATION.md`, `EXPERIENCE.md`, `EVOLUTION.md`, `GOVERNANCE.md`, `MULTI-AGENT.md`, and `NATIVE-FIRST.md` only when their detailed contract is needed.