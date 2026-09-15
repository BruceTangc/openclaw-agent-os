# Experience Protocol v2

Experience converts verified episodes into reusable lessons. It is not a memory database.

## Derivation
`Evidence + relevant VerificationResult -> Situation + Action + Outcome + Feedback -> Lesson`.

`derived_from` contains Evidence IDs. The admission decision must also consider the relevant VerificationResult; the current v2.0 Experience serialization intentionally does not duplicate a verification-result ID field.

Do not learn a durable lesson from unsupported agent narration. Explicit user corrections/preferences may be strong evidence without repeated task failures, but the correction itself must be represented as USER evidence and its relevance to the lesson checked.

PASS, PARTIAL and FAIL can all support Experience. UNKNOWN does not justify a durable causal/general rule. It may support only a narrow observability/process lesson when the missing evidence/visibility is itself directly established.

## Types
SUCCESS, FAILURE, WORKFLOW, TOOL, DELEGATION, USER_INTERACTION.

## Durable scopes
AGENT: specific permanent agent.
TEAM: collaboration/interface lesson supported across relevant participants.
SHARED: general lesson supported across agents/teams and approved by governance.

Ephemeral subagent evidence defaults to the requester/owning permanent agent. Do not create durable identities for subagent UUIDs.

## Promotion
RUN/SESSION/TASK/DELEGATION evidence is local evidence, not durable scope. Promotion requires sufficient confidence and governance. Inferred user preferences remain low confidence; explicit corrections are stronger. Persist/recall through OpenClaw native memory/user mechanisms when those capabilities are actually exposed.

## Admission invariants
- no Experience without supporting Evidence IDs
- no causal/general lesson from UNKNOWN outcome
- no TEAM/SHARED promotion by identity guess
- no duplicate Experience merely because the same episode is observed again
- current explicit user instruction outranks recalled/inferred Experience for the current task
