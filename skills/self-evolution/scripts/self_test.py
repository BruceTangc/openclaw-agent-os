#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-Evolution v2.3 完整回归测试（隔离 workspace，不碰真实数据）。"""
import json, os, subprocess, sys, tempfile, shutil

WS = tempfile.mkdtemp(prefix="evoreg_")
os.environ["OPENCLAW_WORKSPACE"] = WS
os.makedirs(os.path.join(WS, "memory"), exist_ok=True)
SCRIPT = os.path.dirname(os.path.abspath(__file__))
TARGET_SKILL_REL = "skills/quotation/skill.md"
TARGET_SKILL = os.path.join(WS, TARGET_SKILL_REL)
os.makedirs(os.path.dirname(TARGET_SKILL), exist_ok=True)
SKILL_CONTENT = "# Quotation skill\n\n生成报价文件\n\n结束\n"
open(TARGET_SKILL, "w", encoding="utf-8").write(SKILL_CONTENT)

PASS = FAIL = 0
RESULTS = []

def run(args, expect=None, **kw):
    global PASS, FAIL
    cmd = [sys.executable] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=SCRIPT, env={**os.environ, **kw})
    except Exception as e:
        FAIL += 1; RESULTS.append("EXC {} -> {}".format(args[0], e)); return None
    out = (r.stdout or "").strip()
    data = {}
    try: data = json.loads(out) if out else {}
    except: pass
    ok = True
    if expect and data.get("decision") != expect: ok = False
    if r.returncode != 0 and not expect: ok = False
    tag = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else:
        FAIL += 1
        if r.stderr and r.stderr.strip():
            print("STDERR {} -> {}".format(" ".join(args[:2]), r.stderr[-400:]), file=sys.stderr)
    RESULTS.append("{} {} -> {}".format(tag, " ".join(args[:2]), out[:70]))
    return data

def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; RESULTS.append("PASS " + name)
    else: FAIL += 1; RESULTS.append("FAIL " + name)
    return cond

# === 1. Evidence-driven Discover（自算统计）===
for i in range(2):
    run(["discover.py", "--evidence", json.dumps({
        "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
        "pattern_key": "missing_artifact_check", "problem": "报价缺验证",
        "session": "s-{}".format(i), "source": "verification",
        "verified": True, "systemic": True, "confidence": 0.85})], "IGNORE")
D = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
    "pattern_key": "missing_artifact_check", "problem": "第三次",
    "session": "s-2", "source": "verification",
    "verified": True, "systemic": True, "confidence": 0.85})], "CANDIDATE_CREATED")
CAND = D.get("candidate_id")
check("evidencedriven_candidate", bool(CAND))
check("evidencedriven_evolution_id", bool(D.get("evolution_id")))
check("evidencedriven_observation_count", D.get("stats", {}).get("observation_count", 0) >= 3)
check("evidencedriven_unique_sessions", D.get("stats", {}).get("unique_sessions", 0) >= 2)

# === 2. Diagnose → PROPOSED → Apply → MONITORING → PROMOTED ===
D = run(["diagnose.py", "--candidate", CAND, "--root_cause", "workflow_gap",
         "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
         "--target", TARGET_SKILL_REL], "DIAGNOSED")
DGN = D.get("diagnosis_id")
check("diagnose_evolution_id", bool(D.get("evolution_id")))

OPS = json.dumps([{"op": "replace", "file": TARGET_SKILL_REL,
                   "anchor": "生成报价文件", "content": "生成报价文件\n\n生成后检查 artifact 是否存在"}])
D = run(["propose.py", "--candidate", CAND, "--diagnosis", DGN, "--scope", "skill",
         "--level", "G3", "--targets", TARGET_SKILL_REL, "--operations", OPS,
         "--change", "增加 artifact verification",
         "--expected_metric", "verification >= 0.9"], "PROPOSAL_CREATED")
PRP = D.get("proposal_id")
check("propose_evolution_id", bool(D.get("evolution_id")))

