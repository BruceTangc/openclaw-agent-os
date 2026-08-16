---
name: self-evolution
version: 3.2.2
description: >
  Multi-Agent Learning OS for OpenClaw. Provides centralized experience
  capture (including intermediate states), shared/project/agent memory,
  Agent Registry, Learning Bus, confidence-based learning with evidence
  decay, decision memory, skill evolution with bidirectional feedback,
  verification, contradiction detection & resolution, demotion, forgetting,
  governance and rollback.
---
# Agent OS v1.1 Policy（正式版政策层, 来自整合包）

# OpenClaw Skill
## Compatibility baseline: OpenClaw 2026.7.1-2

# Self-Evolution

Purpose: improve skills/workflows/policies through controlled evidence.

## Evidence
verified failure, repeated user correction, repeated evaluation weakness, recurring inefficiency, or stable new requirement.

## Loop
Observe -> Verify -> Diagnose -> Propose -> Test -> Evaluate -> Approve -> Apply -> Regression check.

Low-risk instruction/workflow improvements may follow an existing authorization policy. Changes to security, permissions, external side-effect rules or core runtime require explicit human approval unless already authorized.

Never weaken security for completion. Never self-modify from one unverified failure.

---

# 本地实现部分（完整版, 保留）

# Self-Improvement LLM V3.2.2 — Multi-Agent Learning OS

## 1. Purpose

Turn an OpenClaw installation with many Agents into one coordinated learning system.

Core principle:

> Many Agents, one Learning OS.

Agents may have private expertise, but learning must be classified by scope before it is shared.

Core loop:

```text
Task
 ↓
Experience (including intermediate states)
 ↓
Detection
 ↓
Classification
 ↓
Candidate Learning
 ↓
Scope Resolution (default: narrowest)
 ↓
Confidence / Evidence Decay / Contradiction Check
 ↓
Governance
 ↓
Private / Project / User / Global Promotion
 ↓
Verification
 ↓
Reinforce / Demote / Revert / Expire
```

Never treat a single observation as permanent truth.

---

# 2. Architecture

```text
                         OpenClaw
                            │
              ┌───────────▼───────────┐
              │  Global Scheduler     │
              │  (Global Learning     │
              │   Cycle / Cron)       │
              └───────────┬───────────┘
                    ┌───────▼────────┐
                    │  Learning OS   │
                    │ Central Brain  │
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   Shared Memory       Project Memory      Agent Memory
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ↓
                     Learning Bus
                            │
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
           Agent A       Agent B       Agent C
              │             │             │
              └─────────────┼─────────────┘
                            ↓
                  Verification / Governance
```

The Learning OS is centralized.

Do NOT create an independent learning system for every Agent unless there is a technical reason.

---

# 3. Seven Core Engines

## 3.1 Experience Engine

Captures:

- corrections
- errors
- successes
- feature requests
- knowledge gaps
- discoveries
- workflow improvements
- verification results
- **intermediate states** (near-miss, almost-failure, partial-success, delayed-failure)

Raw experience is evidence, not truth.

Intermediate states are especially valuable for Skill Evolution and should enter the Candidate layer rather than being discarded as noise.

## 3.2 Memory Engine

Manages:

- Global Memory
- User Memory
- Project Memory
- Agent Private Memory
- Session Memory
- Decision Memory

## 3.3 Learning Engine

Handles:

- classification
- deduplication
- confidence (with evidence & time decay)
- recurrence
- contradiction detection & resolution
- promotion
- demotion
- forgetting

## 3.4 Agent Registry

Tracks:

- Agent ID
- role
- purpose
- project
- skills
- permissions
- memory scope
- status
- capability overlap

## 3.5 Learning Bus

Provides controlled cross-Agent learning events.

An Agent does not directly overwrite another Agent's memory.

## 3.6 Skill Evolution Engine

Determines whether to:

- reuse an existing Skill
- improve an existing Skill
- merge overlapping Skills
- create a new Skill proposal

Maintains **bidirectional feedback** with the Learning Engine:
- Learning can drive Skill change
- Skill usage outcomes (success / failure / near-miss) feed back into Learning confidence and re-classification

## 3.7 Governance + Verification Engine

Controls:

- auto-apply
- proposal
- approval
- verification
- demotion
- rollback
- expiration

---

# 4. Memory Scope

Every learning item MUST have a scope.

Allowed scopes:

```text
TASK
AGENT
PROJECT
USER
GLOBAL
```

Meaning:

### TASK

Only valid for the current task/session.

### AGENT

Only valid for one specialist Agent.

Example:

```text
short-term-trader:
某种短线信号在特定市场环境下容易误判
```

### PROJECT

Shared by Agents participating in one project.

Example:

```text
A股模拟交易项目:
所有交易 Agent 必须使用新鲜行情数据
```

### USER

A stable user preference or constraint.

Example:

```text
用户希望复杂任务一次性整理完整方案
```

### GLOBAL

General Agent principle applicable across OpenClaw.

Example:

```text
编辑文件前必须先读取当前内容
```

GLOBAL should be the hardest scope to promote into.

**Default principle**: always store at the narrowest valid scope. Wider scope requires explicit evidence that the learning is context-independent.

---

# 5. Scope Promotion

Learning should not be copied blindly.

It should be promoted when evidence supports a wider scope.

Example:

```text
Agent discovery
 ↓
AGENT
 ↓ verification
PROJECT
 ↓ independent evidence of context-independence
GLOBAL
```

Never promote:

```text
AGENT → GLOBAL
```

just because it occurred three times.

The system must ask:

```text
Is it Agent-specific?
Project-specific?
User-specific?
Tool-specific?
General?
Temporary?
Context-dependent?
```

Store information at the narrowest valid scope.

Promotion to a wider scope requires proof that the learning does **not** depend on local context (tool version, market regime, user temporary preference, Agent specialization assumption, etc.).

---

# 6. Shared Memory Architecture

Recommended structure:

```text
memory/
├── global/
│   ├── PRINCIPLES.md
│   ├── KNOWLEDGE.md
│   └── DECISIONS.md
│
├── user/
│   ├── USER.md
│   └── preferences.json
│
├── projects/
│   └── <project>/
│       ├── STATE.md
│       ├── DECISIONS.md
│       ├── TASKS.md
│       └── LEARNINGS.md
│
├── agents/
│   └── <agent-id>/
│       ├── MEMORY.md
│       ├── LEARNINGS.md
│       └── DECISIONS.md
│
├── sessions/
├── skills/
├── .learning-trail.json
└── .memory-index.json
```

