# Heartbeat

When the OpenClaw heartbeat wakes this agent:

1. Invoke the `proactive` Skill.
2. Let the Proactive Skill execute its Core Procedure.
3. Follow its decision, permission, action, and verification rules.
4. If no action is required, return `HEARTBEAT_OK`.
5. Do not perform unrelated work.

Periodic exact-time tasks (e.g. "check market at 9:00") should use OpenClaw cron, not HEARTBEAT.md.
