# Agent OS v1.3 Hardening Patch — 修复跟踪表

基线: ea0dee4
结论: 不重做架构, 只做代码硬化 + 协议兑现 + 并发/ID/验证边界。
这是 v1.3 Hardening Patch, 不是 v1.4/OS2。

## 修复优先级 (Phase 顺序)
- PHASE 1 安全: P0 Permission fail-closed / P1 authorization scope / P1 unknown action
- PHASE 2 数据完整性: P1 unified ID / P1 atomic persistence / P1 JSON corruption
- PHASE 3 Anti-loop: P1 progress / P1 UNKNOWN-retry / P1 concurrent execution record
- PHASE 4 Ontology: append-only rollback / mutation scope / proposal atomic / evidence schema
- PHASE 5 Verification: independent verification / evidence refs / V3/V4 enforcement
- PHASE 6 Self-Evolution: expected file hash / atomic apply / post-apply verify / crash recovery
- PHASE 7 Knowledge/Memory/Context: provenance / uncertainty / contradiction
- PHASE 8 Summarize: provenance/uncertainty

## Batch 状态 (50 项表)
Phase 1 安全
- [x] #1 P0 Permission fail-closed (P0) — orchestrator.py + permission.py ✅
- [x] #28 Unknown action 默认 ASK ✅(permission.py check() unknown→ASK, 补充ASKING词)
- [x] #29 authorized 增加 source/scope/expiry ✅(本轮 P1-9 实现: check() 解析 authorization dict, 输出 source/scope/expiry/scope_ok)
- [x] #30 requested scope ≤ authorized scope ✅(本轮 P1-9 实现: 越界(requested>authorized) 拒绝授权 → ask)
Phase 2 ID + Atomic Persistence
- [x] #2 Orchestrator hash() → canonical+SHA256 ✅
- [x] #3 Task ID → UUID ✅(orchestrator/proactive; task_manager 待)
- [x] #4 Proactive Signal/Opportunity/Queue → UUID + fingerprint ✅
- [x] #5 Ontology Entity/Relation/Proposal → UUID ✅(id_utils.generate_id)
- [x] #6 tasks.json atomic persistence ✅(atomic_write_json lock+temp+fsync+os.replace)
- [x] #7 Proactive Queue atomic ✅(persistence.atomic_write_json)
- [x] #8 Proactive State atomic ✅(persistence.atomic_write_json)
- [x] #9 Execution Record JSONL 文件锁+append ✅(append_atomic+flock)
Phase 3 Execution Record + Anti-loop
- [x] #10 损坏 JSONL 行记录 corruption ✅(corruption 记录不静默跳过)
- [x] #11 Progress 判断加 artifact/goal_progress/state ✅
- [x] #12 history_unavailable 禁止静默 pass ✅
- [x] #13 same action+input+evidence+state+strategy → NOOP/ESCALATE ✅
- [x] #14 UNKNOWN → WAIT/OBSERVE/ASK/ESCALATE ✅
Phase 4 Task Manager + Proactive
- [x] #15 JSON 损坏进 recovery/error ✅(抛错不进 recovery, 不再返空列表)
- [x] #16 ordered dedup ✅(ordered_dedup 保序去重)
- [x] #17 Task↔Goal/Artifact 并发 atomic ✅(atomic_write_json 锁覆盖读写)
Phase 5 Ontology
- [x] #18 Rollback 追加 ROLLBACK Event ✅(append-only 重放过滤)
- [x] #19 只撤销指定 change mutation ✅(重复回滚拒绝)
- [x] #20 changelog 永不删除 ✅(追加 ROLLED_BACK, 不 rewrite)
- [x] #21 Proposal 全成功才 APPLIED ✅(任一失败→FAILED)
- [x] #22 Evidence 支持 string/object/list ✅(normalize_evidence schema)
- [x] #23 Proposal/state/index atomic ✅(atomic_write_json + atomic_write_jsonlines)
- [x] #24 status 默认只读 ✅(仅系统生命周期写, CLI 不可改实体 status)
Phase 6 Verification
- [x] #25 V3 需独立 method+evidence+source ✅(verify_result 需 method+evidence_refs+verified_by, 否则 UNKNOWN)
- [x] #26 加 verification_method/evidence_refs/verified_by ✅
- [x] #27 UNKNOWN 不得自动 Retry ✅(orchestrator UNKNOWN decision + link.py WAITING)
Phase 7 Self-Evolution
- [x] #31 expected SHA-256/fingerprint ✅(_core baseline/expected fingerprint + apply 记录)
- [x] #32 lock+fingerprint check ✅(apply_lock flock + validate_applied_files)
- [x] #33 Apply→verify→regression→APPLIED ✅(apply 只推进 APPLIED，verify 指纹；regression 负责后续)
- [x] #34 APPLYING 崩溃 recovery ✅(detect_incomplete_apply + recover_apply + _retry_from_change)
- [x] #35 artifact ID → UUID ✅(gen_id→id_utils.generate_id)
Phase 8 Memory/Knowledge/Context/Summarize
- [x] #36-44 provenance/uncertainty/conflict 保留 ✅(summarize 加 uncertainties/conflicts, SUMMARY≠FACT)
- [x] #45 manifest regression test ✅(self_test 60 + anti_loop 14 全绿)
Phase 9 回归测试
- [x] 全量回归 ✅(self_test 60 + anti_loop 14 + 全部 py_compile)
不做 (明确禁止/锁死)
- ❌ #47-50 禁止新增 Agent OS Runtime/Scheduler/Event Bus/Loop/Tool Runtime/Approval Runtime; 禁止重构 Self-Evolution
- ❌ 不新增架构; 不改 Proactive 非 Scheduler 边界; 不把 Execution Record 改数据库

