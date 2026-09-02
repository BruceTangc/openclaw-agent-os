# Compatibility

Baseline: OpenClaw 2026.8.1 (OpenClaw 2.0).

Heartbeat integration uses `agents.defaults.heartbeat.agentId/every/prompt`. OpenClaw owns
the system heartbeat automation; Agent OS does not create or edit its persisted job row.
Legacy workspace `HEARTBEAT.md` files are neither installed nor used as the runtime contract.
Only the selected ambient owner is enrolled; helper agents must not receive placeholder `heartbeat` blocks, because OpenClaw 2.0 treats any per-agent block as an explicit enrollment list.

Shared Skills may be linked into multiple workspaces. Prefer a configured global Skills directory or relative links that stay inside the OpenClaw data tree. Some OpenClaw full-backup implementations reject absolute links escaping a workspace; config-only backup remains available, but a full backup must be verified before relying on it.

Compatibility principles:
- use native OpenClaw mechanisms first;
- do not assume undocumented tools;
- do not replace Context Engine;
- do not replace Memory runtime;
- do not replace Task/Automation runtime;
- do not bypass native approvals or policies;
- verify external side effects.

If a future OpenClaw release changes a native capability, update the relevant Skill rather than creating a duplicate runtime.
