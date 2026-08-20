# Evolution Protocol

> Agent OS v1.3 Core Protocol 之一。受控的、有证据的自我改进循环。边界：安全规则永不自行修改。
>
> **核心原则：Evolution is evidence-driven, not schedule-driven.**
> 不是"每天 3 点进化"，也不是"每完成一个任务就进化"；
> 而是 `Evidence → Candidate → Evolution`。Heartbeat/Cron 只是**发现 Evidence 的触发器**，
> 不是 Evolution 本身的触发条件。

## 1. 进料边界（Evidence → Candidate，关键）

**Evolution 只接受 Evolution Candidate，不直接接受任意 Evidence。**

```
Evidence (来自 Verification / Evaluation / Proactive / User Feedback / 观测)
  → Evidence Classification (判断: 有进化价值吗?)
       ├─ NO  → 结束 (一次性纠正/噪音/无复用价值, 不触发)
       └─ YES → Evolution Candidate
                   → Evolution (判断: 是否值得改变系统, 改变什么)
```

- **Evidence** = 原始事实：一次失败、一次纠正、一个观测。
- **Candidate** = 经过分类、判定"有进化价值"的 Evidence。
- 未分类的 Evidence 不得直接触发修改——防止 evolution 变成"看到什么都想改系统"。

### Evidence Sources（统一术语，v1.3.1）

所有进入进料边界的原始观测统一归为 **Evidence**，按来源分 5 类：

```
Evidence
├── Verification Evidence       （验证失败/漏洞）
├── Evaluation Evidence         （质量评判弱项）
├── User Feedback Evidence      （用户纠正/明确要求）
├── Proactive Observation       （巡检/心跳发现的长期模式）
└── Operational Evidence        （运营日志/learning trail/多 Agent 上报）
```

统一链路：`Raw Observation → Evidence → Classification → Candidate`。
任何来源（verification / evaluation / proactive / 用户反馈 / 观测 / 多 Agent 事件）在本文档一律称 **Evidence**；
不再使用 learning ledger / experience event / 原始观测等平行词。

## 2. Evolution Candidate 触发器（6 类）

| # | 触发器 | 说明 | 示例 |
|:--|:--|:--|:--|
| ① | 重复失败 | 同类任务重复 FAIL / PARTIAL（≥2 且可复现） | 连续 3 次总结 PDF 漏表格 |
| ② | 重复纠正 | 用户/Agent 多次修正同一问题 | 两次纠正"不要用表格" |
| ③ | 稳定新需求 | 持续、稳定的新行为要求 | 跨 ≥2 个任务都要"转 PDF" |
| ④ | 流程低效 | 同一任务长期存在重复劳动 | 每次都要手动补上下文 |
| ⑤ | Verification 暴露系统性漏洞 | 某 Skill/Procedure 经常无法通过验证 | 报价单常缺材料利用率检查 |
| ⑥ | 用户明确要求改进 | "以后都这样做"/"记住这个流程"/"加入你的方法" | 用户明确指定新规则 |

**禁止的来源**：单次偶发失败、无证据的主观感觉、为提高完成率而造的"改进"。

## 3. 触发者分工（谁发现问题，谁决定改变）

| 角色 | 职责 | 输出 |
|:--|:--|:--|
| Verification / Evaluation | 任务执行中发现失败/弱点 | Evidence |
| Proactive / Heartbeat / self-evolution discover 巡检 | **Discover + Classify**：扫描长期 Evidence，判定进化价值 | **Evolution Candidate** |
| 用户反馈 | “你每次报价都漏材料利用率” | Evidence（由 Classification 判定） |
| **Evolution** | **Judge + Propose + Apply**：判断“是否值得改变系统、应该改变什么” | Candidate → Proposal / Apply |

**边界**：
- Heartbeat **不直接执行 evolution**；正确路径是 `Heartbeat → Proactive → 检查长期 Evidence → 产生 Candidate → Evolution`。
- **Proactive / 巡检 可以执行 Evidence Classification，但不能执行 Evolution Judgment**——
  分类（Discover + Classify）是 Proactive 的职责，判断改不改/改什么（Judge + Propose + Apply）是 Evolution 的职责。
- 二者通过 Candidate 交接，不越界。

