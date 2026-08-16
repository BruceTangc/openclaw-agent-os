# Self-Evolution 学习循环管线参考（learn.py --cycle，10 Phase）

> `learn.py --cycle` 是完整学习循环入口（V3.2.2 实测 10 Phase）。

## 1. 十阶段

```text
🔌 Phase 0  Aggregate Learning Bus   聚合中央总线事件（drain → trail）
📁 Phase 1  Memory scan              扫描 memory 文件
✅ Phase 2  Verification check       待验证项检查
🚀 Phase 3  Pattern promotion        pattern 晋升检查
⏳ Phase 4  Forgetting check         遗忘/过期检查
↩️ Phase 5  Auto-revert check        自动回滚检查
🗑️ Phase 6  Memory retention         记忆保留（90 天清理）
🔍 Phase 7  Auto-detect learning     自动检测新学习
🌙 Phase 8  Dream distillation       梦境蒸馏（记忆压缩）
📚 Phase 9  Memory index             重建主题索引
📝 Phase 10 Session summary          会话总结
```

## 2. Phase 0：Learning Bus Drain

读 `memory/agents/bus.json` pending 事件 → 去重（topic+content 比对 trail）→ 写 trail（source=external 初始不信任）→ 标记 resolved → 更新 bus.stats。

## 3. Final Summary 解读

```text
Entries:  N                     # trail 条目总数
Changes:  N                     # 本轮应用变更
Verified: N                     # 本轮验证数
Promoted: N                     # 晋升数
Graph:    N nodes / N edges     # 知识图谱规模
Actions taken this cycle:       # 本轮动作明细
```

## 4. Cron 建议

- `--cycle` 低频（每日 1 次），作为全局调度入口。
- `--status` / `--verify` / `--retention` 高频轻量巡检。
- 多 Agent：各 Agent 用 `bus.py --central` 上报，Global Cycle Phase 0 聚合。
- 不为每个节点各建一套学习循环。

## 5. Cron Lock / Concurrency

`aggregate_bus_events` 用文件锁（`memory/agents/.bus.lock` + fcntl）防并发：拿不到锁 → 本轮跳过；拿到 → 处理完释放。

## 6. Scan Cursor

`bus.stats.last_scan` / `last_pending_count` 记录上次扫描时间与待处理数。无新 pending → Phase 0 快速返回，不空转。

## 7. 全局学习周期定位

Global Learning Cycle 是**调度器**，不是特权晋升通道。所有 Bus 事件仍按 Core Loop 处理：scope 默认最窄（AGENT），晋升须过 Confidence + Context-independence + Governance 三重校验，不因「全局调度」绕过。

## 8. 技能生成（skillgen）

```bash
python3 scripts/skillgen.py --scan                    # 扫描 trail 找候选
python3 scripts/skillgen.py --list                    # 查看草拟技能
python3 scripts/skillgen.py --generate <pattern_id>   # 生成草稿
python3 scripts/skillgen.py --approve <name>          # 审批并安装（人工把关）
python3 scripts/skillgen.py --auto                    # 全自动（scan+generate，不自动安装）
```

纪律：审批安装是人工动作，`--auto` 只到草稿，安装走 `--approve`。

## 9. 梦境蒸馏（dream.py）

```bash
python3 scripts/dream.py --run         # 完整蒸馏（扫描近 14 天日志）
python3 scripts/dream.py --dry-run     # 预览
python3 scripts/dream.py --days 14
python3 scripts/dream.py --report
```

## 10. 日常 runbook

```bash
python3 scripts/learn.py --cycle            # 每日主入口
python3 scripts/learn.py --status            # 统计
python3 scripts/learn.py --verify            # 待验证项
python3 scripts/learn.py --retention         # 过期项
python3 scripts/bus.py --pending             # 总线待处理
python3 scripts/agents.py --status           # Agent 状态
python3 scripts/learn.py --search-memory "<q>"
python3 scripts/learn.py --score 8 7 9 8 8   # 五维自评 accuracy usefulness efficiency tone proactiveness
```
