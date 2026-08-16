# Self-Evolution Agent 与 Learning Inbox 参考

> Agent Registry、Learning Inbox、跨 Agent 学习、Global Learning Cycle 的多 Agent 部分。

## 1. Agent Registry

维护 `memory/agents/REGISTRY.md`：

```markdown
## Agent: short-term-trader
ID: short-term-trader
Role: A股短线交易
Project: A股模拟交易
Status: active
Skills: [market-data, technical-analysis, paper-trading]
Memory Scope: [AGENT, PROJECT]
Shared Learning: allowed
Critical Actions: approval required
```

回答：有哪些 Agent、干什么、属哪个项目、有哪些 Skill、谁能共享哪些记忆、谁权限高。

## 2. Agent Capability Registry

Agent 记 domain/skills/tools/projects/permissions。新建 Agent 时比对新旧能力，重叠高则判 duplicate/overlapping/specialized variant，不自动再建，生成合并提案。

## 3. Agent 生命周期

```text
PROPOSED → CREATED → ACTIVE → SUSPENDED → DEPRECATED → ARCHIVED
```

过时 Agent：保留决策 + 有用学习 + 标记 Skill + 转移已验证项目知识 + 归档私有记忆 + 仅确认后删重复能力。不静默删历史。

## 4. Learning Inbox（受控跨 Agent 通信）

Agent 上报事件（learning_candidate/correction/error/success/intermediate_state/decision/skill_candidate/verification_result/contradiction/promotion_request/demotion_request/demotion_notification/rollback_request/agent_created/agent_updated/agent_deprecated）。

Learning OS 决定 keep/promote/propose/demote/reject。Agent 不直接写 GLOBAL/USER/他人私有记忆，须过 governance。

```bash
python3 scripts/bus.py --central --event learning_candidate \
  --topic "主题" --content "经验" --scope AGENT --agent 厂长 --confidence 85 --project "项目名"
```

## 5. 跨 Agent 学习 / 相关 Agent 匹配

可共享条件：同项目 或 同工具 或 同领域 或 同工作流 或 明确依赖，且通过上下文独立检查（或显式作用域到匹配上下文）。不广播每一条学习；默认本地直到证明上下文无关。

## 6. 外部事件信任模型（external 事件）

- 聚合进来的 external 事件初始 trusted=False，effective_confidence ≤ 60。
- 至少一次独立验证（同项目其他 Agent 复现 / 后续 session 确认）才提升。
- 单源 external 事件**永不自动晋升 GLOBAL**（代码层 execute_promotion 强制拦截）。
- 多源交叉验证后才可进入晋升候选。

## 7. 降级反向传播

学习降级后经 Bus 发 `demotion_notification` 反向通知相关 Agent，降其本地有效置信度或标记重新评估。

## 8. 多项目冲突

同学习涉多项目且证据矛盾 → 默认各自 PROJECT 范围，禁自动统一 GLOBAL；无法解决标 Unresolved 交人工。

## 9. Bus 事件生命周期

```text
pending → resolved（已聚合进 trail）
pending → rejected（人工/校验拒绝，保留不删）
pending → expired（超时未处理，标记后清理）
重复事件：topic+content 去重，合并 evidence
```

## 10. Agent 创建协议

注册 → 定义 role/project/Skills/memory scope → 对比现有 → 查重复能力 → 定义权限/共享访问 → 初始化私有记忆。不定义 scope 不建 Agent。

## 11. Multi-Agent Status 查询

```bash
python3 scripts/agents.py --list / --status / --capabilities / --overlap
python3 scripts/bus.py --status / --pending
```

## 12. 数据备份与迁移

备份（不含 Secret）：MEMORY/USER/GLOBAL/PROJECTS/AGENTS/SESSIONS/SKILLS/.learning-trail.json/.memory-index.json/DECISIONS。

```bash
python3 scripts/sync.py export <path>
python3 scripts/migrate.py --migrate
```
