---
name: agent-os-vault
description: Agent OS × Obsidian 长期知识空间桥接——单向导出视图 / 受控反向导入 / reconcile / provenance / migration
metadata: { "openclaw": { "emoji": "📝" }, "agent_os": { "protocol_version": "1.3", "layer": "business" } }
version: 1.0.0
x-agent-os:
  protocol_version: "1.3"
  layer: "business"
  trigger: "user|cron|hook"
  path:
    fast: true
    full: true
  entry_mode: "both"
  requires:
    context: true
    goal_task_semantics: true
    task: conditional
    decision: conditional
    orchestrator: conditional
    permission: true
    verification: true
    evaluation: conditional
    writeback: conditional
    evolution: conditional
  capabilities:
    - read          # L0：读取机器真相源 / Vault 视图
    - export        # L1：生成 Vault 视图（本地可逆写）
    - reconcile     # L1：只读 drift 检测
    - validate      # L1：schema/provenance 校验
    - import        # L2：生成 Import Candidate（逐步审批）
    - accept        # L3：受控写回 JSONL/.agent-os（需审批）
  permissions:
    export: L1
    reconcile: L1
    validate: L1
    provenance: L1
    import: L1
    candidate-status: L2
    accept: L3
    migrate: L1
  delegation:
    max_level: "L1"
    inherit_parent: false
    requires_scope: true
  outputs:
    success_condition: required
    evidence: required
  verification: "V2"
  memory_write: "governed"
  knowledge_write: "governed"
  evolution_feedback: true
---

# Agent OS Vault Bridge

## Purpose

把 Agent OS 长期知识对象（Ontology/Knowledge/Experience/Decision/Evidence/Memory）单向只读导出为 Obsidian Vault 视图；支持受控反向导入（Import Candidate → governance gate → accept）；检测漂移（reconcile）；提供 provenance 溯源；首次幂等迁移（migration）。

Agent OS 本体仍是**唯一机器真相源**；Obsidian Vault 只是其**人工可读投影 + 编辑入口**。反向导入任何机器真相变更都必须走本 Skill 的 import → candidate → **现有 Agent OS Governance** → accept 通道，**绝不 obsidian→overwrite JSONL**。

## 硬边界（不可违背）

- 不改 OpenClaw 核心；不建新 Memory Runtime/DB/GraphDB/VectorDB/Scheduler/EventBus。
- 机器真相源（JSONL/.agent-os/evolution/native memory/governance/verification/security）只读或经既有治理写。
- 绝不 obsidian→overwrite JSONL。
- Vault 不能成为新 Evidence 源（self-evolution 不消费 Vault）。
- **Obsidian 是不可信输入**：所有 Vault 输入（frontmatter 的 confidence / provenance_ref / status / entity_id / relation / evidence_ref）都必须经本 Skill 的 Schema → Identity → Provenance → Governance → Truth Source 校验链，不因文件在自己的 Vault 里就信任。

## 机器真相源（Source of Truth）与 Vault 角色

> 机器真相 = JSONL / `.agent-os` / OpenClaw native memory；Obsidian = 投影 + 人工编辑面。
> 下列路径为 Skill 实际读取的真相源位置。`<BRIDGE_WS>` 统一取 OpenClaw workspace
>（兼容旧 `AGENT_OS_VAULT_WORKSPACE`）；Vault 根目录必须由 `AGENT_OS_VAULT_DIR`
> 或 CLI `--vault` 显式提供，未配置时集成保持禁用。

| 对象 | 机器真相源（真实路径） | Vault 角色 |
|:--|:--|:--|
| Ontology Entity | `<REPO>/skills/ontology/memory/ontology/entities.jsonl`（append-only JSONL） | 单向只读导出 `ontology/entities/<type>/<id>.md` |
| Ontology Relation | `<REPO>/skills/ontology/memory/ontology/relations.jsonl` + `schema.json` + `proposals.jsonl` | 只读 `ontology/relations.base` + `graph.canvas` |
| Evidence | `<BRIDGE_WS>/.agent-os/evolution/evidence.jsonl`（self-evolution `_core.register_evidence` 唯一写入） | 只读投影 `evolution/evidence/<evid>.md`（不可作为新证据源） |
| Experience | `<BRIDGE_WS>/.agent-os/evolution/{changes,proposals,candidates,regressions}/<id>.json` | 只读回放 `evolution/experience/` |
| Decision | 同上 evolution artifacts 的 `decision` 字段 | 只读回放 `evolution/decisions/` |
| Knowledge | Obsidian 可选持久化目标（本 skill registry：`<BRIDGE_WS>/.agent-os-vault/registry.jsonl` 为接入 knowledge-governance 的治理导入书签；正式治理身份由 knowledge-governance 承担） | 人类可读视图 `knowledge/` + 编辑入口 |
| Memory (journal) | OpenClaw native `memory/YYYY-MM-DD.md` | 轻量投影 `memory/journal/`（存在性 + 来源） |
| Memory (durable) | OpenClaw native `MEMORY.md`（memory-governance 已晋升） | 已晋升条目投影 `memory/durable/` |

