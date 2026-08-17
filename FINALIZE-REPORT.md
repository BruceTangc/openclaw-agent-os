# Agent OS v1.2 Finalize Report（历史存档，当前版本 v1.3）

> Agent OS v1.2 冻结存档。记录整轮重构、精修、脚本审计的最终状态。
> 让后续读者（无论人还是 AI）一眼看清：这套体系审到哪、定稿状态如何、边界如何守住。

## 1. 定位（为什么有这个体系）

```
OpenClaw Native Runtime（OpenClaw 拥有：agent loop / session / tool wiring /
prompt assembly / skills / approval / sandbox / Cron / Heartbeat / Hooks）
        │  Wakeup
        ▼
┌─────────────────────────────────────────────────────┐
│  Agent OS Control Plane（policy / protocol / 治理）  │
│                                                     │
│   WHETHER  Proactive                                │
│   HOW      Orchestrator                             │
│   WHAT     Task Manager                             │
│   MAY I    Permission Security                      │
│   DID IT   Verification & Evaluation                │
│   进化     Self-Evolution                           │
│   支撑     Context / Memory / Knowledge / Ontology / Summarize │
└─────────────────────────────────────────────────────┘
        │  执行
        ▼
OpenClaw Native Execution（Agent / Sub-agent / Tool / Skill）
```

**硬性边界**：Agent OS 是 OpenClaw 之上的治理层，**绝不建并行 Runtime**
（Scheduler / Event Bus / Task Runtime / Memory Runtime / Context Engine / Agent Runtime / Permission Runtime 一律禁止）。

## 2. 11 个 Core Skills 定稿状态

| Skill | 定位 | 冻结评级 | 备注 |
|:--|:--|:--|:--|
| proactive | 被唤醒后决定"是否值得做、做什么" | 🟢 9.3 | 决策节点，非定时器 |
| memory-governance | 决定写什么记忆、分层晋升 | 🟢 9.3 | 存储/召回归 OpenClaw |
| knowledge-governance | 可复用知识→持久声明治理 | 🟡 9.0 | 物理持久化用 OpenClaw 设施 |
| context-orchestration | 选择最小充分上下文 | 🟢 9.4 | 不加工成结论 |
| task-manager | 任务语义/状态管理 | 🟡 9.0 | 恢复/重试→建议，不自行执行 |
| orchestrator | 决定怎么拆、谁做、顺序 | 🟢 9.4 | 执行走 OpenClaw |
| permission-security | L0-L4 风险分级+授权建议 | 🟢 9.5 | native policy 是最终边界 |
| verification-evaluation | 区分工具成功/任务成功 | 🟢 9.6 | V0-V4 + PASS/…/UNKNOWN |
| ontology | 实体/关系语义索引 | 🟢 9.2 | 不建图数据库 |
| self-evolution | 受控改进循环 | 🟡 9.0 | 脚本审计最重点 |
| summarize | 信息压缩为决策可用 | 🟢 9.5 | 只产 candidates |

## 3. 统一 Skill 规范（对齐 OpenClaw 2026.7.1-2）

- **Frontmatter**：name + description（<160字符，一行）+ metadata 单行 JSON
  `metadata: { "openclaw": {...}, "agent_os": { "protocol_version": "1.2", "layer": "core" } }`
- **17 节结构**：Purpose/Scope/Non-Goals/OpenClaw Boundary/When to Activate/Inputs/Core Procedure/Decision Rules/Outputs/Interaction/Permission/Verification/Failure Handling/Memory-Knowledge Writeback/Self-Evolution Feedback/Safety-Anti-Loop/Examples
- **统一执行链**（系统级生命周期，单 Skill 只做其中一环）：
  `Trigger → Intake → Context → Goal/Task → Decision → Permission → Action → Verification → Evaluation → Writeback → Evolution`
- **职责节点**：每个 Skill 是生命周期的一个环节，不要求自己跑完整 loop

## 4. 脚本级安全审计结论（16 个脚本全查）

**总判断：整体守住"不建并行 Runtime"边界** —— 无 while True / 无线程常驻 / 无自建 scheduler / 无推送式 event bus / 无绕过原生 approval。

| # | 检查项 | 结论 |
|:--|:--|:--|
| 1 | 自建 Runtime | ✅ 无 |
| 2 | 自建 Event Bus | ✅ 无（bus.py 是静态读写文件，非推送总线）|
| 3 | 自建 Scheduler | ✅ 无 |
| 4 | 绕过执行直接副作用 | ✅ 无 |
| 5 | 权限绕过 | 🟡 `--no-approval` 仅设元数据，不绕过 native approval（非越权）|
| 6 | 自动修改 Skill | ✅ 已修复（learn.py 不再自动写 SOUL/AGENTS）|
| 7 | 状态系统重复 | ✅ 三领域不重叠（任务/决策/学习）|
| 8 | 循环调用 | ✅ 调用链无环，acyclic DAG |
| 9 | 重复存储 | ✅ 无冗余冲突 |
| 10 | 与 OpenClaw 原生冲突 | ✅ 只读自己 workspace，无读 session/凭证 |

### 已修复的越界问题
- **learn.py**：阻断自动写入 SOUL.md/AGENTS.md（安全红线/人格）→ 改 MEMORY/TOOLS 自动、AGENTS/SOUL 需人批
- **skillgen.py**：`--approve` 需 `--yes` 显式确认（L2 动作）
- **sync.py**：修复 zip 路径穿越（zip-slip）

## 5. 冻结结论

- 架构方向：✅ 正确（OpenClaw native runtime first）
- 模块划分：✅ 11 个核心，不再增 Skill
- SKILL.md 规范：✅ 对齐 OpenClaw 官方
- 职责边界：✅ 已收口
- 脚本审计：✅ 完成，越界项已修
- **整体定稿：Agent OS v1.2 可以冻结**

## 6. 后续可选优化（非阻断）

- `--no-approval` 可改名为 `--mark-auto-approvable`（更准确，不构成风险）
- `V0 = tool_success` 术语可改 `execution acknowledgement`（术语，无需折腾）
- 业务 Skill 后续按 `x-agent-os` 接入协议往上挂，不增加核心模块