## 4. Candidate 的修改目标分类（Classify）

Candidate 进入 Evolution 后，先分类"改什么"：

```
preference       → 用户偏好 (USER)
memory           → 经验记忆 (memory-governance)
knowledge        → 可复用声明 (knowledge-governance)
ontology         → 语义关系 (ontology)
skill procedure  → Skill 工作流/指令 (G1-G3)
AGENTS/protocol  → 行为规范/协议 (G5)
tooling          → 工具/脚本改进 (G3)
```

分类决定走哪条治理路径与审批级别（见 §5）。

## 5. 进化的最小单位（Change Granularity）

进化按"影响面从小到大"分级，**每次只改最小单位**，禁止一次改多个维度：

| 级别 | 最小单位 | 示例 | 审批 |
|:--|:--|:--|:--|
| G1 | Prompt 指令措辞 | SKILL.md 里一句话的澄清 | 低风险可走授权策略 |
| G2 | 示例/模板 | 加一个 few-shot 示例、补 schema 字段 | 低风险可走授权策略 |
| G3 | 工作流/流程 | 调整 SKILL.md 的步骤顺序、加检查点 | 需 review |
| G4 | 评估标准/验证等级 | 调整 V 等级匹配规则 | 需 review + 人工 |
| G5 | 协议/策略定义 | 改 PROTOCOL 文档、决策词汇表 | 必须人工审批 |
| G6 | 安全/权限/Runtime | 权限规则、凭证处理、外部副作用 | **禁止自动，强制人工审批** |

规则：
- 一次进化只动一个 G 级别，从当前级别开始，不跳级。
- 高一级的修改包含低一级的全部影响面（如改 G4 评估标准需连带 G1-G3 的回归检查）。
- 无法归入以上级别的变更 → 默认按最高级别处理。

## 6. 审批流（Approval Flow）

按变更级别分两级审批，**不是单节点**：

```
G1-G2（低风险指令/示例改进）
  → 走已有授权策略（如果用户在 AGENTS.md / 授权策略里已预授权）
  → 否则仍需用户确认
  → 应用后 Regression check

G3-G6（工作流 / 评估 / 协议 / 安全）
  → 生成变更候选（问题、证据、提议变更、预期影响、回归检查）
  → 进入 review queue（人工）
  → 多级审批：
      ① Skill Owner / 主 Agent 复核（证据是否成立、影响面是否清晰）
      ② 用户/管理员审批（G5-G6 必须人工显式批准）
      ③ 应用 → Regression check → 记录
```

**多级审批要点：**
- G5/G6 必须两级以上：先技术复核（主 Agent），再人工批准（用户）。
- 审批必须绑定：变更内容、范围、生效时间、回滚方案。
- 被拒的候选保留记录（含拒绝原因），不静默丢弃。
- 紧急修复（如安全漏洞）可走快速通道，但事后必须补完整审批记录。

## 7. 循环

```
Observe → Verify → Diagnose → Propose → Test → Evaluate → Approve → Apply → Regression check
```

每一步都必须有证据；单次未验证失败**不得**触发修改。

## 8. 允许修改的目标

- Skill 指令（G1-G2）
- 示例/模板（G2）
- 工作流（G3）
- 评估标准（G4）
- 检索优先级（G2-G3）
- 安全配置的**建议**（仅建议，不自动生效，G5-G6 需人工）

## 9. 禁止自行修改（必须人工审批）

以下任何变更都需要显式的人工批准（除非已有授权策略）：

```
权限规则
安全策略
凭证处理
外部副作用规则
核心 Runtime 行为
```

> 绝不为"提高完成率"而削弱安全。
> 绝不因"减少上下文"而删除有用知识。

## 10. 不允许的行为

- 单次失败 → 立即自我修改
- 削弱安全以换取完成
- 静默覆盖自己之前的策略
- 绕过 Permission Gate 做"修复"
- 自动批准自己的变更
- 一次进化同时改多个 G 级别（跳级）
- 用未分类的 Evidence 直接触发修改（必须先过 Candidate 判定）
- 把 Heartbeat/定时唤醒当作 Evolution 触发条件（evidence-driven, not schedule-driven）

## 10.1 Evolution Anti-Loop（v1.3 强制，防自我制造 Evidence）

