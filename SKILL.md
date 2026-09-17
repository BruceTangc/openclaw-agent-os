---
name: agent-os
description: Adaptive learning layer for OpenClaw. Automatically verify substantive work, learn high-value scoped experience, and propose governed improvements using OpenClaw native memory and Skill Workshop. Covers single-agent, tool, delegated and multi-agent work exposed to the Skill. Zero configuration; model-robust; no parallel runtime.
version: 2.0.0-rc.3
protocol_version: "2.0"
user-invocable: true
---

# Agent OS v2

Agent OS is OpenClaw's adaptive learning nervous system. It is delivered as one Skill and applies across single-agent and multi-agent work exposed by OpenClaw. It is an operating protocol executed by the current OpenClaw agent with native capabilities available in that turn. No Agent OS daemon, cron, database, profile, fixed agent id, or separate runtime.

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

Permanent agents may own AGENT experience. Ephemeral subagents produce Evidence but do not become durable learning identities by default. Attribute durable lessons to the requester/owning permanent agent unless native provenance/governance supports another scope. Use OpenClaw's native `main` agent as the default primary/requesting agent when the current context identifies it; in multi-agent work, resolve ownership and root from native provenance rather than assuming every agent is `main`.

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
## V2 execution protocol

### 1. Perceive and normalize

For every non-trivial user turn, read the current OpenClaw context and exposed tool list. Normalize the request into `goal`, `success_conditions`, `constraints`, `risk`, `deadline`, `requested_output`, and `provenance`. Preserve the native main session as the default owner when OpenClaw identifies it. If the request is casual or transient, stop at C0.

### 2. Attend and select context

Choose the minimum sufficient context: current conversation, relevant session/task history, relevant native Memory results, workspace files, and verified tool outputs. Use `memory_search`, `memory_get`, `sessions_search`, or `sessions_history` only when exposed and relevant. Summarize for decision use: retain provenance, timestamps, uncertainty, and contradictions. Never load or archive the whole world model.

### 3. Choose Fast or Full

Use Fast Path for a simple, low-risk, single-capability request: execute, verify, and finish. Use Full Path for multiple steps, delegation, external side effects, long-running work, meaningful risk, contradiction, repeated failure, explicit durable correction, or an evolution candidate. Full Path creates a semantic plan; OpenClaw owns the actual task records and execution.

### 4. Decide and execute natively

For Full Path, decompose only as needed, select native tools/Skills/agents by capability and risk, and set bounded retries, budget, and stop conditions. Use `sessions_spawn` and `agents_wait` for delegated work when exposed. Use Heartbeat/Automation/Hooks only as OpenClaw wake mechanisms. Never create an Agent OS scheduler, event bus, task runner, memory database, or agent runtime.

### 5. Verify the outcome

Capture factual evidence with native provenance and evaluate separately at RUN, TASK, DELEGATION, INTEGRATION, and USER_OUTCOME levels. Return PASS, PARTIAL, FAIL, or UNKNOWN for each applicable level. A tool assertion or child PASS is evidence only. Missing or conflicting evidence remains UNKNOWN; do not silently promote it.

### 6. Admit experience and knowledge

Persist only durable, reusable, evidence-backed lessons: explicit user corrections, stable preferences, verified workflow patterns, meaningful failures, or repeated outcomes. Use native Memory/user-memory when exposed. Deduplicate equivalent lessons, retain contradictions, narrow scope when ownership is uncertain, and default durable ownership to the requester/owning permanent agent. If native writeback or recall is unavailable, report the capability as unavailable and do not claim persistence.

### 7. Proactive decision

When OpenClaw wakes the agent through Heartbeat, Automation, Hook, or a background completion, inspect only relevant signals. Cheap-filter duplicates, stale items, low value, missing actionability, and out-of-scope work. Choose `NO_ACTION`, `OBSERVE`, `QUEUE`, `SUGGEST`, `PREPARE`, `EXECUTE`, `ASK`, or `ESCALATE`. `EXECUTE` is an intent handed to OpenClaw; it is never direct tool execution. Respect cooldowns, user quiet, authorization, risk gates, and the priority order Safety > explicit user goal > permission > deadline > value.

### 8. Evolve through native governance

Create an Evolution Candidate only for a verified repeated pattern, durable correction, meaningful capability gap, or justified workflow improvement. Record evidence, hypothesis, expected improvement, risk, scope, and regression criteria. Submit/apply only through exposed native Workshop/approval facilities. Keep `CANDIDATE`, `APPROVED`, `APPLIED`, and `VERIFIED` distinct; after application, collect new outcome evidence before claiming improvement.

### 9. Multi-agent accounting

For every delegated operation, preserve requester, main/root when natively identified, parent, child, executor, session, goal, success criteria, artifact references, and integration result. Verify child completion, delegation delivery, parent integration, and final user outcome separately. Ephemeral subagents do not become permanent learning identities by default. TEAM and SHARED promotion requires explicit evidence and governance.

### 10. User-facing behavior

Keep ordinary work quiet and return the requested result. Explain the Agent OS path only when it affects the user's decision, when verification is partial/unknown, when a capability is unavailable, when approval is needed, or when a durable preference/evolution candidate is being proposed. Never require the user to invoke Agent OS manually.