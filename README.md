# OpenClaw Agent OS v1.2

Governance, decision and workflow policy layer around OpenClaw's native runtime.

> 官方协议：见 [docs/PROTOCOL.md](docs/PROTOCOL.md)（统一行为协议）。
> 冻结存档：见 [FINALIZE-REPORT.md](FINALIZE-REPORT.md)、[DEEP-AUDIT.md](DEEP-AUDIT.md)、[SCRIPTS-AUDIT-FINAL.md](SCRIPTS-AUDIT-FINAL.md)。

> **Design rule:** OpenClaw native runtime first. These skills must **not** create
> parallel runtimes for memory, context, tasks, scheduling, events, agents or permissions.
> Skills provide policy, reasoning procedures and workflows; OpenClaw owns the runtime.

## Modules (11)

| Module | Type | Purpose |
|---|---|---|
| `proactive` | adjusted | Decide whether something useful should happen after wakeup |
| `task-manager` | adjusted | Goal/task semantics; OpenClaw owns task runtime |
| `orchestrator` | adjusted | Decomposition/delegation/sequencing policy; OpenClaw remains runtime |
| `ontology` | adjusted | Minimal semantic model of entities, relations, attributes, states |
| `summarize` | adjusted | Transform large/noisy material into decision-useful information |
| `self-evolution` | adjusted | Controlled, evidence-based improvement loop |
| `memory-governance` | new | What becomes durable memory; promotion path |
| `knowledge-governance` | new | Durable claims with provenance, freshness, uncertainty |
| `context-orchestration` | new | Select minimum useful information for a task |
| `verification-evaluation` | new | Prove task success vs. tool success; PASS/PARTIAL/FAIL/UNKNOWN |
| `permission-security` | new | L0-L4 risk/authority policy above native policy/approval |

## Architecture

```
Trigger (user / heartbeat / automation / hook)
  -> Intake (signal ingestion)
  -> Context Orchestration
 -> Goal / Task semantics
 -> Proactive Decision
 -> Orchestrator
 -> Permission Security
 -> OpenClaw execution (native)
 -> Verification
 -> Evaluation
 -> Memory / Knowledge writeback
 -> Self-Evolution candidate
```


## Control Plane (v1.2 Core Protocol)

```
OpenClaw Native Runtime (owner: OpenClaw)
   │  agent loop / tool wiring / prompt assembly / session / workspace / skills
   ▼
┌────────────────────────────────────────────────────────────┐
│ Agent OS Control Plane (policy / protocol / governance)      │
│   Context → Decision → Permission → Action → Verification   │
│   → Memory/Knowledge writeback → Evolution candidate         │
├────────────────────────────────────────────────────────────┤
│  Cognition        │  Action          │  Control             │
│  memory-governance│  proactive       │  permission-security │
│  knowledge-gov.   │  task-manager    │  verification-eval.  │
│  ontology         │  orchestrator    │  self-evolution      │
│  context-orch.    │  summarize       │                      │
└────────────────────────────────────────────────────────────┘
   ▼
OpenClaw Tools / Sub-agents / Skills / Runtime
```

> **Trigger 边界：** Cron / Heartbeat / Hook / User Message / Background Tasks 都是
> **外部 Trigger**（OpenClaw 提供）。Agent OS 不制造 Trigger、不建 Scheduler ——
> proactive 是**主动决策能力**，不是定时器。

## Core Protocol 文档

所有 Skill（Agent OS 模块 + 业务 Skill）必须遵守统一行为协议：

| 文档 | 内容 |
|:--|:--|
| [PROTOCOL.md](docs/PROTOCOL.md) | 总纲：统一执行链、分层模型、业务 Skill 接入协议 |
| [DECISION-PROTOCOL.md](docs/DECISION-PROTOCOL.md) | 决策词汇表、输入/输出 schema、anti-loop |
| [ACTION-PROTOCOL.md](docs/ACTION-PROTOCOL.md) | L0-L4 动作分级、Permission Gate、幂等 |
| [VERIFICATION-PROTOCOL.md](docs/VERIFICATION-PROTOCOL.md) | V0-V4 验证分级、PASS/PARTIAL/FAIL/UNKNOWN |
| [MEMORY-PROTOCOL.md](docs/MEMORY-PROTOCOL.md) | 写入判定、晋升路径、矛盾保留 |
| [EVOLUTION-PROTOCOL.md](docs/EVOLUTION-PROTOCOL.md) | 进化证据、授权边界、禁止自行修改安全规则 |
| [SKILL-INTEGRATION.md](docs/SKILL-INTEGRATION.md) | 业务 Skill 接入协议（x-agent-os 声明块） |
| [HEARTBEAT-CRON-POLICY.md](docs/HEARTBEAT-CRON-POLICY.md) | Trigger 边界；Proactive 是决策层不是定时器 |
| [PROTOCOL-CHECKLIST.md](docs/PROTOCOL-CHECKLIST.md) | 逐文件审计清单 |
| [templates/](templates/) | 通用主动模板：HEARTBEAT.md + proactive-registry.yaml（让 Proactive 知道每轮检查什么） |

## Design guardrails

- **不建并行 Runtime**：scheduler / event bus / task runtime / memory runtime /
  context engine / agent runtime / permission runtime 全部禁止。
- **Verification 独立**：tool success ≠ task success；必须检查实际结果 → PASS/PARTIAL/FAIL/UNKNOWN。
- **Self-Evolution 受控**：权限/安全/凭证/外部副作用/Runtime 变更必须人工审批。
- **OpenClaw 原生优先**：重复造 OpenClaw 已有的机制 = 违反协议。

## Explicitly do NOT build

- scheduler runtime
- event bus runtime
- task database/runtime
- memory database/runtime
- context engine
- agent runtime
- parallel permission enforcement runtime

## Install

1. Back up existing same-named skills.
2. Copy each directory under `skills/` into your OpenClaw skills directory.
3. Read `docs/INSTALL.md`.
4. Run the smoke tests in `docs/tests/`.

Target baseline: OpenClaw 2026.7.1-2.

## Docs

- `docs/ARCHITECTURE.md`
- `docs/INSTALL.md`
- `docs/COMPATIBILITY.md`
- `docs/OPERATIONS.md`
- `docs/schemas/` — decision / evidence / state / task models
- `docs/tests/` — smoke test cases

## License

MIT