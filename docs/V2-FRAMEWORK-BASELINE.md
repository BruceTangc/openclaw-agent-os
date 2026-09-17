# Agent OS V2 Framework Baseline

Status: proposed stable semantic boundary

## Purpose

Agent OS is the cognitive control plane that makes OpenClaw improve through verified experience. OpenClaw remains the execution body and source of truth for runtime state. The framework is stable across OpenClaw upgrades because it depends on semantic contracts and late-bound native capability adapters, never on OpenClaw internal versions.

## One Skill and multi-agent invariant

V2 ships and installs as exactly one OpenClaw Skill: `agent-os`. Perception, attention, context, goal/task semantics, proactive decision, ontology, summarization, verification, experience, evolution, and governance are internal semantic capabilities of this Skill, not separately installed Skills or cooperating runtimes.

The Skill recognizes OpenClaw's native `main` agent as the default primary entry point and is multi-agent capable by consuming OpenClaw-native agent, session, task, delegation, and subagent provenance. OpenClaw creates and routes agents; Agent OS verifies child work, delegation integration, owning-agent integration, and final user outcome separately. Ephemeral subagents provide evidence by default and do not become durable learning identities. Durable scope remains AGENT, TEAM, or SHARED only through explicit provenance and governance.
## Fixed boundary

OpenClaw owns agent loops, model/provider wiring, tools, skills, workspace, sessions, context assembly and compaction, task execution, subagents, background tasks, automation, heartbeat, hooks, memory storage/search, approvals, sandboxing, messaging, and Workshop application.

Agent OS owns the cognitive decisions around those facilities: perception of exposed capabilities, attention, context selection, goal and success-criteria modeling, Fast/Full routing, proactive decision, ontology and knowledge semantics, verification/evaluation, experience admission and scope, evolution reasoning, governance decisions, and execution observability.

A native capability may replace an Agent OS implementation only when it fully satisfies the semantic contract and exposes an observable result. Replacing an implementation never changes the contract.

## V1.3 disposition

| V1.3 capability | V2 status | Stable responsibility |
|---|---|---|
| proactive | retain as Attention / Proactive Decision | classify signals, priority, autonomy and notification; OpenClaw supplies wakes and executes |
| task-manager | retain as Goal / Task Semantics | normalize goals, success criteria, lifecycle meaning, stale/blocked evaluation; OpenClaw owns task runtime |
| orchestrator | retain as Execution Planning | complexity routing, decomposition, capability matching, sequencing, synthesis; OpenClaw owns subagent/task execution |
| ontology | retain | entities, relations, identity, ownership and scope semantics |
| summarize | retain as Information Distillation | target-aware evidence compression and working-memory selection; OpenClaw owns context packing/compaction |
| self-evolution | retain as Evolution Reasoning | pattern, hypothesis, candidate, regression criteria; OpenClaw Workshop owns application |
| memory-governance | retain as Experience Admission | durability, deduplication, contradiction, scope and provenance; OpenClaw Memory owns storage/recall |
| knowledge-governance | retain | claim provenance, freshness, uncertainty and conflict semantics |
| context-orchestration | retain as Context / Attention Policy | choose minimum sufficient context; OpenClaw Context Engine assembles it |
| verification-evaluation | retain as Core | verify run, task, delegation, integration and user outcome independently |
| permission-security | retain as Governance Decision | risk/authority decision; OpenClaw enforces approval, sandbox and policy |

No V1.3 semantic capability is deleted merely because OpenClaw owns its runtime implementation. Only duplicate runtimes, stores, schedulers, buses, state machines and enforcement engines are removed.

## Stable cognitive loop

`Native perception -> Context/Attention -> Goal/Success Criteria -> Fast/Full decision -> Governance decision -> Native execution -> Verification/Evaluation -> Experience/Knowledge admission -> Native recall -> Feedback -> Evolution candidate -> Native Workshop -> post-change verification`

For a simple task, stop after verification. For durable correction, stable preference, repeated pattern, contradiction, multi-agent integration, meaningful risk, or improvement candidate, continue to the relevant deeper path. `NO_ACTION` is a valid proactive result.

## Native capability binding

At the beginning of an eligible turn, build a capability snapshot only from tools and native context actually exposed in that turn. Bind semantic operations late:

- execution: native tools, skills, sessions, tasks, subagents and background tasks;
- recall/writeback: `memory_search`, `memory_get`, user-memory and exposed session history;
- proactive wake: Heartbeat, Automation/Cron, Hooks and event wakes;
- delegation: `sessions_spawn`, `agents_wait`, session result/announce surfaces;
- governance/application: native approval, sandbox and `skill_workshop`;
- context: exposed prompt/context assembly and compaction surfaces.

A registry or version number is not runtime evidence. If a capability is absent, failed, or unobservable, return UNKNOWN or use the smallest safe semantic fallback and record the capability gap.

## OpenClaw-native surfaces covered by the baseline

The baseline treats the current OpenClaw surfaces as replaceable providers behind the same semantic contracts: the native `main` session as the convergence point for direct messages, group notices, heartbeat wakes, and child announcements; session tools for history/search/send/spawn/yield; background-task records as an activity ledger; Heartbeat and Automation for wake/scheduling; Hooks for lifecycle events; built-in tools and Skills for execution; Context Engine and compaction for prompt assembly; Memory and active-memory for recall; Approval and sandbox policy for enforcement; and Skill Workshop/self-learning for governed application.

Agent OS must not assume every surface is enabled. Tool profile, per-agent policy, channel policy, provider restrictions, sandbox mode, plugin availability, and session visibility can remove a tool after configuration. Capability use is therefore decided per turn and per operation from the actually exposed surface.

The `main` session is the default cognitive convergence point, not a reason to collapse all agent identities. Child sessions remain separately attributable, and multi-agent verification must follow native requester, parent, child, integration, and user-outcome provenance.
## Future-proofing rules

1. Contracts are semantic: Goal, Evidence, VerificationResult, Experience, EvolutionCandidate, GovernanceDecision, DelegationTrace and CapabilityObservation remain stable.
2. Adapters are replaceable: a new OpenClaw native equivalent changes only the binding and capability matrix, not the cognitive loop.
3. Native-first is evaluated per operation, not per product release.
4. OpenClaw improvements make Agent OS thinner; they never remove Verification, Experience admission, feedback, or governance semantics unless OpenClaw demonstrably satisfies that contract and exposes evidence.
5. No parallel runtime is allowed for scheduler, event bus, task execution, context engine, memory store, agent orchestration, permission enforcement, or Workshop mutation.
6. Every durable lesson records provenance, scope, confidence, evidence and whether native persistence/recall was actually observed.
7. Every applied improvement requires separate evidence for APPROVED, APPLIED and VERIFIED.

## Decision rule for future OpenClaw features

When OpenClaw adds a feature, classify it as FULL, PARTIAL or NONE against the relevant semantic contract. FULL replaces only the implementation; PARTIAL is used through a thin adapter; NONE uses conservative degradation. Do not redesign the framework because a runtime feature moved between providers.