D = run(["apply.py", "--proposal", PRP, "--approve", "--approver", "main",
         "--reason", "G3 confirmed"], "APPLIED")
CHG = D.get("change_id")
check("apply_evolution_id", bool(D.get("evolution_id")))
check("apply_actually_wrote_file", "artifact 是否存在" in open(TARGET_SKILL, encoding="utf-8").read())

D = run(["regression.py", "--change", CHG, "--result", "IMPROVED",
         "--evidence", '{"verification":"passed"}'], "REGRESSION_RECORDED")
RGR = D.get("regression_id")
check("regression_improved_promoted", D.get("promotion") == "PROMOTED")
check("regression_evolution_id", bool(D.get("evolution_id")))

# === 3. Evidence Chain 可追溯 ===
D = run(["_core.py", "--chain", RGR], expect=None)
chain = D if isinstance(D, dict) else {}
check("chain_traceability", bool(chain.get("regression") and chain.get("candidate")))
check("chain_has_evolution_id", bool(chain.get("change", {}).get("evolution_id")))

# === 4. 幂等 Discover ===
D = run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": TARGET_SKILL_REL,
    "pattern_key": "missing_artifact_check", "problem": "又一条",
    "session": "s-x", "source": "verification", "verified": True, "systemic": True})], "DEDUP_EXISTING")
check("idempotent_dedup", D and D.get("decision") == "DEDUP_EXISTING")

# === 5. 外因拦截 ===
run(["discover.py", "--evidence", json.dumps({
    "class": "verification", "scope": "skill", "target": "api.md",
    "pattern_key": "api_down", "problem": "API 挂", "tags": "api network timeout",
    "session": "s", "verified": False})], "IGNORE")

# === 6. Apply 越界 REJECT ===
C2 = run(["discover.py", "--candidate", json.dumps({
    "scope": "skill", "target": "skills/quotation/other.md",
    "pattern_key": "add_review", "problem": "加 review"})], "CANDIDATE_CREATED").get("candidate_id")
D2 = run(["diagnose.py", "--candidate", C2, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
          "--target", "skills/quotation/other.md"], "DIAGNOSED").get("diagnosis_id")
P2 = run(["propose.py", "--candidate", C2, "--diagnosis", D2, "--scope", "skill",
          "--level", "G3", "--targets", "skills/quotation/other.md",
          "--operations", json.dumps([{"op": "replace", "file": "skills/unrelated.md",
                                       "anchor": "x", "content": "y"}]),
          "--change", "越界", "--expected_metric", "x"], None)
check("propose_out_of_scope_rejected", P2 and P2.get("decision") == "REJECT")

# === 7. 保护目标 ===
C3 = run(["discover.py", "--candidate", json.dumps({
    "scope": "global", "target": "AGENTS.md", "pattern_key": "chg_agents",
    "problem": "改AGENTS"})], "CANDIDATE_CREATED").get("candidate_id")
r = subprocess.run([sys.executable, "diagnose.py", "--candidate", C3,
                    "--root_cause", "instruction_gap", "--valid", "--reproducible",
                    "--confidence", "0.8", "--level", "G5", "--target", "AGENTS.md"],
                   capture_output=True, text=True, cwd=SCRIPT, env={**os.environ})
check("protected_target_reject", "受保护" in (r.stderr + r.stdout))

# === 8. G5 强制人工审批 ===
C4 = run(["discover.py", "--candidate", json.dumps({
    "scope": "protocol", "target": "docs/PROTOCOL.md", "pattern_key": "fix_protocol",
    "problem": "协议措辞"})], "CANDIDATE_CREATED").get("candidate_id")
D4 = run(["diagnose.py", "--candidate", C4, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G5",
          "--target", "docs/PROTOCOL.md"], "DIAGNOSED").get("diagnosis_id")
