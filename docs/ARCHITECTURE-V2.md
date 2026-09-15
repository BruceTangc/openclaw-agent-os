# Agent OS v2 Architecture Freeze

Status: **Architecture Freeze**

## Positioning

Agent OS is OpenClaw's **Adaptive Nervous System**. It is a learning layer over OpenClaw Native, not a second runtime or control plane.

OpenClaw is the working organism: agent runtime, main/root sessions, permanent agents, subagents, task flow, tools, skills, memory, automation and enforcement. Agent OS observes outcomes and converts trustworthy evidence into governed learning.

## Architecture

```text
USER
  |
OpenClaw root/owning agent + native runtime
  |-- permanent/specialist agents
  |-- ephemeral subagent tree
  |-- background tasks/task flow
  |
  v
Verification -> Evidence -> Experience -> Evolution -> Governance
                                              |
                                   Native Capability Adapter
                                              |
                                      OpenClaw Native
                                  Memory / Workshop / Approval
```

## Core ownership

### Verification
Owns outcome semantics. Inputs include original goal, success criteria, native execution results, environment evidence and user feedback. Outputs PASS/PARTIAL/FAIL/UNKNOWN plus evidence.

### Experience
Owns lesson extraction, not storage. It converts verified Situation/Action/Outcome/Feedback into reusable lessons. Persistence/recall is delegated to OpenClaw native memory/user/knowledge facilities.

### Evolution
Owns pattern detection, hypothesis formation and improvement-candidate generation. It does not directly mutate skills or runtime configuration.

### Governance
Owns learning/change decisions: evidence sufficiency, scope promotion, confidence, risk and approval requirements. Runtime enforcement remains OpenClaw-owned.

## Multi-agent model

Agent OS consumes OpenClaw-native identities and provenance. It never creates a second Agent registry or communication bus.

Permanent configured agents can own durable AGENT-scoped experience. Ephemeral subagents contribute evidence to the requester/owning permanent agent by default.

Root ownership is resolved from native provenance; the literal id `main` is never a semantic requirement.

### Evidence scopes

- RUN
- SESSION
- TASK
- DELEGATION

### Durable learning scopes

- AGENT
- TEAM
- SHARED

Scope promotion is governed and explicit. No implicit global learning.

## Verification invariant

```text
Tool result
  -> Run verification
  -> Task verification
  -> Delegation verification
  -> Root integration
  -> User-outcome verification
```

A lower-level PASS never proves a higher-level PASS.

## Stable contracts

- Evidence
- VerificationResult
- Experience
- EvolutionCandidate
- AgentIdentity
- DelegationTrace
- Capability

These contracts are version-stable relative to OpenClaw implementation details.

## Native adaptation

Core modules call semantic capabilities, never version-specific OpenClaw internals. `Capability Registry` discovers providers and `Native Adapter` maps stable contracts to the current OpenClaw mechanisms.

Provider precedence:

1. OPENCLAW_NATIVE
2. OPENCLAW_OFFICIAL_PLUGIN
3. AGENT_OS_ADAPTER
4. AGENT_OS_FALLBACK

When a native capability fully supersedes a fallback, mark the fallback deprecated and remove it after one compatibility window.

## Non-goals

Agent OS does not own: Agent Runtime, multi-agent orchestration, task manager/runtime, scheduler, session manager, context engine, memory DB, user-profile DB, tool runtime, permission enforcement, agent communication, skill editing/application runtime.

## Upgrade invariant

**OpenClaw gets stronger -> Agent OS implementation gets thinner; Agent OS semantic contracts remain stable.**
