# Agent OS v2 Installation

## Recommended — zero configuration

```bash
openclaw skills install git:BruceTangc/openclaw-agent-os@agent-os-v2
```

No `install.sh`, Python dependency, Agent OS config, cron, heartbeat, AGENTS.md merge, database, agent-id selection, or memory-path selection is required.

OpenClaw installs Git skills into the active workspace by default. To intentionally share the skill across local agents, use OpenClaw's native global installation option if appropriate for your deployment; Agent OS itself does not create or copy per-agent runtimes.

## Verify

```bash
openclaw skills info agent-os
openclaw skills check
```

The skill should be eligible/ready for the selected agent. OpenClaw watches normal skill roots and refreshes skill snapshots; no Agent OS restart hook is required.

## Upgrade

Git installs are unmanaged sources. Reinstall the desired Git ref to refresh Agent OS. Do not use the old v1.3 `install.sh` workflow.

## Runtime behavior

Agent OS v2 is instruction/protocol based. It runs inside the current OpenClaw agent turn and uses native capabilities already exposed to that agent. It does not install a background daemon or hook service. Native memory/self-learning/Workshop features are used when available; if unavailable, Agent OS degrades without inventing parallel storage or claiming durable learning occurred.
