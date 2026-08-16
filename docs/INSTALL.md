# Installation

## Compatibility
Designed for OpenClaw 2026.7.1-2.

## Install layout
Install the folders under `skills/` as normal OpenClaw Skills. Do not install `schemas/` or `tests/` as Skills.

Example conceptual layout:

skills/
  proactive/
    SKILL.md
  memory-governance/
    SKILL.md
  ...

Use the skills directory configured by your OpenClaw installation rather than assuming a fixed path.

## Upgrade procedure
1. Back up existing same-name Skills.
2. Replace the Skill directory.
3. Restart/reload the agent runtime as appropriate for your OpenClaw setup.
4. Verify the Skill is discoverable.
5. Run the smoke tests.

## Do not install
There is intentionally no scheduler, event bus, memory runtime, context engine, task runtime, agent runtime or permission runtime in this package.
