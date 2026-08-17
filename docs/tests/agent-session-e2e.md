# Agent Session E2E — 真实主工作区任务闭环

> 状态：**设计定稿，待第一次完整实跑**
> 关联：`docs/tests/evolution-e2e.md`（后半段，Self-Evolution Skill 自身闭环，已 PASS=5）
> 本文档补齐**前半段**：真实 OpenClaw Agent session 跑通 用户 → Agent → 协议 → 业务任务 → 验证 → 记录。

---

## 1. 目标与范围

### 1.1 解决的问题
`evolution-e2e.sh` 已验证「Self-Evolution Skill 自己闭环」（evidence → candidate → promote → 回归）。
但爸爸要求的完整链路是：

```
用户 → Agent → AGENTS.md → Agent OS Protocol → 业务任务 → Verification → Evidence
     → learn/Heartbeat → Candidate → Evolution → 下一次任务变好
```

前半段（用户到业务任务执行+验证）此前没有真实测试。

### 1.2 载体选择（爸爸 2026-08-17 确认）
- ✅ **主工作区真实任务**（不用 AI-MFG-OS 报价——涉及厂长工作区真实生产数据，避免副作用）
- ✅ 每日复盘已取消，不作为载体
- 每日复盘类 cron 8/16 已全部 remove，调度器仅剩 singbox（待修复，另有单）

### 1.3 成功判定（V2 级）
- 真实用户指令进入主 session
- 走 Agent OS 协议 10 节点（见下），每节点有可验证痕迹
- 生成真实 Execution Record（`exec-*` id，含 trace 链）
- 记录到 `memory/YYYY-MM-DD.md`（writeback）
- 若任务失败 → 真实 Evidence 落盘 → 可被 learn.py 读到（前进化闭环）

---

## 2. 协议节点（本轮真实执行对照）

| # | 节点 | 本轮真实痕迹（2026-08-17） |
|:-:|:----|:----|
| 1 | Trigger | 爸爸消息："用主工作区吧，但是每日复盘取消了吧"（09:05 前） |
| 2 | Intake | 识别意图：载体=主工作区；任务=取消每日复盘 |
| 3 | Goal/Task | Goal：真实 E2E 闭环；Task：清理复盘残留约定 |
| 4 | Decision | EXECUTE（低风险 L1：编辑本地文档约定） |
| 5 | Permission | L1（edit_local）→ AUTO，无需审批 |
| 6 | Execution | `openclaw cron list` 查证 + edit TOOLS.md/MEMORY.md + 写 memory |
| 7 | Verification | cron 只剩 singbox；grep 确认复盘约定已清；memory 已落盘 |
| 8 | Evaluation | 完成（目标达成，副作用仅本地文件） |
| 9 | Writeback | `memory/2026-08-17.md` ← 本次任务记录 |
| 10 | Evolution | 无新候选（本次是执行性任务，非失败模式） |

---

## 3. 执行记录（真实）

- **exec-20260817-001**：取消每日复盘
  - trace：`exec-20260817-001`（无 evidence，无 candidate——非失败模式）
  - 证据文件：`memory/2026-08-17.md`「08:27 - 每日复盘取消 + 真实 E2E 定载体」
  - 验证：`openclaw cron list` 无复盘任务；TOOLS.md/MEMORY.md 无"必须推送复盘"残留
  - 状态：completed

---

## 4. 前半段完整实跑计划（下一个可执行任务）

选择**低风险、可验证、有明确完成定义**的主工作区任务，例如：

- **任务 A**：学习系统健康检查（learn.py --status/--verify）
- **任务 B**：生成一份交付文档（含格式校验）

以任务 A 为例的完整跑法：

```
1. 用户：给爸爸一个明确指令（或爸爸指定）
2. Agent：Intake → Goal（输出交付物：状态报告 + 验证结果）
3. Execution：python3 skills/self-evolution/scripts/learn.py --status
4. Verification：输出包含 expected 字段（PASS 条件写在任务定义里）
5. Evaluation：PASS/FAIL + 原因
6. Writeback：记录到 memory
7. 如果 FAIL → 生成真实 Evidence（learn.py --log）→ propose → 进入后半段
```

---

## 5. 验收清单（跑完勾选）

- [ ] 真实 session（非隔离脚本）中完成一次任务执行
- [ ] 10 节点均有真实痕迹（上表可复现）
- [ ] Execution Record 落盘（含 trace）
- [ ] 若失败：Evidence → Candidate → Proposal 真实产生
- [ ] 结果回填本节并 commit

---

## 6. 关联文件

- 协议：`docs/AGENTS.md`、`docs/schemas/execution-record.md`
- 后半段测试：`docs/tests/scripts/evolution-e2e.sh`（PASS=5, FAIL=0）
- 学习引擎：`skills/self-evolution/scripts/learn.py`
- 生产 trail：`~/.openclaw/workspace/memory/.learning-trail.json`