If the existing OpenClaw installation uses another memory layout, adapt to the existing structure instead of blindly creating duplicates.

---

# 7. Agent Registry

Maintain:

```text
memory/agents/REGISTRY.md
```

Recommended format:

```markdown
# Agent Registry

## Agent: short-term-trader

ID: short-term-trader
Role: A股短线交易
Project: A股模拟交易
Status: active

Skills:
- market-data
- technical-analysis
- paper-trading

Memory Scope:
- AGENT
- PROJECT

Shared Learning:
- allowed

Critical Actions:
- approval required
```

The registry should answer:

```text
有哪些 Agent？
每个 Agent 是干什么的？
属于哪个项目？
有哪些 Skill？
哪些 Agent 能共享哪些记忆？
哪些 Agent 权限较高？
```

---

# 8. Agent Capability Registry

Track capabilities:

```text
Agent
 ├── domain
 ├── skills
 ├── tools
 ├── projects
 └── permissions
```

When a new Agent is created, compare its capabilities with existing Agents.

If overlap is high:

```text
duplicate
overlapping
specialized variant
```

Do not automatically create another Agent.

Generate a consolidation proposal when useful.

---

# 9. Agent Lifecycle

```text
PROPOSED
 ↓
CREATED
 ↓
ACTIVE
 ↓
SUSPENDED
 ↓
DEPRECATED
 ↓
ARCHIVED
```

When an Agent becomes obsolete:

1. preserve its decisions
2. preserve useful learning
3. mark its Skills
4. transfer verified Project knowledge
5. archive its private memory
6. remove duplicate capabilities only after confirmation

Never silently delete Agent history.

---

# 10. Learning Bus

The Learning Bus is the controlled communication layer between Agents and the central Learning OS.

An Agent emits:

```json
{
  "event": "learning_candidate",
  "source_agent": "short-term-trader",
  "scope": "AGENT",
  "topic": "market-data-freshness",
  "content": "必须验证行情时间戳",
  "confidence": 82,
  "project": "A股模拟交易",
  "evidence": [
    "error-20260813-001",
    "session-20260813-002"
  ]
}
```

The Learning OS then decides:

```text
keep AGENT
promote PROJECT
propose USER
propose GLOBAL
demote
reject
```

Agents must not directly write to:

```text
GLOBAL
USER
another Agent's private memory
```

without passing through governance.

---

# 11. Cross-Agent Learning

When Agent A learns something:

```text
Agent A
 ↓
Learning Bus
 ↓
Learning OS
 ↓
Scope Resolver
 ↓
Relevant Agents (after context filter)
```

Only Agents whose:

- project
- domain
- skill
- tool
- task

matches the learning **and** for whom the learning is judged context-compatible should receive it.

Do not broadcast every learning event to every Agent.

**Default stance**: treat learning as local until proven context-independent.

---

# 12. Relevant-Agent Matching

A learning candidate can be shared when:

```text
same project
OR
same tool
OR
same domain
OR
same workflow
OR
explicit dependency
```

**AND** the learning passes the context-independence check (or is explicitly scoped to the matching context).

Example:

```text
short-term-trader:
API X requires timestamp validation
```

Relevant:

```text
long-term-trader
market-data-agent
risk-agent
```

Potentially irrelevant:

```text
warehouse-agent
quotation-agent
```

If the learning depends on a specific tool version, market regime, or Agent specialization assumption, keep it at AGENT or PROJECT scope and do not auto-propagate further.

---

# 13. Experience Detection

Automatically detect:

### Corrections

Examples:

```text
不对
错了
不是这样
实际上应该是
That's wrong
That's outdated
```

Log to:

```text
.learning-trail.json
```

### Errors

Examples:

- non-zero exit code
- exception
- timeout
- connection failure
- wrong API result
- invalid assumptions

### Successes

Examples:

- faster workflow
- more reliable workflow
- successful correction
- cleaner reusable pattern

### Intermediate States (important)

- near-miss (almost succeeded)
- almost-failure (nearly failed but recovered)
- partial-success (correct in part, hidden defect remains)
- delayed-failure (appeared successful at the time, failed later)

These intermediate states should enter Candidate Learning; they are often more informative than pure success or pure failure.

### Feature Requests

Do not automatically turn every feature request into a permanent preference.

### Knowledge Gaps

Record when:

- user provides unknown information
- documentation is outdated
- actual tool behavior differs from assumptions

---

# 14. Learning Classification

Every candidate must be classified:

```text
user_preference
user_constraint
project_fact
project_decision
agent_knowledge
tool_knowledge
workflow
behavior_rule
universal_principle
skill_improvement
temporary_context
intermediate_state
noise
```

Example:

```text
"这次详细一点"
→ TASK

"以后直接给我完整方案"
→ USER candidate (only if persistence criteria met)

"这个项目不用妙想自选"
→ PROJECT decision

"这个交易 API 必须检查时间戳"
→ AGENT/PROJECT candidate

"所有文件修改前必须 read"
→ GLOBAL principle
```

---

# 15. Learning Candidate Layer

All new learning enters:

```text
candidate
```

before promotion.

Recommended data:

```json
{
  "id": "LRN-20260813-001",
  "type": "workflow",
  "scope": "AGENT",
  "source_agent": "example-agent",
  "project": "example-project",
  "content": "...",
  "first_seen": "...",
  "last_seen": "...",
  "recurrence": 1,
  "sessions": [],
  "user_confirmed": false,
  "confidence": 0,
  "effective_confidence": 0,
  "status": "candidate",
  "contradicts": [],
  "supersedes": [],
  "evidence": [],
  "context_dependencies": [],
  "verification": {
    "required": true,
    "due": null,
    "result": null
  }
}
```

---

# 16. Confidence & Evidence Decay

Confidence should combine:

```text
recurrence
cross-session evidence
cross-Agent evidence
user confirmation
successful verification
source reliability
recency
contradictions
evidence quality
```

Suggested range:

```text
0–30   weak
31–50  tentative
51–70  probable
71–85  strong
86–95  highly reliable
96–100 established
```

Three repetitions alone must not create a high-confidence global rule.

**Evidence & time decay** (logical requirement):

Effective confidence is not static. It must decay when:

- evidence ages without reinforcement
- newer contradictory or superseding evidence appears
- the original context (tool version, environment, user state) no longer holds

Conceptual form:

```text
effective_confidence = base_confidence
                     × recency_factor
                     × evidence_quality
                     × (1 - contradiction_penalty)
```

Old high-recurrence rules must not permanently lock out newer verified evidence.

---

# 17. Promotion Rules

Default:

