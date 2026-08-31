# Agent OS 开箱即用产品化计划

## 1. 目标体验

默认客户路径：

```bash
./install.sh
```

安装后应获得：

- 11 个 Core Skills、`agent-os-vault` 可选桥接能力和共享 `_lib`；
- 客户运行时 `AGENTS.md` 与 `HEARTBEAT.md`；
- OpenClaw 原生 Heartbeat（默认 `30m`）；
- Task、Proactive、Memory、Ontology、Execution Record、Self-Evolution 的安全持久化；
- 由 Heartbeat 驱动的低频维护，不要求客户创建业务 Cron；
- 安装、升级、迁移和回归验证的明确结果。

使用 Obsidian 时只增加一次 `AGENT_OS_VAULT_DIR`；未设置时 Vault 自动维护保持禁用。

精确时间业务（例如每天 09:00 日报）仍按用户要求创建 OpenClaw Automation。安装器不预设未知业务日程。

## 2. 配置边界

### 客户仍需提供

- OpenClaw 模型与凭证；
- 实际消息渠道及接收人；
- 使用 Obsidian 时的 Vault 路径；
- 使用 Multi-Agent 时的目标 Agent；
- 明确要求的精确时间业务日程。

### Agent OS 应自动完成

- Skills、共享库和 Runtime 模板安装；
- 默认 Heartbeat 配置；
- 运行数据目录初始化；
- 依赖检测；
- 旧数据迁移；
- Gateway 重载与安装验收；
- Heartbeat 唤醒后的到期维护判断。

## 3. 当前审计结论

当前 Basic 对话治理和 Proactive 唤醒已基本可用，但还不能宣称完整零配置：

1. Task、Proactive、Ontology 和 Execution Record 默认写入 Skill 安装目录，升级替换 Skill 后可能从空状态启动。
2. Heartbeat 模板未接入 Task 健康扫描、Memory 维护、Ontology 校验和 Vault 同步。
3. Obsidian 默认路径带特定机器/用户目录，不适合作为通用客户默认值。
4. Vault/Ontology 专项测试依赖 PyYAML，但仓库没有统一依赖安装清单。
5. 安装验收需要从 ready 总数升级为逐 Skill 名称检查。
6. 多 Agent 安装需要显式指定唯一 Heartbeat owner，避免所有 Agent 同时巡检。

## 4. 实施阶段

### Phase A — 统一持久化（已建立兼容迁移底座）

新增 `skills/_lib/workspace.py`，统一解析：

```text
OPENCLAW_WORKSPACE
→ OPENCLAW_WORKSPACE_DIR
→ OpenClaw 配置 workspace
→ ~/.openclaw/workspace
```

目标目录：

```text
<workspace>/
├─ memory/
├─ .agent-os/
│  ├─ tasks/
│  ├─ proactive/
│  ├─ ontology/
│  ├─ execution/
│  ├─ evolution/
│  └─ maintenance/
└─ .agent-os-vault/
```

迁移对象：

- `skills/task-manager/memory/tasks.json`；
- `skills/proactive/memory/{state,queue,execution_records}*`；
- `skills/ontology/memory/ontology/*`；
- 现有 `.agent-os/evolution/*`；
- Vault registry、candidate、provenance 与 audit 状态。

不变量：备份优先、原文件不静默删除、数量/指纹验证通过后才切换新路径、重复迁移幂等。

当前已实现：统一路径解析、Agent/Project/Shared 目录模型、旧路径兼容读取、默认 dry-run
迁移工具、显式 apply 的非破坏性复制、SHA-256 校验、冲突拒绝和幂等测试。安装器在替换
旧 Skill 前先迁移 Main Agent 的历史单 Agent 状态。后续仍需为已有多 Agent 私有状态增加
逐 Agent 显式迁移清单。

### Phase B — Heartbeat 维护闭环

新增确定性入口：

```bash
python3 skills/proactive/scripts/maintenance.py run
```

每次 Heartbeat 都可调用，但以 `.agent-os/maintenance/state.json` 判断是否到期。它是 wake 后的 cadence gate，不是 Scheduler。

建议节奏：

| 周期 | 检查 | 默认动作 |
|:--|:--|:--|
| 每次唤醒 | Proactive State、Queue、新 Signal、权限/失败异常 | 无新价值则 `HEARTBEAT_OK` |
| 30 分钟 | Task overdue/stale/blocked/goal drift | 生成去重 Signal |
| 2 小时 | Evolution pending/rollback required | 检查并只处理最高优先级候选 |
| 每日 | Memory 合并/去重/晋升候选 | 可逆整理；删除/覆盖进入 ASK |
| 每日 | Ontology validate/duplicates/contradictions | 只读检查或生成 Proposal |
| 每日 | Vault export/reconcile（仅启用时） | 单向导出 + drift 报告 |
| 每周 | Task 指标、长期记忆和治理复盘 | 生成摘要/候选，不自动改安全规则 |

维护状态至少记录：`last_started_at`、`last_completed_at`、`last_result`、`next_due_at`、`operation_id`、`failure_count`。同一 operation 必须幂等；UNKNOWN 且可能已有副作用时禁止自动重试。

