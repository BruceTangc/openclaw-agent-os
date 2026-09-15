---
name: agent-os
version: 2.0.0
protocol_version: "2.0"
description: Adaptive learning nervous system for OpenClaw. Verifies real outcomes, extracts scoped experience, proposes evidence-driven evolution, and governs learning/change without duplicating OpenClaw runtime capabilities.
---

# Agent OS v2

Agent OS is OpenClaw's adaptive learning nervous system.

## Mission

Make OpenClaw and its agent teams improve from real work while becoming easier for the user to work with over time.

## Native-first boundary

OpenClaw owns agent runtime, reasoning loop, sessions, workspaces, tasks, task flow, subagents, agent-to-agent communication, routing, tools, skills, memory storage/retrieval, context assembly, automation, sandboxing, approvals, and Workshop application.

Agent OS MUST NOT create parallel implementations of those facilities.

If OpenClaw gains a native capability equivalent to an Agent OS fallback, prefer the native capability, deprecate the fallback, then remove it after a compatibility window.

## Four core capabilities

1. **Verification** — determine whether reality satisfies the user's goal and success criteria. Tool success is evidence, never proof of outcome success.
2. **Experience** — derive reusable lessons from verified outcomes, failures, corrections, delegation and interaction. Experience is interpretation; OpenClaw owns memory persistence and recall.
3. **Evolution** — detect repeated patterns, form hypotheses and produce improvement candidates. OpenClaw Workshop/native learning owns actual skill changes.
4. **Governance** — control learning scope, evidence sufficiency, promotion, risk and approval requirements. OpenClaw owns enforcement runtime.

## Multi-agent invariant

Agent OS is multi-agent native but is not a multi-agent orchestrator.

OpenClaw decides which agent works, creates subagents, routes sessions and executes task flows. Agent OS consumes native identity/provenance and learns from the resulting work graph.

Never hard-code `agent_id == "main"` as the root-owner rule. Resolve ownership from native provenance/session/delegation context.

Ephemeral subagents may produce evidence but do not receive permanent learning identities by default; their durable experience belongs to the requester/owning permanent agent unless governance explicitly promotes a team/shared lesson.

## Verification hierarchy

`Tool success != Run success != Task success != Delegation success != User outcome success`.

Local PASS does not imply global PASS. Final outcome verification is against the original user goal and success criteria.

## Scope model

Evidence scopes: `RUN`, `SESSION`, `TASK`, `DELEGATION`.

Durable learning scopes: `AGENT`, `TEAM`, `SHARED`.

Learning MUST NOT silently jump scopes. Agent experience requires repeated/strong evidence before team promotion; team experience requires cross-agent evidence and governance before shared promotion.

## Stable contracts

Agent OS reasons in terms of stable contracts: Evidence, Verification, Experience, EvolutionCandidate, AgentIdentity, DelegationTrace and Capability.

Core logic MUST depend on capability contracts rather than OpenClaw version numbers or concrete storage APIs.

## Capability resolution

Resolution order:

1. OpenClaw native capability
2. Official OpenClaw plugin
3. Agent OS adapter
4. Minimal Agent OS fallback only when necessary

See `protocols/NATIVE-FIRST.md` and `docs/ARCHITECTURE-V2.md`.

## Learning loop

User goal -> OpenClaw execution -> Verification -> Evidence -> Experience -> Pattern -> Evolution candidate -> Governance -> OpenClaw native Workshop/approval -> future execution -> Verification.

User corrections and explicit preferences are evidence too. Stable user adaptation should be persisted through OpenClaw's native user/memory mechanisms, not an Agent OS profile database.
