# Experience Protocol v2

Experience converts verified episodes into reusable lessons. It is not a memory database.

## Derivation
Evidence -> Situation + Action + Outcome + Feedback -> Lesson.

Do not learn a durable lesson from unsupported agent narration. Explicit user corrections/preferences may be strong evidence without repeated task failures.

## Types
SUCCESS, FAILURE, WORKFLOW, TOOL, DELEGATION, USER_INTERACTION.

## Durable scopes
AGENT: specific permanent agent.
TEAM: collaboration/interface lesson supported across relevant participants.
SHARED: general lesson supported across agents/teams and approved by governance.

Ephemeral subagent evidence defaults to the requester/owning permanent agent. Do not create durable identities for subagent UUIDs.

## Promotion
RUN/SESSION/TASK/DELEGATION evidence is local evidence, not durable scope. Promotion requires sufficient confidence and governance. Inferred user preferences remain low confidence; explicit corrections are stronger. Persist/recall through OpenClaw native memory/user mechanisms via adapter.