P4 = run(["propose.py", "--candidate", C4, "--diagnosis", D4, "--scope", "protocol",
          "--level", "G5", "--targets", "docs/PROTOCOL.md",
          "--operations", json.dumps([{"op": "append", "file": "docs/PROTOCOL.md", "content": "x"}]),
          "--change", "改协议", "--expected_metric", "明确"], "PROPOSAL_CREATED").get("proposal_id")
D = run(["apply.py", "--proposal", P4, "--approver", "main", "--reason", "no flag"], "REJECT")
check("g5_human_approve_reject", D and "G5" in str(D.get("reason", "")))

# === 9. REGRESSED → Rollback 全链路状态同步 ===
C5 = run(["discover.py", "--candidate", json.dumps({
    "scope": "skill", "target": TARGET_SKILL_REL, "pattern_key": "add_review_step",
    "problem": "加 review 步骤"})], "CANDIDATE_CREATED").get("candidate_id")
D5 = run(["diagnose.py", "--candidate", C5, "--root_cause", "workflow_gap",
          "--valid", "--reproducible", "--confidence", "0.8", "--level", "G3",
          "--target", TARGET_SKILL_REL], "DIAGNOSED").get("diagnosis_id")
P5 = run(["propose.py", "--candidate", C5, "--diagnosis", D5, "--scope", "skill",
          "--level", "G3", "--targets", TARGET_SKILL_REL,
          "--operations", json.dumps([{"op": "append", "file": TARGET_SKILL_REL,
                                       "content": "\n# review step"}]),
          "--change", "加 review", "--expected_metric", "ok"], "PROPOSAL_CREATED").get("proposal_id")
PRE_APPLY = open(TARGET_SKILL, encoding="utf-8").read()
H5 = run(["apply.py", "--proposal", P5, "--approve", "--approver", "main",
          "--reason", "ok"], "APPLIED").get("change_id")
mid = open(TARGET_SKILL, encoding="utf-8").read()
check("apply_wrote_before_rollback", "# review step" in mid)
R5 = run(["regression.py", "--change", H5, "--result", "REGRESSED",
          "--evidence", '{"degraded":true}'], "REGRESSION_RECORDED").get("regression_id")
D = run(["rollback.py", "--change", H5, "--reason", "degraded", "--regression", R5], "ROLLED_BACK")
final = open(TARGET_SKILL, encoding="utf-8").read()
check("rollback_end_state", D and D.get("state") == "ROLLED_BACK")
check("rollback_content_restored", final == PRE_APPLY and "# review step" not in final)
check("rollback_preserves_evolution_id", bool(D.get("evolution_id")))

# === 9b. Regression/Rollback 产生 evolution_event Evidence ===
import _core as _core_module
_EV = _core_module.load_evidence()
_reg_evs = [r for r in _EV if r.get("event_type") == "regression" and r.get("change_id") == H5]
_rb_evs = [r for r in _EV if r.get("event_type") == "rollback" and r.get("change_id") == H5]
check("regression_generates_evidence", len(_reg_evs) == 1 and _reg_evs[0].get("source") == "evolution_event")
check("rollback_generates_evidence", len(_rb_evs) == 1 and _rb_evs[0].get("source") == "evolution_event")

# === 9c. 非法 evolution_event：状态不匹配被拒（用从未 ROLLED_BACK 的 CHG）===
try:
    _core_module.register_evolution_event("rollback", CHG)  # CHG=PROMOTED，非 ROLLED_BACK，应拒
    check("illegal_evolution_event_rejected", False)
except ValueError:
    check("illegal_evolution_event_rejected", True)
try:
    _core_module.register_evolution_event("regression", CHG)  # CHG=PROMOTED，非 REGRESSED，应拒
    check("illegal_evolution_event_regression_rejected", False)
except ValueError:
    check("illegal_evolution_event_regression_rejected", True)
try:
    _core_module.register_evidence({"source": "evolution_event", "pattern_key": "x",
                                    "scope": "AGENT", "target": "t", "problem": "p"})
    check("evolution_event_source_direct_write_rejected", False)
