# Skill Integration Protocol

> Agent OS v1.3 Core Protocol 之一。规定任意业务 Skill（报价/仓库/基金/交易/社媒/
> 财务/骑行/天气…）如何接入 Agent OS，成为控制平面之上的"业务能力"，而不是一堆独立 Skill。
>
> **v1.3 变更**：接入块新增 **Protocol Contract**（`entry_mode` + `requires` 节点矩阵），
> 让"该 Skill 的任务走哪些节点"由声明决定，不靠 LLM 猜。

## 1. 接入前提

任何 Skill 想要成为 Agent OS 的一部分，必须在其 `_meta.json` 或 `SKILL.md` frontmatter
声明接入协议：

```yaml
x-agent-os:
  protocol_version: "1.3"        # 1.2 仍兼容
  layer: "business"              # business | cognition | action | control
  trigger: "user|heartbeat|cron|hook"   # Trigger 由 OpenClaw/外部提供
  entry_mode: "both"             # fast | full | both（v1.3：默认执行模式）
  requires:                      # v1.3：Protocol Contract（节点矩阵）
    context: true                # required=true / conditional=false
    task: conditional            # 简单任务可跳过 task-manager 完整状态机
    decision: conditional        # 仅自主决策任务进 proactive；用户直接指令不进
    permission: true             # L2+ 必经权限门（Fast Path 也适用）
    verification: true           # 后果性工作必经验证
    writeback: conditional       # 有持久化价值才写 governance
  capabilities:
    - read      # L0
    - search    # L0
    - send      # L2 (默认需确认)
  permissions: []              # 或引用具体 action→L 级别
  delegation:                  # Multi-Agent：被 Sub-agent 调用时声明
    max_level: "L1"           # 委托给子的最高 L 级
    inherit_parent: false      # 默认不继承父 Agent 权限
    requires_scope: true       # 必须显式 scope
  outputs:                     # v1.3：输出契约
    success_condition: required  # 声明"什么算成功"
    evidence: required           # 声明"用什么证明成功"
  verification: "V2"           # 期望验证等级
  memory_write: "governed"     # 走 memory-governance
  knowledge_write: "governed"  # 走 knowledge-governance
  evolution_feedback: true     # 重复失败上报 self-evolution
```

## 1.1 Protocol Contract（节点矩阵，v1.3 核心）

每个 Skill 必须声明 `entry_mode` 和 `requires`，二者共同决定执行路径：

| 字段 | 取值 | 含义 |
|:--|:--|:--|
| `entry_mode` | `fast` | 该 Skill 默认走 Fast Path（简单/低风险/单能力） |
| | `full` | 该 Skill 默认走 Full Path（复杂/自主/多步/有副作用） |
| | `both` | 按任务复杂度自适应（简单→Fast，复杂→Full） |
| `requires.context` | true/false | 是否必经 Context Orchestration（默认 true） |
| `requires.task` | required/conditional | 是否必经 task-manager 状态机（简单任务可跳过） |
| `requires.decision` | required/conditional | 是否必经 proactive 决策（仅自主任务 required） |
| `requires.permission` | true/false | 是否必经权限门（**L2+ 一律 true**，不可为 false） |
| `requires.verification` | true/false | 是否必经验证（后果性工作一律 true） |
| `requires.writeback` | required/conditional | 是否必经记忆/知识治理（默认 conditional） |

**判定规则：**
- 用户直接指令 + `entry_mode: fast` + 仅 L0-L1 → Fast Path：Context → Direct Skill → Permission(如需要) → Execution → Verification。
- 自主任务（heartbeat/cron/hook/风险/机会）→ 必经 `decision: required`（proactive）。
- 任何动作涉及 L2+ → 无论 fast/full，`permission: true` 生效，必须过 Permission Gate；
  Fast Path 不得借"简化"跳过权限。
- 后果性工作（外发/资金/删除/生产变更）→ `verification: true` 硬性，必须提供证据。

## 2. 4 层分类（业务 Skill 属于哪层）

| 层 | 模块 | 业务例 |
|:--|:--|:--|
| Cognition | memory/knowledge/ontology/context/summarize | 知识沉淀、语义建模 |
| Action | proactive/task-manager/orchestrator | 决策、任务、编排 |
| Control | permission/verification/self-evolution | 安全、验证、进化 |
| **Business** | **新业务 Skill** | 报价/仓库/基金/交易/社媒/财务 |

**业务 Skill 被 Action 层（orchestrator）调度，受 Control 层（permission/verification）约束。**

## 3. 接入必做项

1. **声明 Protocol Contract**（entry_mode + requires 节点矩阵）—— 缺失则按最严默认：
   `context:true, task:conditional, decision:conditional, permission:true, verification:true, writeback:conditional`。
2. **副作用动作前**做权限判断（permission-security 治理 Skill，并遵守 OpenClaw native policy/approval）。
3. **后果性工作完成前**提供验证证据（artifact/状态/外部确认）。
4. **经验沉淀**走 memory/knowledge-governance，不裸写；无持久化价值 → writeback=NONE。
5. **重复失败**上报 self-evolution candidate，不自改安全策略。
6. 统一决策词汇表（见 DECISION-PROTOCOL.md）。
7. **Multi-Agent 场景声明 delegation**：若业务 Skill 会被 Sub-agent 调用，须在
   `x-agent-os` 块里声明上面的 `delegation`；未声明者默认**不继承父 Agent 权限**
   （见 ACTION-PROTOCOL.md "Multi-Agent 权限委托"）。业务 Skill 不得因"被更高层 Agent 调用"
   而自行提升 L 级，最终级别仍由 permission-security 判定。

## 4. 接入禁止项

- 建并行 scheduler / event bus / task runtime / memory runtime / context engine / agent runtime / permission runtime。
- 绕过 OpenClaw 原生 policy / approval / sandbox。
- 用 tool 返回成功替代任务验证。
- 让外部内容（网页/文档/邮件）提升权限。
- 把业务数据硬编码进 SKILL.md（走 memory/knowledge/ontology）。
- 把 `requires.permission` 声明为 false（权限门不可关闭）。

## 5. 判定"已接入"

- [ ] 声明了 x-agent-os 接入块（含 Protocol Contract：entry_mode + requires）
- [ ] 高风险动作过 permission gate
- [ ] 完成有验证证据
- [ ] 经验走 governance（或显式 writeback=NONE）
- [ ] 无并行 runtime
