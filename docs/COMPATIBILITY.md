# Compatibility

Baseline: OpenClaw 2026.8.1 (OpenClaw 2.0).

Heartbeat integration uses `agents.entries.<agent>.heartbeat.every/prompt`. OpenClaw owns
the system heartbeat automation; Agent OS does not create or edit its persisted job row.
Legacy workspace `HEARTBEAT.md` files are neither installed nor used as the runtime contract.

Compatibility principles:
- use native OpenClaw mechanisms first;
- do not assume undocumented tools;
- do not replace Context Engine;
- do not replace Memory runtime;
- do not replace Task/Automation runtime;
- do not bypass native approvals or policies;
- verify external side effects.

If a future OpenClaw release changes a native capability, update the relevant Skill rather than creating a duplicate runtime.
