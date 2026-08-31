# Agent OS Heartbeat

1. Invoke the `proactive` Skill and follow its Core Procedure.
2. Run `python3 <proactive-skill>/scripts/maintenance.py plan` and process only returned `due` checks.
3. Route due checks to their owning Skills: `task_health` → task-manager scan/link;
   `memory_governance` → governed memory review; `ontology_health` → validate/duplicates/
   contradictions; `evolution_state` → self-evolution pending state; `vault_sync` → export+
   reconcile only when `AGENT_OS_VAULT_DIR` is configured; `weekly_review` → task/memory summary.
4. After evidence-backed completion, call `maintenance.py record --name <check> --result <status>`.
   Do not record PASS on tool success alone. UNKNOWN with possible side effects must not auto-retry.
5. Inspect only current signals, active goals/tasks, due items, and recent verifiable failures.
6. Do not infer work from stale conversation history and do not repeat an unchanged action or alert.
7. Pass Permission Gate before action and verify actual results afterward.
8. External, destructive, financial, access-control, or production actions require applicable authorization.
9. If nothing has new actionable value, reply exactly `HEARTBEAT_OK`.

Exact-time business tasks belong in OpenClaw Automations and are created only when the user requests them.
