---
name: self-evolution
description: 受控发现重复问题、提出并验证改进、请求批准后应用；绝不自行改权限/安全/Runtime。经验沉淀时触发。
metadata: { "openclaw": { "emoji": "🗂" }, "agent_os": { "protocol_version": "1.3", "layer": "core" } }
version: 1.3.0
---


# Self-Evolution

## Purpose

通过**受控的、有证据的**自我改进循环，把多 Agent 的 OpenClaw 安装变成一个协调的学习系统。核心：`Many Agents, one Learning OS`。循环：`Observe → Verify → Diagnose → Propose → Test → Evaluate → Approve → Apply → Regression check`。

**边界铁律**：只做 `发现问题 → 提出改进 → 验证改进 → 请求批准 → 应用`。**绝不自改权限/安全/凭证/外部副作用规则/Runtime**。

## Scope

- 经验捕获（含中间态 near-miss/almost-failure/partial-success/delayed-failure）
- 学习分类 + 作用域（TASK/AGENT/PROJECT/USER/GLOBAL，默认最窄）
- 置信度 + 证据/时间衰减
- 矛盾检测与解决、降级（demotion）、遗忘（forgetting）
- Agent Registry + Learning Inbox（受控跨 Agent 学习）
- Skill 进化（双向反馈）+ 决策记忆
- 治理（auto-apply / proposal / approval）+ 验证 + 回滚

## Non-Goals

- 不建独立 scheduler / event bus / task runtime / memory runtime / agent runtime（复用 OpenClaw）
- 不单次未验证失败就改自己
- 不削弱安全换完成率
- 不自动批准自己的变更
- 不静默覆盖已有策略

## OpenClaw Boundary

复用 OpenClaw 原生 agent loop / session / memory / files / cron / hooks。**不创建自己的 Scheduler、Event Bus、Task Runtime、Memory Runtime、Agent Runtime**。存储走 workspace 的 memory 文件 + JSONL trail，是学习索引不是并行 runtime。脚本（learn.py/reflect.py/bus.py/agents.py/skillgen.py/dream.py/sync.py/migrate.py）在 `scripts/` 下。

## When to Activate

- 收到 **Evolution Candidate**（来自 verification / evaluation / proactive / 用户反馈）——**主触发**
- Evidence 巡检（learn.py --cycle）：低频扫描近期失败/纠正/低效，
  **Discover + Classify → 产出 Candidate**（巡检可以做分类，但不能做 Evolution Judgment）
  （evolution is evidence-driven, not schedule-driven——巡检不是定时进化）
- 验证到期、晋升检查、遗忘检查、矛盾检测
- 需要生成 Skill 改进提案 / 决策记忆 / 降级 / 回滚
- 多 Agent 场景：各 Agent 上报 Learning Ledger，Global Cycle 聚合

> **进料边界（v1.3）**：本 Skill 只消费 **Evolution Candidate**，不直接接受任意 Evidence。
> 原始 Evidence（一次失败/纠正/观测）必须先过 Classification，判定“有进化价值”才成为 Candidate。

## Inputs

- 经验事件（correction/error/success/intermediate_state/feature_request/knowledge_gap）
- 来源 agent、scope、confidence、evidence
- 已有 learning trail、Agent Registry、Learning Ledger pending 事件

## Core Procedure

本 Skill 只负责生命周期末尾的 **Evolution（进化）** 节点：受控地判断“是否值得改变系统、改变什么”。
系统其余节点由其他 Skill 承担，本 Skill 不跑完整 loop。

0. **Gate（进料判定）**：只接受 Evolution Candidate；原始 Evidence 先分类——
   有进化价值（重复失败/重复纠正/稳定新需求/流程低效/系统性漏洞/用户明确要求）→ 进；
   一次性/噪音/无复用价值 → 拒（不触发修改）。
1. **Obtain（捕获）**：收经验（含中间态），先入 candidate，不当作真理。
2. **Detect（检测）**：correction/error/success/intermediate/feature/knowledge_gap。
3. **Classify（分类）**：user_preference / user_constraint / project_fact / project_decision / agent_knowledge / tool_knowledge / workflow / behavior_rule / universal_principle / skill_improvement / temporary_context / intermediate_state / noise。
4. **Scope Resolution（作用域）**：默认最窄（AGENT）；更宽需上下文独立性证据。
5. **Confidence / Decay / Contradiction**：有效置信度 = base × recency × evidence_quality × (1 − contradiction_penalty)。
6. **Govern（治理）**：auto-apply（低风险）/ proposal（行为变更）/ explicit approval（高风险）。
7. **Promote / Demote / Revert / Forget**：按晋升规则；失败/回归 → demote 或 revert。
8. **Apply（应用）**：仅限可授权变更；安全/权限/凭证/外部副作用/Runtime → 人工审批。
9. **Regression check（回归检查）**：验证前后 metric 对比，失败回滚。

完整循环 10 Phase 见 `references/learning-cycle.md`。

## Decision Rules

**进料（v1.3）**：只接受 Evolution Candidate；Evidence 必须先过 Classification（见 Core Procedure Gate）。

**允许的进化证据**：已验证失败、重复用户纠正、重复评估弱点、反复低效、稳定新需求、Verification 系统性漏洞、用户明确要求改进。**单次未验证失败不得触发修改**。

**允许修改目标**：Skill 指令、工作流、评估标准、检索优先级、安全配置的**建议**（仅建议）。

**禁止自行修改（须人工审批）**：权限规则、安全策略、凭证处理、外部副作用规则、核心 Runtime 行为。**绝不为提高完成率削弱安全；绝不因减少上下文删除有用知识。**

