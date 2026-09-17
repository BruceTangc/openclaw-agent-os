# Agent OS v2 Core Contracts

The following are semantic schemas. Concrete serialization may evolve without changing their meaning.

## AgentIdentity

```yaml
agent_id: string
kind: ROOT | PERMANENT | SPECIALIST | SUBAGENT | ACP | UNKNOWN
root_agent_id: string|null
requester_agent_id: string|null
parent_agent_id: string|null
session_id: string
parent_session_id: string|null
task_id: string|null
parent_task_id: string|null
delegation_path: [string]
```

Rules: do not infer ROOT solely from the literal id `main`; ephemeral subagent UUIDs are not permanent learning identities.

## DelegationTrace

```yaml
requester_agent_id: string
executor_agent_id: string
root_agent_id: string|null
parent_task_id: string|null
child_task_id: string|null
requester_session_id: string|null
executor_session_id: string|null
delegated_goal: string
success_criteria: [string]
artifact_refs: [string]
```

## Evidence

```yaml
id: string
timestamp: string
source: TOOL | ENVIRONMENT | USER | AGENT | TEST | REVIEW | NATIVE_EVENT
identity: AgentIdentity
goal: string
success_criteria: [string]
action: string|null
observation: string
feedback: string|null
scope: RUN | SESSION | TASK | DELEGATION
confidence: number
provenance: [string]
```

Evidence is factual/provenance-bearing input. It is not itself a durable lesson.

## VerificationResult

```yaml
id: string
target: RUN | TASK | DELEGATION | USER_OUTCOME
status: PASS | PARTIAL | FAIL | UNKNOWN
criteria_results:
  - criterion: string
    status: PASS | PARTIAL | FAIL | UNKNOWN
    evidence_ids: [string]
reason: string
confidence: number
```

UNKNOWN is preferred to fabricated certainty.

## Experience

```yaml
id: string
derived_from: [evidence_id]
type: SUCCESS | FAILURE | WORKFLOW | TOOL | DELEGATION | USER_INTERACTION
situation: string
action: string|null
outcome: string
lesson: string
confidence: number
occurrences: number
scope: AGENT | TEAM | SHARED
owner_agent_id: string|null
team_id: string|null
contradicts: [experience_id]
```

Experience is interpretation. OpenClaw native facilities own persistence, retrieval, promotion and user-profile storage.

## EvolutionCandidate

```yaml
id: string
experience_ids: [string]
pattern: string
hypothesis: string
target: AGENT | TEAM | SKILL | WORKFLOW | SHARED_PROTOCOL
expected_improvement: string
proposed_change: string
confidence: number
risk: LOW | MEDIUM | HIGH | CRITICAL
status: CANDIDATE | REVIEW | APPROVED | REJECTED | APPLIED | VERIFIED
```

## Capability

```yaml
id: string
provider: OPENCLAW_NATIVE | OPENCLAW_OFFICIAL_PLUGIN | AGENT_OS_ADAPTER | AGENT_OS_FALLBACK
support: FULL | PARTIAL | NONE
version_hint: string|null
contract_version: string
notes: string|null
```

Capability IDs describe semantics rather than concrete API names, e.g. `memory.persist`, `memory.recall`, `skill.propose_change`, `skill.apply_change`, `approval.request`, `identity.resolve`, `delegation.trace`.