```text
recurrence >= 3
AND
sessions >= 2
AND
no active contradiction
AND
context-independence supported (for wider scopes)
```

Suggested minimum confidence (effective):

```text
AGENT workflow        >= 70
PROJECT workflow      >= 75
USER preference       >= 80
tool knowledge        >= 80
behavior rule         >= 85
GLOBAL principle      >= 90
```

Explicit user confirmation can accelerate promotion, but safety and governance still apply.

---

# 18. Contradiction Detection & Resolution

Before promotion:

```text
search Agent memory
search Project memory
search User memory
search Global memory
search Decisions
```

Detect:

```text
direct contradiction
partial contradiction
superseding information
obsolete information
scope-specific exception
```

Example:

```text
Old:
用户喜欢详细回答

New:
以后直接给我结论

Action:
old = superseded
new = active
```

Never keep directly contradictory active rules without defining their scope.

**Conflict resolution priority** (when two active learnings conflict):

1. Current explicit user instruction (when safe and valid)
2. Newer verified evidence over older
3. Narrower scope over wider scope (local preferred)
4. Higher effective confidence + stronger verification
5. If still unresolved → mark Unresolved, block automatic application, require human review

Do not force a single false global rule.

---

# 19. Scope Resolution Priority

When instructions conflict:

```text
CURRENT EXPLICIT INSTRUCTION
>
CURRENT TASK
>
PROJECT DECISION
>
AGENT-SPECIFIC RULE
>
USER PREFERENCE
>
GLOBAL PRINCIPLE
>
GENERIC KNOWLEDGE
```

Current explicit user instructions always win when safe and valid.

---

# 20. User Memory

User preferences should be stored separately from Agent knowledge.

Store:

- communication preferences
- stable workflow preferences
- recurring requirements
- long-term goals when explicitly known
- stable constraints

Do not infer sensitive personal attributes.

**Persistence judgment** (logical rule):

Temporary instructions remain TASK-scoped unless clear persistence signals exist:

- explicit persistent language (“以后 / 总是 / 下次都 / 永远 / always / from now on”)
- repeated across independent sessions
- no strong conflict with existing USER preferences

Only when these conditions are met may a preference enter USER candidate. Otherwise keep it TASK or AGENT.

---

# 21. Project Memory

Complex projects MUST have project state.

Recommended:

```text
memory/projects/<project>/
├── STATE.md
├── DECISIONS.md
├── TASKS.md
└── LEARNINGS.md
```

STATE.md:

```markdown
# Project State

## Current Version
...

## Current Architecture
...

## Confirmed Decisions
...

## Completed
...

## In Progress
...

## Blocked
...

## Next Actions
...
```

Project memory is shared by participating Agents.

---

# 22. Decision Memory

Important decisions should be stored in:

```text
memory/projects/<project>/DECISIONS.md
```

Format:

```markdown
## DEC-YYYYMMDD-NNN

### Decision
...

### Context
...

### Reason
...

### Alternatives Rejected
...

### Consequences
...

### Confidence
...

### Review Condition
...

### Status
active
```

Statuses:

```text
active
superseded
rejected
expired
reverted
demoted
```

When an Agent encounters a previously decided question, retrieve the decision before reopening it.

**Boundary with Learning**:

- Decision = constraint on future action (“must do X”)
- Learning = knowledge about the world (“X is true / X tends to happen”)

A high-confidence Learning that carries action force may be proposed for upgrade into a Decision.  
A Decision that is falsified should generate a reverse Learning (and possibly demotion), not merely change status.

Every important Decision should carry an explicit review condition or validity trigger (tool/version change, environment shift, user feedback, etc.).

---

# 23. Agent Private Memory

Private memory is for:

- specialist heuristics
- Agent-specific mistakes
- Agent-specific workflows
- internal tool usage patterns
- domain-specific observations

Private learning should not automatically become shared learning.

---

# 24. Learning Promotion Matrix

| Source | Default Target | Promotion |
|---|---|---|
| Agent observation | AGENT | automatic if verified |
| Same-project repeated learning | PROJECT | confidence threshold + context check |
| Stable user instruction | USER | confirmation / high confidence + persistence check |
| Cross-project verified principle | GLOBAL | proposal + context-independence proof |
| Security/permission rule | never automatic GLOBAL | approval |
| Tool-specific knowledge | relevant Agents | controlled sharing |
| Temporary context | TASK | expires |
| Intermediate state | usually AGENT / PROJECT | candidate first |

---

# 25. Skill Evolution

When a complex workflow succeeds (or yields valuable intermediate states):

```text
1. Search existing Skills.
2. Search overlapping Skills.
3. Determine whether the workflow already exists.
4. Improve existing Skill if possible.
5. Merge overlapping Skills if appropriate.
6. Create a new Skill only when genuinely new.
```

Never generate duplicate Skills just because a task is repeated.

**Bidirectional feedback**:

- Outcomes of Skill execution (success, failure, near-miss, regression) must feed back into the Learning Engine to update confidence, trigger re-classification, or generate new candidates.
- Changes to a Skill (especially MAJOR / MINOR) should trigger re-verification of related Learnings.

---

# 26. Skill Generation Conditions

Candidate generation when:

```text
8+ meaningful tool calls
AND
write/exec/workflow involved
```

OR:

```text
same workflow repeated >= 2 times
```

OR:

```text
new reusable workflow discovered
```

OR:

```text
user explicitly asks to remember the workflow
```

OR:

```text
valuable intermediate-state pattern observed repeatedly
```

Before creation:

```text
search memory/skills/
search installed Skills
compare descriptions
```

---

# 27. Skill Ownership

Every Skill should declare:

```text
owner_agent
project
scope
dependencies
shared_with
version
```

Example:

```yaml
name: market-data-validation
owner_agent: market-data-agent
project: A股模拟交易
scope: PROJECT
shared_with:
  - short-term-trader
  - long-term-trader
  - risk-agent
version: 1.2.0
```

Global Skills should be rare.

---

# 28. Skill Versioning

Use:

```text
MAJOR
MINOR
PATCH
```

Example:

```text
v2.4.1
v2.5.0
v3.0.0
```

Record:

```text
problem
evidence
change
expected benefit
risk
verification metric
result
```

MAJOR / MINOR changes require verification with baseline comparison. Failure triggers demotion or rollback of the Skill version.

---

# 29. Skill Deduplication

Classify new Skill requests as:

```text
duplicate
overlapping
extension
new
```

Preferred action:

```text
duplicate → reuse
overlapping → merge/improve
extension → update existing
new → propose
```

---

# 30. Governance

### Auto Apply

