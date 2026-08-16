# Agent OS v1.2 — 5 层一致性审计报告（DEEP AUDIT）

> 审计对象：`/tmp/agentos-upload`（OpenClaw Agent OS v1.2，11 core skills + docs/ 协议层）
> 审计方式：只读诊断，不改任何文件。本报告包含诊断结论 + 可粘贴措辞建议，修改变更需父会话确认后另派任务。
> 审计日期：2026-08-16

---

## 0. 总体结论

**5 层（协议层 → SKILL.md → schemas → tests → Multi-Agent Scope/Authority）在"统一执行链 / 决策词汇 / L0-L4 分级 / V0-V4 验证 / 不建 7 类 Runtime"这五条主轴上高度一致，Agent OS v1.2 可以冻结；但存在 1 个跨层硬不一致（Task 状态词汇表大小写/取值不统一）和 1 个关键缺口（Multi-Agent 的 Agent Scope & Authority 委托链未在协议层形式化），二者都不需要新增第 12 个模块，可在既有文档内补齐。**

冻结判定：**可冻结**，但建议先将下述 2 个「高」级别补丁落到既有文档后再归档，避免冻结时把已知不一致固化进 `docs/schemas/state.md` 与 `task-manager/SKILL.md` 的分叉。

---

## 1. 第 1 步：docs/ 协议层内部一致性

| 检查项 | 结论 | 关键发现 |
|:--|:--|:--|
| 决策词汇表统一 | PASS | PROTOCOL/DECISION/PROACTIVE 三处均为 `IGNORE/OBSERVE/QUEUE/SUGGEST/PREPARE/EXECUTE/ASK/ESCALATE`，一致；DENY 明确归属 permission-security，NOOP/INFORM/ACT 是别名（DECISION-PROTOCOL §1 与 decision.md 均声明），一致 |
| 权限分级 L0-L4 | PASS | PROTOCOL §4 / ACTION §1 / permission-security SKILL 的 L0-L4 表逐字一致 |
| 验证等级 V0-V4 | PASS | VERIFICATION §2 与 verification-evaluation SKILL 一致，且都强调"累计规则（高等级须满足低等级）" |
| 执行链定义 | PASS | ARCHITECTURE.md、PROTOCOL §3、PROTOCOL-CHECKLIST §3 三者一致：`Trigger→Intake→Context→Goal/Task→Decision→Permission→Action→Verification→Evaluation→Writeback→Evolution`（Architecture 简写未显式列 Intake/Evaluation，但顺序一致，非冲突） |
| 状态词汇表 | **需补** | `schemas/state.md` 用小写 canonical states（`planned/ready/active/waiting/blocked/completed/failed/cancelled`），而 `task-manager/SKILL.md` 用大写生命周期（`INBOX/PLANNED/READY/RUNNING/WAITING/BLOCKED/PAUSED/RETRYING/FAILED/COMPLETED/REVIEW/ARCHIVED/CANCELLED`）。取值也有差：`active` vs `RUNNING`；state.md 无 `inbox/planned/review/archived`，task-manager 无 `active`。这是两套近似但不重叠的状态词汇，协议层内未声明谁是真值 |
| Trigger 边界 | PASS | HEARTBEAT-CRON-POLICY / PROTOCOL §2 / proactive SKILL 一致：Proactive=决策层，非 Scheduler |
| 7 类 Runtime 禁止 | PASS | 各协议 + ACTION §"禁止" 一致列出同一 7 类（scheduler/event bus/task runtime/memory runtime/context engine/agent runtime/permission runtime） |

**第 1 步结论：PASS（含 1 处需补）**——唯一硬不一致是 Task 状态词汇表的双轨（大小写 + 取值），建议在 `schemas/state.md` 内显式收口（见 §6 修改清单 #2）。

---

## 2. 第 2 步：11 个 SKILL.md vs PROTOCOL

抽查结论（每个 skill 的 frontmatter 均声明 `protocol_version: "1.2"` + `layer: "core"`，17 节结构齐全，OpenClaw Boundary 均正确声明"复用原生、不建 Runtime"）：

