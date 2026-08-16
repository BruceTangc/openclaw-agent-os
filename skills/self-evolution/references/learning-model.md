# Self-Evolution 学习模型参考

> 学习分类、作用域、置信度、晋升、矛盾、记忆架构的详细定义。

## 1. 作用域（Scope）

```text
TASK < AGENT < PROJECT < USER < GLOBAL
```

- TASK：仅当前任务/会话有效
- AGENT：仅一个专家 Agent 有效
- PROJECT：参与同一项目的 Agent 共享
- USER：稳定的用户偏好/约束
- GLOBAL：跨 OpenClaw 通用的 Agent 原则

**默认原则**：存最窄有效作用域。更宽作用域需明确证据证明上下文无关。GLOBAL 最难晋升。

## 2. 作用域晋升示例

```text
Agent 发现 → AGENT →（验证）PROJECT →（上下文独立证据）GLOBAL
```

禁止仅因「出现三次」AGENT→GLOBAL。晋升到更宽需证明不依赖本地上下文（工具版本/市场 regime/用户临时偏好/Agent 专精假设）。

## 3. 学习分类

user_preference / user_constraint / project_fact / project_decision / agent_knowledge / tool_knowledge / workflow / behavior_rule / universal_principle / skill_improvement / temporary_context / intermediate_state / noise。

## 4. 学习候选（candidate）结构

```json
{
  "id": "LRN-20260813-001",
  "type": "workflow",
  "scope": "AGENT",
  "source_agent": "example-agent",
  "project": "example-project",
  "content": "...",
  "first_seen": "...",
  "last_seen": "...",
  "recurrence": 1,
  "sessions": [],
  "user_confirmed": false,
  "confidence": 0,
  "effective_confidence": 0,
  "status": "candidate",
  "contradicts": [],
  "supersedes": [],
  "evidence": [],
  "context_dependencies": [],
  "verification": { "required": true, "due": null, "result": null }
}
```

## 5. 置信度标尺

```text
0–30   weak        31–50  tentative   51–70  probable
71–85  strong      86–95  highly reliable  96–100 established
```

三次重复本身不产生高置信全局规则。

## 6. 证据/时间衰减

```text
effective_confidence = base_confidence × recency_factor
                       × evidence_quality × (1 − contradiction_penalty)
```

衰减触发：证据老化无强化、出现更新的矛盾/取代证据、原上下文（工具版本/环境/用户态）已不成立。旧高重复规则不得永久锁死新验证证据。

## 7. 晋升规则

默认：recurrence≥3 ∧ sessions≥2 ∧ 无活跃矛盾 ∧（更宽作用域须上下文独立）。

建议最低有效置信度：

```text
AGENT workflow   >= 70
PROJECT workflow >= 75
USER preference  >= 80
tool knowledge   >= 80
behavior rule    >= 85
GLOBAL principle >= 90
```

明确用户确认可加速，但安全与治理仍适用。

## 8. 矛盾检测与解决

晋升前搜索 Agent/Project/User/Global/Decisions 记忆，检测直接矛盾、部分矛盾、取代、过时、作用域例外。

冲突优先级：1 当前明确用户指令（安全有效）2 更新已验证证据 3 更窄作用域 4 更高有效置信度+更强验证 5 仍无法→Unresolved，阻断自动应用，人工裁决。

不保留无作用域的活跃矛盾规则。

## 9. 作用域解析优先级（指令冲突时）

```text
CURRENT EXPLICIT INSTRUCTION > CURRENT TASK > PROJECT DECISION
> AGENT-SPECIFIC RULE > USER PREFERENCE > GLOBAL PRINCIPLE > GENERIC KNOWLEDGE
```

当前明确用户指令在安全有效时始终优先。

## 10. 决策记忆（Decision）与学习的边界

- Decision = 对未来行动的约束（must do X）
- Learning = 关于世界的知识（X is true）

高置信带行动力的学习可建议升级为 Decision；被证伪的 Decision 产生反向 Learning（可能降级），不只改状态。重要 Decision 须带显式 review condition 或 validity trigger（工具/版本/环境/用户反馈变化）。

## 11. 记忆架构（推荐）

```text
memory/
├── global/        PRINCIPLES.md / KNOWLEDGE.md / DECISIONS.md
├── user/          USER.md / preferences.json
├── projects/<p>/  STATE.md / DECISIONS.md / TASKS.md / LEARNINGS.md
├── agents/<id>/   MEMORY.md / LEARNINGS.md / DECISIONS.md
├── sessions/
├── skills/
├── .learning-trail.json
└── .memory-index.json
```

若现有 OpenClaw 用别的布局，适配既有结构而非盲目复制。

## 12. 遗忘/过时生命周期

```text
0–30 天   active
30–60    decay if unused
60–90    stale
90+      archive unless important/verified
```

例外：明确用户偏好、已验证原则、活跃项目决策、当前工具知识。过时标 `obsolete` + `superseded_by`，保留历史。

## 13. 知识图谱关系

Experience + caused_by / supports / contradicts / supersedes / derived_from / verified_by / used_in / improves / demoted_by / reverted_by。

## 14. 经验检测触发词

correction 例：「不对/错了/实际上应该是/That's wrong」；error：非零退出/异常/超时/连接失败/错误结果；success：更快/更可靠流程；intermediate：near-miss/almost-failure/partial-success/delayed-failure；knowledge_gap：用户提供未知信息/文档过时/工具行为与假设不符。

## 15. 用户偏好持久化判断

临时指令保持 TASK，除非有清晰持久信号：「以后/总是/下次都/永远/always/from now on」、跨独立会话重复、与现有 USER 偏好无强冲突。满足才入 USER candidate，否则 TASK 或 AGENT。
