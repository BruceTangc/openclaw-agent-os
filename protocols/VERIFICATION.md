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

## Outputs
Verification has two distinct semantic outputs:

1. `Evidence` records the factual/provenance-bearing observations used for judgment.
2. `VerificationResult` records the verdict for a RUN, TASK, DELEGATION, or USER_OUTCOME and references supporting Evidence IDs per criterion.

Verification therefore **consumes/selects Evidence and produces a VerificationResult**. It must not collapse an agent/tool assertion directly into a verdict. Evidence may be selected or normalized during verification, but Evidence itself is not the verdict.

## Verdicts
PASS: criteria are supported by sufficient direct evidence.
PARTIAL: useful progress but one or more required criteria are unmet.
FAIL: evidence contradicts required criteria or outcome.
UNKNOWN: evidence is insufficient; never coerce UNKNOWN to PASS.

## Evidence rules
Prefer direct observable evidence over agent assertions. Preserve provenance. Tool exit/status is evidence only. For delegated work verify both child deliverable and parent integration. Final USER_OUTCOME is measured against the original user request, not the decomposition chosen by agents.

A higher-level result may cite lower-level evidence/results, but it must evaluate its own success criteria. Local PASS never mechanically propagates upward.

## Learning gate
Experience may derive only from evidence whose relevant outcome has been evaluated. PASS, PARTIAL and FAIL can all teach when the lesson is supported. UNKNOWN normally blocks durable causal/general lessons; an UNKNOWN result may justify only a narrow meta-lesson about missing observability when that fact itself is directly evidenced.

Verification does not schedule retries or execute fixes.