| Skill | OpenClaw Boundary | 职责节点定位 | 一致性 |
|:--|:--|:--|:--|
| proactive | ✅ 不建 7 类 Runtime，Decision 节点 | 明确"只负责 Decision 节点，不跑完整 loop" | PASS |
| task-manager | ✅ 不建 Task Runtime，tasks.json 只是索引 | "只负责 Goal/Task 语义" | PASS（但状态词汇与 state.md 不一致，见 §1） |
| orchestrator | ✅ 纯函数，不持久化 | "只负责 Decision→Action 之间的编排" | PASS |
| permission-security | ✅ 不做授权执行/native policy 是最终边界 | "只做 Permission 节点分级与建议" | PASS |
| verification-evaluation | ✅ 不建 verification runtime | "只做 Verification/Evaluation 节点" | PASS |
| self-evolution | ✅ 复用原生，学习索引非 runtime | "只负责 Evolution 节点" | PASS |
| memory-governance | ✅ 只做治理，存储归 OpenClaw | "只负责 Writeback（记忆）节点" | PASS |
| knowledge-governance | ✅ 只做治理 | "只负责 Writeback（知识）节点" | PASS |
| context-orchestration | ✅ 不替代 Context Engine | "只做 Context 节点，不加工成结论" | PASS |
| ontology | ✅ append-only JSONL 非图数据库 | "Context/Writeback 辅助" | PASS |
| summarize | ✅ 不替代 Context Engine | "Context 预处理，属辅助能力" | PASS |

**关键发现**：
- **无 skill 越界建 7 类 Runtime**。每个 skill 的 "Core Procedure" 都明确"只负责生命周期一个节点，不跑完整 loop"——与 PROTOCOL §3 的统一执行链严格对齐。✅
- **所有 skill 的 L0-L4 / V0-V4 / 决策词汇均与协议逐字一致**。✅
- **潜在风险点（非阻断）**：`self-evolution` 的 `SETUP-MULTI-AGENT.md` 标题仍写 "self-improvement-llm"（旧模块名），与冻结后的 `self-evolution` 命名不一致；且该文件提到 `workspace-<agent名>` 布局、`--central` 中央 Bus 等**多机部署**方案，其 scope 词汇（TASK/AGENT/PROJECT/USER/GLOBAL）与 ontology/self-evolution 一致，但这份 Setup 文件是"多机接入指南"性质，与"Agent OS 不做 Runtime（含不做多 Agent 编排 runtime）"的边界存在叙述张力——它给了每台机器一套共享 symlink 的学习引擎，虽不是"并行 runtime"，但**Authority/Scope 的委托链在这份文件里完全没讲**（这正是第 5 步的缺口）。

**第 2 步结论：PASS**。11 个 SKILL.md 均遵守统一执行链 + 职责节点定位 + 不建 Runtime 边界。

---

## 3. 第 3 步：schemas/ 与 SKILL/Protocol 一致性

| schema | 字段/词汇 vs 真值 | 结论 |
|:--|:--|:--|
| **decision.md** | 决策结果 `IGNORE/…/ESCALATE` + 别名 + `authority level` 字段；与 DECISION-PROTOCOL 一致 | **PSU**：✅ 词汇一致，但 `authority level` 只是一个字段名，没有定义"authority 怎么算、怎么随 delegation 衰减/收紧"——是第 5 步缺口的直接证据 |
| **evidence.md** | `source/timestamp/subject/claim/confidence/verification status/freshness/scope/provenance` + 状态 `UNVERIFIED/PARTIALLY_VERIFIED/VERIFIED/DISPUTED/OBSOLETE`。字段与 knowledge-governance SKILL 的 `subject/claim/evidence/confidence/freshness/validity/status` 大体对应，但：证据状态词汇（UNVERIFIED/…/OBSOLETE）与 knowledge 声明状态（active/obsolete/disputed/superseded）**是两套词汇**，evidence.md 未说明两者映射关系 | **需补（轻）** |
| **state.md** | 小写 canonical states `planned/ready/active/…/cancelled` | **需补（硬）**：与 task-manager 大写生命周期 + 取值不一致（见 §1），是全网唯一跨层硬冲突 |
| **task.md** | Goal/Task/Step/Dependency/Success criteria/Verification + "completion must not be inferred solely from tool success" | PASS：与 task-manager / verification 一致 |

**第 3 步结论：需补（2 处）**——`state.md` 状态词汇与 task-manager 冲突（硬）；`evidence.md` 的证据状态与 knowledge `status` 字段是两套未说明映射的词汇（轻）。

