# Automatic Coverage Protocol

Agent OS must feel automatic after installation without becoming a second runtime. Coverage is therefore a **Skill execution policy**, not a daemon, event bus, scheduler, or shadow database.

## Objective

For work where Agent OS is selected/eligible, automatically decide whether to verify only, learn, or enter deep adaptation. The user must not have to request `总结经验`, `整理记忆`, `复盘`, or `运行 Agent OS` after normal work.

## Coverage classes

### C0 Ignore
Greetings, casual chat, trivial transformations, transient facts, and interactions with no meaningful work outcome. Do not create learning overhead.

### C1 Verify
Substantive answers, tool calls, file/code changes, research, actions, and tasks with an observable requested outcome. Run Fast Path and verify before claiming completion.

### C2 Learn
C1 plus at least one high-value signal: explicit user correction, stable stated preference, reusable success/failure, recurring tool/workflow lesson, meaningful task failure, or repeated pattern. Derive Experience and use native persistence when durable.

### C3 Deep adapt
Delegation/multi-agent integration, repeated patterns, scope promotion, contradictions, skill/workflow improvement candidates, or meaningful risk. Use full Verification -> Experience -> Evolution -> Governance path.

Default to the lower class when uncertain.

## Surface coverage

When the current OpenClaw environment exposes the relevant context, apply the same semantics to:

- root/main conversational sessions
- new and long-running sessions
- permanent/specialist agents
- tool-using work
- native tasks/background work when its result is presented to an eligible agent turn
- subagent/delegated work when provenance/result is available
- multi-agent integration
- explicit user feedback/corrections
- failed/partial/unknown outcomes
- post-Workshop or post-change verification

A Skill does not claim invisible global event interception. If OpenClaw does not expose a background/subagent event to the Skill context, mark that coverage as unavailable rather than pretending it was observed.

## Automatic data lifecycle

`Native trajectory -> Evidence selection -> Verification -> Learn? -> Experience -> Deduplicate/Contradiction -> Scope -> Native persistence -> Native recall -> Future verification`

Agent OS does **not** archive all raw trajectories. OpenClaw remains source-of-truth for sessions/tasks/memory. Agent OS selects only evidence necessary to support learning semantics.

### Evidence
Keep enough provenance to support the conclusion. Do not persist raw logs merely for completeness.

### Experience admission
Persist only when the lesson is reusable, evidence-backed, non-trivial, and likely to improve future work. Explicit stable user instruction/correction can qualify immediately; inferred behavior normally needs stronger/repeated evidence.

### Deduplication
Before durable writeback, prefer updating/strengthening an equivalent native memory/lesson over adding a duplicate when the native mechanism supports this. Repetition raises occurrence/confidence; it should not create endless copies.

### Contradiction
Do not overwrite silently. New contradictory evidence must narrow, weaken, supersede, or flag the older lesson according to evidence and native memory semantics. Current explicit user instruction outranks inferred historical experience.

### Aging and relevance
Agent OS must not invent a private retention scheduler. Native OpenClaw memory governs retention/promotion. During recall/use, prefer current, repeatedly verified, context-relevant experience over stale weak experience.

### Scope
Use the narrowest durable scope: AGENT by default, TEAM with collaboration evidence, SHARED only with generalizable evidence plus Governance.

## Recall policy

Do not dump all learned experience into every prompt. Rely on OpenClaw native recall/context selection. A recalled lesson is advice/evidence, not authority: compare it with the current user request and current environment before applying it.

## Failure modes

- Native memory unavailable -> verify and reason locally; do not claim persistence.
- Provenance unavailable -> do not promote beyond local/AGENT.
- Background event invisible -> do not claim coverage.
- Native Workshop unavailable -> retain/propose candidate only if an exposed native mechanism supports it; do not build a mutation runtime.
- Conflicting user instruction -> current explicit instruction wins for current task; update durable learning only when appropriate.

## Coverage invariant

**Automatic does not mean omniscient.** Agent OS automatically processes the work OpenClaw actually exposes to it; it must never fabricate observation of hidden events.