> 防止 `Evolution → Regression FAIL → Evidence → 又改 → 又 FAIL` 死循环。
> 关键：**Regression FAIL 产生的 Evidence 只用于回滚决策，不自动成为新 candidate 的输入**；
> 新 candidate 必须来自独立的失败/纠正/观测。

四道闸 + 人工兜底：

| # | 闸 | 规则 |
|:--|:--|:--|
| 1 | Change Cooldown | 同一 target 修改后冷却期（默认 7 天），冷却期内不接受同 target candidate |
| 2 | Same-target Dedup | candidate 入库前按 target+pattern 去重；重复者合并，不新增 |
| 3 | Regression Failure Limit | 同一 change 连续 2 次 Regression FAIL → 自动回滚 + 标记需人工 |
| 4 | Max Evolution Depth | 同一 pattern_key 累计 ≥3 次 change → 停止自动进化，转人工评估 |
| 5 | Manual Escalation | 任一闸触发或 G5-G6 修改 → 人工审批 |

长期监控清单见 `docs/tests/long-running.md`（7d/30d 观察项：candidate 重复、evolution loop、
regression 过期、heartbeat 噪音、stale state、repeated proposal、failed change、rollback、permission drift）。

## 11. 输出

- 变更候选必须有：问题、证据、提议变更、预期影响、回归检查、G 级别、审批路径。
- 高影响变更（G3+）进入 review queue（人工）；低风险指令改进（G1-G2）可走已有授权策略。
- 每次应用后写 Regression check 结果，失败则回滚并记录。

## 12. Agent Scope 隔离（v1.3.1，Multi-Agent 硬规则）

> **Shared Skill ≠ Shared Evolution State。** Skill 是能力可以共享，但进化状态默认按 Agent 隔离。
> 本规则防止“Research 的 self-evolution 自动改掉所有 Agent 的 Shared Skill”。

### 12.1 默认：Evolution State 按 Agent 隔离

```
Agent A
  ↓
自己的 Evidence
  ↓
自己的 Candidate
  ↓
自己的 Proposal
  ↓
只允许影响自己的 Evolution Scope
  ── (Agent-specific State) ──
```

- **Evolution State**（Evidence / Candidate / Proposal / Apply / Change / Regression）默认归属**当前 Agent**。
- **per-agent state 隔离**：即使多个 Agent 共享同一份 Skill 代码，它们的 evolution state 彼此独立
  （对应 `_state_path` per-agent 隔离，见 proactive / self-evolution 实现）。
- 一个候选**默认只能影响自己 Agent 的 scope**，不得自动改动 Shared Skill / 其他 Agent / Agent OS Core。

### 12.2 Cross-Agent / Shared Evolution（必须升级治理）

若一次进化需要影响：

```
Shared Skill         （多个 Agent 共用的 Skill 定义）
Agent B              （其他 Agent 的行为/状态）
Agent OS Core        （协议/权限/验证核心）
```

则不能按“单 Agent 自己改自己”处理，必须升级为 **Cross-Agent / Shared Evolution**：

- 提案必须显式声明 `scope: cross-agent | shared-skill | agent-os-core`。
- 走**更高一级 Governance**：跨 Agent 影响 = 更高风险，审批级别相应升档（G5/G6 或要求多 Agent 相关方
  复核 + 人工显式批准）。
- 禁止：某 Agent 在**本 Agent 内**发现候选后，未经 Cross-Agent 流程就把改动直接应用到 Shared Skill。
- 影响范围超出本 Agent 时，Self-Evolution 只能**产出 Proposal**，不能自行 Apply（Apply 权限是 scope 的）。

### 12.3 Multi-Agent Contract 对齐

对应 PROTOCOL.md §8 的 Contract 项 #10 `Evolution Scope`：默认仅影响自身 Agent（Agent-specific）；
跨 Agent 影响必须升级 Cross-Agent / Shared Evolution 并走更高一级治理。

> 相关审计：MULTI-AGENT-AUDIT-20260820.md（self-evolution 已列为代码强制 scope，且 protected
> target 禁止自改权限/安全/Runtime）。本 §12 把“scope 只影响自身 Agent”明确为文档级硬规则。
