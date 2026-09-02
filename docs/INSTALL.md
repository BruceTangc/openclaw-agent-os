# Installation

## Compatibility
Requires OpenClaw 2026.8.1 (OpenClaw 2.0) or newer and Python 3.9 or newer. Agent OS v1.3（Protocol v1.3；v1.2 Skill 属 legacy compatibility mode，可兼容运行）。

## 一键安装（默认 Active，客户无需手配 Heartbeat/Cron）

```bash
./install.sh
```

默认行为：安装全部 Core Skills、共享 `_lib` 和客户运行时 `AGENTS.md`，把维护入口写入
指定 Agent 的 OpenClaw 2.0 原生 Heartbeat prompt，并将周期固定为 `30m`，重启 Gateway 并动态
验证 Skills。升级时会先把旧 Skill-local 状态非破坏性复制到 workspace，逐文件
校验且不删除源；发现目标冲突即停止。不会创建任何业务 Cron。

安装器会从 `agents.entries` 自动选择唯一默认 Agent（或唯一 Agent）。多 Agent roster
没有明确默认 owner 时会安全停止，请显式传 `--heartbeat-agent <id>`，不会擅自创建 `main`。

可选：`--profile basic` 不修改 Heartbeat；`--heartbeat-every 1h` 修改主动巡检周期；
`--heartbeat-agent main` 指定唯一的主巡检 Agent。所有 Agent 共用同一份 Skills，安装器不会
为子 Agent 复制 Skills 或单独开启 Heartbeat。

可选启用 Obsidian：

```bash
./install.sh --vault-dir "/absolute/path/to/Obsidian/Vault"
```

安装器通过 OpenClaw 官方 `env.vars.AGENT_OS_VAULT_DIR` 保存路径。未设置时完全禁用 Vault
维护且不创建默认目录；启用后 Heartbeat 每日只自动执行单向 `export + reconcile`。

## 手动安装

### Step 0 — 确认 OpenClaw
```bash
openclaw --version   # ≥ 2026.8.1
```

### Step 1 — 找到你的 Skills 目录
```bash
openclaw skills list --help   # 或看 openclaw.json 的 skills 配置/官方文档
```
不要假设固定路径，使用你安装里实际配置的 skills 目录。

### Step 2 — 复制 Skills 与共享库
```bash
cp -r skills/*  <你的-skills-目录>/
```

### Step 3 — 安装 AGENTS.md（关键，勿跳过）
Agent OS 的治理/决策/协议全靠 AGENTS.md 注入行为约束；不装它 = 只有 Skill 没有协议层。
```bash
cp templates/AGENTS.runtime.md  <你的-openclaw-workspace>/AGENTS.md
# Heartbeat 不再复制 workspace 文件；安装器写入 agents.defaults.heartbeat.prompt
# 如已存在同名文件：先备份，再按需合并；不要覆盖客户已有个性化规则
# 注：AGENTS.md 保留项目边界、权限与验证要求；代码审查方式按项目风险和用户要求决定
```

### Step 4 — 重载 / 重启
```bash
openclaw gateway restart     # 或按你的安装 reload 方式
```

### Step 5 — 验证
```bash
openclaw skills list                         # 11 Core + 默认 bundled agent-os-vault
```

### Step 6 — 跑 smoke tests
见 [docs/tests/README.md](tests/README.md) 与 [QUICK-START.md](QUICK-START.md)（5 项验收）。

---

## 安装等级（按需选择）

| 等级 | 包含 | 得到 |
|:--|:--|:--|
| **Level 1 — Basic** | Core Skills + `_lib` + Runtime AGENTS.md | 基础治理能力：Fast/Full Path、Permission Gate、Verification、Memory/Knowledge/Ontology、Evolution |
| **Level 2 — Active（安装器默认）** | Level 1 + single-owner OpenClaw Heartbeat prompt | 主动性：Proactive 决策 + Evolution 巡检；无需另建 Cron |
| **Level 3 — Full** | Level 2 + Memory Search + Sub-agents + Execution Record + Long-running monitoring | 完整 Agent OS：跨 Session 记忆、Multi-Agent 委派、可追溯执行、长期运行验证 |

---

## Upgrade procedure（升级已有安装）

再次运行同一条 `./install.sh` 即可。安装器会先迁移旧运行状态，再备份并替换共享
Skill；客户的 `AGENTS.md`、已有 Heartbeat/Automation 配置和各 Agent 私有 workspace 状态不会被整文件覆盖。
迁移冲突或任一 bundled Skill 未 ready 时安装以非零状态退出。

## Do not install
There is intentionally no scheduler, event bus, memory runtime, context engine, task runtime, agent runtime or permission runtime in this package.
