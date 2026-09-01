# Heartbeat

When the OpenClaw heartbeat wakes this agent:

1. Invoke the `proactive` Skill.
2. Run `python3 skills/proactive/scripts/proactive.py heartbeat` once.
3. If it prints `HEARTBEAT_OK`, return exactly `HEARTBEAT_OK`.
4. Otherwise handle only its structured attention items through the owning Skills and gates.
5. Do not manually repeat maintenance or perform unrelated work.

Periodic exact-time tasks (e.g. "check market at 9:00") should use OpenClaw Automations, not the heartbeat prompt.
