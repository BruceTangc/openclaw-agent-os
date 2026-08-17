# Installation

## Compatibility
Designed for OpenClaw 2026.7.1-2. Agent OS v1.3（Protocol v1.3；v1.2 Skill 属 legacy compatibility mode，可兼容运行）。

## 5 分钟安装（三分钟到 11 个 Skill ready）

### Step 0 — 确认 OpenClaw
```bash
openclaw --version   # ≥ 2026.7.1-2
```

### Step 1 — 找到你的 Skills 目录
```bash
openclaw skills list --help   # 或看 openclaw.json 的 skills 配置/官方文档
```
不要假设固定路径，使用你安装里实际配置的 skills 目录。

### Step 2 — 复制 11 个 Core Skills
```bash
cp -r skills/*  <你的-skills-目录>/
```

### Step 3 — 安装 AGENTS.md（关键，勿跳过）
Agent OS 的治理/决策/协议全靠 AGENTS.md 注入行为约束；不装它 = 只有 Skill 没有协议层。
```bash
cp AGENTS.md  <你的-openclaw-workspace>/
# 如已存在 AGENTS.md：先备份，再把本仓库 AGENTS.md 的「Agent OS 核心协议」段合并进去
```

### Step 4 — 重载 / 重启
```bash
openclaw gateway restart     # 或按你的安装 reload 方式
```

### Step 5 — 验证
```bash
openclaw skills list | grep -c "✓ ready"    # 应 ≥ 11
```

### Step 6 — 跑 smoke tests
见 [docs/tests/README.md](tests/README.md) 与 [QUICK-START.md](QUICK-START.md)（5 项验收）。

---

## 安装等级（按需选择）

| 等级 | 包含 | 得到 |
|:--|:--|:--|
| **Level 1 — Basic** | 11 Skills + AGENTS.md | 基础治理能力：Fast/Full Path、Permission Gate、Verification、Memory/Knowledge/Ontology、Evolution |
| **Level 2 — Active** | Level 1 + OpenClaw Heartbeat | 主动性：Proactive 决策 + Evolution 巡检 + 长期监控（配置见 RUNNING-GUIDE.md §1.1） |
| **Level 3 — Full** | Level 2 + Memory Search + Sub-agents + Execution Record + Long-running monitoring | 完整 Agent OS：跨 Session 记忆、Multi-Agent 委派、可追溯执行、长期运行验证 |

---

## Upgrade procedure（升级已有安装）
1. Back up existing same-name Skills（及 AGENTS.md 先备份合并）。
2. Replace the Skill directory。
3. Restart/reload the agent runtime。
4. Verify the Skill is discoverable（`openclaw skills list`）。
5. Run the smoke tests。

## Do not install
There is intentionally no scheduler, event bus, memory runtime, context engine, task runtime, agent runtime or permission runtime in this package.