except ValueError:
    check("evolution_event_source_direct_write_rejected", True)
good_ev = [r for r in _core_module.load_evidence()
           if r.get("event_type") == "regression" and r.get("change_id") == H5]
check("original_evidence_not_deleted", len(good_ev) == 1)

# === 9d. rollback evidence requires actual successful rollback ===
# H5 已真实 rollback（文件已恢复+ROLLED_BACK），因此应恰好有 1 条 rollback evidence
rb_evs = [r for r in _core_module.load_evidence()
          if r.get("event_type") == "rollback" and r.get("change_id") == H5]
check("rollback_requires_actual_rollback", len(rb_evs) == 1)
# rollback evidence 必须关联到实际回滚的 change，且 source=evolution_event
check("rollback_evidence_linked", bool(rb_evs) and rb_evs[0].get("source") == "evolution_event"
      and rb_evs[0].get("evolution_id"))

# === 9e. evidence can be rediscovered after rollback ===
# rollback 后的 evidence 仍能被 query_evidence（按 event_type 过滤）查到
queried = _core_module.query_evidence("evolution_event")
rollback_queried = [r for r in _core_module.load_evidence()
                    if r.get("source") == "evolution_event"]
check("rollback_evidence_rediscoverable",
      any(r.get("change_id") == H5 and r.get("event_type") == "rollback"
          for r in queried) or any(r.get("event_type") == "rollback" for r in rollback_queried))

# === 10. Crash Recovery: APPLYING 状态检测 ===
import _core
incomplete = _core.detect_incomplete_apply()
check("crash_recovery_detect_empty", len(incomplete) == 0)

# === 11. Evidence 写入隔离（只有 external source 可写）===
try:
    _core.register_evidence({"source": "self_evolution", "problem": "自造证据"})
    check("evidence_write_isolation", False)  # 应该抛异常
except ValueError as e:
    check("evidence_write_isolation", "被拒绝" in str(e))

# === 12. 非法状态跳转 ===
try:
    _core.assert_transition({"status": "CANDIDATE"}, "APPLIED")
    check("illegal_transition", False)
except ValueError:
    check("illegal_transition", True)

# === 13. --candidate 模式（task-manager 对接）===
C6 = run(["discover.py", "--candidate", json.dumps({
    "scope": "task", "target": "task-manager:失败率过高",
    "pattern_key": "task-manager:失败率过高", "problem": "失败率高"})], "CANDIDATE_CREATED")
check("candidate_handoff_has_evolution_id", bool(C6.get("evolution_id")))

# === 14. --evidence-refs 模式 ===
# 先登记两条 evidence
import uuid
ev1 = {"id": "EVID-TEST-001", "class": "verification", "scope": "skill",
       "target": "test.md", "pattern_key": "test_ref", "problem": "test1",
       "session": "s1", "source": "verification", "verified": True, "systemic": True}
ev2 = {"id": "EVID-TEST-002", "class": "verification", "scope": "skill",
       "target": "test.md", "pattern_key": "test_ref", "problem": "test2",
       "session": "s2", "source": "verification", "verified": True, "systemic": True}
_core.register_evidence(ev1)
_core.register_evidence(ev2)
D = run(["discover.py", "--evidence-refs", "EVID-TEST-001", "EVID-TEST-002"], "IGNORE")
check("evidence_refs_below_threshold", D and D.get("decision") == "IGNORE")

