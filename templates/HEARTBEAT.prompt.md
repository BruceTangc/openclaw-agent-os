# Agent OS Heartbeat Prompt

1. Execute exactly this command once and no other diagnostic, status, queue, cron, or maintenance command:
   `OPENCLAW_WORKSPACE='{{WORKSPACE}}' OPENCLAW_AGENT_ID={{AGENT_ID}} python3 '{{PROACTIVE_SCRIPT}}' heartbeat`
2. This command is the authoritative cadence gate: it runs only due checks and records results.
3. If it prints `HEARTBEAT_OK`, reply exactly `HEARTBEAT_OK` and do no unrelated work.
4. If it returns attention items, report or handle only those items through their owning Skills and gates; add no unrelated checks.
5. Do not rerun maintenance manually in the same wake. Vault is export+reconcile only.
6. Pass Permission Gate before action and verify actual results afterward.
7. External, destructive, financial, access-control, or production actions require authorization.

Exact-time business tasks belong in OpenClaw Automations and are created only when the user requests them.
