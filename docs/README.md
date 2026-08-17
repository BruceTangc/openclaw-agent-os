# OpenClaw Agent OS v1.3 Production

Target baseline: OpenClaw 2026.7.1-2.

> 协议总纲见 [PROTOCOL.md](PROTOCOL.md)，冻结存档见根目录 FINALIZE-REPORT.md。

This package provides the governance, decision and workflow layer around OpenClaw's native runtime.

## Install
1. Back up existing versions of any same-named Skills.
2. Copy each directory under `skills/` into the OpenClaw skills directory you use.
3. Read `INSTALL.md`.
4. Enable/verify Skills according to your OpenClaw installation.
5. Run the smoke tests in `tests/`.

## Design rule
OpenClaw native runtime first. These Skills must not create parallel runtimes for memory, context, tasks, scheduling, events, agents or permissions.

## AGENTS.md 参考模板
新机器 / 新工作区装完 Agent OS 后，复制 [AGENTS-TEMPLATE.md](AGENTS-TEMPLATE.md) 为你的 `AGENTS.md`，按需删改即可让 Main Agent 正确加载 Agent OS 行为规范。

## Modules
proactive
memory-governance
knowledge-governance
ontology
context-orchestration
task-manager
orchestrator
permission-security
verification-evaluation
self-evolution
summarize

## Safety
High-risk external actions remain subject to OpenClaw native policy/approval. Self-evolution cannot silently weaken security.
