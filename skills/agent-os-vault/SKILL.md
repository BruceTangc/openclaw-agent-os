---
name: agent-os-vault
description: Agent OS × Obsidian 长期知识空间桥接——单向导出视图 / 受控反向导入 / reconcile / provenance / migration
metadata: { "openclaw": { "emoji": "📝" }, "agent_os": { "protocol_version": "1.3", "layer": "core" } }
version: 1.0.0
---

# Agent OS Vault Bridge

## Purpose

把 Agent OS 长期知识对象（Ontology/Knowledge/Experience/Decision/Evidence/Memory）单向只读导出为 Obsidian Vault 视图；支持受控反向导入（Import Candidate → governance gate → accept）；检测漂移（reconcile）；提供 provenance 溯源；首次幂等迁移（migration）。

## 硬边界（不可违背）

- 不改 OpenClaw 核心；不建新 Memory Runtime/DB/GraphDB/VectorDB/Scheduler/EventBus。
- 机器真相源（JSONL/.agent-os/evolution/native memory/Governance/Verification/Security）只读或经治理写。
- 绝不 obsidian→overwrite JSONL。
- Vault 不能成为新 Evidence 源（self-evolution 不消费 Vault）。

## 机器真相源（Source of Truth）

| 对象 | 机器真相源 | Vault 角色 |
|:--|:--|:--|
| Ontology Entity/Relation |  /  | 单向只读导出视图 |
| Knowledge | （经治理导入） | 人类可读视图 + 编辑入口 |
| Experience |  artifacts（change/proposal/regression） | 只读回放视图 |
| Decision |  artifacts（decision 字段） | 只读回放视图 |
| Evidence |  | 只读投影（不可作为新证据源） |
| Memory (journal) | （native） | 轻量投影（存在性 + 来源） |
| Memory (durable) | （已晋升） | 已晋升条目投影 |

## Vault Schema（ 文件）

所有视图文件使用 YAML frontmatter（osv=1）+ 标准 Markdown body + Wikilink。

**通用 frontmatter 字段**：、、uid=1000(admin) gid=1000(admin) groups=1000(admin),988(docker)、、、、。

**Knowledge 额外字段**：、、、、、、。

**Evidence 额外字段**：、、、、。

**Experience 额外字段**：、、、。

**Decision 额外字段**：、、。

## CLI



## Export 流程

1. 读取机器真相源（ontology JSONL / evidence.jsonl / evolution artifacts / native memory）
2. 按 object_type 渲染  文件（frontmatter + body + wikilink）
3. 生成 provenance-map.json（id → 源文件 + 行号 + SHA-256 指纹）
4. 幂等：重复 export 覆盖视图文件，不改源

## Import 流程

1. 解析 Vault  → frontmatter + body
2. Schema 校验（_VALIDATORS 按 object_type）
3. Governance gate 判定（level: deny/review/approve）
4. 生成 Import Candidate → 
5. Reviewer 执行  → accepted →  写回

## Reconcile 流程（3-way 比较）

- origin = 上一次 export 的 provenance-map（机器指纹 + vault_content_fp）
- machine_now = 当前机器真相源指纹
- vault_now = 当前 Vault 视图 content_fp
- 判定：machine-only / vault-only / both-changed / deleted / conflict / in-sync

## Conflict 策略

| 情况 | 处理 |
|:--|:--|
| machine-changed | 重新 export 以机器真相刷新视图 |
| vault-changed（人工编辑） | import-candidate → governance，不直接回写 |
| both-changed | 人工裁决（以 machine 为准重导出，Vault 变更保留供 review） |
| deleted-in-vault | 不删机器真相，Vault 应清理/归档 |
| obsolete | 标记（status=obsolete），不删除 |
| superseded | 保留旧 + superseded_by 指向新 |

## 测试

== 0) 现有 ontology 命令回归（只读，不写 key）==
  [PASS] --status 可运行
  [PASS] --entity 可读取

== 1) Ontology export 测试 ==
  [PASS] --export-vault 退出码 0
  [PASS] 产物存在: ontology/_index.md
  [PASS] 产物存在: ontology/relations.base
  [PASS] 产物存在: ontology/graph.canvas
  [PASS] 产物存在: _meta/META.md
  [PASS] 实体卡片数量=8
  [PASS] 全部实体 id 有卡片

== 2) provenance 完整性（行号 + SHA-256 可回溯）==
  [PASS] 每条实体卡片 provenance_ref 可追溯（行号+指纹重算一致）
  [PASS] META.md 说明 serialization 规则

== 3) 重复 export 幂等性 ==
  [PASS] 两次导出文件集合一致
  [PASS] 二次导出内容一致（除时间戳文件）
  [PASS] 重复导出不损坏 graph.canvas

== 4) obsolete/superseded/contradiction 状态保留 ==
  [PASS] obsolete 实体存在
  [PASS] disputed 实体存在
  [PASS] obsolete status 保留
  [PASS] obsolete 渲染 warning callout
  [PASS] disputed status 保留
  [PASS] contradiction 保留双方不合并
  [PASS] disputed 渲染 warning callout
  [PASS] supersedes 关系作为 wikilink 渲染

== 5) Vault 文件 schema 检查 ==
  [PASS] relations.base 可被 YAML 解析（跳过注释）
  [PASS] relations.base 语法有效(纯 YAML 子集)
  [PASS] graph.canvas JSON 有效
  [PASS] canvas nodes 类型合规
  [PASS] canvas edges 引用的 node 存在
  [PASS] 每张卡片 frontmatter 含必需字段
  [PASS] wikilink 指向 entities/<type>/<id>

===== RESULT: 29 PASS / 0 FAIL =====

## 权限模型

| 操作 | 级别 | 说明 |
|:--|:--|:--|
| export / reconcile / validate / provenance | L1 | 本地可逆写视图 |
| import（生成 candidate） | L1 | 不触真相源 |
| accept（写回 JSONL/.agent-os） | L2/L3 | 需审批 |
| migrate（首次） | L1 | 只写 vault + provenance map |
