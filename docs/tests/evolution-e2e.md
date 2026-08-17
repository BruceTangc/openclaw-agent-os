# Evolution E2E — 端到端闭环测试

> Agent OS v1.3。**目的：证明"Agent 实际运行时，真的能从 Evidence 一路走到
> Evolution，再重新影响下一次任务"**——不是纸面流程，是可重复执行的真实闭环。

## 场景设计

**报价 Skill 连续漏检材料利用率**（重复失败 → 重复纠正 → 进化 → 下次任务变好）：

| 任务 | 时间 | 结果 | 说明 |
|:--|:--|:--|:--|
| T1 | 08-15 | FAIL | 报价清单缺材料利用率检查（历史会话 1） |
| T2 | 08-16 | FAIL | 同一错误，第二次会话（历史会话 2） |
| T3 | 08-17 | FAIL | 第三次失败，通过 `learn.py --log` 真实记录 Evidence |
| — | 08-17 | 晋升 | Pattern 达到 ≥2 次 / 跨 ≥2 会话阈值 → Candidate |
| — | 08-17 | Apply | 真实修改 TOOLS.md（低风险 G2） |
| T4 | 08-17 | **PASS** | 报价检查脚本回归：规则已生效，任务变好 |

晋升阈值特意按 learn.py 的设计要求 **≥2 occurrences across ≥2 sessions** 设计，
所以 T1/T2 为跨会话历史（seeded），T3 为当日真实 CLI 记录。

## 隔离性

测试使用独立 workspace（`E2E_WS=/tmp/agent-os-e2e-ws`，通过
`OPENCLAW_WORKSPACE` 指向），**不触碰生产 learning trail**
（`~/.openclaw/workspace/memory/.learning-trail.json`）。

## 运行方式

```bash
bash docs/tests/scripts/evolution-e2e.sh
# 或指定隔离目录：
E2E_WS=/tmp/foo bash docs/tests/scripts/evolution-e2e.sh
```

依赖：`docs/tests/scripts/e2e_setup.py`（构造隔离 trail + 报价检查脚本）。

## 实测结果（2026-08-17 本地运行）

```
═══ 1. T1 — material-utilization check MISSING        ✅ T1 FAIL (Evidence #1)
═══ 2. T2 — same failure, second session              ✅ T2 FAIL (Evidence #2)
═══ 3. T3 — log REAL evidence via learn.py
     🔄 Pattern 'quote-material-utilization-correction' incremented to 2x
     🔄 Pattern 'quote-material-utilization-check' incremented to 2x
                                                      ✅ T3 FAIL — threshold reached
═══ 4. Discover + Classify → Propose
     📋 2 Proposal(s):
     [1] PROMOTION → SOUL.md   (risk: Medium — persona)
     [2] PROMOTION → TOOLS.md  (risk: Low — adds a note)
═══ 5. Promote → execute Apply (real file change)
     ⛔ 安全文件 [SOUL.md] 不自动写入（需人工确认）
     📌 Change recorded: change-20260817-001 → TOOLS.md (verify by 2026-08-24)
     ✅ Promoted to TOOLS.md: - 报价完成前必须检查材料利用率
═══ 6. SOUL.md untouched（人格/安全文件须人工批准）    ✅
═══ 7. Regression — T4: re-run quotation task         ✅ T4 PASS
RESULT: PASS=5 FAIL=0 — Evolution loop works
```

## 关键验证点（全部通过）

1. **Evidence → Candidate**：T3 真实 `--log` 后，两个 pattern 的
   recurrence_count 均为 2、跨 3 个会话日期，达到晋升阈值。
2. **Discover + Classify → Proposal**：`--propose` 生成 2 个候选，
   各自带 target / risk / impact 分级。
3. **Apply 真实改动**：`--promote` 执行 `execute_promotion`，
   **真实写入 TOOLS.md**（`- 报价完成前必须检查材料利用率`），并生成
   `change-20260817-001`（7 天验证期，符合 G3 治理）。
4. **安全阀生效**：correction 类（→ SOUL.md）**不自动写入**，打
   "需人工确认"，人格/安全文件不被自动修改。
5. **Regression 证明改善**：T4 运行 `quote_check.sh` → PASS——
   **下一次任务真的变好了**，不是只改了文档。

## Execution Record 关联（P2）

每次 Full Path / 高风险任务应在结束时生成
`Execution Record`（见 `docs/schemas/execution-record.md`），
把本次测试的关键节点连成可审计链。**本次 E2E 的真实 trace 链**：

```
exec-001 (T3 报价任务)
  ↓ evidence_id: LRN-E2E-B  （报价完成前必须检查材料利用率）
  ↓ candidate_id: LRN-E2E-B （recurrence 2x / 跨 3 sessions）
  ↓ proposal_id: #2         （PROMOTION → TOOLS.md, Low risk）
  ↓ change_id: change-20260817-001 （G2 自动批准, 7 天验证期）
  ↓ regression_id: T4       （quote_check.sh）
  ↓ result: PASS
```

对应 Execution Record 中的 evolution 段：

```yaml
task:
  id: "e2e-quote-t3"
  objective: "报价清单生成并验证材料利用率检查"
  skill: "business-quote"
steps:
  verification:
    result: "FAIL"            # 缺材料利用率检查
    evidence: "LRN-E2E-B"     # Evidence 记录
  evaluation:
    result: "FAIL"            # 发现重复失败模式（T1/T2/T3 同模式）
  evolution:
    status: "applied"
    candidate_id: "LRN-E2E-B" # Candidate
    trace:
      execution_id: "exec-001"
      evidence_id: "LRN-E2E-B"
      candidate_id: "LRN-E2E-B"
      proposal_id: "#2"
      change_id: "change-20260817-001"
      regression_id: "T4"
      regression_result: "PASS"
  writeback:
    status: "knowledge"       # TOOLS.md Known Gotchas 落盘
```

这条链让 Agent 可以回答：**"为什么 TOOLS.md 突然多了这条报价规则？"**
→ 因为 T1/T2/T3 连续漏检 → Candidate → Proposal #2 → G2 自动批准 →
change-20260817-001 → T4 Regression PASS。

## 结论

闭环成立：**T1→FAIL → Evidence → Candidate → Proposal → Apply(TOOLS.md)
→ Regression → T4 PASS**。E2E 测试还真实暴露并修复了一个 learn.py bug
（`show_status` 将 promotion 元组当 dict 使用，已修）。

下一步（P4）：配置 Heartbeat → Proactive 自动巡检 Evidence →
Candidate discovery，让系统长期运行中持续产出真实进化案例。