本体 JSONL / evidence.jsonl / evolution artifacts 由原模块**唯一写入**（ontology.py、self-evolution `_core`、memory-governance）。
本 skill 对它们**只读**；机器真相的任何变更只能经 import → candidate → 现有 governance → accept 回流。

## Vault Schema（frontmatter）

所有视图文件使用 YAML frontmatter（`osv=1`）+ 标准 Markdown body + Wikilink。

**通用 frontmatter 字段**：`osv`、`object_type`、`id`、`scope`、`status`、`confidence`、`freshness`、`validity`、`source_type`、`provenance_ref`、`source_agent`、`created_at`、`updated_at`。

**Knowledge 额外字段**：`claim`、`subject`、`evidence_refs`、`contradicts`、`superseded_by`、`related`。

**Evidence 额外字段**：`source`、`event_type`、`pattern_key`、`verified`、`agent_id`。

**Experience 额外字段**：`source_kind`、`source_id`、`pattern_key`、`target`。

**Decision 额外字段**：`decision`、`objective`、`reason`。

## CLI

```
agent_os_vault.py export|reconcile|validate|import|candidates|candidate-status|accept|provenance|migrate|status
```

## Export 流程

1. 读取机器真相源（ontology JSONL / evidence.jsonl / evolution artifacts / native memory）
2. 按 object_type 渲染视图文件（frontmatter + body + wikilink）
3. 生成 provenance-map.json（id → 源文件 + 行号 + SHA-256 指纹）
4. 幂等：重复 export 覆盖视图文件，不改源

## Import 流程（受控反向导入，先过校验再走现有 Governance）

1. 解析 Vault → frontmatter + body
2. **Schema 校验**（_VALIDATORS 按 object_type）
3. **Provenance 校验（P1-1）**：provenance_ref 必须经机器真相源验证——源记录存在 + SHA-256 指纹重新计算一致；**不信任 Vault 自带 hash**；伪造/不存在/指纹不匹配 → 拒绝
4. **Identity 校验（P1-2）**：用 `_lib/identity.py` 生成候选身份链，跨 Agent 归属检查
5. **ontology-consistency**：subject/predicate/object 参照现有 ontology
6. **Contradiction 预检**：对照现有 knowledge registry 标记潜在矛盾
7. Governance gate 判定（level: deny/review/approve）→ 生成 Import Candidate
8. Reviewer 执行 `candidate-status → accepted` → `accept`（**accept 前再次机器复核 provenance**）
9. 本体变更经 `ontology.py --propose` 原生治理通道落库；knowledge 写入接入 knowledge-governance 的治理书签

**reverse import 绝不 bypass Governance**：候选仅表示"人工编辑意图"，未经治理 gate 批准不写任何机器真相。

## Reconcile 流程（3-way 比较）

- origin = 上一次 export 的 provenance-map（机器指纹 + vault_content_fp）
- machine_now = 当前机器真相源指纹
- vault_now = 当前 Vault 视图 content_fp
- 判定：machine-only / vault-only / both-changed / deleted / conflict / in-sync
- deleted 覆盖 entity/relation/evidence/knowledge/experience/decision（机器真相消失才标 deleted，只提示清理，绝不动 JSONL）

## Conflict 策略

| 情况 | 处理 |
|:--|:--|
| machine-changed | 重新 export 以机器真相刷新视图 |
| vault-changed（人工编辑） | import-candidate → governance，不直接回写 |
| both-changed | 人工裁决（以 machine 为准重导出，Vault 变更保留供 review） |
| deleted-in-vault | 不删机器真相，Vault 应清理/归档 |
| deleted-in-machine | 机器真相已删/标 deleted，Vault 视图清理/归档 |
| obsolete | 标记（status=obsolete），不删除 |
| superseded | 保留旧 + superseded_by 指向新 |
| contradiction | 保留双方，标 disputed（不静默合并） |

## 权限模型

| 操作 | 级别 | 说明 |
|:--|:--|:--|
| export / reconcile / validate / provenance | L1 | 本地可逆写视图 |
| import（生成 candidate） | L1 | 不触真相源 |
| candidate-status | L2 | 候选状态流转 |
| accept（写回 JSONL/.agent-os） | L2/L3 | 需审批 + 机器 provenance 复核 |
| migrate（首次） | L1 | 只写 vault + provenance map |

## 测试

见 `docs/tests/scripts/agent_os_vault_test.py`（58 现有测试 + provenance/governance 增强）。
现有 ontology 导出回归、provenance 完整性、重复导出幂等、状态保留、schema 检查均 PASS。