## 不做 (明确禁止)
- ❌ 不新增 Agent OS Runtime/Scheduler/Event Bus/Memory Engine/Context Engine/Agent Loop/Tool Runtime/Approval Runtime
- ❌ 不重构架构, 不做 v1.4/OS2
- ❌ 不改 Self-Evolution 10 脚本职责 (不重构)
- ❌ 不把 Execution Record 改数据库 (保持 append-only recording, 状态持久化用 atomic)
- ❌ 不改 Proactive 非 Scheduler 边界
- ❌ Verification 架构不重写 (只补代码兑现)

## 复验轮 (2026-08-19) — 验收报告 8+3 项修复
> 上一轮(124a290→c983607)验收发现部分"打勾没兑现"。本轮按验收报告口径逐项落实，未改架构。

| 项 | 内容 | 状态 |
|----|------|------|
| P1-1 | Orchestrator.record 统一调 execution_record.check_action_loop (删除旧两套 Anti-loop + 静默 pass→降级 UNKNOWN) | ✅ |
| P1-2 | task_manager(create/update/assign) + proactive(queue/state) 的 read→modify→write 放入同一 FileLock 事务 | ✅ |
| P1-3 | Ontology duplicate rollback 真正拒绝 (修复 op/action 字段名 bug, add_relation 重复回滚→rc=3) | ✅ |
| P1-4 | Ontology Change ID 改 UUID (create_entity + add_relation 两处) | ✅ |
| P1-5 | Ontology --status 真正只读 (去 write_state 副作用, --rebuild-index 才写) | ✅ |
| P1-6 | Self-Evolution Apply 前重新 hash 比对 baseline fingerprint, 外部修改→STOP | ✅ |
| P1-7 | Self-Evolution verify FAIL→APPLY_FAILED+RESTORED (不再 APPLIED) | ✅ |
| P1-8 | Recovery retry 前重新验证 baseline fingerprint (拒绝覆盖中断期外部修改) | ✅ |
| P1-9 | Permission #29/#30: authorization source/scope/expiry + requested≤authorized (越界→ask) | ✅ |
| P2-1 | persistence 非 POSIX fallback 用 O_EXCL .stamp 真锁 + FileLock 线程级可重入 (修重入死锁) | ✅ |
| P2-2 | Summarize aggregate 加 truncation metadata | ✅ |

回归: 全部 py_compile ✅ / self_test 60 PASS ✅ / anti_loop 14 PASS ✅

### 终验轮 (2026-08-19) — e46d432 代码逐项复核后补修 3 项
> 上一轮(124a290→e46d432)推送后, 父对 commit e46d432 逐项复核, 发现 3 项"看似修复/未形成有效保护", 本轮补全。未改架构。