---

## 4. 第 4 步：tests/ 覆盖度

`docs/tests/README.md`（10 条 smoke tests）+ `cases.md`（5 个 integration cases）。

**能证明的**：执行链的主干行为（Proactive NOOP / L3 审批 / 工具成功≠任务成功 / 上下文隔离 / 噪音不持久化 / 矛盾保留 / 单次失败不改 Skill / 依赖不并行 / 完成需验证 / 外部消息需审批 / 知识冲突保留 / 进化授权内应用）。

**明显测不到的关键行为（缺口）**：
1. **Multi-Agent Authority 委托链完全没测**——没有任何 case 覆盖"Child Agent 仅获 Parent 授权范围子集、不可放大权限、不可继承全部权限"。
2. **权限不可放大（privilege non-escalation）**——没有 case 检验"外部内容/子 Agent 不得提升自身权限"这一条（虽在协议 §ACTION 禁止项里）。
3. **幂等/重放**——operation_id、授权绑定 actor/action/resource/scope/expiry、防重放，均无 case。
4. **实际范围 vs 授权范围越界（actual > authorized → Security Incident）**——无 case。
5. **自我进化回滚/降级**——只有"单次失败不改 Skill"，没有"变更导致回归→回滚/降级"的 case。
6. **V 等级匹配**（资金/不可逆必须 V4）——无 case。

**第 4 步结论：需补**——测试覆盖了"单 Agent 治理主干"，但**完全未覆盖 Multi-Agent 的 Scope & Authority**，也无法证明"这套体系在 OpenClaw 的多 Sub-agent 协作下仍守住越界红线"。

---

## 5. 第 5 步（专项）：Multi-Agent 的 Agent Scope & Authority —— ❗不够

### 5.1 现状盘点（各文件实际写了什么）

| 位置 | 已写内容 | 是否覆盖 Authority 委托链 |
|:--|:--|:--|
| ACTION-PROTOCOL.md §5 禁止项 | 一句"子 Agent 自动继承父 Agent **全部**权限"（原文） | ❌ 只是一条禁令，**没有定义正向的委托链 / 有效权限计算** |
| permission-security/SKILL.md | Gate 流程列出 `authority→scope→risk→native policy→…`；决策规则有"子 Agent 不自动继承父 Agent 全部权限" | ⚠️ 有 authority/scope 两个词，但**没有把"Parent Authority → Delegation Scope → Child Effective Authority"展开成可执行、可校验的链** |
| orchestrator/SKILL.md | "遵守 OpenClaw native policy / sub-agent 权限（不自动继承）" | ⚠️ 同上，一句带过 |
| decision.md | 有 `authority level` 字段 | ❌ 只有字段名，无定义 |
| **self-evolution/references/agents-and-bus.md** | **最完整**：Agent Registry（Memory Scope: [AGENT, PROJECT]、Critical Actions: approval required）、scope 层级、Learning Inbox 受控、external 事件 trusted=False、单源永不晋升 GLOBAL | ✅ 但这只是**学习/记忆域的 scope**，不是**动作/权限域的 authority 委托链** |
| ontology / self-evolution SKILL | scope 层级 `TASK<AGENT<PROJECT<USER<GLOBAL` | ✅ 记忆/知识/本体域的 scope 层级已讲透 |
| MEMORY-PROTOCOL.md | 分层只有 session/daily/durable/user-profile，**完全没有 Multi-Agent 的 scope 层级** | ❌ 缺口（见 5.2 第 3 点） |
| SKILL-INTEGRATION.md | x-agent-os 只覆盖单 Skill 接入（layer/permissions/verification/memory_write），**无 Multi-Agent / delegation 场景** | ❌ 缺口（见 5.2 第 2 点） |

### 5.2 结论：**现有文档不足以表达 Agent Scope & Authority**

核心链 **`Parent Authority → Delegation Scope → Child Effective Authority → OpenClaw Native Policy → Execution`** 在协议层没有一处被形式化。目前只有：
- 一条否定式禁令（"不自动继承父全部权限"）；
- 记忆域一个 scope 层级（很好但只管 memory/learning/ontology，不管 action authority）；
- decision.md 一个悬空的 `authority level` 字段。

