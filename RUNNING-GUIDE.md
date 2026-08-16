# Agent OS v1.2 — Running Guide（运行环境配置指南）

> 目的：让**另一台服务器 / 新安装**的人 clone 本文档仓库后，不只复制 `skills/`，还能清楚知道
> **要配置哪些 OpenClaw 环境、各自配成什么样，这套 Agent OS 才能真正跑起来**。
> 本指南只指出"去哪配、配什么"，不重复造 Runtime —— 执行侧始终由 OpenClaw 承担。

---

## 0. 前置确认

- OpenClaw 版本：`2026.7.1-2`（Agent OS v1.2 以此为目标基线）
- 复制 `skills/` 下的 11 个目录到你的 OpenClaw skills 目录（见 `docs/INSTALL.md`）
- 装完后用 `openclaw skills list` 确认 11 个 skill 均为 `✓ ready`：
  `proactive / context-orchestration / task-manager / orchestrator / permission-security /
   verification-evaluation / memory-governance / knowledge-governance / ontology /
   self-evolution / summarize`

> 若某个 skill 显示 `disabled`，检查 `openclaw.json` 的 `skills.entries.<name>.enabled`（例如容易误禁 `summarize`）。

---

## 1. 可选环境配置（让 Agent OS 真正"活起来"）

以下配置都在 `openclaw.json` 的 `agents.defaults.*` 下。**均非必须**（Agent OS 在对话时也能运行），
但配置后能解锁持续主动性 / 跨 Agent / 跨 Session 记忆能力。

### 1.1 Heartbeat（解锁 Proactive 持续主动）

让 OpenClaw 周期性唤醒 Agent，Proactive 醒来后判断"有没有值得主动处理的事项"。

```json5
{
  agents: {
    defaults: {
      heartbeat: {
        every: "2h",      // 周期：30m / 1h / 2h；0m 关闭。默认 30m
        target: "last",   // 投递：last(最近渠道) | none(只内部)  | <channel-id>(指定渠道)
      },
    },
  },
}
```

- 配置命令：`openclaw config set agents.defaults.heartbeat.every "2h"`
- 说明：`target: "last"` 会把 heartbeat 唤醒后 Proactive 的主动提醒投递到最近联系过的渠道（如飞书 DM）。
- 详见官方文档 `docs/gateway/heartbeat`。

### 1.2 Sub-agents（解锁 Multi-Agent 委派）

让 Main Agent 能在任务中 spawn 子 Agent（研究/验证/分析等）。

```json5
{
  agents: {
    defaults: {
      subagents: {
        allowAgents: ["*"],   // 允许 spawn 到哪些已配置 agent；["*"]=任意
        maxConcurrent: 8,
        archiveAfterMinutes: 60,
      },
    },
  },
}
```

- 说明：`allowAgents: ["*"]` 表示 Main 可 spawn 到任意 `agents.list[]` 里配置过的 agent。
- 需在 `agents.list[]` 里有实际配置的目标 agent，否则 spawn 会被拒绝（可 `openclaw doctor --fix` 清理失效条目）。
- 权限边界见 `docs/ACTION-PROTOCOL.md` §5（Multi-Agent 权限委托）。

### 1.3 Memory Search（解锁跨 Session 记忆恢复）

让 Agent 能跨 Session 检索持久记忆（例如用户之前说过的默认要求）。

```json5
{
  agents: {
    defaults: {
      memorySearch: {
        enabled: true,
        provider: "none",
        store: { fts: { tokenizer: "trigram" } },
      },
    },
  },
}
```

- 配置命令：`openclaw config set agents.defaults.memorySearch.enabled true`
- 详见官方文档 `reference/memory-config`。

### 1.4 Skills 注册（确保 11 个 skill 被加载）

若某 skill 被误禁用，确认 `skills.entries.<name>.enabled` 为 true：

```json5
{
  skills: { entries: { summarize: { enabled: true } } },
}
```

---

## 2. 修改后如何生效

- 大部分配置 OpenClaw 会**热加载**；`heartbeat` 这类**调度器类**配置建议**重启网关**确保完全生效：
  ```bash
  openclaw gateway restart
  ```
- 重启后验证：
  - `openclaw skills list` → 11 个 `✓ ready`
  - 手动触发一次 heartbeat 或用 `openclaw config get agents.defaults.heartbeat` 确认运行时已读入

---

## 3. 常见问题（FAQ）

**Q1：Agent OS 需要 Cron 吗？**
不需要。Agent OS 是加载在 OpenClaw Agent 上的治理/决策层，不建自己的 scheduler。
对话时即自动参与；持续主动靠 OpenClaw Heartbeat/Cron/事件 等 Trigger 唤醒。

**Q2：装完但 skill 显示 disabled？**
看 `skills.entries` 是否误设为 `enabled:false`（常见误禁 `summarize`）。

**Q3：proactive 不提醒我？**
先确认 heartbeat 已配置（§1.1）并重启；且 Proactive 只在"有值得处理的事项"才打扰，
无价值时会 NOOP（保持安静）——这是设计，不是故障。

**Q4：spawn sub-agent 失败？**
确认 `subagents.allowAgents` 非空、目标 agent 在 `agents.list[]` 里真实配置。

---

## 4. 验证（RAT 精简版）

装完/配完可跑【脚本层验证】确认引擎真的在工作：

```bash
# 11 skill 发现
openclaw skills list | grep -c "✓ ready.*summarize"  # 或其他 core skill

# Task Manager 状态机
python3 skills/task-manager/scripts/task_manager.py stats

# Proactive 决策（无价值→NO_ACTION 正常）
python3 skills/proactive/scripts/proactive.py noop

# Permission 分级
python3 skills/permission-security/scripts/permission.py classify delete
```

逐项完整验收见 会话中的 Agent OS Runtime Acceptance Test（RAT-01~16）。