Low risk:

```text
private memory
verified factual knowledge
duplicate cleanup
explicit user preference (after persistence check)
low-risk project notes
```

### Proposal Required

Behavior changes:

```text
Agent behavior
Skill behavior
Project workflow
cron behavior
AGENTS.md
SOUL.md
shared memory
demotion of previously promoted rules
```

### Explicit Approval Required

High risk:

```text
permissions
credentials
external communication
financial actions
data deletion
security settings
automatic transactions
system-level changes
GLOBAL policy changes
```

Never bypass this.

---

# 31. Proposal Format

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

User responses:

```text
approve N
skip N
```

---

# 32. Verification

Every important promotion, demotion, or Skill change should have:

```text
baseline
metric
review period
result
action
```

Example:

```markdown
### Verification

Before:
error rate = 18%

After:
error rate = 11%

Metric:
next 20 tasks

Result:
improved

Action:
reinforce
```

---

# 33. Dynamic Verification Period

```text
low-risk change       → 3 days
normal workflow       → 7 days
important behavior    → 14 days
core architecture     → 30 days
```

Do not force every change into one fixed period.

---

# 34. Cross-Agent Verification

If a learning is proposed for PROJECT or GLOBAL scope:

1. test it in the source Agent
2. test it in at least one relevant Agent when practical
3. compare outcomes
4. promote only if evidence supports the wider scope **and** context-independence

This prevents specialist mistakes from becoming global rules.

---

# 35. Revert & Demotion

If a change causes:

```text
regression
repeated user rejection
new tool failures
security risk
worse metrics
```

then:

```text
1. mark failed
2. restore previous behavior (Revert)
   OR narrow the scope (Demote)
3. record cause
4. lower confidence / apply decay
5. block identical automatic promotion
```

**Demotion path** (logical counterpart to promotion):

- GLOBAL → PROJECT (when later evidence shows project-specificity)
- PROJECT → AGENT (when later evidence shows agent-specificity)
- Any wider scope → narrower scope when context dependence is discovered

Demotion is preferred over complete deletion when the knowledge remains useful at a narrower scope.

Recommended command:

```bash
python3 scripts/learn.py --rollback <change_id>
python3 scripts/learn.py --demote <change_id> --to <scope>
```

---

# 36. Anti-Loop Protection

If the same learning repeatedly fails verification:

```text
failure_count += 1
```

After repeated failure:

```text
status = blocked_learning
```

Do not automatically promote again.

Require human review.

---

# 37. Anti-Overfitting

Before promoting:

```text
Is this general?
Is this project-specific?
Is this Agent-specific?
Is this tool-specific?
Is this user-specific?
Is this temporary?
Is this context-dependent?
```

Store at the narrowest valid scope.

---

# 38. Forgetting and Obsolescence

Suggested lifecycle:

```text
0–30 days   active
30–60       decay if unused
60–90       stale
90+         archive unless important/verified
```

Exceptions:

- explicit user preferences
- verified principles
- active project decisions
- current tool knowledge

When knowledge is outdated:

```text
status: obsolete
superseded_by: <id>
```

Preserve history when useful. Decay of effective confidence is the continuous mechanism; archival is the discrete end state.

---

# 39. Session Memory

At session end, create:

```text
memory/sessions/YYYY-MM-DD-NNN.md
```

Format:

```markdown
# Session Summary: YYYY-MM-DD-NNN

## Tasks Completed
- ...

## Decisions
- ...

## Learnings
- ...

## Intermediate States Noted
- ...

## User Feedback
- ...

## Skills Changed
- ...

## Open Items
- ...
```

Do not put every micro-error into the session summary.

Micro-errors belong in the learning trail.

---

# 40. Mandatory File Safety

Before editing ANY file:

```text
READ FIRST
```

Correct:

```text
read(path="MEMORY.md")
```

Then construct an exact edit from the returned content.

Never invent oldText from memory.

This is a hard rule of the Learning OS.

---

# 41. Session File Safety

Never use:

```text
exec
cat
tail
grep
wc
jq
```

against raw OpenClaw session files to create L1 summaries.

Use:

```text
sessions_list
sessions_history
```

Workflow:

```text
sessions_list
 ↓
identify session
 ↓
sessions_history
 ↓
summarize
 ↓
write L1
```

If unavailable, skip rather than guess.

---

# 42. Memory Retrieval

When asked:

```text
之前说过什么
上次怎么决定的
继续那个项目
你还记得吗
```

Search:

```text
1. Current task
2. Project STATE
3. Project DECISIONS
4. Agent memory
5. User memory
6. Global memory
7. Learning trail
8. Session summaries
```

When conflicts exist, surface:

- active items
- contradicted / superseded items
- unresolved conflicts

Never fabricate history.

---

# 43. Knowledge Graph

Recommended relationships:

```text
Experience
 ├── caused_by
 ├── supports
 ├── contradicts
 ├── supersedes
 ├── derived_from
 ├── verified_by
 ├── used_in
 ├── improves
 ├── demoted_by
 └── reverted_by
```

Project graph:

```text
Project
 ├── Agent
 ├── Decision
 ├── Skill
 ├── Workflow
 └── Learning
```

---

# 44. Agent Conflict Resolution

If two Agents produce conflicting learning:

```text
1. compare scope
2. compare evidence quality
3. compare verification
4. check tool/version differences
5. check project differences
6. determine whether both are context-specific
```

Possible result:

```text
Agent-specific A
Agent-specific B
Project rule
Superseded
Demoted
Unresolved
```

Do not force a false single rule. Prefer keeping both with explicit scope over inventing a false unification.

---

# 45. Shared Memory Write Protection

Agents may normally:

```text
read shared memory
create private candidates
submit Learning Bus events
update approved private memory
```

Agents must not automatically:

```text
overwrite GLOBAL
overwrite another Agent
change USER preferences silently
change core policy
change security rules
```

---

# 46. Learning Bus Event Types

Recommended:

```text
learning_candidate
correction
error
success
intermediate_state
decision
skill_candidate
verification_result
contradiction
promotion_request
demotion_request
demotion_notification
rollback_request
agent_created
agent_updated
agent_deprecated
```

---

# 47. Agent Creation Protocol

When creating a new Agent:

```text
1. Register Agent.
2. Define role.
3. Define project.
4. Define Skills.
5. Define memory scope.
6. Compare existing Agents.
7. Check duplicate capability.
8. Define permissions.
9. Define shared-memory access.
10. Initialize private memory.
```

Never create an Agent without defining its scope.

---

# 48. Agent Retirement Protocol

When retiring:

