# Agent OS v2 Architecture Acceptance

All scenarios must pass before v1.3 retirement.

## A1 Single agent learning
A permanent agent completes/fails a task. Verification produces evidence; Experience derives a scoped lesson; no parallel task/memory runtime is created.

## A2 Local PASS / global FAIL
A root/requester delegates work. Child task PASSes but final user outcome FAILs. System must preserve child PASS while recording USER_OUTCOME FAIL; it must not promote global success.

## A3 Multi-agent collaboration
Root/coordinator -> Developer -> Reviewer. Preserve native provenance. A delegation-interface lesson may become TEAM experience without creating an Agent OS orchestrator.

## A4 Scope isolation
An AGENT lesson for Developer must not appear as Reviewer/Investment/shared experience without explicit promotion evidence and governance.

## A5 Team to shared promotion
TEAM experience may promote to SHARED only with cross-agent/generalizable evidence and governance decision. No automatic jump.

## A6 Native supersession
Simulate OpenClaw adding a FULL native experience-learning capability. Registry changes provider/support and adapter delegates to native capability. Verification/Experience/Evolution/Governance contracts require zero semantic changes; fallback is marked deprecated then removable.

## A7 Ephemeral subagent
Subagent UUID produces useful evidence. No durable identity/store is created for the UUID; durable lesson is attributed to requester/owning permanent agent unless promoted.

## A8 Unknown safety
Insufficient evidence yields UNKNOWN. UNKNOWN cannot autonomously create a durable/shared rule or authorize risky evolution.
