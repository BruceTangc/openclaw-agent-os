# Verification Protocol

> Agent OS v1.3 Core Protocol 之一。证明"工具跑了"≠"任务成功"。

## 1. 核心区分

```
tool success          ≠  task success
工具返回成功            任务实际达成
```

必须：
```
tool success
  → 检查实际结果/工件/状态/证据
  → PASS / PARTIAL / FAIL / UNKNOWN
  → 才允许宣称完成
```

## 2. 验证分级（V0-V4，与 orchestrator.py 一致且累计）

| 级别 | 检查内容 | 证据要求 |
|:--|:--|:--|
| V0 | 工具返回成功 | tool_success=true |
| V1 | 输出格式正确 | output/outputs/summary 存在 |
| V2 | 结果符合任务条件 | success_condition_met=true |
| V3 | 独立验证 | independently_verified=true（独立于执行方） |
| V4 | 外部状态变化确认 | state_changed=true（外部/持久状态确已改变） |

**累计规则：** 高等级必须同时满足低等级全部检查（`all(checks)`），不允许跳过。

## 3. 状态定义

| 状态 | 含义 |
|:--|:--|
| PASS | 满足该等级全部验证项，有证据 |
| PARTIAL | 部分满足（缺证据/部分完成） |
| FAIL | 有失败证据，或验证项不通过 |
| UNKNOWN | 证据不足/无法确认（≠ PASS） |

## 4. Verify 维度（verification-evaluation）

- 执行：动作真的发生且只发生一次
- 工件/状态：产物可打开/状态符合预期
- 数据正确性：数字/日期/名称未变
- 范围：实际 ≤ 授权
- 证据：可独立复核
- 安全：无越权/无副作用泄漏

## 5. 失败处理

```
diagnose → repair → retry within budget → re-verify → escalate
```

- 瞬时错误：预算内重试
- 确定性错误：修复后验证
- 连续可验证失败 → self-evolution candidate（有证据才升级）

## 6. 禁止

- 因为工具返回成功就写 COMPLETED。
- 宣称外部状态改变但没有证据。
- 验证等级与任务重要性不匹配（资金/不可逆必须 V4）。