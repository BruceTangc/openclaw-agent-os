# Self-Evolution 治理与 Skill 进化参考

> 治理分级、提案、验证、回滚、Skill 进化、安全边界的详细定义。

## 1. 治理分级

### Auto Apply（低风险）
私有记忆、已验证事实性知识、去重清理、明确用户偏好（过持久化检查后）、低风险项目笔记。

### Proposal Required（行为变更）
Agent 行为、Skill 行为、项目工作流、cron 行为、AGENTS.md、SOUL.md、共享记忆、已晋升规则的降级。

### Explicit Approval Required（高风险，人工审批）
权限、凭证、外部通信、财务动作、数据删除、安全设置、自动交易、系统级变更、GLOBAL 策略变更。**绝不绕过**。

## 2. 提案格式

```markdown
## Proposal PROP-YYYYMMDD-NNN

### Type
promotion | demotion | skill_change | policy_change | verification | critical_fix

### Source Agent
...
### Target Scope
AGENT | PROJECT | USER | GLOBAL
### Target
...
### Change
...
### Evidence
...
### Confidence
...
### Risk
low | medium | high | critical
### Expected Impact
...
### Rollback / Demotion Path
...
### Status
pending
```

用户回应：`approve N` / `skip N`。

## 3. 验证

每次重要晋升/降级/Skill 变更须带：

```markdown
### Verification
Before: error rate = 18%
After:  error rate = 11%
Metric: next 20 tasks
Result: improved
Action: reinforce
```

## 4. 动态验证期

```text
low-risk change    → 3 days
normal workflow    → 7 days
important behavior → 14 days
core architecture  → 30 days
```

## 5. 跨 Agent 验证

PROJECT/GLOBAL 晋升：源 Agent 测试 → 至少一个相关 Agent 测试 → 对比结果 → 证据支持更宽作用域且上下文独立才晋升。防专家错误变全局。

## 6. 回滚 / 降级

回归/重复拒绝/新工具失败/安全风险/指标变差 → 标记失败 + 恢复旧行为（Revert）或收窄作用域（Demote）+ 记因 + 降置信度/衰减 + 阻断同类自动晋升。

降级路径：GLOBAL→PROJECT、PROJECT→AGENT、任何更宽→更窄（发现上下文依赖）。降级优于完全删除（更窄仍有用）。

```bash
python3 scripts/learn.py --rollback <change_id>
python3 scripts/learn.py --demote <change_id> --to <scope>
```

## 7. Anti-Loop / Anti-Overfit

- 同学习反复验证失败 → failure_count++ → status=blocked_learning，不自动再晋升，需人工复核。
- 晋升前问：一般？项目特有？Agent 特有？工具特有？用户特有？临时？上下文依赖？存最窄有效作用域。

## 8. Skill 进化

复杂工作流成功（或产生有价值中间态）时：

1 搜索现有 Skill → 2 搜索重叠 Skill → 3 判断是否已存在 → 4 改进现有 → 5 合并重叠 → 6 仅全新才新建。

不因任务重复就生成重复 Skill。

**双向反馈**：Skill 执行结果（成功/失败/近失败/回归）反哺 Learning Engine 更新置信度/触发重分类/生成新候选；Skill 变更（尤其 MAJOR/MINOR）触发相关学习重新验证。

## 9. Skill 生成条件

```text
8+ 有意义 tool calls 且涉及 write/exec/workflow
或同工作流重复 >=2 次
或发现新可复用工作流
或用户明确要求记住工作流
或有价值中间态模式反复出现
```

创建前：搜索 memory/skills + 已装 Skill + 对比描述。

## 10. Skill 归属 / 版本 / 去重

归属声明：owner_agent / project / scope / dependencies / shared_with / version。

版本用 MAJOR/MINOR/PATCH，记录 problem/evidence/change/expected benefit/risk/verification metric/result。MAJOR/MINOR 变更须与基线对比验证，失败触发降级或回滚。

去重：duplicate→reuse；overlapping→merge/improve；extension→update；new→propose。

## 11. 安全边界（严禁自改，须人工审批）

```text
权限规则、安全策略、凭证处理、外部副作用规则、核心 Runtime 行为
```

绝不为提高完成率削弱安全；绝不因减少上下文删除有用知识。

## 12. 禁止行为清单

- 单次失败→立即自改
- 削弱安全换完成
- 静默覆盖自己之前策略
- 绕过 Permission Gate 做「修复」
- 自动批准自己变更
- 发明记忆/决策；单次错误升原则；广播全部学习；覆盖他人私有记忆；
  静默改用户偏好/全局策略；建重复 Agent/Skill；忽略矛盾；
  无证据声称验证；存 Secret；用 exec 读 session；不 read 就 edit。

## 13. 文件安全铁律

编辑任何文件前先 `read`，从返回内容构造精确 edit，绝不自造 oldText。

Session 文件：不用 `exec/cat/tail/grep/wc/jq` 处理原始 session 文件做 L1 总结；用 `sessions_list` + `sessions_history`；不可用则跳过不猜。

## 14. 成功指标

目标：更少错误、更少重复、更好连续性、更好专精、更好共享、更少重复、更可靠 Skill、必要时健康降级。**不是**更多记忆/Agent/Skill/自动变更。