**作用域晋升**：recurrence≥3 ∧ sessions≥2 ∧ 无活跃矛盾 ∧（更宽作用域须上下文独立证明）。默认窄作用域最优；GLOBAL 最难晋升，需独立证据证明上下文无关。

**冲突解决优先级**：1 当前明确用户指令（安全有效时）2 更新的已验证证据 3 更窄作用域 4 更高有效置信度+更强验证 5 仍无法→标 Unresolved，阻断自动应用，人工裁决。

**降级**：GLOBAL→PROJECT / PROJECT→AGENT（发现上下文依赖时），降级优于删除（更窄仍有用）。

**禁止**：发明记忆/决策、单次错误升原则、广播全部学习、覆盖他人私有记忆、静默改用户偏好/全局策略、建重复 Agent/Skill、忽略矛盾、无证据声称验证、存 Secret、用 exec 读 session 文件、不 read 就 edit。

## Outputs

- learning trail 条目（candidate/promoted/demoted/reverted/expired）
- 提案（PROP-xxx：type/source/target scope/target/change/evidence/confidence/risk/impact/rollback/status）
- 验证结果（baseline/metric/review/result/action）
- 最终 summary（Entries/Changes/Verified/Promoted/Graph/Actions）

## Interaction With Agent OS

- 消耗 **proactive/orchestrator/task-manager** 上报的经验与指标，产出改进候选反哺。
- 发现新概念/实体/关系 → 创建 **ontology** Proposal（不静默改本体）。
- 经验记忆 → 走 **memory-governance**；可复用声明 → **knowledge-governance**。
- 高置信带约束学习 → 建议升级为 Decision。
- Skill 改变需过 **permission-security**（安全类）与 **verification-evaluation**（回归）。

## Permission

记录学习/低风险私有记忆 = L1 可自动。行为变更/共享记忆/降级（已晋升规则）= proposal。权限/凭证/外部通信/财务/删除/安全设置/自动交易/系统级/全局策略变更 = **显式人工审批**。遵守 OpenClaw native policy。

## Verification

- 每次重要晋升/降级/Skill 变更须带 baseline + metric + review period + result + action。
- 动态验证期：低风险 3 天 / 正常 7 天 / 重要行为 14 天 / 核心架构 30 天。
- PROJECT/GLOBAL 晋升须跨 Agent 验证（源 + 至少一个相关 Agent），防止专家错误变全局规则。

## Failure Handling

- 单次失败 → 记录，不修改。
- 连续验证失败 → status=blocked_learning，需人工复核，不自动再晋升。
- 变更导致回归/拒绝/工具失败/安全风险/指标变差 → 标记失败 + 回滚或降级 + 记因 + 降置信度 + 阻断同类自动晋升。

## Memory / Knowledge Writeback

学习候选先入 candidate → 验证 → 晋升到 durable；决策入 DECISIONS.md；用户偏好入 USER；项目事实入 PROJECT。经验与知识走 governance，不裸写。会话总结走 sessions。

## Self-Evolution Feedback

本模块是进化层本身：双向反馈——Skill 执行结果反哺学习置信度/重分类；学习变化触发 Skill 复用/改进/合并/新建决策。矛盾/降级通过 Learning Inbox 反向通知相关 Agent。

## Safety / Anti-Loop

- **只做**：发现问题→提出改进→验证改进→请求批准→应用。
- **绝不自己做**：改权限/安全/凭证/外部副作用规则/Runtime（必须人工审批）。
- **单次未验证失败不触发修改**；**不为提高完成率削弱安全**。
- 不自动批准自己的变更；不绕过 Permission Gate 做「修复」。
- Anti-loop：同学习反复失败 → blocked_learning，停止自动晋升。
- **硬规则（v1.3，简版，与 EVOLUTION-PROTOCOL.md §10.1 一致）**：
  - Change Cooldown：同一 target 修改后冷却 7 天，冷却期内不收同 target candidate。
  - Same-target Dedup：candidate 入库前按 target+pattern 去重，重复合并不新增。
  - Regression Failure Limit：同一 change 连续 2 次回归 FAIL → 自动回滚 + 标需人工。
  - Max Evolution Depth：同一 pattern_key 累计 ≥3 次 change → 停止自动进化，转人工。
  - **Regression FAIL 产生的 Evidence 只用于回滚决策，不得自动成为新 candidate 输入**（防止 Evolution 制造 Evidence 死循环）。
- Anti-overfit：先问「一般?项目特有?Agent 特有?工具特有?用户特有?临时?上下文依赖?」，存最窄有效作用域。
- 不建自己的 Scheduler/Event Bus/Task/Memory/Agent Runtime；复用 OpenClaw 原生。

## Examples

```bash
python3 scripts/learn.py --cycle                              # 完整学习循环（10 Phase）
python3 scripts/learn.py --status                            # 学习统计
python3 scripts/learn.py --log error "行情 API 超时未重试"
python3 scripts/learn.py --add-change skillgen "增加 --approve" "降低误装风险"
python3 scripts/learn.py --add-principle "编辑文件前必须先读取当前内容"
python3 scripts/learn.py --rollback <change_id>
python3 scripts/learn.py --demote <entry_id> --to AGENT
python3 scripts/bus.py --central --event learning_candidate --topic "..." --content "..." --scope AGENT --agent 厂长 --confidence 85
python3 scripts/skillgen.py --scan && python3 scripts/skillgen.py --approve <name>
```

详细模型（分类/置信度/晋升/矛盾/记忆架构/治理/生命周期）见 `references/learning-model.md`、`references/governance-model.md`、`references/agents-and-bus.md`。全局学习循环 10 Phase 见 `references/learning-cycle.md`。