| 项 | 内容 | 状态 |
|----|------|------|
| SE-01 | baseline fingerprint 前移到 Proposal 创建时记录 (propose.py `_baseline_fingerprints`), Apply 前与 Proposal 阶段基准比对。**修复前**: Apply 时才拍 baseline, 等于自己拍自己马上验, 检测不到"Proposal→Apply"之间的外部修改。**修复后**: proposal 阶段采样 targets SHA-256, apply 前重 hash 当前文件与 proposal 基准比对, 不等则 APPLY_FAILED 拒绝覆盖 (旧 proposal 缺该字段时 fallback 到 apply 时采样, 向后兼容) | ✅ |
| PERM-01 | Permission expiry 真正参与授权决策 (permission.py)。**修复前**: expiry 只存字段不判断, 过期授权仍判有效。**修复后**: `datetime.now() >= expiry` → expired → auth_valid=False → decision=ask (重新确认), 绝不静默 allow; 未过期/无 expiry 不误判; 输出增 `expired`/`expiry_problem` 字段 | ✅ |
| SE-02 | Recovery retry 的所有 post-verify failure 统一收敛到 terminal APPLY_FAILED (apply.py `_retry_from_change`)。**修复前**: 只处理了 baseline mismatch 落盘 APPLY_FAILED, post-verify mismatch 路径仍不落盘状态→下次 recovery 会再次 apply 形成 retry 循环。**修复后**: validate failure → 设 status=APPLY_FAILED + verify_error + save, 返回 RETRY_FAILED+APPLY_FAILED, 终止 retry loop | ✅ |

定向验证 (隔离 workspace, 不碰真实数据):
- SE-01: propose 记录 baseline ✅ / apply 检测外部篡改→REJECT(APPLY_FAILED) ✅ / 外部内容保留 ✅
- PERM-01: 过期→ask(valid=False,expired=True) ✅ / 未过期→allow ✅ / 无expiry不误判 ✅
- SE-02: post-verify mismatch→RETRY_FAILED+APPLY_FAILED ✅ / change.status 落盘 APPLY_FAILED ✅

回归: py_compile ✅ / self_test 60 PASS ✅ / anti_loop 14 PASS ✅

> 已确认关闭: P1-1~P1-5, P1-7, P2-1, P2-2, P1-9(基础结构)。
> 可后置 (P2): PERM-02 具体 scope 与 TASK/AGENT/PROJECT 层级关系; LOCK-01 Windows stale .stamp recovery (当前 fail-safe: 宁可 ASK 不错 ALLOW, 主运行于 Linux)。
> 终验后建议进入全项目最终验收, 不再无限加修复项。

---

## 底层正确性审查轮 (2026-08-19) — 语义层/状态机/故障模型 (ChatGPT 深审, 基线 a40b914)
> 父引入更严格标准: 不只查"字段缺了", 而是审查语义层/状态机/故障模型。核心结论:**架构方向正确, 不需要 OS2 / Agent Runtime / Scheduler / Event Bus / Memory Runtime / Context Runtime**。全部问题属于 Implementation Hardening / State Machine Enforcement / Persistence Correctness / Failure Semantics / Long-running。以下为逐项核实记录。

### 审查结论
架构 🟢 正确: OpenClaw Runtime → Agent OS Control Plane → Policy/Governance/Verification/Evidence → OpenClaw Native Execution。README 已正确分开 Execution Model 与 Control Plane 两图。OpenClaw 官方 Runtime 已含 agent loop/tool wiring/prompt assembly/session，Agent OS 绝不再做 Agent Runtime。**这条原则永久冻结**。

### 逐项核实表 (按重要性排序)

