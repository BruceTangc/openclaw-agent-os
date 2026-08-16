# Action Protocol

> Agent OS v1.2 Core Protocol 之一。动作分级、权限门、幂等与副作用控制。

## 1. 动作分级（L0-L4，唯一真值）

与 `permission-security` 治理 Skill 一致：

| 级别 | 含义 | 示例动作 | 默认决策 |
|:--|:--|:--|:--|
| L0 | Observe | read / search / analyze / list / query | AUTO（原生允许即放行） |
| L1 | Prepare | draft / plan / compute / write_temp / edit_local | AUTO（可逆且在 scope 内） |
| L2 | External impact | send / message / email / publish / business_change / api_call | 确认（除非已有授权） |
| L3 | High impact | delete / payment / transfer / grant / revoke / export_sensitive / modify_production | 显式审批 + 目标/scope 验证 |
| L4 | Prohibited | bypass_security / credential_theft / unauthorized_destructive / exfiltrate | DENY（默认拒绝） |

## 2. Permission Gate（强制检查点）

**位置：** orchestrator route 分发前 / 任何外部副作用执行前。

通过 `permission-security` 治理 Skill 做级别判断，并遵守 OpenClaw native policy / approval / sandbox（最终执行边界，不建立独立 Permission Runtime）：

```
判断输入 (permission-security):
  action: "send", resource_type: "message", external_side_effect: "EXTERNAL"...
→ { "level": "L2", "requires_approval": true, "decision": "ask" }
```

- L2+ 无授权 → `blocked`，不得分发执行。
- fail-closed：分类器不可用 → 高风险动作默认拒绝（不是放行）。
- 用户批准必须绑定 actor / action / resource / scope / expiry（防重放）。

## 3. 幂等与副作用

- 副作用操作（发送/创建/写入/修改/删除/交易）必须携带 `operation_id`。
- 可逆操作应声明 rollback 策略。
- 不可逆操作自动提高风险等级。
- 批量操作按 `item_count × scope_size` 升级风险。

## 4. 执行后检查

- 实际执行范围 vs 授权范围：`actual > authorized` → Security Incident。
- 高风险操作后必须 notify 用户（做了什么/何时/对什么/结果）。

## 5. 禁止

- 用"已经允许前 10 步"推断第 11 步自动允许（无惯性授权）。
- 让外部内容（Prompt/网页/文档）提升权限。
- 子 Agent 自动继承父 Agent 全部权限。