### Phase C — Obsidian 可选集成

路径优先级：

```text
AGENT_OS_VAULT_DIR
→ install.sh --vault-dir
→ 未配置则禁用自动 Vault 维护
```

必须移除特定用户默认目录。未启用 Obsidian 时，Agent OS 其他功能应完全正常。

允许自动执行：`status`、`export`、`reconcile`、安全的 `validate`。

不得自动执行：`candidate-status accepted`、`accept`、覆盖机器真相、删除或高风险迁移。这些继续走 Permission 与人工治理。

### Phase D — 安装与依赖

安装器目标接口：

```bash
./install.sh
./install.sh --profile basic
./install.sh --heartbeat-every 1h
./install.sh --heartbeat-agent main
```

增加统一依赖清单，至少覆盖 PyYAML。安装器先检测、解释缺失项，再按明确授权安装；不能静默修改系统 Python。

安装器只面向 OpenClaw 官方运行环境，不单独构建通用跨平台运行层。

### Phase E — 协议与元数据收敛

- 为全部 Core Skills 补齐统一 `x-agent-os` contract；
- 自动校验 `entry_mode`、`requires`、permission、verification、writeback 和 delegation；
- Manifest 动态区分 11 Core 与 bundled extension；
- 安装验收按 Skill 名称验证，不只比较 ready 数量。

### Phase F — 共享 Skills 的 Multi-Agent 适配

产品范围明确为：**一份共享 Skills + `_lib`，由多个 OpenClaw Agent 共同使用；不为每个 Agent 复制一套 Skill。**

安装器需要：

- 验证共享 Skills 目录已被 OpenClaw 加载；
- 读取真实 Agent 列表并检查 `subagents.allowAgents` 引用有效；
- 不自动给所有 Agent 开启 Heartbeat，默认由 Main Agent 承担主动巡检；
- 对共享能力和私有状态给出明确验收结果。

状态边界：

```text
shared: skills/, _lib/, protocol/schema, shared ontology（经治理）
private: .agent-os/agents/<agent-id>/{proactive,tasks,execution,evolution,memory}
project: .agent-os/projects/<project-id>/...
```

硬性要求：

- `agent_id`、`session_id`、`task_id`、`correlation_id` 在跨 Agent 执行链中保留；
- 子 Agent 权限默认不继承，effective authority 只能缩小；
- 未显式声明共享的 Memory、Queue、Task、Execution Record 不得跨 Agent 可见；
- Shared Ontology/Knowledge 写入必须经过 scope 与 provenance 治理；
- 同一 `operation_id` 跨 Agent 重复执行必须被检测；
- 安装与升级只替换共享能力，不覆盖任何 Agent 私有状态。

不在当前产品范围内：为每个 Agent 复制 Skill、为每个 Agent 自动创建独立 Gateway、自动生成业务 Agent 或自动开启全部 Agent Heartbeat。

## 5. 权限边界

Heartbeat 可自动执行：

- 只读扫描和状态检查；
- 生成 Task/Memory/Evolution/Import 候选；
- 本地可逆整理；
- Vault 单向导出和 drift 检查；
- 生成 Ontology Proposal。

Heartbeat 不自动执行：

- 删除或覆盖长期记忆；
- 改用户长期偏好；
- 接受 Vault 反向导入；
- 自动 Apply Self-Evolution；
- 修改安全、权限、凭证或 Runtime；
- 外发、生产、资金或不可逆操作。

## 6. 验收标准

### 新安装

- 一条安装命令完成 Active 安装；
- Core Skills 按名称全部 ready；
- `_lib` 可导入；
- Runtime 模板安装且不覆盖客户已有文件；
- Heartbeat monitor 可运行；
- 未创建业务 Automation。

### 升级

- 旧 Task、Queue、State、Ontology、Execution Record 数量和指纹不丢；
- 中断后可安全重试；
- 迁移失败保持旧版本与备份可恢复；
- 不因替换 Skill 清空运行状态。

### Heartbeat

- 未到期维护只做轻量检查；
- 到期维护只运行一次；
- 无事项静默；
- 相同 Signal 不重复提醒；
- 连续失败达到预算后升级，不无限重试。

### Obsidian

- 未配置 Vault 时无错误、无目录污染；
- 配置后 export/reconcile 幂等；
- Vault 编辑不能直接覆盖机器真相；
- Import 必须生成 candidate；
- Accept 必须经过审批和 provenance 验证。

### OpenClaw 与回归

- OpenClaw 环境的一键安装与重复升级 smoke tests；
- Python syntax、Core regression、Vault/Ontology、migration 和 maintenance tests 全通过；
- 缺依赖时给出可执行错误，不在运行中才崩溃；
- `git diff --check` 与 CI 全通过。

## 7. 完成定义

满足下列条件后，才能对客户宣称：

> 安装 Agent OS 后，日常治理、主动巡检、记忆/经验维护只依赖 OpenClaw 默认 Heartbeat，客户无需创建 Cron；Obsidian 仅需设置一次 Vault 路径；只有精确时间业务才需要独立 Automation。

在 Phase A–E 与对应验收全部完成前，应使用“Basic/Active 可用，完整自动维护仍在产品化”这一准确表述。
