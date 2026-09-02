# Agent OS v1.3 — Running Guide（运行环境配置指南）

> 目的：让**另一台服务器 / 新安装**的人 clone 本文档仓库后，不只复制 `skills/`，还能清楚知道
> **要配置哪些 OpenClaw 环境、各自配成什么样，这套 Agent OS 才能真正跑起来**。
> 本指南只指出"去哪配、配什么"，不重复造 Runtime —— 执行侧始终由 OpenClaw 承担。

---

## 0. 前置确认

- OpenClaw 版本：`2026.8.1` 或更新版本（Agent OS v1.3 目标基线）
- 推荐直接运行 `./install.sh`；它会复制全部 Skills 与共享 `_lib`（见 `docs/INSTALL.md`）
- 装完后用 `openclaw skills list` 确认 11 个 Core Skill 均为 `✓ ready`：
  `proactive / context-orchestration / task-manager / orchestrator / permission-security /
   verification-evaluation / memory-governance / knowledge-governance / ontology /
   self-evolution / summarize`

> 若某个 skill 显示 `disabled`，检查 `openclaw.json` 的 `skills.entries.<name>.enabled`（例如容易误禁 `summarize`）。

---

## 1. 可选环境配置（安装器已处理常用默认值）

以下配置都在 `openclaw.json` 的 `agents.defaults.*` 下。**均非必须**（Agent OS 在对话时也能运行），
但配置后能解锁持续主动性 / 跨 Agent / 跨 Session 记忆能力。

### 1.1 Heartbeat（默认不需要客户手动配置）

现代 OpenClaw 默认启用 Heartbeat；`./install.sh` 的默认 Active profile 仍会显式写入
`30m`，从而避免不同认证方式的默认周期差异。客户无需编辑 `openclaw.json`，也无需
创建 Cron。只有要改变周期或关闭主动性时才需要调整。

```json5
{
  agents: {
    defaults: {
      heartbeat: {
        agentId: "main",  // 多 Agent 时唯一的环境巡检 owner
        every: "10m",     // 推荐：开发/测试 10m；轻量长期运行 30m；低频 1h-2h。0m 关闭。默认 30m
        target: "owner",  // 默认投递给 operator owner；也可选 last / none / channel-id
      },
    },
  },
}
```

- 安装器默认已执行：`openclaw config set agents.defaults.heartbeat.every "30m"`
- 安装器同时设置 `agents.defaults.heartbeat.agentId=main`；用 `--heartbeat-agent <id>` 可改 owner。
- **推荐配置（按主动性需求选）**：
  - 开发/测试/验证期：`10m`（快速反馈，本文档仓库 agent-session-e2e 实测值）
  - 轻量长期运行：`30m`
  - 低频巡检 / 节省调用：`1h` 或 `2h`
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

- 说明：`allowAgents: ["*"]` 表示 Main 可 spawn 到任意 `agents.entries` 中配置过的 agent。
- 目标 Agent 必须真实存在；安装器不自动生成业务 Agent，也不扩大已有委派权限。
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

### 1.4 Skills 注册（确保 Core Skills 被加载）

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
  - `openclaw skills list` → 11 Core Skills 均为 `✓ ready`；默认另含 `agent-os-vault`
  - 手动触发一次 heartbeat 或用 `openclaw config get agents.defaults.heartbeat` 确认运行时已读入

---

## 3. 常见问题（FAQ）

**Q1：Agent OS 需要客户配置 Cron 吗？**
通常不需要。OpenClaw Heartbeat 本身由原生 Automations scheduler 承载，安装器默认启用
Heartbeat。只有"每天 9:00"这类精确时间业务才按用户要求创建独立 Automation；Agent OS
不会预设未知业务日程。

**Q2：装完但 skill 显示 disabled？**
看 `skills.entries` 是否误设为 `enabled:false`（常见误禁 `summarize`）。

**Q3：proactive 不提醒我？**
先确认 `cron.enabled` 没有被客户显式关闭，并重启 Gateway；且 Proactive 只在"有值得处理的事项"才打扰，
无价值时会 NOOP（保持安静）——这是设计，不是故障。

**Q3b：我装完了，为什么 Agent 没有主动找我？**
使用手动复制方式时，**仅安装 Skill 不等于自动获得主动性**；一键安装器已补齐前两项：
① OpenClaw Heartbeat/Cron/Hook（外部 Trigger，§1.1）
② Proactive Skill（决策层，判断值不值得做）
③ 有价值的 Signal（有异常/机会/到期项才提醒）
若使用 `./install.sh` 默认 Active profile，Heartbeat 与运行指令已安装；仍没有提醒通常表示
没有新价值 Signal，或客户显式设置了 `cron.enabled=false`。

**Q4：spawn sub-agent 失败？**
确认 `subagents.allowAgents` 非空、目标 agent 在 `agents.entries` 中真实配置。

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
