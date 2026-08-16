# Operations

## Daily operation
- Proactive checks should be quiet when there is nothing valuable to do.
- External actions must pass permission-security.
- Consequential work must pass verification.
- Repeated failures may create self-evolution candidates.

## Failure handling
Transient -> retry within budget.
Deterministic -> repair then verify.
Ambiguous -> request clarification.
Unauthorized/high-risk -> escalate.
Repeated systemic failure -> self-evolution candidate.

## Anti-loop controls
Every proactive/task cycle should carry:
- cycle_id
- parent_task_id when applicable
- retry_count
- action_signature
- last_action_time
- escalation state

Never repeat the same unchanged action solely because a wakeup occurred.