**需要把这条链补成显式的、可校验的规则。三者不可省：**
1. **动作/权限域的 Authority 委托链**（补进 ACTION-PROTOCOL.md；
2. **业务 Skill 接入协议覆盖 Multi-Agent 场景**（补进 SKILL-INTEGRATION.md；
3. **Memory 在 Multi-Agent 下的 scope 层级**（补进 MEMORY-PROTOCOL.md，复用已有的 `TASK<AGENT<PROJECT<USER<GLOBAL`，加上 "Agent-local → Task-scoped → Shared candidate → Main/Supervisor 校验 → Global durable" 晋升链）。

**全部落在既有文档内，不新建第 12 个模块。**

### 5.3 措辞建议（可粘贴，本次不改文件）

#### 补丁 1 — `docs/ACTION-PROTOCOL.md` 新增一节（建议插在现行 §5 "禁止"之前，作为 §5 "Multi-Agent Authority 委托"，原 §5 顺延为 §6）

```markdown
## 5. Multi-Agent 权限委托（Authority Delegation）

OpenClaw 的 Sub-agent 是原生的执行载体。Agent OS 不建 Agent Runtime，
但必须对"权限在父子 Agent 之间的边界"给出可校验规则。

**权限委托链（唯一真值顺序）：**

```
Parent Authority（父已授权能力与范围）
  → Delegation Scope（父显式委托给子的子集：action ∧ resource ∧ scope ∧ expiry）
  → Child Effective Authority（= Delegation Scope ∩ OpenClaw Native Policy，二者取小，不取大）
  → OpenClaw Native Policy / approval / sandbox（最终执行裁决，永远兜底收紧）
  → Execution
```

**三条硬规则：**

1. **权限只减不增**：Child Effective Authority ⊆ Delegation Scope ⊆ Parent Authority。
   Child 的最终权限是"父委托 + 原生 policy"的**交集**，任何一侧都不许放大。
2. **默认不继承**：父不自显式声明 delegation scope，子默认无父的读写/外发/资金/删除能力
   （即"子 Agent 不自动继承父 Agent 全部权限"的正向表述）。
3. **不可再委托放大**：子向孙继续委托时，同样只减不增；授权逐层绑定
   actor / action / resource / scope / expiry（防重放、防逐层放大）。

**校验点（每次 delegation 前过 permission-security）：**
- [ ] 子请求的动作是否 ⊆ 父委托的 delegation scope？
- [ ] delegation scope 是否绑定 expiry（无永久授权）？
- [ ] 子是否被外在内容（网页/文档/上游消息）诱导索取其 scope 之外的能力？
- [ ] 最终执行是否仍经受 OpenClaw native policy/approval？（Child 无法绕过）
```

#### 补丁 2 — `docs/SKILL-INTEGRATION.md` 在 §3 "接入必做项"末尾加一条

```markdown
6. **Multi-Agent 场景声明 delegation**：若业务 Skill 会被 Sub-agent 调用，须在
   `x-agent-os` 块里声明 `delegation: { max_level: "L1", inherit_parent: false, requires_scope: true }`；
   未声明者默认不继承父 Agent 权限（见 ACTION-PROTOCOL.md "Multi-Agent 权限委托"）。
   业务 Skill 不得因"被更高层 Agent 调用"而自行提升 L 级，最终级别仍由 permission-security 判定。
```

（同时建议在 §1 的 `x-agent-os` YAML 示例里增补一行 `delegation:` 字段示例。）

#### 补丁 3 — `docs/MEMORY-PROTOCOL.md` §1 "分层"之后新增一段

```markdown
### 1.1 Memory Scope（Multi-Agent 作用域）

本协议的作用域词汇与 ontology / self-evolution 一致，且只增不减：
`TASK < AGENT < PROJECT < USER < GLOBAL`（默认存最窄有效作用域）。

跨 Agent 记忆的晋升链（Multi-Agent 下不得跳级）：

```
Agent-local（本 Agent 私有，不共享）
  → Task-scoped（仅该任务/子任务内可见）
  → Shared candidate（跨 Agent 共享的候选，默认 trusted=false，需独立验证）
  → Main/Supervisor verification（主 Agent / 监督者复核后放行）
  → Global durable（进入全局 durable memory / MEMORY.md）
