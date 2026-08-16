# Compatibility

Baseline: OpenClaw 2026.7.1-2.

Compatibility principles:
- use native OpenClaw mechanisms first;
- do not assume undocumented tools;
- do not replace Context Engine;
- do not replace Memory runtime;
- do not replace Task/Automation runtime;
- do not bypass native approvals or policies;
- verify external side effects.

If a future OpenClaw release changes a native capability, update the relevant Skill rather than creating a duplicate runtime.
