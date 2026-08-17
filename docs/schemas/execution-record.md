# Execution Record (Protocol Execution Trace)

> Agent OS v1.3。证明"实际经过了哪些协议节点"——不是新建 Runtime，
> 而是每个 Full Path / 高风险任务附带的一份轻量语义记录。
> OpenClaw 仍是执行者；本记录只回答：**这次行为是否符合 Agent OS Protocol**。

## 定位

```
Protocol Contract 决定"应该经过什么"（SKILL-INTEGRATION.md）
Execution Record 证明"实际经过了什么"（本文件）
```

Execution Record 不是 scheduler / event bus / task runtime，不参与调度；
它是**任务结束时（或高风险动作前后）生成的可审计快照**。

## 何时生成（必做）

- Full Path 任务结束（COMPLETE 或 FAIL/ESCALATE）时。
- Fast Path 中涉及 L2+ 动作的任务（权限门被触发过）。
- 用户/审计要求时（"这次报价为什么完成了？"）。

## Schema

```yaml
protocol:
  version: "1.3"
  path: "full"                # fast | full
  contract: "x-agent-os"      # 引用的 Skill Contract（entry_mode + requires）

task:
  id: "task_xxx"              # task-manager id（如有）
  objective: "一句话目标"
  skill: "business-quote"     # 实际使用的 Skill

steps:
  context:
    status: "completed"       # completed | skipped | conditional
  goal_task:
    status: "completed"       # Goal/Task Semantics（Mandatory）
  task_manager_state_machine:
    status: "skipped"         # 仅 Full Path/长任务才 required
    note: "简单任务无需完整状态机"
  decision:                   # 仅自主任务
    status: "completed"
    result: "EXECUTE"         # 决策词汇表
  permission:
    status: "completed"
    level: "L2"
    result: "ALLOW"           # ALLOW | ASK | DENY | AUTO
  execution:
    status: "completed"
  verification:
    status: "completed"
    level: "V3"
    result: "PASS"            # PASS | PARTIAL | FAIL | UNKNOWN
    evidence: "quotation.xlsx"
  evaluation:
    status: "completed"
    result: "PASS"
  writeback:
    status: "none"            # none | memory | knowledge | ontology
  evolution:
    status: "none"            # none | candidate | applied | blocked
    candidate_id: null
    # 轻量 trace 链（P2）：回答“这次行为改变从哪来、到哪去”
    # 不建 trace runtime，只做关联：exec → evidence → candidate → proposal → change → regression
    trace:
      execution_id: "exec_xxx"     # 本次任务执行 id
      evidence_id: null             # 触发 Evidence（如 LRN-xxx / ERR-xxx）
      candidate_id: null            # Candidate id（若已晋升）
      proposal_id: null             # Proposal 序号/id
      change_id: null               # change-YYYYMMDD-xxx
      regression_id: null           # 回归测试标识（如 T4）
      regression_result: null       # PASS | PARTIAL | FAIL | UNKNOWN

audit:
  operation_id: "op_xxx"      # 副作用操作的幂等 id
  actual_vs_authorized: "within"   # within | exceeded → Security Incident
  notified_user: true         # 高风险操作后是否已通知
```

## 使用规则

- **status 三态**：`completed`（真实经过）/ `skipped`（按 Contract 条件性跳过，需 note）/ `conditional`（按任务类型）。
- 不允许填"假 completed"：某节点没做就不能标 completed（这是审计点，不是装饰）。
- 高风险（L3+ / 资金 / 不可逆）任务的 Execution Record 必须保留到任务结束并可供用户调阅。
- 普通 Fast Path（L0-L1 无副作用）可不生成记录——生成是义务不是开销，无谓记录是噪音。

## 与 OpenClaw 边界

- OpenClaw 拥有：session / execution / tools / tasks / memory storage / approvals / sandbox。
- Agent OS 只记录：本次行为是否符合协议（语义记录，可放 memory 或随任务结果输出）。
- 不建并行 runtime、不拦截执行、不替代 approval。
