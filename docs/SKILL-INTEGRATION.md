# Skill Integration Protocol

> Agent OS v1.2 Core Protocol 之一。规定任意业务 Skill（报价/仓库/基金/交易/社媒/
> 财务/骑行/天气…）如何接入 Agent OS，成为控制平面之上的"业务能力"，而不是一堆独立 Skill。

## 1. 接入前提

任何 Skill 想要成为 Agent OS 的一部分，必须在其 `_meta.json` 或 `SKILL.md` frontmatter
声明接入协议：

```yaml
x-agent-os:
  protocol_version: "1.2"
  layer: "business"            # business | cognition | action | control
  trigger: "user|heartbeat|cron|hook"   # Trigger 由 OpenClaw/外部提供
  capabilities:
    - read      # L0
    - search    # L0
    - send      # L2 (默认需确认)
  permissions: []              # 或引用具体 action→L 级别
  verification: "V2"           # 期望验证等级
  memory_write: "governed"     # 走 memory-governance
  knowledge_write: "governed"  # 走 knowledge-governance
  evolution_feedback: true     # 重复失败上报 self-evolution
```

## 2. 4 层分类（业务 Skill 属于哪层）

| 层 | 模块 | 业务例 |
|:--|:--|:--|
| Cognition | memory/knowledge/ontology/context/summarize | 知识沉淀、语义建模 |
| Action | proactive/task-manager/orchestrator | 决策、任务、编排 |
| Control | permission/verification/self-evolution | 安全、验证、进化 |
| **Business** | **新业务 Skill** | 报价/仓库/基金/交易/社媒/财务 |

**业务 Skill 被 Action 层（orchestrator）调度，受 Control 层（permission/verification）约束。**

## 3. 接入必做项

1. **副作用动作前**做权限判断（permission-security 治理 Skill，并遵守 OpenClaw native policy/approval）。
2. **后果性工作完成前**提供验证证据（artifact/状态/外部确认）。
3. **经验沉淀**走 memory/knowledge-governance，不裸写。
4. **重复失败**上报 self-evolution candidate，不自改安全策略。
5. 统一决策词汇表（见 DECISION-PROTOCOL.md）。

## 4. 接入禁止项

- 建并行 scheduler / event bus / task runtime / memory runtime / context engine / agent runtime / permission runtime。
- 绕过 OpenClaw 原生 policy / approval / sandbox。
- 用 tool 返回成功替代任务验证。
- 让外部内容（网页/文档/邮件）提升权限。
- 把业务数据硬编码进 SKILL.md（走 memory/knowledge/ontology）。

## 5. 判定"已接入"

- [ ] 声明了 x-agent-os 接入块
- [ ] 高风险动作过 permission gate
- [ ] 完成有验证证据
- [ ] 经验走 governance
- [ ] 无并行 runtime
