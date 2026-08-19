# Execution Record (Protocol Execution Trace)

> Agent OS v1.3。证明"实际经过了哪些协议节点"——不是新建 Runtime，
> 而是每个 Full Path / 高风险任务附带的一份轻量语义记录。
> OpenClaw 仍是执行者；本记录只回答：**这次行为是否符合 Agent OS Protocol**。
>
> **P1（2026-08-17 升级）**：从 P2 升为 P1。可追溯性是 Agent OS 的核心能力——
> 必须能回答"这次行为从哪来、到哪去、为什么改"。仍只做语义关联，不建 trace runtime。

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

## 谁创建（v1.3 强制，防止有的任务有 record、有的没有）

| 场景 | 责任方 | 规则 |
|:--|:--|:--|
| Full Path 任务 | 执行该任务的 Agent（或 Orchestrator 编排者） | **MUST** produce Execution Record |
| L2+ 动作（Fast 或 Full） | 执行动作的 Agent | **MUST** produce Execution Record |
| Evolution Apply（任何 change） | self-evolution / 执行 Apply 的 Agent | **MUST** produce Execution Record |
| Fast Path L0/L1 | 执行 Agent | **MAY** omit（无副作用低风险不产生噪音） |

> 不允许“Skill 自己决定要不要、Orchestrator 认为 Verification 会记、Verification 以为 Skill 记”。
> 归属明确：**谁执行，谁创建**；Evolution Apply 由进化路径单独强制。
> 创建时机：任务结束时（或高风险动作前后），作为可审计快照随结果输出或存 memory。

## Schema

```yaml
# v1.3.1: execution 顶层元数据（P1-1）
# 回答"这次执行是谁、什么时候、什么触发的"——多 Agent 场景必备。
execution:
  id: "exec_xxx"              # 唯一执行 id（exec-YYYYMMDD-xxx）
  actor: "agent-main"         # 执行者（agent-main / agent-research / agent-trader / ...）
  trigger: "user"             # 触发来源（user / heartbeat / cron / hook / proactive）
  started_at: "2026-08-17T10:00:00+08:00"
  ended_at: "2026-08-17T10:02:30+08:00"

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
    # 轻量 trace 链（P1）：回答“这次行为改变从哪来、到哪去”
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

## Provenance（跨 Agent 硬约束，v1.3.1）

> 任何跨 Agent 操作不得丢失 origin。A → B → C 委托链中，最终记录必须能追溯回 origin。
> 对应 PROTOCOL.md §8.2。

```yaml
# 当前执行者（必填）
agent_id: "agent-c"                # 当前执行 Agent
session_id: "ses_xxx"             # 当前 OpenClaw session

# 当前执行的实体 id（必填）
execution_id: "exec_xxx"
task_id: "task_xxx"               # 当前任务 id
operation_id: "op_xxx"            # 副作用幂等 id（跨 agent 去重用）
correlation_id: "corr_xxx"         # 关联 id：串联一次业务请求的多次执行
parent_task_id: "task_xxx"         # 上级任务 id（委托/子任务时必填）

# 跨 Agent delegation chain（任意一层有跨 Agent 委托时必填）
origin_agent: "agent-a"           # 最初的发起者
parent_agent: "agent-b"           # 直接上级（若无则同 origin）
delegation_chain: ["agent-a", "agent-b", "agent-c"]  # A → B → C
current_agent: "agent-c"          # 当前执行者

# 校验（MA-1.0 validate_ma_consistency）
provenance_complete: true          # origin/parent/current 齐全
cross_agent_ok: true               # 委托链完整、未丢失 origin
```

**约束**：
- 无跨 Agent 场景（单 Agent 独立执行）：`origin_agent = current_agent`，chain 可省略。
- 有跨 Agent 场景：`origin_agent` / `delegation_chain` / `current_agent` 必填，缺失视为 provenance 不完整 → 审计点。
- `correlation_id` 用于把 A→B→C 的多段 Execution Record 串联成一条业务链路；禁止中间层新建 correlation 而丢弃原始关联。
- `parent_task_id` 记录每一层的直接上级，用于还原 delegation 树。
- 应经 `validate_ma_consistency`（execution_record 代码）校验 cross_agent / cross_task / duplicate_operation / parent_forgery。
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
