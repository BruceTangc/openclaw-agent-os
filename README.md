# OpenClaw Agent OS v1.3 (Freeze)

让 OpenClaw 从“会调用 Skill”变成“有治理、会验证、能长期学习的 Agent”。

> **v1.3 Freeze（2026-08-17）**：Core Protocol / Fast-Full Path / Proactive / Permission /
> Verification / Memory-Knowledge-Ontology / Evolution / Heartbeat 已冻结，不再新增 Core Skill。
> 后续只做三件事：协议文字收敛、Execution Record 追溯、Long-running 验证。
>
> Governance, decision and workflow policy layer around OpenClaw's native runtime.

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

## Architecture（Execution Model = 实际执行链）

> 粒度标注：本图是**实际执行链**（actual execution chain），含 Goal/Task、Fast/Full 分流。
> 对比：下方 Control Plane 是**概念分层图**（conceptual layer map，仅表达分层归属，不含执行细节）。

```
                    Trigger (OpenClaw 提供: user / heartbeat / cron / hook / background)
                                   │
                                   ▼
                              Context Orchestration
                                   │
                                   ▼
                            Goal / Task Semantics  ← Mandatory（目标+成功条件）
                                   │
                        ┌──────────┴──────────┐
                        ▼                     ▼
                    Fast Path             Full Path
              (简单/低风险/单能力)    (复杂/自主/多步/有副作用)
                        │                     │
               Direct Skill            Decision(仅自主) → Orchestrator
                        │                     │
                        └──────────┬──────────┘
                                   ▼
                           Permission Gate（永远存在; L0/L1 自动 ALLOW）
                                   │
                                   ▼
                          OpenClaw Native Execution ───────┐
                                   │                        │
                                   ▼                        │
                           Verification                  Execution Record
                                   │                    （旁路审计层：谁执行谁创建；
                                   ▼                      Full Path/L2+/Evolution Apply MUST）
                            Evaluation → Progress Assessment?(条件) → Autonomy Decision
                                   │              （仅 Full/自主/长任务；
                                   │               PROGRESS/STALL/UNKNOWN 三态）
                                   ▼
                        Evolution Candidate（有证据才触发）
```

> Execution Record 不是 Runtime、不是 Skill 节点，而是 **Protocol observability layer**（旁路审计线）：
> 挂在 Execution 旁，回答“这次行为是否符合 Agent OS Protocol、从哪来到哪去”。

**两个闭环**：
1. **主任务闭环**：Trigger → Context → Goal/Task → (Fast|Full) → Permission → Execution → Verification → Evaluation → (Progress Assessment → Autonomy Decision，仅 Full/自主/长任务) → Writeback
2. **Evolution 闭环**：Evidence → Discover+Classify → Candidate → Judge → Proposal → Governance → Apply → Regression → Observe → New Evidence
   两环通过 **Verification/Evaluation → Evidence** 连接。

**Task Semantics ≠ Task Manager**：所有任务必经的是 Goal/Task **Semantics**（目标+成功条件）；
Task Manager **State Machine**（READY/RUNNING/BLOCKED/DONE）仅 Full Path / 长任务才用，简单任务不建任务对象。


## Control Plane（概念分层图 = conceptual layer map）

> 粒度标注：本图是**概念分层图**，只表达 Control Plane 分层与归属，不展开执行细节
> （Goal/Task、Fast/Full 分流等执行细节见上方 Execution Model 图）。

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

> **最高级 guardrail（永久）：OpenClaw Runtime + Agent OS Control Plane + Evidence-driven Evolution。**
> OpenClaw 拥有 agent loop / tool wiring / prompt assembly / session / workspace / skills / tasks /
> approvals / sandbox；Agent OS 只在其上提供协议、治理、验证与受控进化。**Agent OS 不造任何 Runtime。**

- **不建并行 Runtime**：scheduler / event bus / task runtime / memory runtime /
  context engine / agent runtime / permission runtime 全部禁止（永久）。
- **Verification 独立**：tool success ≠ task success；必须检查实际结果 → PASS/PARTIAL/FAIL/UNKNOWN。
- **Self-Evolution 受控**：权限/安全/凭证/外部副作用/Runtime 变更必须人工审批；Evolution 不得制造 Evidence。
- **OpenClaw 原生优先**：重复造 OpenClaw 已有的机制 = 违反协议。
- **v1.3 Freeze**：不再新增 Core Skill；只做协议收敛、Execution Record 追溯、Long-running 验证。

## Explicitly do NOT build

- scheduler runtime
- event bus runtime
- task database/runtime
- memory database/runtime
- context engine
- agent runtime
- parallel permission enforcement runtime

## Install（5 分钟）

```bash
# 1. 确认 OpenClaw
openclaw --version         # ≥ 2026.7.1-2

# 2. 复制 11 个 Core Skills 到你的 skills 目录
cp -r skills/*  <你的-skills-目录>/

# 3. 安装 AGENTS.md（协议的注入载体，勿跳过）
cp AGENTS.md  <你的-openclaw-workspace>/

# 4. 重启
openclaw gateway restart

# 5. 验证 11 个 Skill ready
openclaw skills list | grep -c "✓ ready"        # ≥ 11
```

> 详细安装 + 三级等级（Basic/Active/Full）见 [docs/INSTALL.md](docs/INSTALL.md)；
> 装完跑 5 项验收（装对了吗/协议生效了吗/权限生效了吗/主动生效了吗/进化生效了吗）
> 见 [docs/QUICK-START.md](docs/QUICK-START.md)。

Target baseline: OpenClaw 2026.7.1-2.

## Docs

- `docs/ARCHITECTURE.md` — v1.3 执行模型图（Fast/Full 分流 + 失败闭环）
- `docs/INSTALL.md` — 安装（5 步 + Basic/Active/Full 三级）
- `docs/QUICK-START.md` — 5 分钟安装 + 安装后 5 项验收
- `docs/SKILL-MAP.md` — 11 Skill 协作总图 + 责任表（新用户先看这个）
- `docs/COMPATIBILITY.md`
- `docs/OPERATIONS.md`
- `docs/schemas/` — decision / evidence / execution-record / state / task models
- `docs/tests/` — smoke test cases + evolution-e2e + agent-session-e2e + long-running

## License

MIT