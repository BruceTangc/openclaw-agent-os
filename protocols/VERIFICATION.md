# Verification Protocol v2

Purpose: establish what actually happened relative to the original goal.

## Inputs
- original user goal and explicit success criteria
- native OpenClaw identity/session/task/delegation provenance
- tool/run outputs and observable environment state
- downstream integration result
- user feedback/correction when available

## Levels
TOOL -> RUN -> TASK -> DELEGATION -> USER_OUTCOME.

Invariant: success at a lower level never proves success at a higher level.

## Verdicts
PASS: criteria are supported by sufficient direct evidence.
PARTIAL: useful progress but one or more required criteria are unmet.
FAIL: evidence contradicts required criteria or outcome.
UNKNOWN: evidence is insufficient; never coerce UNKNOWN to PASS.

## Evidence rules
Prefer direct observable evidence over agent assertions. Preserve provenance. Tool exit/status is evidence only. For delegated work verify both child deliverable and parent integration. Final USER_OUTCOME is measured against the original user request, not the decomposition chosen by agents.

Verification produces Evidence; it does not schedule retries or execute fixes.