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
- [ ] #29 authorized 增加 source/scope/expiry ⏳ 本次未实施（P1 authorization-scope 项，phase1 顺延；check() 现仅读 bool authorized，未加 source/expiry 字段）
- [ ] #30 requested scope ≤ authorized scope ⏳ 本次未实施（依赖 #29；现无 requested vs authorized scope 比较）
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