```text
1. mark deprecated
2. stop new tasks
3. preserve private memory
4. extract verified project learning
5. preserve decisions
6. check dependent Agents
7. archive
```

Do not delete useful learning automatically.

---

# 49. Cron

Recommended:

```text
Session start
→ status / pending checks

During task
→ real-time learning

After meaningful task
→ session summary

Heartbeat
→ lightweight learning maintenance (including decay)

Daily
→ full learning cycle

Verification date
→ verify changes
```

Before adding cron:

```text
list existing jobs
compare schedule
compare command
compare purpose
```

Never create duplicate learning cycles.

---

## 49.1 Global Learning Cycle (V3.2.1 多 Agent 全局调度)

> 多 Agent 场景下，Learning OS 不是"主 Agent 自己学"，而是作为**全局调度器**
> 面向整个 OpenClaw 工作区运行。设计目标：**一个 Learning OS，多个 Agent**，
> 不给每个 Agent 装一套 self-improvement。
>
> **Global Learning Cycle 是调度器，不是特权晋升通道。** 所有从 Bus 进入的事件
> 仍按 Core Loop 处理：scope 默认最窄（AGENT），晋升必须走
> Confidence + Context-independence + Governance 三重校验，不得因"全局调度"绕过。

### 全局结构

```text
OpenClaw
 │
 主 Agent / Global Scheduler
 │
 Global Learning Cycle（唯一 Cron）
 │
 Agent Registry（agents.py 自动扫描 workspace-*）
 │
 ┌──────────────┼──────────────┐
 ↓              ↓              ↓
 Agent A      Agent B       Agent C
 │              │              │
 └──────────────┼──────────────┘
                ↓
          Learning Bus（bus.py --central 中央总线）
                ↓
          Central Learning（learn.py --cycle Phase 0 聚合）
                ↓
          Scope / Conflict / Evidence
                ↓
          Agent / Project / User / Global
```

### 49.1.1 调度职责

Global Learning Cycle 只做一件事：**告诉 Learning OS "现在轮到你检查所有 Agent"**。
不亲自学，不读全部聊天记录，只消费结构化事件。

```text
1. 读取 Agent Registry（有哪些 ACTIVE Agent）
2. 读取中央 Learning Bus（bus.json 的 pending 事件）
3. 聚合 → 去重 → scope 判断 → 写入 learning trail
4. 验证 / 晋升 / 降级 / 清理
5. 更新 Registry / Index
```

### 49.1.2 Agent Discovery

用 `agents.py`（自动扫描 `workspace-*` 目录）维护 `memory/agents/registry.json`。
Cron 不猜 Agent 列表，直接读 Registry。

```bash
python3 scripts/agents.py --list
python3 scripts/agents.py --status
```

### 49.1.3 Incremental Agent Scan（增量扫描）

不把 20 个 Agent 的聊天记录全拉回来。每个 Agent 平时自己产生结构化
learning event（任务收尾/踩坑/验证后通过 `bus.py --central` 上报），
Global Cycle 只读"有变化的 Agent"的 Bus 事件。

```bash
# 各 Agent 上报（必须 --central，写中央总线）
python3 skills/self-evolution/scripts/bus.py --central   --topic "主题" --content "经验" --scope AGENT --agent <agent_id> --confidence 85
```

### 49.1.4 Learning Bus Drain

`learn.py --cycle` 的 **Phase 0** 每轮 Drain 中央 Bus：

```text
读取 memory/agents/bus.json 的 pending 事件
→ 去重（topic+content 比对 learning trail）
→ 写入 trail（source=external 初始不信任）
→ 事件标记 resolved
→ 更新 bus.stats
```

### 49.1.5 Cross-Agent Verification

scope=PROJECT / GLOBAL 的事件需要多源确认，聚合时自动标记
`extra_meta.xverify = "pending"`，等待后续跨 Agent 验证后晋升。
单 Agent 的 AGENT 范围事件不强制跨源验证。

### 49.1.6 Cron Lock / Concurrency

多个 `--cycle` 同时跑（cron + 手动）可能重复处理。`aggregate_bus_events`
用文件锁（`memory/agents/.bus.lock` + fcntl）防止并发：

```text
拿不到锁 → 本轮跳过（skipped），避免重复写 trail
拿到锁 → 处理完释放
```

### 49.1.7 Scan Cursor / Last Scan

`bus.stats.last_scan` 记录上次扫描时间、`last_pending_count` 记录待处理数，
供外部观察增量进度。无新 pending 事件时 Phase 0 快速返回，不空转。

### 49.1.8 Governance Guardrails（治理护栏）

#### 信任模型（external 事件）

- 聚合进来的 external 事件初始 `trusted=False`，`effective_confidence` 上限 ≤ 60
- 必须经过至少一次独立验证（同项目其他 Agent 复现 / 后续 session 确认）才能提升
- 单源 external 事件**永远不能自动晋升到 GLOBAL**（代码层 execute_promotion 已强制拦截）
- 多源交叉验证过的 external 事件才可进入晋升候选

#### Demotion 反向传播

学习被降级后，通过 Learning Bus 发布 `demotion_notification` 事件反向通知相关 Agent。
Agent 收到后应降低本地对该规则的有效置信度，或将其标记为需重新评估，避免继续按旧的高 scope 规则执行。

#### 中间态 → Skill Evolution

有价值的 intermediate-state 模式，满足以下任一条件即进入 Skill Evolution 候选：
- 重复出现 ≥ 2 次
- 一次 intermediate 导致后续 Skill 行为实际调整
与 success / error 同等对待，不设歧视。

#### 多项目冲突

同一条学习涉及多个 Project 且证据矛盾时，**默认保持各自 PROJECT 范围**，
禁止自动统一为 GLOBAL。冲突无法解决时标记 Unresolved 交人工裁决。

#### Bus 事件生命周期

```text
pending → resolved（已聚合进 trail）
pending → rejected（人工/校验拒绝，保留记录不删除）
pending → expired（超时未处理，标记后清理）
重复事件：topic+content 去重，同时合并 evidence 字段
```

## 49.2 完整学习循环管线（learn.py --cycle 实测）

`learn.py --cycle` 是单 Agent 场景的完整循环入口，**实际运行 10 个 Phase**（V3.2.2 实测）：

