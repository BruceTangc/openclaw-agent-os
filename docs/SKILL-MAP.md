# Skill Cooperation Map（11 Skill 协作总图）

> Agent OS v1.3。回答一个用户问题："这 11 个 Skill 到底怎么互相配合？"
> 不是第 12 个 Skill，而是把 11 个 SKILL.md 拼成一张图——用户不用自己拼。

---

## 1. 分层

```
Cognition（认知）         Action（行动）         Control（控制）
memory-governance        proactive              permission-security
knowledge-governance     task-manager           verification-evaluation
ontology                 orchestrator           self-evolution
context-orchestration    summarize
```

---

## 2. 协作总图（一张图看懂）

```
                ┌───────────────┐
                │    Trigger    │  OpenClaw 提供: user / heartbeat / cron / hook
                └───────┬───────┘
                        ▼
        ┌───────────────────────────┐
        │  Context Orchestration    │  选"当前任务需要的最少信息"
        └───────────┬───────────────┘
                    ▼
           Goal / Task Semantics    目标 + 成功条件（Mandatory）
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      Fast Path           Full Path
      （简单/低风险）      （复杂/自主/多步/有副作用）
          │                   │
   Direct Skill         Proactive（仅自主任务）→ Task Manager（状态机）
          │                   │
          │              Orchestrator（编排/委派）
          │                   │
          └─────────┬─────────┘
                    ▼
           Permission Security（永远存在; L0/L1 自动 ALLOW）
                    │
                    ▼
                OpenClaw（执行）
                    │
                    ▼
         Verification / Evaluation
          证明完成 / 评判质量
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      Writeback            Evidence
      （有持久化价值）     （有证据的失败/纠正/观测）
          │                   │
    Memory / Knowledge    Self-Evolution（受控改进）
          │                   │
          ▼                   ▼
      Ontology（语义关联）←───┘（改进后回流，被后续 Context 使用）
```

---

## 3. 责任表（Skill 负责什么 / 上游 / 下游 / 何时用 / 不负责什么）

| Skill | 负责什么 | 上游 | 下游 | 什么时候用 | 不负责什么 |
|:--|:--|:--|:--|:--|:--|
| context-orchestration | 上下文选择（最少必要信息） | Trigger | Goal | 每个任务 | 不执行业务 |
| proactive | 自主决策（值不值得做） | Heartbeat/Cron/Hook | Task/Orchestrator | 自主任务 | 不建调度器 |
| task-manager | Task 语义与状态（语义层） | Goal/Proactive | Orchestrator | Full Path | 不执行业务、不建执行队列 |
| orchestrator | 编排/分解/委派/顺序 | Task/Proactive | Permission | Full Path | 不保存任务生命周期 |
| summarize | 大段材料压缩为决策可用信息 | 任意任务 | Context/Memory | 材料多/杂时 | 不做自动决策 |
| permission-security | 风险分级 L0-L4 / 授权建议 | 任意动作前 | OpenClaw native policy | 所有动作 | 不决定任务目标 |
| verification-evaluation | 证明工具结果 ≠ 任务结果 | Execution | Evaluation | 后果性任务 | 不执行任务 |
| memory-governance | 经验/事件治理（我经历了什么） | Outcome/Evidence | 未来 Context | 有持久价值时 | 不存知识声明 |
| knowledge-governance | 稳定事实/声明治理（世界是什么） | Summarize/外部源 | Ontology/Context | 稳定事实 | 不存经验 |
| ontology | 实体/关系/语义索引（如何关联） | Context/Knowledge | Context | 语义建模 | 不存记忆 |
| self-evolution | 受控系统改进（Evidence→Change） | Verification/Proactive | Change/Regression | 有证据的重复失败 | 不改安全规则 |

> **一句话分工**：context 选信息 → task 定语义 → proactive 判价值 → orchestrator 定顺序 →
> permission 控风险 → verify/eval 证结果 → memory/knowledge/ontology 沉淀 →
> evolution 改进系统。互相通过**协议交接**，不互相调用实现。

---

## 4. 关键边界（容易混淆的三对）

| 成对概念 | 区别 |
|:--|:--|
| **Verification vs Evaluation** | Verification proves completion（有没有真的做到）；Evaluation judges quality（做得好不好） |
| **Task Semantics vs Task Manager** | 语义（目标+成功条件）对所有任务 Mandatory；状态机（READY/RUNNING/DONE）仅 Full Path |
| **Memory vs Knowledge vs Ontology** | Memory=我经历了什么；Knowledge=世界是什么；Ontology=它们如何关联 |

## 5. 认知层三角

```
          Ontology（实体/关系/意义）
           /        \
          /          \
   Memory —————— Knowledge
  （经历）          （世界事实）
```

- Memory：经验、事件、教训。
- Knowledge：可复用的稳定声明（带来源/新鲜度/置信度）。
- Ontology：实体、关系、属性、状态的语义索引（含别名）。

---

## 6. Verification & Evaluation 在协作中的位置

```
Execution → Verification（有没有真的做到）→ Evaluation（做得好不好）
                                              │
                     Writeback（有价值才写）←─┘
                          │
                     Evidence（有证据才进化）
```

- **Verification proves completion; Evaluation judges quality.**（Agent OS 固定术语）
- Evaluation 通过才写 writeback；有证据的失败/弱项才进 Evolution。