| # | 问题 (ChatGPT 断言) | 核实 | 精确定位 | 处置建议 |
|----|------|------|---------|---------|
| L-01 | save_artifact 非事务 (artifact JSON + index.jsonl 无统一锁/事务) | 🔴 属实 | _core.py save_artifact: `open(path,"w")` + `open(index,"a")`, 无锁无事务。崩溃 → artifact/index 不一致; 并发会乱 | 事务化 + Index=Derived View 强不变量 (丢失可从 artifact rebuild) |
| L-02 | Evidence JSONL 未统一 append_atomic | 🔴 属实 | _core.py register_evidence 直接 `open(evidence.jsonl,"a")` 手写, 未走 persistence.append_atomic; 而 Execution Record 已用 append_atomic → 两处不一致 | 统一走 persistenc.append_atomic |
| L-03 | evolution_id 不一致却 pass | 🔴 属实 | _core.py L373-376 register_evolution_event: `if cnd.evolution_id != evo_id and cnd.id != evo_id: pass` (注释"放宽"但没 reject) | 改成 REJECT (I-012) |
| L-04 | Rollback 部分绕过状态机 | 🔴 属实 | _core.py rollback_full_state: `chg["status"]="ROLLED_BACK"` 直接写绕过 assert_transition; `_safe_transition` 内 `except ValueError: pass` | 走 assert_transition, 失败则真失败(I-009) |
| L-05 | Proactive JSON 损坏 → 默认空 → 覆盖 | 🔴 属实 | proactive.py load_json(QUEUE_PATH, []) / state 同; 损坏读回 []→save 覆盖全 queue | 区分 NOT_FOUND / CORRUPTED, 损坏不覆盖(I-008) |
| L-06 | Orchestrator load_json 损坏 → 默认值 | 🔴 属实(轻) | orchestrator.py load_json(path, default) except→default | Control Plane 数据不静默降级, 区分 NOT_FOUND/CORRUPTED |
| L-07 | Task create 可绕过状态机 (直接 COMPLETED) | 🔴 属实 | task_manager.py normalize_task: `st=data.get("status"); if st in VALID_STATUS: t["status"]=st` → create 可直进 COMPLETED 且 completed_at=None | create 只允许 INBOX(或 creation-rule 合法初始), 走状态机 |
| L-08 | Self-Evolution apply 未重做 realpath/symlink 防护 | 🔴 属实 | _core.py allowed_ops 用 is_within_workspace(含 realpath) 检查; 但 apply_patch 写文件 `path=ws_abs(rel)` 未重做 realpath → Proposal→Apply 间 symlink 替换 TOCTOU | Apply 时重新 realpath/symlink 检查(I-安全边界) |
| L-09 | Goal-level A→B→C→A loop (Anti-loop 局部动作级) | 🟡 需长期验证 | execution_record 主比较 action/result/evidence 局部 | Anti-loop 正确性缺口, 建议 long-running 验证非本轮修 |
| L-10 | Snapshot 对 create 文件无完整 crash recovery 语义 | 🟡 需长期验证 | take_snapshot 跳过 os.path.exists=False; apply_patch 单次异常有内存回滚, 但多步中途崩溃在 create 上无 delete 语义 | long-running test 佐证 |
| L-11 | Task ID / Orchestrator Task ID namespace 不统一 | 🟡 后置 | orchestrator T1/T2 vs task_manager task_UUID | 明确 plan_task_id / persistent_task_id 语义 |
| L-12 | Verification independence (LLM 伪造 evidence) | 🟡 后置 | source=verification 不能自证独立 | 检查 verification_method/evidence_ref/execution_id/independent_source 闭环 |

> 注: L-01/02/03/04/05/07/08 共 8 项经我方 clone 源码核实**属实**; L-06 属实但偏轻; L-09/10 为长期验证; L-11/12 后置。

### 第二轮深审 (2026-08-19) — 跨模块调用链走查新增点 (父选择 C)
> 照“Persistence → State Machine → Execution Record → Anti-loop → Permission → Verification → Ontology → Self-Evolution → Crash Recovery”走了一遍跨模块调用链。重点找“单文件无恙、接合处断裂”。以下为新增核实点（补充上表，不重复）。