```text
🔌 Phase 0  Aggregate Learning Bus   聚合中央总线事件（drain → trail）
📁 Phase 1  Memory scan              扫描 memory 文件
✅ Phase 2  Verification check       待验证项检查
🚀 Phase 3  Pattern promotion        pattern 晋升检查
⏳ Phase 4  Forgetting check         遗忘/过期检查
↩️ Phase 5  Auto-revert check        自动回滚检查
🗑️ Phase 6  Memory retention         记忆保留（90 天清理）
🔍 Phase 7  Auto-detect learning     自动检测新学习
🌙 Phase 8  Dream distillation       梦境蒸馏（记忆压缩）
📚 Phase 9  Memory index             重建主题索引
📝 Phase 10 Session summary          会话总结
```

Final Summary 字段解读：

```text
Entries:  N    # trail 中条目总数
Changes:  N    # 本轮应用的变更
Verified: N    # 本轮验证数
Promoted: N    # 晋升数
Graph:    N nodes / N edges   # 知识图谱规模
Actions taken this cycle:     # 本轮实际动作明细
```

Cron 建议：多 Agent 场景用 `--cycle`（§49.1）作为全局调度入口；
单 Agent 场景直接跑 `--cycle` 即可。轻量巡检用 `--verify` / `--status` / `--retention`，
不要为每个节点各建一套学习循环。

---

# 50. CLI Reference

> 以下命令与当前脚本实现一一对应（V3.2.2 实测核对），在
> `skills/self-evolution/scripts/` 目录下执行。每个脚本都支持 `--help`。

## 50.1 learn.py — 学习引擎（核心）

### 生命周期 / 状态

```bash
python3 scripts/learn.py --cycle          # 完整学习循环（10 Phase，见 §49.2）
python3 scripts/learn.py --status         # 学习统计
python3 scripts/learn.py --verify         # 检查待验证项
python3 scripts/learn.py --trail          # 导出完整 learning trail
python3 scripts/learn.py --promote        # 检查可晋升的 pattern
python3 scripts/learn.py --retention      # 检查过期条目（90 天）
python3 scripts/learn.py --propose        # 生成改进提案供人工审批
```

### 记录日志

```bash
python3 scripts/learn.py --log correction "..."
python3 scripts/learn.py --log error "..."
python3 scripts/learn.py --log learning "..." \
  --area behavior \
  --priority high
```

- `--log TYPE SUMMARY`：TYPE = `learning | error | feature | correction`
- 可选参数：`--area`、`--priority {critical,high,medium,low}`、`--pattern-key`（去重）、`--source {conversation,error,user_feedback,self_discovery,external}`

### 高级记录

```bash
python3 scripts/learn.py --log-daily "..."          # 写入今日 memory 文件
python3 scripts/learn.py --add-change <target> "<change>" "<hypothesis>"   # 记录变更+验证
python3 scripts/learn.py --add-principle "<principle>"                    # 沉淀原则
```

### 记忆检索 / 索引

```bash
python3 scripts/learn.py --search-memory "<query>"   # 跨 memory 文件搜索
python3 scripts/learn.py --build-index                 # 重建主题索引
python3 scripts/learn.py --query-memory <topic>        # 按主题查询
```

### 对话自评分（五维 0-10）

```bash
python3 scripts/learn.py --score <acc> <use> <eff> <ton> <pro>
# accuracy usefulness efficiency tone proactiveness
python3 scripts/learn.py --trends 7    # 最近 N 天评分趋势
```

### Knowledge Graph（知识图谱）

```bash
python3 scripts/learn.py --graph-node <type> "<content>" <manual|auto>
# type = event | lesson | principle | knowledge | pattern
python3 scripts/learn.py --graph-edge <from> <to> <type>
# type = caused_by | led_to | supports | contradicts | related_to | derived_from
python3 scripts/learn.py --graph-query [node_id|type:TYPE|tag:TAG]
python3 scripts/learn.py --graph-auto-link <node_id> "<content>"   # 语义自动连线
python3 scripts/learn.py --graph-rank "<query>"                    # PageRank 排序
python3 scripts/learn.py --graph-dedup <threshold>                  # 查重 0.0-1.0
python3 scripts/learn.py --merge-nodes <node_a> <node_b>            # 合并重复节点
```

### 回滚 / 降级

```bash
python3 scripts/learn.py --rollback <change_id>
python3 scripts/learn.py --demote <entry_id> --to <scope>
# scope = TASK | AGENT | PROJECT | USER | GLOBAL
```

## 50.2 reflect.py — 反思 / 检测

```bash
python3 scripts/reflect.py --detect "USER_MESSAGE"          # 分析文本触发点
python3 scripts/reflect.py --log "任务描述" success          # 记录结果
python3 scripts/reflect.py --collect [recent|failed|all]     # 批量收集会话数据
python3 scripts/reflect.py --collect --hours 24              # 回溯 N 小时
```

## 50.3 bus.py — Learning Bus（多 Agent）

```bash
python3 scripts/bus.py --status                               # 总线状态
python3 scripts/bus.py --pending                              # 待处理事件
python3 scripts/bus.py --publish '{"event":"...","scope":"AGENT",...}'
python3 scripts/bus.py --central --event learning_candidate \
  --topic "主题" --content "经验" --scope AGENT \
  --agent <agent_id> --confidence 85 --project "项目名"
```

- `--central`：强制写入中央 Learning Bus（主工作区 `memory/agents/bus.json`）
- 各 Agent 通过 `--central` 上报，Global Learning Cycle 在 Phase 0 消费（§49.1.4）

## 50.4 agents.py — Agent Registry

```bash
python3 scripts/agents.py --list
python3 scripts/agents.py --status
python3 scripts/agents.py --capabilities
python3 scripts/agents.py --overlap
```

## 50.5 skillgen.py — 自动技能生成器

```bash
python3 scripts/skillgen.py --scan                     # 扫描 trail 找技能候选
python3 scripts/skillgen.py --generate [pattern_id]    # 生成技能草稿
python3 scripts/skillgen.py --auto                     # 全自动：scan + generate
python3 scripts/skillgen.py --list                     # 列出草拟技能
python3 scripts/skillgen.py --approve <name>           # 审批并安装
python3 scripts/skillgen.py --status                   # 生成器统计
python3 scripts/skillgen.py --scan --min-recurrence 3 --days 30
```

## 50.6 dream.py — 梦境蒸馏（记忆压缩）

```bash
python3 scripts/dream.py --run         # 完整蒸馏（扫描近 14 天日志）
python3 scripts/dream.py --dry-run     # 预览将发生什么（不写盘）
python3 scripts/dream.py --days 14     # 指定回溯天数
python3 scripts/dream.py --report      # 查看近期蒸馏活动
```

## 50.7 sync.py — 备份 / 迁移

