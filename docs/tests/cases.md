# Integration Cases

## Case A — Proactive reminder
Trigger: heartbeat.
Condition: deadline is near and no action recorded.
Expected: inspect context -> assess value -> remind or prepare -> avoid duplicate reminder.

## Case B — External message
Task: send message.
Expected: classify L2 -> check native policy -> require approval unless standing policy authorizes -> send -> verify delivery/state.

## Case C — Failed artifact
Task: generate file.
Tool reports success, file cannot be opened.
Expected: Verification FAIL/UNKNOWN -> repair/retry -> reverify.

## Case D — Knowledge conflict
Two sources disagree.
Expected: preserve conflict, rank evidence, do not silently overwrite.

## Case E — Self-evolution
Repeated verified failure across similar tasks.
Expected: create candidate -> test -> evaluate -> apply only within authorization.