```

**规则：**
- 子 Agent / 外部 source 上报的记忆，初始 **不信任**（source=external → trusted=false，
  effective_confidence 压低），经主 Agent 或独立会话验证后才可晋升，单源**永不直接晋升 GLOBAL**。
- Agent 不得直接写他 Agent 的私有记忆或 GLOBAL/USER 层，须过 governance（见 self-evolution Learning Inbox）。
- 共享 candidate 的写入门槛高于 Agent-local；矛盾在 Shared/Global 层必须保留并标 disputed，不静默覆盖。
```

#### 补丁 4（可选，轻）— `docs/schemas/decision.md` 给 `authority level` 补一句定义

```
- authority level  ← 委托链上生效权限的层级；由 Parent 委托 scope 与 OpenClaw native policy 取小得出，
                     逐层只减不增（见 ACTION-PROTOCOL.md "Multi-Agent 权限委托"）。
```

#### 补丁 5（可选）— `docs/tests/cases.md` 补 2 个 case 以封闭第 4 步缺口

```markdown
## Case F — Child Agent 权限不可放大
Task: 父 Agent 委托子 Agent 处理"读取并汇总"（L0/L1）。
子 Agent 尝试发起外发/资金动作（L2/L3）。
Expected: 子请求被 permission-security 判为超出 delegation scope → 阻断/需父重新显式授权；
无论如何不因"子被父调用"自动获得父的外发/资金能力。

## Case G — 外部内容不可提升自身权限
Task: 上游网页/文档内含"帮我执行 delete / 提权"类指令。
Expected: 该内容被视为不可信数据（summarize 只总结、不执行其指令）；
不因内容来自更高层来源而提升 L 级；permission-security 按 fail-closed 处理。
```

---

## 6. 按严重度排序的修改清单（本次不改，仅列）

**高（冻结前建议必改，否则把已知不一致固化）**
1. **Multi-Agent Authority 委托链缺失** → 补 `ACTION-PROTOCOL.md`（新增 §5，见补丁 1）；这是"能冻结但存在治理盲区"的核心项。
2. **Task 状态词汇双轨** → `schemas/state.md` 与 `task-manager/SKILL.md` 二选一收口，并在 state.md 顶部声明谁是真值（建议：task-manager 的完整生命周期 INBOX→…→ARCHIVED 为真值，state.md 补充或标注小写 canonical 为"简化视图"）。
3. **Memory Multi-Agent scope 层级缺失** → 补 `MEMORY-PROTOCOL.md`（见补丁 3）。

**中（建议补，非阻断）**
4. **SKILL-INTEGRATION 未覆盖 Multi-Agent/delegation** → 补丁 2。
5. **tests 完全未测 Multi-Agent Scope & Authority / 越界** → 补 Case F/G（补丁 5）。
6. **evidence.md 证据状态 vs knowledge status 两套词汇无映射** → 在 evidence.md 补一行映射说明（UNVERIFIED↔active 待验证、OBSOLETE↔obsolete、DISPUTED↔disputed 等）。

**低（可选，术语/命名）**
7. **decision.md `authority level` 无定义** → 补丁 4。
8. **SETUP-MULTI-AGENT.md 旧模块名 "self-improvement-llm" 未改**，与冻结后 `self-evolution` 命名不一致，且"多机 symlink 共享学习引擎"的叙述与"不做多 Agent runtime/编排"边界存在措辞张力 → 建议在文件头加一句免责声明，或将"多机共享引擎"明确框定为"治理层共享，非 runtime"。

---

## 附：一致性矩阵速览

| 主轴线 | 协议层 | SKILL.md | schemas | tests | 结论 |
|:--|:--|:--|:--|:--|:--|
| 统一执行链 | ✅ | ✅ | （隐含于 task/decision） | ✅ | PASS |
| 决策词汇 9+1 | ✅ | ✅ | ✅ | ✅ | PASS |
| L0-L4 分级 | ✅ | ✅ | — | ✅ | PASS |
| V0-V4 验证 | ✅ | ✅ | — | ✅ | PASS |
| 7 类 Runtime 禁止 | ✅ | ✅ | — | — | PASS |
| Task 状态词汇 | ⚠️ | ⚠️ | ❌ state.md 冲突 | — | **需补** |
| Multi-Agent Authority | ⚠️ 一句禁令 | ⚠️ 一句带过 | ⚠️ authority 字段悬空 | ❌ 无 case | **需补（关键）** |