```bash
python3 scripts/sync.py export [path]             # 导出为 zip
python3 scripts/sync.py import <zip_path>         # 导入
python3 scripts/sync.py import <zip_path> --overwrite  # 覆盖导入
python3 scripts/sync.py status                    # 数据状态
```

## 50.8 migrate.py — 数据迁移

```bash
python3 scripts/migrate.py --migrate
# 迁移前：python3 scripts/sync.py export
# 迁移后：python3 scripts/learn.py --status + --build-index
```

---

# 51. Multi-Agent Status

Agent Registry:

```bash
python3 scripts/agents.py --list
python3 scripts/agents.py --status
python3 scripts/agents.py --capabilities
python3 scripts/agents.py --overlap
```

Learning Bus:

```bash
python3 scripts/bus.py --status
python3 scripts/bus.py --pending
python3 scripts/bus.py --publish <json>
python3 scripts/bus.py --central --event <type> --topic <t> --content <c> --scope <s>
```

以上脚本为本实现提供并已实测可用。

---

# 52. Backup

Before major migration:

```bash
python3 scripts/sync.py export
```

Backup should include:

```text
MEMORY
USER
GLOBAL
PROJECTS
AGENTS
SESSIONS
SKILLS
.learning-trail.json
.memory-index.json
DECISIONS
```

Never backup secrets.

---

# 53. Migration

Before migration:

```text
backup all memory
backup learning trail
backup project state
backup Agent state
backup Skills
```

Then:

```bash
python3 scripts/migrate.py --migrate
```

After migration:

```bash
python3 scripts/learn.py --status
python3 scripts/learn.py --build-index
python3 scripts/agents.py --status
```

If the installed implementation does not yet provide these commands, create the migration tooling before attempting migration.

---

# 54. Multi-Agent Example

Example:

```text
OpenClaw
│
├── Learning OS
│
├── User
│   └── preferences
│
├── Project: A股模拟交易
│   ├── long-term-trader
│   ├── short-term-trader
│   ├── market-data-agent
│   └── risk-agent
│
├── Project: 报价
│   ├── quotation-agent
│   └── factory-agent
│
└── Project: 仓库管理
    └── warehouse-agent
```

Suppose:

```text
short-term-trader
发现:
行情必须验证时间戳
```

First:

```text
AGENT learning
```

After evidence + context check:

```text
PROJECT learning
```

Only after broader evidence of context-independence:

```text
GLOBAL principle
```

No blind broadcasting. If later evidence shows the rule only holds for certain market regimes, demote back to PROJECT or AGENT.

---

# 55. Agent Specialization Rule

A Multi-Agent system should follow:

> Shared brain, specialized hands.

Shared:

```text
user preferences
project decisions
verified principles
relevant tool knowledge
```

Private:

```text
specialist heuristics
private experiments
unverified observations
Agent-specific mistakes
```

This prevents both:

```text
knowledge isolation
```

and:

```text
knowledge pollution
```

---

# 56. Success Metrics

Track:

```text
user corrections
repeated errors
tool failures
duplicate Skills
duplicate Agents
verification failures
successful workflows
project continuity
decision recall accuracy
cross-Agent learning usefulness
demotion frequency
unresolved conflict rate
```

Success means:

```text
fewer mistakes
less repetition
better continuity
better specialization
better sharing
less duplication
more reliable Skills
healthy demotion when needed
```

Not:

```text
more memory
more Agents
more Skills
more automatic changes
```

---

# 57. What The System Must Never Do

Never:

```text
invent memories
invent previous decisions
promote one-off errors into principles
broadcast every learning to every Agent
overwrite another Agent's private memory
silently change User preferences
silently modify GLOBAL policy
create duplicate Agents
create duplicate Skills
ignore contradictions
claim verification without evidence
store secrets
read raw session files with exec
edit files without reading them first
treat a single high-confidence Agent observation as GLOBAL without independent evidence
force a false unified rule when scopes legitimately differ
```

---

# 58. Final Operating Rules

When uncertain:

```text
observe rather than promote
```

When scope is unclear:

```text
choose the narrowest valid scope
```

When evidence conflicts:

```text
prefer newer verified evidence; prefer narrower scope; mark Unresolved if needed
```

When risk is high:

```text
proposal / approval
```

When verification fails:

```text
revert or demote
```

When a Skill already exists:

```text
improve it before creating another
```

When another Agent has learned something:

```text
receive through Learning Bus (after context filter)
```

When a learning is useful to multiple Agents:

```text
promote its scope rather than copying it manually
```

When the user explicitly gives a current instruction:

```text
follow the current instruction
```

When context dependence is later discovered:

```text
demote rather than delete
```

---

# 59. Final Architecture

```text
                         ┌──────────────────────┐
                         │       OpenClaw       │
                         └───────────┬──────────┘
                                     │
                     ┌───────────────▼───────────────┐
                     │  Global Scheduler (主 Agent)  │
                     │  Global Learning Cycle / Cron │
                     └───────────────┬───────────────┘
                                     │
                         ┌───────────▼───────────┐
                         │   Learning OS 中央    │
                         │ Central Learning     │
                         │ Phase 0: Bus Drain   │
                         └───────────┬───────────┘
                                     │
               ┌─────────────────────┼─────────────────────┐
               ↓                     ↓                     ↓
         Global Memory          User Memory          Agent Registry
               │                     │                     │
               └─────────────────────┼─────────────────────┘
                                     ↓
                              Project Memory
                                     │
                       ┌─────────────┴─────────────┐
                       ↓                           ↓
                  Learning Bus（中央）           Decisions
                       │
          ┌────────────┼────────────┐
          ↓            ↓            ↓
       Agent A      Agent B      Agent C
          │            │            │
          └────────────┼────────────┘
                       ↓
                  Experience
                  (incl. intermediate)
                       ↓
                    Candidate
                       ↓
        Confidence / Decay / Conflict
                       ↓
                    Governance
                       ↓
            ┌───────────┴───────────┐
            ↓                       ↓
        Promotion                Proposal
            │                       │
            └───────────┬───────────┘
                        ↓
                 Memory / Skill / Rule
                        ↓
                    Verification
                        ↓
             Reinforce / Demote / Revert
                        ↓
                      Learning
```

---

# 60. Version

## V3.2.2

Documentation-implementation alignment (doc-code parity).

- Rewrote §50 CLI Reference to match real script capabilities (verified by running each `--help`)
- Documented previously-undocumented features: Knowledge Graph CLI (§50.1), conversation scoring `--score`/`--trends`, `--log-daily`/`--add-change`/`--add-principle`, `skillgen.py`, `dream.py`, `reflect.py --collect`, `bus.py --central`
- Added §49.2 full learning-cycle pipeline (10 Phases, verified via `learn.py --cycle`)
- Added §62 Runbook (operation manual)
- Updated §51 Multi-Agent Status to actual `bus.py`/`agents.py` flags

