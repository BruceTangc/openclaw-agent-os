# 证据采集模板（Evidence Collection Template）

> 与 `docs/schemas/evidence.md`（Evidence 状态模型）及 `verify.py` 的 V3/V4
> 校验字段对齐。任务完成宣称「成功」前，按此模板采集并留存证据。

## 一、先回答 5 问（采集 5 问）

| # | 问题 | 作用 |
|:--|:--|:--|
| 1 | 这次任务成功的**验证等级**是 V0–V4 的哪一级？ | 决定证据深度（V0 工具回执 / V4 外部状态） |
| 2 | **artifact 路径**在哪？（文件/报告/日志/输出） | 提供可独立复核的物证 |
| 3 | **外部确认方式**是什么？（对方到账/API 响应/第三方审计/人工复核） | 支撑 V4 外部状态变化 |
| 4 | 证据能否被**独立复核**？（谁来验证，何时） | 支撑 V3 independent + verified_by |
| 5 | 有无**不确定点 / 存疑项**？（数据旧了/只测了局部/结论待补） | 决定 UNKNOWN 而非 PASS，避免自欺成功 |

## 二、evidence_refs 字段模板（对齐 verify.py V3 校验）

```yaml
verification:
  level: "V3"                  # V0 | V1 | V2 | V3 | V4（累计，高等级须满足低等级全部）
  result: "PASS"               # PASS | PARTIAL | FAIL | UNKNOWN | UNAVAILABLE
  method: "file_inspection"    # 验证方法：file_inspection | api_check | external_confirm | human_review | ...
  independently_verified: true # V3 必备：是否经独立复核
  verified_by: "agent-main + reviewer-alice"   # 谁验证/复核（V3 必备）
  evidence_refs:
    - artifact_path: "reports/quotation-20260817.xlsx"   # 物证路径
      kind: "artifact"                                    # artifact | api_response | external_state | log | human
      produced_at: "2026-08-17T10:02:30+08:00"
      producer: "agent-quote"
    - artifact_path: "audit/transfer-confirm-20260817.json"   # 资金/外部状态 → V4
      kind: "external_state"
      state_changed: true                                    # V4 必备：外部状态变化确认
  state_changed: true          # 仅 V4（外部状态变化）
  success_condition_met: true  # V2：结果符合任务成功条件
```

## 三、输出格式模板（关键事实 + 不确定点 + 建议下一步）

```text
## Verification Result
- 等级 / 状态: V3 / PASS
- 关键事实（事实，非推断）:
  - 报价单已生成于 reports/quotation-20260817.xlsx（158 行，含材料利用率列）
  - 材料利用率检查项已核对（≤ 预算线 92%，实际 88%）
- 不确定点（存疑/待确认）:
  - 未对 3 天前的旧价格行做二次核对（数据新鲜度 V1 满足、V3 局部未达）
  - 外部客户回执未收到（若需 V4 则 state_changed 当前为假）
- 建议下一步:
  - 如需 V4：等待客户/对方到账确认后补 external_confirm
  - 数据新鲜度存疑行 → 走 knowledge-governance 标注 freshness
```

> 原则：**关键事实与推断分开标记**；不确定点不写成 PASS；宣称外部状态改变必须有独立证据（`state_changed`）。