| # | 问题 | 核实 | 精确定位 | 处置建议 |
|----|------|------|---------|---------|
| L-13 | link.py 重复实现一套并行 Anti-loop (retry_count/escalation) | 🔴 属实 | task-manager/scripts/link.py cmd_result_to_task: 自己 `retry_count+1`、`>=3 escalation`、`escalated_at` 去重 —— 与 execution_record.check_action_loop (v1.3 P1-1 统一的那套) 平行。同 goal 下两套各自计数, 可能重复 escalation / 计数不一致 | 统一走 execution_record, link 层只做状态回填不再自算 retry |
| L-14 | link.py sync-memory 裸 append 未走原子写/锁 | 🟡 较轻 | link.py cmd_sync_memory: `open(mem_file,"a")` 直接写; 与其它写 memory 的模块并发会交错 | 统一走 persistence.append_atomic, 或写入前加锁 |
| L-15 | link.py 全 subprocess 无事务边界 → 半完成状态 | 🟡 较轻 | link.py cmd_result_to_task: 先 update RUNNING 成功, 再 update target 失败 → task 悬在 RUNNING; 跨子进程无事务 | 需可重入/幂等的状态回程, 或失败补尝置回 |
| L-16 | Task Manager update 有状态机保护, create 泄漏 (L-07 补充确认) | 🔴 证实 | update: `if ns not in VALID_TRANSITIONS.get(old,set()): raise` ✅ 有保护; create: normalize_task 只 `if st in VALID_STATUS` 直接放行 → 唯 create 可绕过 | 只修 create (限定初始态), update 已没问题 |
| L-17 | Ontology entities/relations.jsonl (source of truth) 裸 append + read_log 静默跳损坏行 | 🔴 属实 | ontology.py append_log 全用裸 `open("a")` (未走 append_atomic); read_log `except json.JSONDecodeError: continue` 静默跳过 → read_entities 靠重放重建, 崩溃半行/并发交错导致实体静默丢失。比 L-02 更严重: 这是 ontology 的 source of truth 本身 | entities/relations 改 append_atomic; read_log 损坏行向 status/metrics 暴露 corruption 计数而非静默跳 |

> 深审结论与 ChatGPT 一致: 全是 hardening/状态机/持久化/故障语义, 无架构错误, 不需要 OS2。跨模块接合处出现的断裂 (L-13 两套 anti-loop、L-15 无事务) 正是“单文件无恙、接起来断裂”的实证。

### 建议冻结的 12 条底层不变量 (作为 Agent OS 底线宪法, 以后任何 commit 先回归)

I-001 OpenClaw owns Runtime. Agent OS never owns the Agent Loop.
I-002 OpenClaw Native Policy/Approval 是最终执行边界.
I-003 Agent OS Permission 是 fail-closed.
I-004 Tool success ≠ Task success.
I-005 Verification 不能由产生该 claim 的同一执行自证.
I-006 Execution Record 是 append-only observability, 不是 Runtime.
I-007 Mutable state 用事务级 read-modify-write locking.
I-008 损坏状态(CORRUPTED) ≠ 空状态(NOT_FOUND).
I-009 每个状态转换必须过状态机.
I-010 Self-Evolution 不能制造 Evidence.
I-011 Self-Evolution 不能绕过 Permission/Approval/Verification.
I-012 Evolution artifacts 必须保持一条一致的 evolution_id 链.
I-013 Every autonomous Task (Proactive/Self-Evolution/Autonomous 创建) 必须能追溯到恰一个 active Goal, 或显式声明为 standalone (人工一次性任务不强制).
I-014 Task state 由 execution history 派生或用状态机显式控制, 绝不通过破坏性覆盖 execution history 达成.
I-015 UNKNOWN execution outcome 在可能产生外部副作用 (转账/发消息/下单/删除/commit Git/改生产文件) 时 MUST NOT 被自动 retry.

## 自主闭环审查轮 (2026-08-19) — Goal→Task→Execution→Action→Observation→Evidence→Verification→Transition→Completion (ChatGPT 第二轮)
> 审查对象从"找字段 bug"升级为整个 Agent OS 核心自主闭环。核心结论: 自我循环的真正源不是"重复 action"(L1 已防), 而是"Goal 无进展仍在推进当前 Action"(L3 Goal-loop, A→B→C→D 每步不重复但 goal_progress=0)。不要求新架构, 要求把现有机制硬化。(基线 a40b914)

### 跨模块闭环与三个新不变量 (I-013/014/015) 核实