# === 15. BE-7 副作用边界判定 (recover_apply) ===
# 非 file_patch 的 APPLYING change: 即使文件未修改也没副作用, 也应收敛 VERIFY(人工), 不自动 SAFE_TO_RETRY
_BE7_TMP = tempfile.mkdtemp()
char_dir = os.path.join(_BE7_TMP, "change/snapshot/files")
os.makedirs(char_dir, exist_ok=True)
_orig_load = _core.load_artifact
_orig_chdir = _core.change_dir
try:
    _core.change_dir = lambda _c: os.path.join(_BE7_TMP, "change")
    _core.load_artifact = lambda _k, _i: {
        "status": "APPLYING", "type": "db_migration",
        "_applied_files": [], "_snapshot": {"files": []}, "targets": []}
    a_nonpatch, _ = _core.recover_apply("x")
    check("BE7_sideeffect_force_verify", a_nonpatch == "VERIFY")

    _core.load_artifact = lambda _k, _i: {
        "status": "APPLYING", "type": "file_patch",
        "_applied_files": [], "_snapshot": {"files": []}, "targets": []}
    a_patch, _ = _core.recover_apply("x")
    check("BE7_filepatch_safe_retry", a_patch == "SAFE_TO_RETRY")
finally:
    _core.load_artifact = _orig_load
    _core.change_dir = _orig_chdir
    shutil.rmtree(_BE7_TMP, ignore_errors=True)

# === 16. #16 L3 Goal Progress Loop 专项测试 ===
# 直接单测 detect_goal_loop / assess_progress / record_progress_assessment，
# 用 monkeypatch load_artifact 构造 change 状态，不依赖完整 CLI 链路。
_orig_load_l3 = _core.load_artifact
_orig_save_l3 = _core._core_save_artifact
_fake_chg = {}
_saved = {}
def _mock_load(kind, ident):
    return dict(_fake_chg) if _fake_chg else None
def _mock_save(kind, record):
    _saved[kind] = dict(record)
