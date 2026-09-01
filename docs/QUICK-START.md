# Quick Start — 5 分钟安装 + 验收

> Agent OS v1.3。真正装完、并且**确认装成功了**的最小路径。
> 装完跑一遍下面的 5 个问题，全过 = 你的 OpenClaw 已经是 Agent OS。

## 一键安装

```bash
./install.sh
```

它会安装 11 Core Skills、`agent-os-vault` 扩展、共享 `_lib`、运行时 AGENTS/Heartbeat
模板，自动配置 OpenClaw 原生 Heartbeat 并重启验证；不会创建业务 Cron。

> 详细分级安装见 [INSTALL.md](INSTALL.md)（Basic / Active / Full 三级）。

---

## 验收：5 个问题

### ① 我装对了吗？
```bash
openclaw skills list | grep -c "✓ ready"
```
应至少包含 11 Core：`proactive / context-orchestration / task-manager / orchestrator /
permission-security / verification-evaluation / memory-governance /
knowledge-governance / ontology / self-evolution / summarize`；默认安装还包含
`agent-os-vault`。

### ② Agent OS 生效了吗？（Goal + Verification）
给 Agent 发：

> "总结这段文本，并告诉我成功条件和验证证据。"

正常响应应体现：
- **Goal/Task Semantics**：明确"总结出 X，成功条件 = 结构完整 + 关键事实无遗漏"
- **Verification**：给出证据（"已提取 5 个关键点，源文对照无遗漏"）
- 没有这两个 → 协议层没生效，检查 AGENTS.md 是否已装。

### ③ Permission 生效了吗？
分别要求：
- 读操作（`read` 一个文件）→ 应直接执行（L0 自动 ALLOW）
- 发送操作（如 `send` 到外部渠道）→ 应触发确认/权限门（L2 ASK）
- 都直接执行、没有权限门 → 检查 permission-security 是否 ready。

### ④ Proactive 生效了吗？
手动触发一次 heartbeat（或等下一次自动唤醒）：
```bash
openclaw config get agents.entries.main.heartbeat.every  # 默认 owner=main 时为 30m
openclaw config get agents.entries.main.heartbeat.prompt # 应包含 proactive.py heartbeat
```
正常：有事件 → 提醒；无事件 → `HEARTBEAT_OK` / 安静。
一键安装已配置 Heartbeat + Proactive；客户无需另建 Cron。没有提醒通常表示当前没有
新价值 Signal（见 [RUNNING-GUIDE.md](RUNNING-GUIDE.md) §1.1 与 FAQ Q3b）。

### ⑤ Evolution 生效了吗？
构造一次可复现的重复失败（如让一个检查脚本两次漏同一项），然后：
```bash
python3 skills/self-evolution/scripts/discover.py --evidence \
    '{"class":"verification","scope":"skill","target":"<skill.md>","pattern_key":"demo-xxx","problem":"重复漏项","recurrence":3,"sessions":2,"independent_sources":2,"systemic":true,"confidence":0.8,"evidence_refs":["e1","e2","e3"]}'
python3 skills/self-evolution/scripts/discover.py --status   # 查看候选
```
预期：单次失败 → 不会晋升（安全阀）；≥3 次 recurrence 且跨 ≥2 session → 出现 candidate，走 Diagnose → Propose → Governance → Apply → Regression。
> 安全阀：recurrence < 3 或 sessions < 2 均不晋升（详见 self-evolution/references/candidate-policy.md）。
> 完整 E2E：`skills/self-evolution/scripts/self_test.py`（24 断言，回归自测）。

---

## 装完你会得到什么（对照表）

| 能力 | 对应模块 | 怎么触发 |
|:--|:--|:--|
| Fast Path / Full Path | 协议层（PROTOCOL.md） | 按任务复杂度自动分流 |
| Permission Gate（L0-L4） | permission-security | 所有动作前 |
| Verification（V0-V4） | verification-evaluation | 后果性任务 |
| Memory / Knowledge / Ontology | 三个认知模块 | writeback 时 |
| Proactive（主动决策） | proactive | Heartbeat 唤醒时 |
| Evolution（受控改进） | self-evolution | 有证据的重复失败 |

验证后的可复用成功/失败模式由 Runtime 指令统一送入 `proactive/scripts/learning.py`：
Evidence 自动登记；满足重复与跨 Session 门槛后自动生成 Evolution Candidate；合格的
daily/durable memory 自动写回。共享知识、Evolution Apply、删除与 Obsidian 反向导入不会自动批准。

## 下一步

- 看 11 个 Skill 怎么协作 → [SKILL-MAP.md](SKILL-MAP.md)
- 让 Agent 主动 → [RUNNING-GUIDE.md](RUNNING-GUIDE.md) §1.1
- 接自己的业务 Skill → [SKILL-INTEGRATION.md](SKILL-INTEGRATION.md)
- 高级：协议 / Execution Record / 长期运行 → [PROTOCOL.md](PROTOCOL.md)、
  [schemas/execution-record.md](schemas/execution-record.md)、[tests/long-running.md](tests/long-running.md)
