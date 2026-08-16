# SETUP-MULTI-AGENT.md — self-evolution 多 Agent 接入指南

> ⚠️ 本文档早期内容沿用旧模块名 `self-improvement-llm`；现统一为 **`self-evolution`**
> （Agent OS v1.2 模块名）。下文中 `self-improvement` / `self-improvement-llm` 均指代同一个 skill。
>
> **边界声明**：本文件描述的"多机共享学习引擎（symlink）"属于 **治理/学习层的共享**，
> 不是并行 Agent runtime 或多 Agent 编排 runtime。真正的跨 Agent 权限委托/记忆作用域
> 见 `ACTION-PROTOCOL.md` "Multi-Agent 权限委托" 与 `MEMORY-PROTOCOL.md` §1.1。
> Agent OS 仍遵守"不建 7 类 Runtime"的硬边界（见 PROTOCOL.md）。

> 目标：把 `self-evolution`（V3.2 multi-agent learning engine）从"单 Agent 学习框架"升级成
> 真正覆盖多个 Agent 工作区的统一学习系统。本文件面向**新的一台 OpenClaw 机器**接入时使用。

---

## 一、仓库同步了什么

从本仓库 `self-improvement/` 拉下来的内容：

| 部分 | 说明 | 能否直接使用 |
|:---|:---|:---:|
| `scripts/*.py` | 学习引擎（learn.py）、Learning Bus（bus.py）、Agent 注册（agents.py）、Dream 蒸馏（dream.py）等 | ✅ 零第三方依赖，纯标准库 |
| `SKILL.md` / `_meta.json` / `skill-card.md` | skill 本体定义 | ✅ |
| `references/` | 反思框架等参考资料 | ✅ |

> 注意：仓库只同步**代码**，不同步 `memory/` 运行数据（`.learning-trail.json`、
> `agents/registry.json`、`agents/bus.json` 等）。每台机器各建各的，互不共享。

---

## 二、最小启动步骤（新机器）

```bash
# 1. 把 skill 放到主工作区 skills/ 下
mkdir -p ~/.openclaw/workspace/skills
cp -r self-improvement ~/.openclaw/workspace/skills/self-improvement-llm

# 2. 初始化 memory 结构（脚本会自动建目录和默认数据）
cd ~/.openclaw/workspace/skills/self-improvement-llm
python3 scripts/learn.py --build-index      # 建记忆索引
python3 scripts/learn.py --status           # 确认能跑

# 3. 验证 Learning Bus 可用
python3 scripts/bus.py --status

# 4. 跑一次完整学习循环（含 Phase 0 聚合中央 Bus）
python3 scripts/learn.py --cycle
```

`learn.py` 的路径解析：优先读环境变量 `OPENCLAW_WORKSPACE` / `OPENCLAW_WORKSPACE_DIR`，
都没有则用 `~/.openclaw/workspace`。**不硬编码具体机器路径**，所以换机器照常。

---

## 三、启用多 Agent 上报

核心思路：**不给每个 Agent 装一套 skill**，而是共享同一份代码 + 统一写中央 Bus。
Agent 工作区命名约定：`workspace-<agent名>`（OpenClaw 多 Agent 标准布局）。

### 3.1 共享代码（symlink，沿用工作区惯例）

```bash
# 假设主工作区已装好 self-improvement-llm，为每个 Agent 建 symlink
for w in <agent名1> <agent名2>; do
  ln -s ~/.openclaw/workspace/skills/self-improvement-llm \
        ~/.openclaw/workspace-$w/skills/self-improvement-llm
done
```

### 3.2 上报走中央 Bus（关键：--central）

各 Agent 上报时必须带 `--central`，强制写主工作区的中央 Bus：

```bash
cd ~/.openclaw/workspace-<agent名>
python3 skills/self-improvement-llm/scripts/bus.py --central \
  --topic "<主题>" \
  --content "<经验内容>" \
  --scope AGENT --agent <agent名> --confidence 85
```

- `--central` 会把事件写入 `~/.openclaw/workspace/memory/agents/bus.json`（单一事实源）
- 不带 `--central` 会写各 Agent 自己的工作区，中央引擎看不到，等于白报
- scope 可选：TASK | AGENT | PROJECT | USER | GLOBAL，默认 AGENT

### 3.3 给每个 Agent 的 AGENTS.md 加上报 Hook

在每个 Agent 的 `AGENTS.md` 里加一段：
任务收尾/踩坑/验证经验后，用上面 3.2 的命令上报。只报有验证价值的经验，
避免刷屏污染全局学习。

### 3.4 全局学习引擎自动聚合

`learn.py --cycle` 内置 **Phase 0: Aggregate Learning Bus**，会自动：
读取中央 Bus → 去重 → 写入 learning trail（source=external 初始不信任，防记忆污染）→ 事件标记 resolved。

定时任务（cron）直接跑 `--cycle` 即可，**不需要单独改 cron**。

---

## 四、日常使用速查

```bash
# 学习引擎
python3 scripts/learn.py --cycle            # 完整学习循环（含 Bus 聚合）
python3 scripts/learn.py --status           # 学习统计
python3 scripts/learn.py --build-index      # 重建记忆索引
python3 scripts/learn.py --promote          # 检查可晋升模式

# Learning Bus
python3 scripts/bus.py --status             # 总线状态（pending/resolved）
python3 scripts/bus.py --pending            # 待处理事件
python3 scripts/bus.py --central --status   # 中央 Bus 状态（多 Agent 场景必带 --central）

# Agent 注册
python3 scripts/agents.py --list            # 列出所有 Agent 工作区
python3 scripts/agents.py --status          # 各 Agent 状态
```

---

## 五、已知边界与提醒

1. **运行数据不共享**：memory/ 状态（trail、registry、bus）各机器独立，别误提交。
2. **source=external 初始不信任**：Bus 上报的经验默认 `trusted=False`，这是防记忆污染的
   设计，不是 bug。验证后（重复出现 / 用户确认）会自然晋升。
3. **没有流量先别堆架构**：先让各 Agent 真实上报几周，看中央 Bus 有没有有效内容，
   再决定要不要加 Registry 元数据（last_scan / pending_events 等）。
4. **版本一致性**：改动 `bus.py --central` / `learn.py Phase 0` 等核心逻辑后，
   记得同步回本仓库，避免多台机器逻辑分叉。
