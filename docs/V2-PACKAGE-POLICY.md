# Agent OS v2 Package Policy

Agent OS v2 is a single OpenClaw Skill and an adaptive learning layer. The v2 installable branch must contain only assets that are valid for that architecture.

## Canonical runtime surface

The installable v2 package is defined by the root `SKILL.md` plus the v2 protocols, contracts/schemas, native capability binding metadata, acceptance specification, validator, and current installation/architecture documentation.

OpenClaw owns runtime, sessions, tasks, multi-agent routing, subagents, memory, context, tools, approvals, automation, and Workshop application. Agent OS owns Verification, Experience, Evolution, and Governance semantics.

## Retired v1.3 assets

The v2 branch must not ship executable tests, scripts, installers, heartbeat/cron machinery, Vault/Obsidian runtime, ontology runtime, or eleven-Skill runtime assumptions from v1.3.

Historical v1.3 behavior remains available on `main` and in Git history. Migration documentation may name retired components only to explain their v2 replacement or retirement; those names do not imply a runtime dependency.

## Documentation rule

A document belongs in the installable v2 branch only when it describes the current v2 architecture, contracts, installation, operation, migration, testing, or implementation status. Historical design documents that describe a superseded runtime model should stay on the v1.3 branch/history rather than coexist as apparently-current v2 documentation.

## No personal-workflow dependency

User-specific integrations such as Obsidian or GitHub-backed vault synchronization are not Agent OS Core requirements. Agent OS uses OpenClaw native memory semantics and remains storage/integration agnostic.

## Gate invariant

Runnable v2 assets must never import, invoke, or require retired v1.3 modules. Static validation should fail closed when such dependencies reappear.
