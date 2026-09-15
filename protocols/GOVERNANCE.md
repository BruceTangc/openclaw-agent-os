# Governance Protocol v2

Governance controls learning and change boundaries; it is not a parallel permission runtime.

## Questions
Is evidence trustworthy? Is the lesson durable? What is the narrowest valid scope? May it promote AGENT -> TEAM -> SHARED? Is the proposed change reversible? What risk/approval is required?

## Default rules
- prefer narrow scope
- no silent scope jumps
- UNKNOWN verification cannot justify autonomous durable causal/general change
- explicit user instructions outrank inferred preference
- security, credentials, external side effects and shared protocol changes require native approval according to risk
- preserve provenance from candidate back to Experience and Evidence
- use OpenClaw native enforcement, sandbox and approval

## Decisions
Governance reasoning uses four semantic decisions: `ALLOW`, `REVIEW`, `REJECT`, `DEFER`.

They map to the serialized `EvolutionCandidate.status` state machine rather than creating a second status field:

- new candidate -> `CANDIDATE`
- `REVIEW` or `DEFER` -> `REVIEW` (pending evidence/native approval; no application claim)
- `REJECT` -> `REJECTED`
- `ALLOW` -> `APPROVED` only after all required native approval conditions are satisfied
- native application actually observed -> `APPLIED`
- post-application outcome/regression verification succeeds -> `VERIFIED`

`APPROVED` never means applied. `APPLIED` never means successful. `VERIFIED` requires new post-change evidence. If native application/approval capability is unavailable or invisible, do not advance the state by assumption.

A rejected/deferred candidate may be reconsidered only with new relevant evidence or changed native/user constraints; do not loop-promote it automatically.

Governance decisions never bypass native OpenClaw restrictions.
