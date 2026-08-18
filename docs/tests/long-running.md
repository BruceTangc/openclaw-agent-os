# Long-running Test Plan (7d / 30d)

> Agent OS v1.3 Freeze 的验证主线。单次任务 / 单次 Evolution / Heartbeat / Regression
> 均已验证（见 `evolution-e2e.md`、`agent-session-e2e.md`）；本文件验证**长期运行不漂移**。

## 1. 目标

回答三个问题：
1. 长期跑下来，Evolution 是否**重复改同一个问题**（candidate dedup 失败）？
2. Evolution 是否**自己制造 Evidence → 无限自我修改**（evolution loop）？
3. Heartbeat 巡检是否**噪音化**（正常时也打扰）或 **stale**（到期不提醒）？

## 2. 周期

| 阶段 | 时长 | 检查频率 | 判定 |
|:--|:--|:--|:--|
| Phase 1 | 7 天 | 每天 heartbeat 巡检时 | 无异常 → 进入 Phase 2；有异常 → 修复后重跑 |
| Phase 2 | 30 天 | 每周一次深度检查 | 全部 PASS → v1.3 稳定确认 |

## 3. 观察项清单（每项含 PASS 条件）

| # | 观察项 | 检查方法 | PASS 条件 |
|:--|:--|:--|:--|
| 1 | **Candidate 重复** | `discover.py --status` 按 pattern_key 统计 | 同一 pattern_key 7 天内不产生 ≥2 个 candidate |
| 2 | **Evolution 循环** | 检查同一 target 的 change 序列 | 同一 target 无连续 ≥3 次修改（否则触发 cooldown） |
| 3 | **Regression 过期** | `--verify` / change.next_check | 无过期未验证的 change；PENDING→DUE→PASS/FAIL/EXPIRED 闭环 |
| 4 | **Heartbeat 噪音** | heartbeat 推送统计 | 正常期 7 天 SUGGEST/ACTION ≤ 2 次（且均为真实异常） |
| 5 | **Stale state** | proactive state 的 last_wake_at 新鲜度 | last_wake_at 不落后于 24h（除 22:00-06:00 静默期） |
| 6 | **Repeated proposal** | `--propose` 输出去重 | 同一 proposal 不重复出现（被拒后带拒绝原因归档） |
| 7 | **Failed change** | change 的 regression 结果 | FAIL 的 change 有回滚记录或人工决策记录 |
| 8 | **Permission drift** | 抽查 Execution Record 的 permission 节点 | 无 L 级越权（actual ≤ authorized） |
| 9 | **Rollback 完备** | 检查回滚记录 | 每次 FAIL 都有 rollback/处置记录 |

## 4. Evolution Anti-Loop 机制（v1.3 强制）

防止 `Evolution → Regression FAIL → Evidence → 又改 → 又 FAIL` 死循环。四道闸 + 人工兜底：

```
1. Change Cooldown      同一 target 修改后进入冷却期（默认 7 天），冷却期内不再接受同 target candidate
2. Same-target Dedup    candidate 入库前按 target+pattern 去重；重复者合并，不新增
3. Regression Failure Limit   同一 change 连续 2 次 Regression FAIL → 自动回滚 + 标记需人工
4. Max Evolution Depth 同一 pattern_key 累计 ≥3 次 change → 停止自动进化，转人工评估
5. Manual Escalation   以上任一闸触发或高风险修改 → 人工审批（G5-G6 必须人工）
```

**Evolution 不得制造 Evidence**：Regression FAIL 产生的 Evidence 只用于回滚决策，
不自动成为新 candidate 的输入；新 candidate 必须来自**独立**的失败/纠正/观测（见 EVOLUTION-PROTOCOL §1）。

## 5. 记录方式

- 每天 heartbeat 巡检输出写入 `memory/YYYY-MM-DD.md`（巡检段），异常才推送。
- 每周深度检查生成一张检查表，结果 commit 到 `docs/tests/long-running-YYYYMMDD.md`。
- 7 天期结束出结论：PASS → 30 天期；FAIL → 记录问题 + 修复 + 重跑。

## 6. 关联

- 巡检实现：`~/.openclaw/workspace/HEARTBEAT.md`（学习系统巡检段）
- 学习引擎：`skills/self-evolution/scripts/`（discover.py --status / regression.py / rollback.py）
- 生产 trail：`~/.openclaw/workspace/memory/.learning-trail.json`
- 协议：`docs/EVOLUTION-PROTOCOL.md`（§10 不允许的行为 = anti-loop 的文字版）