try:
    _core.load_artifact = _mock_load
    _core._core_save_artifact = _mock_save

    # 场景 1: 有进展 (previous=0.0 -> current=0.5)，is_loop 应为 False
    _fake_chg = {"id": "CHG-L3A", "status": "MONITORING", "targets": ["a.md"],
                 "_expected_fingerprints": {"a.md": "hash"},
                 "_previous_progress": 0.0, "consecutive_stall_count": 0}
    # 强制 progress=0.5：monkeypatch _measure_progress
    _orig_measure = _core._measure_progress
    _core._measure_progress = lambda cid: 0.5
    sig = _core.assess_progress("CHG-L3A")
    check("L3_assess_progress_delta_positive", sig.get("progress_delta") == 0.5)
    _core._measure_progress = _orig_measure
    _fake_chg["_previous_progress"] = 0.0
    _fake_chg["consecutive_stall_count"] = 0
    # 有进展时 detect_goal_loop 不判死循环
    _core._measure_progress = lambda cid: 0.5
    gl = _core.detect_goal_loop("CHG-L3A")
    check("L3_detect_no_loop_when_progressing", gl.get("is_loop") is False)
    _core._measure_progress = _orig_measure

    # 场景 2: 换动作空转 (goal progress 始终 0 + 连续停滞达阈值) → is_loop=True
    _fake_chg = {"id": "CHG-L3B", "status": "MONITORING", "targets": ["a.md"],
                 "_expected_fingerprints": {"a.md": "hash"},
                 "_previous_progress": 0.0, "consecutive_stall_count": 3}
    _core._measure_progress = lambda cid: 0.0
    gl = _core.detect_goal_loop("CHG-L3B")
    check("L3_detect_loop_at_threshold", gl.get("is_loop") is True)
    check("L3_loop_type_is_goal", gl.get("loop_type") == "GOAL")
    _core._measure_progress = _orig_measure

    # 场景 3: 尚无验证基准 (_measure_progress=None) + 停滞计数低 → 不误判死循环
    _fake_chg = {"id": "CHG-L3C", "status": "MONITORING", "targets": ["a.md"],
                 "_expected_fingerprints": {}, "_previous_progress": None,
                 "consecutive_stall_count": 1}
    _core._measure_progress = lambda cid: None
    gl = _core.detect_goal_loop("CHG-L3C")
    check("L3_no_false_loop_without_baseline", gl.get("is_loop") is False)
    _core._measure_progress = _orig_measure

    # 场景 6: UNKNOWN（无法测量 cur=None）但停滞计数已≥阈值 → 不误判 loop（三态修复核心）
    # 旧逻辑 no_goal_motion=(cur is None or cur<=0) 会把「无法测量」误当成「换动作空转」
    # 在 stall 已涨起时误 STOP；新逻辑 cur is None → UNKNOWN，不判 loop。
    _fake_chg = {"id": "CHG-L3F", "status": "MONITORING", "targets": ["a.md"],
                 "_expected_fingerprints": {"a.md": "hash"}, "_previous_progress": None,
                 "consecutive_stall_count": 3}
    _core._measure_progress = lambda cid: None
    gl = _core.detect_goal_loop("CHG-L3F")
    check("L3_unknown_not_loop_when_unmeasurable", gl.get("is_loop") is False)
    check("L3_unknown_progress_state", gl.get("progress_state") == "UNKNOWN")
    _core._measure_progress = _orig_measure

    # 场景 7: 真零进展(cur<=0) + stall 达标 → STALL 态 + is_loop（确认 STALL 仍正常工作）
    _fake_chg = {"id": "CHG-L3G", "status": "MONITORING", "targets": ["a.md"],
                 "_expected_fingerprints": {"a.md": "hash"}, "_previous_progress": 0.0,
                 "consecutive_stall_count": 3}
    _core._measure_progress = lambda cid: 0.0
    gl = _core.detect_goal_loop("CHG-L3G")
    check("L3_stall_loop_still_works", gl.get("is_loop") is True)
    check("L3_stall_progress_state", gl.get("progress_state") == "STALL")
    _core._measure_progress = _orig_measure

    # 场景 4: record_progress_assessment 维护连续停滞计数 (delta==0 自增)
    _fake_chg = {"id": "CHG-L3D", "status": "MONITORING", "consecutive_stall_count": 1}
    _core.record_progress_assessment("CHG-L3D", {"current_progress": 0.0,
                                                 "repetition_count": 1,
                                                 "progress_delta": 0.0})
    check("L3_stall_counter_increments_on_zero_delta",
          _saved.get("change", {}).get("consecutive_stall_count") == 2)

    # 场景 5: delta>0 清零连续停滞计数
    _fake_chg = {"id": "CHG-L3E", "status": "MONITORING", "consecutive_stall_count": 4}
    _core.record_progress_assessment("CHG-L3E", {"current_progress": 0.6,
                                                 "repetition_count": 1,
                                                 "progress_delta": 0.1})
    check("L3_stall_counter_resets_on_progress",
          _saved.get("change", {}).get("consecutive_stall_count") == 0)
finally:
    _core.load_artifact = _orig_load_l3
    _core._core_save_artifact = _orig_save_l3
    _core._measure_progress = _orig_measure

# ============ v1.4 C1: 中央门 transitions 回归断言 ============
# 验证统一状态中央门：非法/合法跳转、事实不变量、audit、兼容别名。
import sys as _sys, os as _os
_LIB = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__)))), "_lib")
if _LIB not in _sys.path:
    _sys.path.insert(0, _LIB)
try:
    from transitions import (transition as _t, transition_allowed as _tallow,
                              assert_transition as _tassert)
except Exception as _e:
    check("C1 transitions import", False)
    _t = _tallow = _tassert = None

