# Memory Protocol

> Agent OS v1.3 Core Protocol 之一。什么该成为持久记忆、如何晋升、如何治理。
> OpenClaw 拥有存储/索引/召回 — 本协议只规定治理政策。

## 1. 分层

```
session context   — 会话内，不持久
daily memory      — 日记层，高频更新，可定期清理
durable memory    — 长期记忆（如 MEMORY.md），精选
user-profile      — 用户事实/长期偏好指令
```

### 1.1 Memory Scope（Multi-Agent 作用域）

作用域词汇与 ontology / self-evolution 一致，且**只减不增**：
`TASK < AGENT < PROJECT < USER < GLOBAL`（默认存最窄有效作用域）。

**跨 Agent 记忆晋升链（Multi-Agent 下不得跳级）：**

```
Agent-local（本 Agent 私有，不共享）
  → Task-scoped（仅该任务/子任务内可见）
  → Shared candidate（跨 Agent 共享的候选，默认 trusted=false，需独立验证）
  → Main/Supervisor verification（主 Agent / 监督者复核后放行）
  → Global durable（进入全局 durable memory / MEMORY.md）
```

**规则：**
- 子 Agent / 外部 source 上报的记忆，初始**不信任**（source=external → trusted=false，effective_confidence 压低）；
  经主 Agent 或独立会话验证后才可晋升，单源**永不直接晋升 GLOBAL**。
- Agent 不得直接写其他 Agent 的私有记忆或 GLOBAL/USER 层，须过 governance（见 self-evolution Learning Inbox）。
- 共享 candidate 的写入门槛高于 Agent-local；矛盾在 Shared/Global 层必须保留并标 disputed，不静默覆盖。

## 2. 写入判定（写前问 7 问）

1. 稳定吗？（不是一次性噪音）
2. 以后有用吗？
3. 足够确定吗？
4. 来源可溯吗？
5. 冗余吗？（重复的跳过去）
6. 允许存吗？（Secret/敏感不存）
7. 会过期吗？（易过期的进日记层不进长期）

## 3. 晋升路径

```
observation → candidate → validate → promote → review
```

- 观察 → 候选：出现且有复用价值
- 候选 → 验证：跨多次确认有效
- 验证 → 晋升：写入 durable memory
- 晋升 → 回顾：定期检查是否过时

## 4. 优先级（来源可信度）

```
用户明确事实 > 已验证外部事实 > Agent 推断
```

## 5. 治理规则

- 重要矛盾**保留**，不静默覆盖，直到解决。
- 重复/过时的操作笔记去重、清理。
- 事实与推断分开标记。
- Secret（API key/token/凭证）**绝不写入普通 memory**，只走 secret store。
- 不建并行 memory database/runtime（OpenClaw 拥有存储）。

## 6. 写后检查

- 写入内容是否可溯源？
- 是否与现有条目重复？
- 是否含敏感信息？
- 是否需要回写 ontology/knowledge 做结构化？