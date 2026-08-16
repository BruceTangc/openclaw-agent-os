# Self-Evolution Scripts Audit — Final

> 对 `skills/self-evolution/scripts/` 的专项审计定格（Agent OS v1.2 最终验收）。
> 目的：确认代码没有偷偷做 SKILL.md 明确禁止的事——尤其 ChatGPT 点名的
> skillgen.py / agents.py 是否"生成候选 ≠ 自动修改/运行"，learn.py 是否越权改安全文件。

## 审计结论（逐脚本）

| 脚本 | 角色 | 是否越权执行 | 结论 |
|:--|:--|:--|:--|
| `agents.py` | Agent Registry 索引管理 | 否 | ✅ 纯 list/status/capabilities/overlap/sync-ontology，**无启动/执行/调度 Agent** → 不是 Agent Runtime |
| `skillgen.py` | Skill 候选草稿生成 | 否 | ✅ `--auto` 只 scan+generate **drafts**（提示用 --approve 安装）；`--approve` 需 `--yes` 显式确认 → **不自动修改 Skill** |
| `learn.py` | 学习/自蒸馏循环 | 否（已加固） | ✅ `auto_promote` 只对 MEMORY.md/TOOLS.md；AGENTS.md(Red Lines)/SOUL.md(人格) 在 `execute_promotion` 入口被拦截（status=requires_review）→ **不自改安全/人格文件** |
| `bus.py` | 学习记录读写（静态文件） | 否 | ✅ 非推送式事件总线，只是内存/文件读写 |
| `dream.py`/`reflect.py`/`sync.py`/`migrate.py`/`ontology_bridge.py` | 辅助工具 | 否 | ✅ 均为短命 CLI 编排，无 while True/线程/常驻 |
| 全部 16 脚本（全 Agent OS） | 见 DEEP-AUDIT | 否 | ✅ 无自建 Runtime/Event Bus/Scheduler，无绕过 native approval |

## 三项关键红线（已验证代码层落实）

1. **生成候选 ≠ 自动修改**：skillgen 生成草稿需 `--approve --yes` 才安装。
2. **Agent Registry ≠ Agent Runtime**：agents.py 只登记能力/状态，无执行/调度能力。
3. **不自改安全/人格文件**：learn.py 自动提升仅限 MEMORY/TOOLS，AGENTS(安全红线)/SOUL(人格)必须人批。

## 与 SKILL.md 边界一致性

self-evolution/SKILL.md 声明的 4 条铁律（只做发现→提改进→验证→请求批准→应用；
绝不自改权限/安全/凭证/Runtime；单次未验证失败不触发；不为完成率削弱安全）
在代码层均得到遵守，无"文档合法、代码越界"的撕裂。

## 结论

**Self-Evolution 脚本通过验收**。整套 Agent OS v1.2（11 SKILL.md + 16 scripts + docs 协议 + schemas + tests）
已完成：SKILL.md 规范对齐、脚本级安全审计、5 层一致性整改、Multi-Agent Authority/Memory 委托链形式化。
**可以正式冻结。**

（本文件与 DEEP-AUDIT.md 共同构成 Agent OS v1.2 的完整验收存档。）
