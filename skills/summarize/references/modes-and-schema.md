# Summarize 模式与输出 Schema 参考

> 本文档承载 SKILL.md 之外的模式细节与完整输出结构，供实现/复用参考。

## 1. 模式（Mode）

| Mode | 用途 | 输出侧重 |
|---|---|---|
| `quick` | 快速浏览 | 一句话结论 + 3-5 要点 |
| `standard` | 默认 | 核心结论 / 关键点 / 风险 |
| `deep` | 报告/PDF/长文 | 背景/结论/事实/观点/证据/数据/争议/风险/未决问题/来源 |
| `executive` | 决策层 | 发生了什么/为何重要/影响/风险/建议/下一步 |
| `decision` | 方案对比 | 问题/现状/事实/方案/优缺点/风险/建议/待决策 |
| `action` | 只执行 | `action_items[]`（缺 owner/deadline 留 null） |
| `research` | 研究 | 问题/发现/证据/不同观点/矛盾/知识缺口/结论/来源 |
| `meeting` | 会议 | 主题/讨论/已确认/决策/行动项/未决/风险/后续 |
| `conversation` | 对话 | 目标/已确认/已完成/当前方案/约束/决策/待办/下一步 |
| `agent` | Agent 交接 | 结构化 YAML：task/goal/context/facts/decisions/constraints/completed/in_progress/pending/actions/risks/open_questions/entities/relations/user_requirements/sources/confidence |

## 2. 处理管线明细

```text
Input → 内容提取 → 清洗(去导航/广告/页脚噪音) → 结构识别
→ 语义分块(章节/标题/段落边界，硬切需 10-15% overlap)
→ 信息单元提取 → 事实/观点/推断分离 → 重要性排序(S0/S1/S2/S3)
→ 聚类 → 去重(区分 same_claim/same_source/independent_sources)
→ 矛盾检测 → 分层压缩 → 按模式格式化 → 质量验证 → 输出
```

- 长内容用分层摘要（章节→主题→全文→执行摘要），不一次塞满上下文。
- 多文档先逐份理解再交叉综合，禁止盲拼后一次总结；多来源重复不算独立证实。

## 3. 结构化输出 Schema（仅 mode=agent 或 json_output=true 全量）

```yaml
result:
  status: success
  summary: { title, one_liner, executive_summary, key_points: [] }
  structured:
    facts: []      claims: []    conclusions: []  inferences: []
    evidence: []   decisions: [] action_items: []  risks: []
    uncertainties: []  contradictions: []  open_questions: []
    entities: []   relations: []  constraints: []
  state: { completed: [], in_progress: [], pending: [] }
  integrations:
    memory_candidates: []     # working/episodic/semantic/preference/project/experience
    ontology_candidates: { entities: [], relations: [] }
    experience: null          # task/goal/approach/result/success/failures/patterns
  sources: [ { source_id, title, url, author, date, type } ]
  quality: { faithfulness, completeness, relevance, compression, redundancy, attribution, overall }
  warnings: []
```

注意：action_items/decisions 的 owner/deadline/status 未知就留 null；「我倾向 A」≠ 已确认决策；model_inferred 不得伪装成 source_stated。

## 4. 输出规范

默认（用户可读）：结论先行 → 关键信息 → 支撑细节 → 风险/行动项。避免「本文主要介绍了…」等废话；不暴露 chunk id、模型名、质量分数、处理日志。

## 5. 做重要摘要的质量验证（10 问）

1. 每个重要事实能追溯到输入吗？
2. 意思被改了吗？
3. 观点变事实了吗？
4. 预测变确定了吗？
5. 重要结论丢了吗？
6. 有冗余吗？
7. 来源标注对了吗？
8. 行动项真实存在吗？
9. 决策真的确认了吗？
10. 有编造吗？

未过 → 重试或降置信度。内部质量分 `>=0.85 正常 / 0.70-0.84 谨慎 / <0.70 重试`（仅内部信号）。

## 6. 与下游系统的边界

| 系统 | 输入给它的 | 它自己决定 |
|---|---|---|
| Memory | memory_candidates | 是否存/存哪/保留期 |
| Ontology | entity/relation candidates | 实体解析/校验/持久化/合并/图谱维护 |
| Self-Evolving | experience/failure/candidate_rules | 模式是否可靠、是否改进 |
| Agent Browser | 接收页面内容 → 本 Skill 加工 | Browser 管抓取，本 Skill 管压缩提取 |

Summarize 绝不直接改 Memory / Ontology / Skill / 工作流，除非被明确授权。

## 7. 性能与恢复

- 分阶段：便宜提取 → 结构检测 → 语义分析 → 高质量综合 → 验证。
- 模型升级：快模型 → 质检 → 不足 → 强模型。
- 单块失败：重试 → 更小块 → 回退提取，不整任务失败，记 warnings[]。
- 缓存按 input_hash+mode+audience+length；输入/模式/受众变了必须失效。

## 8. 脚本接口

复杂预处理（chunking/去重/多文档聚合）走 scripts/summarize.py，LLM 只做核心抽取与格式化。

```bash
python3 scripts/summarize.py --chunk <file> --overlap 0.15   # 语义分块
python3 scripts/summarize.py --dedup <file>                  # 多文档去重
python3 scripts/summarize.py --aggregate <dir>               # 多文档聚合
python3 scripts/summarize.py --extract <text> --mode agent   # 结构化提取骨架
```