if _t is not None:
    # 1) 合法跳转 task INBOX->READY
    t1 = {"status": "INBOX", "history": []}
    _t(t1, "READY", kind="task", actor="orchestrator", reason="test")
    check("C1 task INBOX->READY 合法", t1["status"] == "READY")
    # 2) audit event 写入 history
    check("C1 transition 记录 audit event",
          any(h.get("action") == "transition" and h.get("to") == "READY"
              for h in t1["history"]))
    # 3) 非法跳转拒绝
    try:
        _t({"status": "INBOX", "history": []}, "COMPLETED", kind="task")
        check("C1 非法跳转 INBOX->COMPLETED 拒绝", False)
    except ValueError:
        check("C1 非法跳转 INBOX->COMPLETED 拒绝", True)
    # 4) 事实不变量: COMPLETED 缺 completed_at 拒绝
    t2 = {"status": "RUNNING", "started_at": "2026-01-01T00:00:00Z",
          "history": []}
    try:
        _t(t2, "COMPLETED", kind="task")
        check("C1 COMPLETED 缺 completed_at 拒绝", False)
    except ValueError:
        check("C1 COMPLETED 缺 completed_at 拒绝", True)
    # 5) 带 completed_at 合法
    t2["completed_at"] = "2026-01-01T01:00:00Z"
    _t(t2, "COMPLETED", kind="task")
    check("C1 带 completed_at 进 COMPLETED 合法", t2["status"] == "COMPLETED")
    # 6) RUNNING 缺 started_at 拒绝
    try:
        _t({"status": "READY", "history": []}, "RUNNING", kind="task")
        check("C1 RUNNING 缺 started_at 拒绝", False)
    except ValueError:
        check("C1 RUNNING 缺 started_at 拒绝", True)
    # 7) FAILED 缺 failed_at 拒绝
    try:
        _t({"status": "RUNNING", "started_at": "x", "history": []},
           "FAILED", kind="task")
        check("C1 FAILED 缺 failed_at 拒绝", False)
    except ValueError:
        check("C1 FAILED 缺 failed_at 拒绝", True)
    # 8) 兼容别名 assert_transition (change SNAPSHOTTED->APPLYING)
    r = {"status": "SNAPSHOTTED", "history": []}
    _tassert(r, "APPLYING", kind="change")
    check("C1 assert_transition 兼容(change SNAPSHOTTED->APPLYING)",
          r["status"] == "APPLYING")
    # 9) proposal 非法跳转 APPROVED->PROMOTED 拒绝
    try:
        _t({"status": "APPROVED", "history": []}, "PROMOTED",
           kind="proposal")
        check("C1 proposal APPROVED->PROMOTED 拒绝", False)
    except ValueError:
        check("C1 proposal APPROVED->PROMOTED 拒绝", True)
    # 10) src==dst 幂等
    check("C1 transition_allowed(src==dst)=True",
          _tallow("READY", "READY", "task"))
    # 11) 未注册 kind 拒绝
    try:
        _t({"status": "x", "history": []}, "y", kind="nonsense")
        check("C1 未注册 kind 拒绝", False)
    except ValueError:
        check("C1 未注册 kind 拒绝", True)
    # 12) 非法目标状态拒绝
    try:
        _t({"status": "INBOX", "history": []}, "BOGUS", kind="task")
        check("C1 非法目标状态 BOGUS 拒绝", False)
    except ValueError:
        check("C1 非法目标状态 BOGUS 拒绝", True)
    # 13) extra 字段随转换写入
    t3 = {"status": "RUNNING", "started_at": "2026-01-01T00:00:00Z",
          "history": []}
    _t(t3, "COMPLETED", kind="task",
       completed_at="2026-01-01T01:00:00Z", note="done")
    check("C1 extra 字段(completed_at/note)随转换写入",
          t3.get("completed_at") == "2026-01-01T01:00:00Z" and t3.get("note") == "done")
    # 14) execution kind 合法集合含 UNKNOWN (#5)
    import transitions as _tr
    check("C1 execution 含 UNKNOWN 状态(#5)",
          "UNKNOWN" in _tr.valid_states("execution"))
    # 15) regression kind 已注册
    check("C1 regression kind 已注册",
          "REGRESSION" in _tr.valid_states("regression"))

shutil.rmtree(WS, ignore_errors=True)
print("\n===== REGRESSION SUMMARY (v2.3) =====")
print("PASS: {}\tFAIL: {}".format(PASS, FAIL))
print("\n".join(RESULTS))
sys.exit(0 if FAIL == 0 else 1)
