# Candidate Policy — Self-Evolution v2

Candidate 只描述「什么问题值得解决」，不描述「应该怎么解决」。
Candidate **不允许直接修改任何文件**。

## Discover 的判定清单

每次从 Evidence 出发，必须判断：

- 是否真实问题（不是幻觉/误报）
- 是否重复（recurrence / sessions）
- 是否具有独立来源（independent_sources）
- 是否属于 Agent 自身（vs 外部环境）
- 是否只是外部环境（external_environment）
- 是否已有解决方案（existing_solution）
- 是否具有足够影响（impact）

## 默认 Candidate 门槛

```
recurrence >= 3
AND
sessions   >= 2
```

### 唯一例外（系统性问题）

满足以下**全部**才可破例进 Candidate：

```
至少 2 个独立、高质量、已验证的 Evidence
+
明显属于系统性问题 (systemic=true)
```

## 必须避免的错误学习

以下**默认不能**形成 Candidate（标 external_environment 或 one_time）：

- API 连续挂 3 次 → 是 `external_environment`，不学成「这个 API 不应该使用」
- 用户临时要求 / 一次性错误
- 随机网络失败 / 第三方服务异常
- 单次工具故障

## Candidate 建议结构

```json
{
  "candidate_id": "CAND-20260818-001",
  "status": "CANDIDATE",
  "created_at": "...",
  "scope": "skill|agent|project|user|global",
  "target": "技能/文件/流程目标",
  "pattern_key": "去重键",
  "problem": "问题描述",
  "evidence_refs": ["EVID-..."],
  "recurrence": 3,
  "sessions": 2,
  "independent_sources": 2,
  "confidence": 0.8,
  "impact": "low|medium|high",
  "diagnosis_id": null
}
```

## 幂等

同一 `scope + target + pattern_key` 已存在未终结 Candidate 时，**不得重复创建**
（`_core.find_candidate` 负责判重，命中则 DEDUP）。
