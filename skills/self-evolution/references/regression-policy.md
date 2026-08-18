# Regression Policy — Self-Evolution v2

Regression 是 Self-Evolution 的**最终裁判**。Apply 后必须比较 Before vs After。

## 结果判别

| 结果 | 含义 | 动作 |
|:--|:--|:--|
| IMPROVED | 有证据表明改善 | 允许 **Promotion** |
| NO_CHANGE | 无变化 | 不 Promotion |
| REGRESSED | 恶化 | 触发 **Rollback** |
| UNKNOWN | 无法证明改善 | 不 Promotion |

默认铁律：**无法证明改善 = 不进化成功。**

## Regression 方式

Compare Before vs After，可结合：
- 已知失败用例（Known Failure Case）：Apply 前必测
- 正常用例（Normal Case）
- 边界用例（Boundary Case）
- 若有条件：Historical Case / Regression Case

不能只检查「Python 返回 0」，必须尽可能验证**行为结果**。
（判定借用 Agent OS VERIFICATION-PROTOCOL 的 V0-V4 语义，不重复发明。）

## Promotion

只有 `Regression == IMPROVED` 才允许 Promotion。
Promotion 之后记录完整 Evolution Chain：

```
Evidence → Candidate → Diagnosis → Proposal → Change → Regression → Promotion
```

## Rollback

`Regression == REGRESSED` 时必须 Rollback，恢复 Apply 前 Snapshot。
记录：`change_id / rollback_at / reason / regression_id`。

## 防死循环（关键）

Rollback 产生的信息**不得自动形成新的 Candidate**，防止：

```
Evolution → Regression → Rollback → Candidate → Evolution → Regression → ...
```

原因：轮回产生的 Evidence 来自自我制造，非独立来源，不具备进 Candidate 的资格。
（另遵循 Agent OS EVOLUTION-PROTOCOL §10.1 Anti-Loop：Change Cooldown / Same-target Dedup /
Regression Failure Limit / Max Evolution Depth / Manual Escalation。）