## V3.2.1

Upgrade focused on logical completeness of the Multi-Agent Learning OS and Global Learning Cycle governance.

Added / strengthened:

- Intermediate-state experience (near-miss, almost-failure, partial-success, delayed-failure)
- Evidence & time decay for effective confidence
- Context-independence requirement for wider-scope promotion (default local)
- Explicit contradiction resolution priority (local preferred, Unresolved path)
- Active demotion path (scope narrowing) alongside revert
- Bidirectional feedback between Skill Evolution and Learning Engine
- Clearer temporary vs persistent preference judgment
- Explicit Decision ↔ Learning boundary and conversion rules
- Updated core loop, promotion matrix, event types, operating rules, and architecture diagram
- Global Learning Cycle as pure scheduler (no privileged promotion)
- External-event trust model & promotion guardrails (source=external 低信任, 单源不自动 GLOBAL)
- Demotion reverse propagation via Learning Bus (demotion_notification)
- Intermediate-state → Skill Evolution formal trigger (≥2 次 或 触发 Skill 调整)
- Multi-project conflict isolation (默认各自 PROJECT, 禁止自动统一 GLOBAL)
- Bus event lifecycle (pending → resolved / rejected / expired + evidence merge)

Preserved from V3.1:

- Agent Registry & Capability Registry
- Learning Bus
- Multi-Agent Learning
- Scope separation (Global / User / Project / Agent)
- Cross-Agent verification
- Agent lifecycle & retirement
- Skill ownership & deduplication
- Shared-memory write protection
- Experience detection, learning trail, confidence, verification, governance, rollback, forgetting
- File read-before-edit rule
- sessions_list + sessions_history rule
- Secret protection, backup / migration, cron maintenance

---

# 61. Final Principle

The goal is not:

> Make every Agent know everything.

The goal is:

> Make every Agent know what it needs, while allowing verified knowledge to flow through one controlled learning system — and allowing knowledge to shrink in scope when evidence later shows it was over-generalized.

Therefore:

```text
Many Agents
    +
One Learning OS
    +
Scoped Memory (default narrow)
    +
Controlled Learning Bus
    +
Evidence Decay
    +
Verification
    +
Promotion + Demotion
    +
Governance
    =
A scalable and self-correcting OpenClaw multi-Agent system
```

---

# 62. Runbook（操作手册）

> 面向实际操作者：cron 配什么、每天跑什么、输出怎么读、候选怎么审批。
> 所有命令在 `skills/self-evolution/scripts/` 下执行，每个脚本支持 `--help`。

## 62.1 日常循环（每日必跑）

```bash
# 完整学习循环（10 Phase，见 §49.2）——主入口
python3 scripts/learn.py --cycle
```

- 单 Agent 场景：`--cycle` 一把梭即可。
- 多 Agent 场景：先由各 Agent 通过 `bus.py --central` 上报事件，
  再由 Global Learning Cycle（§49.1）在 Phase 0 统一聚合。

## 62.2 快速巡检（轻量）

```bash
python3 scripts/learn.py --status        # 学习统计：条目/变更/晋升
python3 scripts/learn.py --verify        # 有没有待验证项到期
python3 scripts/learn.py --retention     # 有没有 90 天过期条目
python3 scripts/bus.py --pending         # 总线还有多少待处理事件
python3 scripts/agents.py --status       # Agent 状态
```

建议 cron：`--cycle` 低频（如每日 1 次），
`--status` / `--verify` / `--retention` 高频轻量巡检。
不要为每个节点各建一套学习循环（§49）。

## 62.3 输出怎么读（--cycle 的 Final Summary）

```text
Entries:  N          # learning trail 条目总数（越大知识库越厚）
Changes:  N          # 本轮实际应用的变更（关注异常高峰）
Verified: N          # 本轮完成的验证
Promoted: N          # 晋升条目数（>0 表示有学习升级，值得看一眼）
Graph:    N nodes / N edges   # 知识图谱规模
Actions taken this cycle:     # 本轮动作明细（自动检测到几条新学习等）
```

## 62.4 skillgen 技能生成（审批流程）

```bash
python3 scripts/skillgen.py --scan                    # 1. 扫描 trail 找技能候选
python3 scripts/skillgen.py --list                    # 2. 查看草拟的技能
python3 scripts/skillgen.py --generate <pattern_id>   # 3. 生成某个技能草稿
python3 scripts/skillgen.py --approve <name>          # 4. 审批并安装（人工把关）
python3 scripts/skillgen.py --auto                    # 一键全自动（scan + generate，不自动安装）
```

纪律：**审批安装是人工动作**，`--auto` 只到生成草稿，安装仍需 `--approve`（§30 Governance）。

## 62.5 记忆查询 / 回顾

```bash
python3 scripts/learn.py --search-memory "<query>"   # 跨 memory 搜索
python3 scripts/learn.py --query-memory <topic>        # 按主题查询
python3 scripts/learn.py --trends 7                    # 最近评分趋势
python3 scripts/learn.py --graph-query [node|type:TYPE] # 知识图谱查询
```

## 62.6 记录一次踩坑 / 成功

```bash
# 简单记录（自动分类）
python3 scripts/learn.py --log error "行情 API 超时未重试"
python3 scripts/learn.py --log correction "应该在写文件前先 read"

# 带验证的变更记录（Skill 改动）
python3 scripts/learn.py --add-change skillgen "增加 --approve" "降低误装风险"

# 沉淀一条原则
python3 scripts/learn.py --add-principle "编辑文件前必须先读取当前内容"
```

## 62.7 回滚 / 降级（学习纠偏）

```bash
python3 scripts/learn.py --rollback <change_id>          # 回滚一个已应用的变更
python3 scripts/learn.py --demote <entry_id> --to AGENT  # 范围过大时降级到更窄 scope
```

## 62.8 备份 / 迁移 / 恢复

```bash
python3 scripts/sync.py export /tmp/learning-backup.zip   # 迁移/大改动前备份
python3 scripts/sync.py import /tmp/learning-backup.zip   # 恢复
python3 scripts/sync.py status                            # 确认数据状态
```

## 62.9 对话自评分（可选，培养反馈闭环）

```bash
python3 scripts/learn.py --score 8 7 9 8 8   # accuracy usefulness efficiency tone proactiveness
python3 scripts/learn.py --trends 14          # 看两周趋势
```

---