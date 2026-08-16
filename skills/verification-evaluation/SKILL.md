---
name: verification-evaluation
description: 验证与评估策略层（Agent OS v1.2 核心模块）。区分工具成功与任务成功：verify（执行/工件/数据/范围/证据/安全）+ evaluate（目标/正确性/完整性/质量）；状态 PASS/PARTIAL/FAIL/UNKNOWN；失败→修复→预算内重试→升级。V0-V4 验证分级。在宣称「完成」、验证结果、评估质量、失败处理时触发。
version: 1.2.0
x-agent-os:
  protocol_version: "1.2"
  layer: "core"
---

# Verification & Evaluation

## Purpose

证明「工具跑了」≠「任务成功」。用 verify（执行/工件/数据/范围/证据/安全）证明真的成功，用 evaluate（目标达成/正确性/完整性/质量）评估质量，输出 PASS/PARTIAL/FAIL/UNKNOWN，并驱动失败处理。

## Scope

- V0–V4 验证分级（累计）
- 状态定义（PASS/PARTIAL/FAIL/UNKNOWN）
- Verify 六维度 + Evaluate 质量维度
- 失败处理循环（diagnose→repair→retry→re-verify→escalate）
- 验证等级与任务重要性的匹配

## Non-Goals

- 不执行任务本身
- 不替代 OpenClaw 的执行/审计机制
- 不建独立 verification runtime
- 不做总结/知识（走 summarize/knowledge-governance）

## OpenClaw Boundary

只做验证与评估的判断，复用 OpenClaw 原生工具结果 / session / 文件系统获取证据。不创建自己的 Scheduler、Event Bus、Verification Runtime。

## When to Activate

- 后果性工作结束、宣称「完成」前
- 关键步骤与最终结果需验证时
- 工具返回成功但需确认真实效果时
- 失败需处理（重试/修复/升级）时

## Inputs

- 执行结果 + 工具返回状态（tool_success）
- 任务成功条件（success_condition）
- 目标与约束
- 所需的证据等级（V0–V4）

## Core Procedure

统一执行链：Trigger → Intake → Context → Goal/Task → Decision → Permission → Action → Verification → Evaluation → Writeback → Evolution

1. **核心区分**：`tool success ≠ task success`。
2. **Verify**：检查执行/工件/数据/范围/证据/安全六维度。
3. **定级**：按累计规则确定满足到 V0–V4 哪级。
4. **定状态**：PASS / PARTIAL / FAIL / UNKNOWN。
5. **Evaluate**：目标达成、正确性、完整性、质量、效率、约束、有用性。
6. **失败处理**：diagnose → repair → retry within budget → re-verify → escalate。

## Decision Rules

**V0–V4 验证分级（累计，高等级须满足低等级全部）**：

| 级别 | 检查内容 | 证据要求 |
|:--|:--|:--|
| V0 | 工具返回成功 | tool_success=true |
| V1 | 输出格式正确 | output/outputs/summary 存在 |
| V2 | 结果符合任务条件 | success_condition_met=true |
| V3 | 独立验证 | independently_verified=true |
| V4 | 外部状态变化确认 | state_changed=true |

**状态定义**：

| 状态 | 含义 |
|:--|:--|
| PASS | 满足该等级全部验证项，有证据 |
| PARTIAL | 部分满足（缺证据/部分完成） |
| FAIL | 有失败证据，或验证项不通过 |
| UNKNOWN | 证据不足/无法确认（≠ PASS） |

**Verify 六维度**：执行（只发生一次）、工件/状态、数据正确性、范围（actual ≤ 授权）、证据（可独立复核）、安全（无越权/副作用泄漏）。

**失败处理**：瞬时错误→预算内重试；确定性错误→修复后验证；连续可验证失败→ self-evolution candidate（有证据才升级）。

**等级匹配**：简单阅读 V1；研究/数据分析 V2/V3；外部写入 V3；资金/不可逆 V4 + 人工确认。

## Outputs

- 验证等级 + 状态（PASS/PARTIAL/FAIL/UNKNOWN）+ 证据
- 评估结论（goal attainment / correctness / completeness / quality）
- 失败处理的下一步（retry/repair/escalate）

## Interaction With Agent OS

- 被 **orchestrator / task-manager / proactive** 调用，验证执行结果与最终结果。
- 验证失败产物转 **self-evolution** candidate（有证据）。
- 与 **permission-security** 配合：范围验证（actual ≤ authorized）越界即 Security Incident。

## Permission

只读证据检查 = L0/L1，可自动。不产生副作用。

## Verification

（本模块自身）验证结论是否有证据支撑？等级是否与任务重要性匹配？是否有「工具成功即完成」的偷懒？

## Failure Handling

- 证据不足 → UNKNOWN（不写成 PASS）。
- 修复后仍失败 → 预算内重试有限次，否则 escalate。
- 确定性错误 → 先诊断修复，非盲目重试。

## Memory / Knowledge Writeback

验证结论、失败模式如需沉淀，走 memory/knowledge-governance；连续失败转 self-evolution。

## Self-Evolution Feedback

- 连续可验证失败（≥ 有证据）→ 上报 improvement candidate。
- 反复「工具成功但任务失败」→ 上报验证标准改进 candidate。

## Safety / Anti-Loop

- 不建自己的 Scheduler、Event Bus、Verification Runtime；复用 OpenClaw 原生。
- 不因工具返回成功就写 COMPLETED。
- 宣称外部状态改变必须有独立证据（state_changed）。

## Examples

- 生成报告后 `tool_success=true`，但无法打开 → V1 都不过，PARTIAL/FAIL。
- 资金转账后需确认对方账户到账 → 必须 V4（外部状态变化）+ 人工确认。
- 搜索结果返回成功但无来源 → 数据正确性/证据维度不足，标 UNKNOWN。
- 结果符合条件但非独立验证 → V2 通过，V3 未达，据任务需要决定是否补验。
