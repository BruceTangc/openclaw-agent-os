# Evidence Model

A durable claim/result should conceptually track:
- source
- timestamp
- subject
- claim/result
- confidence
- verification status
- freshness
- scope
- provenance

Evidence states:
UNVERIFIED / PARTIALLY_VERIFIED / VERIFIED / DISPUTED / OBSOLETE

## 与 Knowledge 声明状态映射

Evidence 状态（校验维度）与 knowledge 声明的 `status`（生命周期维度）是两套视图，映射如下：

| Evidence（校验状态） | Knowledge status（生命周期） | 含义 |
|:--|:--|:--|
| UNVERIFIED / PARTIALLY_VERIFIED | active（待验证） | 声明存活但证据不完全 |
| VERIFIED | active | 声明存活且有完整验证 |
| DISPUTED | disputed | 存在矛盾，保留并标记，不静默覆盖 |
| OBSOLETE | obsolete | 已被新声明取代 / 失效，而非删除 |

> 后续晋升/降级（active↔obsolete、superseded）走 knowledge-governance 治理，见 `knowledge-governance/SKILL.md`。