| 不变量/论断 | 核实 | 源码证据 | 现状 |
|----|------|---------|------|
| I-013 Task→Goal 强制溯源 | 🔴 属实(缺口) | task_manager.py normalize_task: `goal_id: data.get("goal_id")` 无任何强制校验; proactive/link 创建的任务带 goal_id 但系统不验证其存在/active | goal_id 只是 metadata, 非不变量; 自主创建的任务无 goal provenance 强制 |
| I-014 Task vs Execution 分离 | 🔴 属实(缺口) | task_manager.py 只有 `history`(状态变更列表)+`retry_count`, 无独立 Execution #; orchestrator plan 纯生成不持久化每次 execution; `Task.status=RUNNING` 覆盖执行信息 | 无 Execution # 概念, 无 attempt 级历史; Anti-loop/成本/Self-Evolution 缺可靠数据 |
| I-015 UNKNOWN 不自动 retry | 🟢 已防护(部分) | link.py L253-271: `unknown→WAITING` + `execution_state=UNKNOWN` + reason="不自动重试" (即 v1.3 早修的 #14) | 主路径已满足; 剩余: Recovery scanner 对"副作用已发生"的 UNKNOWN 判定 (见 L-18) |
| Anti-loop L1 Action | ✅ 已有 | execution_record.check_action_loop 主比较 action/result/evidence/state/strategy/input | 已统一 (P1-1) |
| Anti-loop L2 State | 🟡 缺 | 无 RUNNING↔WAITING 等状态振荡检测 | 增强项 |
| Anti-loop L3 Goal | 🟡 仅布尔 | execution_record 有 `goal_progress` 布尔 (v1.3 #11), 无 Progress Vector (stall_count/cycle_signature/last_progress_at/progress_count) | 增强项: Goal Progress Vector |
| Recovery Scanner | 🟢 已有雏形 | recovery.py run_crash_recovery 检测 APPLYING 中断; 复用 CLI/heartbeat 触发, 未自造 scheduler | 方向正确; 副作用判定见 L-18 |

### 新增审查项

| # | 问题 | 核实 | 处置 |
|----|------|------|------|
| L-18 | Recovery 需先判断"副作用是否已发生"再决定 RETRY/VERIFY (删除/提交等可能已执行的副作用) | 🟡 属实(需补) | recovery/recover_apply 对可能有副作用的 operation 返回人工 VERIFY, 不盲 RETRY (I-015 落地) |

### A/B/C 三类清单 (ChatGPT 建议 + 我方核实)
**A 类必修**: AE-1 save_artifact 事务化 (=L-01) / AE-2 Evidence append_atomic (=L-02) / AE-3 evolution_id 不一致 REJECT (=L-03) / AE-4 rollback 过状态机 (=L-04) / AE-5 Proactive 损坏≠空 (=L-05) / AE-6 Orchestrator 损坏≠空 (=L-06) / AE-7 Task create 不绕状态机 (=L-16) / AE-8 apply 重做 path/symlink (=L-08)
**B 类增强** (增量, I-013/014/L2/L3/L-18) — **✅ 全部完成 (分支 fix/v1.4-hardening-b, commit b97a711/80b24ca/ffeecab/797e174)**
- BE-1 Goal→Task provenance (I-013) ✅ task_manager goal_id 显式默认空串, 独立 standalone 语义
- BE-2 Task↔Execution 分离 (I-014) ✅ task 新增 executions/attempt 历史: RUNNING 记 attempt, 离开记 outcome
- BE-3 Action→Observation 对应 ✅ execution_record 加 observation/observation_hash, 纳入 progress
- BE-4 Evidence→Verification 来源链 ✅ record 加 verification{method,evidence_ref,independent_source}
- BE-5 Goal Progress Vector (L3) ✅ progress 加 stall_count/cycle_signature/progress_count/last_progress_at
- BE-6 State-loop 检测 (L2) ✅ progress 加 state_oscillation, check 检测状态对振荡→ESCALATE
- BE-7 UNKNOWN 副作用回收 (L-18) ✅ recover_apply 副作用边界: type!=file_patch→VERIFY(不自动 retry)
- BE-8 crash recovery 完整 ✅ 修 recover_apply 三元优先级 bug(mism=[] 返字符串而非元组)
**C 类不动**: Windows stale lock / scope 复杂继承 / 多主机 / 自造 scheduler / event bus / model runtime / memory runtime

### 结论
与第一轮一致: 全部是 hardening/状态机/持久化/故障语义, 无架构错误, 不需要 OS2。跨模块闭环的核心发现: L1 Anti-loop 已覆盖"重复动作", 但缺 L2 State-loop / L3 Goal Progress Vector——这是"模型偶尔陷入循环"(A→B→C→D 每步不重复但 goal 无进展)的底层根源, 属 B 类增强而非当前 A 类必修。

### 下一阶段重点 (ChatGPT 建议 + 我方认同)
不是继续加功能, 而是把底层逻辑证明到足够可靠: Persistence → State Machine → Execution Record → Anti-loop → Permission → Verification → Ontology → Self-Evolution → Crash Recovery, 再走一遍全部跨模块调用链 (单独每文件无恙, 两模块接合可能出现语义断裂)。
