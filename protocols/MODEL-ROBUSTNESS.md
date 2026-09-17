# Model Robustness Protocol

Agent OS correctness must not depend on a frontier model understanding the whole architecture at once.

## Design objective

A minimally capable tool-using model should fail conservative; a stronger model should improve reasoning quality without receiving extra authority.

`model capability -> quality/depth`, never `model capability -> safety boundary`.

## Two execution depths

### Fast Path
Default for ordinary tasks: GOAL -> DO -> VERIFY -> LEARN-OR-SKIP.

Do not load or simulate the full governance pipeline for simple work. If no durable lesson exists, stop after verification.

### Deep Path
Trigger only for multi-agent/delegation, explicit correction/stable preference, repeated pattern, reusable workflow/tool lesson, evolution candidate, promotion, contradiction, or meaningful risk.

## Deterministic decision rules

Verification: direct environment/test/user evidence > tool return > agent assertion. Missing evidence means UNKNOWN.

Persistence: persist only when evidence-supported + reusable + likely useful later. Otherwise skip.

Scope: AGENT is default. TEAM requires collaboration-specific/cross-agent evidence. SHARED requires generalizable evidence plus Governance.

Evolution: one ordinary failure does not authorize mutation. Strong explicit correction can justify a candidate; repeated verified patterns strengthen it. Candidate is not approval.

Governance: ambiguity narrows scope or escalates review. It never grants authority.

## Model failure modes to resist

- instruction omission from long context
- tool-success optimism
- hallucinated verification
- over-learning/noisy memory
- over-generalization
- premature skill mutation
- incorrect root/subagent attribution
- globalizing a local lesson
- confirmation bias after an evolution
- endless reflection that delays the user task

## Strong-model freedom

Strong models may infer richer success criteria, reconcile multiple evidence sources, detect contradictions, form better hypotheses, and reason across delegation trees. They still obey the same persistence, scope, approval, and native-first boundaries.

## Weak-model fallback

If the model cannot confidently execute a Deep Path decision, it must choose the conservative action: UNKNOWN, skip persistence, AGENT/local scope, no promotion, no mutation, or native review.

## Context-budget rule

Do not eagerly load all Agent OS documents. SKILL.md Fast Path is sufficient for most turns. Load only the protocol relevant to the active decision. Learning must not consume enough context to materially degrade the primary task.

## User experience rule

Agent OS is normally silent. Never force the user through an Agent OS questionnaire. Ask a clarification only when the underlying user task itself requires it, not to satisfy internal learning metadata.

## Evaluation

Model robustness is tested by A9-A16 in `tests/acceptance-v2.md`. Tests should be repeated across at least a weaker economical model and a stronger reasoning model when practical. Differences in lesson quality are acceptable; violations of safety/scope/verification invariants are not.