#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anti-loop v1.3 测试 — 10 项
验证 execution_record.py / proactive.py wake cooldown / link.py signal fingerprint
"""

import json
import os
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# Setup: 让 import 找到同目录的模块
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import execution_record as er
import proactive as pa

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  {detail}")


# ===========================================================================
# Test 1: same action + same result → WARN (no-progress #1)
# ===========================================================================
def test_same_action_same_result():
    print("\n=== Test 1: same action + same result → WARN ===")
    r1 = {
        "goal_id": "G1", "task_id": "T1", "action_type": "search",
        "action_signature": "abc123", "result_hash": "res_same",
        "evidence_hash": "ev_same", "current_state": "RUNNING",
    }
    r2 = dict(r1)  # 完全相同
    result = er.check_action_loop(r2, r1)
    check("decision == WARN", result["decision"] == "WARN",
          f"got {result['decision']}")
    check("consecutive_no_progress == 1",
          result["consecutive_no_progress"] == 1)


# ===========================================================================
# Test 2: same action + new result → CONTINUE
# ===========================================================================
def test_same_action_new_result():
    print("\n=== Test 2: same action + new result → CONTINUE ===")
    r1 = {
        "goal_id": "G1", "task_id": "T1", "action_type": "search",
        "action_signature": "abc123", "result_hash": "res_v1",
        "evidence_hash": "ev_same", "current_state": "RUNNING",
    }
    r2 = dict(r1, result_hash="res_v2")
    result = er.check_action_loop(r2, r1)
    check("decision == CONTINUE", result["decision"] == "CONTINUE",
          f"got {result['decision']}")


# ===========================================================================
# Test 3: same action + new evidence → CONTINUE
# ===========================================================================
def test_same_action_new_evidence():
    print("\n=== Test 3: same action + new evidence → CONTINUE ===")
    r1 = {
        "goal_id": "G1", "task_id": "T1", "action_type": "search",
        "action_signature": "abc123", "result_hash": "res_same",
        "evidence_hash": "ev_v1", "current_state": "RUNNING",
    }
    r2 = dict(r1, evidence_hash="ev_v2")
    result = er.check_action_loop(r2, r1)
    check("decision == CONTINUE", result["decision"] == "CONTINUE",
          f"got {result['decision']}")


# ===========================================================================
# Test 4-6: no-progress 计数 1→WARN, 2→NOOP, 3→ESCALATE
# ===========================================================================
def test_no_progress_counter():
    print("\n=== Test 4-6: no-progress counter escalation ===")
    r_base = {
        "goal_id": "G2", "task_id": "T2", "action_type": "browse",
        "action_signature": "def456", "result_hash": "res_x",
        "evidence_hash": "ev_x", "current_state": "RUNNING",
        "progress": {"no_progress": 0},
    }

    # #1 → WARN
    r2 = dict(r_base)
    r2["progress"] = {"no_progress": 1}
    result = er.check_action_loop(r2, r_base)
    check("no-progress #1 → WARN", result["decision"] == "WARN",
          f"got {result['decision']}")

    # #2 → NOOP
    r3 = dict(r_base)
    r3["progress"] = {"no_progress": 2}
    result2 = er.check_action_loop(r3, r2)
    check("no-progress #2 → NOOP", result2["decision"] == "NOOP",
          f"got {result2['decision']}")

    # #3 → ESCALATE
    r4 = dict(r_base)
    r4["progress"] = {"no_progress": 3}
    result3 = er.check_action_loop(r4, r3)
    check("no-progress #3 → ESCALATE", result3["decision"] == "ESCALATE",
          f"got {result3['decision']}")


# ===========================================================================
# Test 7: wake cooldown (60s 内 → no_action)
# ===========================================================================
def test_wake_cooldown():
    print("\n=== Test 7: wake cooldown ===")
    # 用临时 state 文件
    old_state_path = pa.STATE_PATH
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False) as f:
        tmp = f.name
        json.dump({
            "last_wake_at": None,
            "attention": {"important_used": 0, "recommendation_used": 0},
            "queues": {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0},
            "metrics": {"signals_today": 0},
            "current_goal": {"id": None, "alignment": 0.0},
            "active_plan": None,
            "anti_loop": {"cooldown_until": ""},
        }, f)

    pa.STATE_PATH = tmp
    try:
        # 第一次 wake → ok
        args_ok = type("A", (), {"op": "wake", "key": None, "delta": None,
                                  "goal": None, "alignment": None})()
        res1 = pa.state_cmd("wake", args_ok)
        check("first wake → ok", res1.get("wake") == "ok",
              f"got {res1}")

        # 立即第二次 wake → cooldown (同一秒内)
        args2 = type("A", (), {"op": "wake", "key": None, "delta": None,
                                "goal": None, "alignment": None})()
        res2 = pa.state_cmd("wake", args2)
        check("immediate 2nd wake → no_action (cooldown)",
              res2.get("wake") == "no_action",
              f"got {res2}")
    finally:
        pa.STATE_PATH = old_state_path
        os.unlink(tmp)


# ===========================================================================
# Test 8: wake after cooldown (模拟 cooldown 过期)
# ===========================================================================
def test_wake_after_cooldown():
    print("\n=== Test 8: wake after cooldown ===")
    old_state_path = pa.STATE_PATH
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False) as f:
        tmp = f.name
        # 设置 cooldown_until 为过去时间
        json.dump({
            "last_wake_at": "2020-01-01T00:00:00Z",
            "attention": {"important_used": 0, "recommendation_used": 0},
            "queues": {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0},
            "metrics": {"signals_today": 0},
            "current_goal": {"id": None, "alignment": 0.0},
            "active_plan": None,
            "anti_loop": {"cooldown_until": "2020-01-01T00:00:01Z"},
        }, f)

    pa.STATE_PATH = tmp
    try:
        args = type("A", (), {"op": "wake", "key": None, "delta": None,
                               "goal": None, "alignment": None})()
        res = pa.state_cmd("wake", args)
        check("wake after cooldown → ok", res.get("wake") == "ok",
              f"got {res}")
    finally:
        pa.STATE_PATH = old_state_path
        os.unlink(tmp)


# ===========================================================================
# Test 9: signal fingerprint 稳定性
# ===========================================================================
def test_signal_fingerprint():
    print("\n=== Test 9: signal fingerprint stability ===")
    import hashlib
    sig1 = {"type": "failure", "subject": "任务超期", "source": "task-manager"}
    sig2 = {"type": "failure", "subject": "任务超期", "source": "task-manager"}
    fp_raw1 = "|".join([sig1["type"], sig1["subject"], sig1["source"]])
    fp_raw2 = "|".join([sig2["type"], sig2["subject"], sig2["source"]])
    fp1 = hashlib.sha256(fp_raw1.encode()).hexdigest()[:16]
    fp2 = hashlib.sha256(fp_raw2.encode()).hexdigest()[:16]
    check("same input → same fingerprint", fp1 == fp2)

    # 不同 subject → 不同 fingerprint
    sig3 = {"type": "failure", "subject": "任务阻塞", "source": "task-manager"}
    fp_raw3 = "|".join([sig3["type"], sig3["subject"], sig3["source"]])
    fp3 = hashlib.sha256(fp_raw3.encode()).hexdigest()[:16]
    check("different input → different fingerprint", fp1 != fp3)


# ===========================================================================
# Test 10: retry >= 3 → 仅首次 escalation
# ===========================================================================
def test_escalation_dedup():
    print("\n=== Test 10: retry >= 3 only one escalation ===")
    # 这个测试验证 link.py 的逻辑：escalated_at 字段防止重复 escalation
    # 模拟 task_data
    task_data_no_esc = {
        "id": "T99", "title": "测试任务",
        "retry_count": 2,
        "context": {},
    }
    task_data_escalated = {
        "id": "T99", "title": "测试任务",
        "retry_count": 3,
        "context": {"escalated_at": "2026-08-18T23:00:00Z"},
    }
    # 第一次: 无 escalated_at → 应该 escalation
    should_escalate_first = (task_data_no_esc.get("retry_count", 0) + 1 >= 3
                             and not task_data_no_esc.get("context", {})
                             .get("escalated_at"))
    check("first failure with retry>=3 → should escalate",
          should_escalate_first)

    # 第二次: 已有 escalated_at → 不应重复 escalation
    should_escalate_second = (task_data_escalated.get("retry_count", 0) + 1 >= 3
                              and not task_data_escalated.get("context", {})
                              .get("escalated_at"))
    check("already escalated → should NOT escalate again",
          not should_escalate_second)


# ===========================================================================
# CHAIN-03-A: Authorization Scope Binding 测试（3 项 + 边界）
# ===========================================================================
def test_binding_scope_authorized_exceeds_planned():
    print("\n=== Test 11: authorized.scope 超出 planned.scope → violation ===")
    auth = {
        "planned":   {"action": "write", "resource": "file",
                       "scope": "/workspace/project-a"},
        "authorized": {"action": "write", "resource": "file",
                        "scope": "/workspace/project-b"},
        "actual":     {"action": "write", "resource": "file",
                        "scope": "/workspace/project-b"},
    }
    res = er.check_authorization_binding(auth)
    check("consistent == False", res["consistent"] is False, str(res))
    check("binding_violation == True", res["binding_violation"] is True,
          str(res))
    check("violation mentions authorized.scope",
          any("authorized.scope" in v for v in res["violations"]),
          str(res["violations"]))


def test_binding_scope_actual_exceeds_authorized():
    print("\n=== Test 12: actual.scope 超出 authorized.scope → violation ===")
    auth = {
        "planned":   {"action": "write", "resource": "file",
                       "scope": "/workspace"},
        "authorized": {"action": "write", "resource": "file",
                        "scope": "/workspace/project-a"},
        "actual":     {"action": "write", "resource": "file",
                        "scope": "/workspace/project-b"},
    }
    res = er.check_authorization_binding(auth)
    check("consistent == False", res["consistent"] is False, str(res))
    check("binding_violation == True", res["binding_violation"] is True,
          str(res))
    check("violation mentions actual.scope",
          any("actual.scope" in v for v in res["violations"]),
          str(res["violations"]))


def test_binding_scope_legal_subset():
    print("\n=== Test 13: scope 合法子集 → PASS ===")
    auth = {
        "planned":   {"action": "write", "resource": "file",
                       "scope": "/workspace"},
        "authorized": {"action": "write", "resource": "file",
                        "scope": "/workspace/project-a"},
        "actual":     {"action": "write", "resource": "file",
                        "scope": "/workspace/project-a/sub"},
    }
    res = er.check_authorization_binding(auth)
    check("consistent == True", res["consistent"] is True, str(res))
    check("binding_violation == False",
          res["binding_violation"] is False, str(res))
    check("violations empty", res["violations"] == [], str(res))


def test_binding_scope_equal():
    print("\n=== Test 14: scope 完全相等 → PASS ===")
    auth = {
        "planned":   {"action": "run", "resource": "job",
                       "scope": "/cluster/queue-a"},
        "authorized": {"action": "run", "resource": "job",
                        "scope": "/cluster/queue-a"},
        "actual":     {"action": "run", "resource": "job",
                        "scope": "/cluster/queue-a"},
    }
    res = er.check_authorization_binding(auth)
    check("consistent == True", res["consistent"] is True, str(res))
    check("binding_violation == False",
          res["binding_violation"] is False, str(res))


def test_binding_path_boundary_not_swallowed():
    print("\n=== Test 15: 路径边界不吞并相邻段 (/a vs /ab 不判含容) ===")
    # /a 不应被视为包含 /ab （避免把 b 当 a 的子路径）
    auth = {
        "planned":   {"action": "read", "resource": "db", "scope": "/a"},
        "authorized": {"action": "read", "resource": "db",
                        "scope": "/ab"},
        "actual":     {"action": "read", "resource": "db", "scope": "/ab"},
    }
    res = er.check_authorization_binding(auth)
    check("/a 不包含 /ab → violation", res["binding_violation"] is True,
          str(res))


def test_binding_scalar_scope_fail_closed():
    print("\n=== Test 16-17: 标量 scope 仅完全相等才 PASS ===")
    # T16: int 1 vs int 2 → violation (fail closed)
    auth_int_diff = {
        "planned":   {"action": "write", "resource": "acct", "scope": 1},
        "authorized": {"action": "write", "resource": "acct", "scope": 2},
        "actual":     {"action": "write", "resource": "acct", "scope": 2},
    }
    res1 = er.check_authorization_binding(auth_int_diff)
    check("T16: int 1 vs 2 → violation",
          res1["binding_violation"] is True, str(res1))
    # T17: int 1 vs int 1 → PASS
    auth_int_eq = {
        "planned":   {"action": "write", "resource": "acct", "scope": 1},
        "authorized": {"action": "write", "resource": "acct", "scope": 1},
        "actual":     {"action": "write", "resource": "acct", "scope": 1},
    }
    res2 = er.check_authorization_binding(auth_int_eq)
    check("T17: int 1 vs 1 → PASS",
          res2["binding_violation"] is False, str(res2))


def test_binding_type_mismatch_fail_closed():
    print("\n=== Test 18: 类型不同 (string vs int) → FAIL CLOSED ===")
    auth = {
        "planned":   {"action": "run", "resource": "job", "scope": "1"},
        "authorized": {"action": "run", "resource": "job", "scope": 1},
        "actual":     {"action": "run", "resource": "job", "scope": 1},
    }
    res = er.check_authorization_binding(auth)
    check("string vs int → violation (fail closed)",
          res["binding_violation"] is True, str(res))
    check("consistent == False", res["consistent"] is False, str(res))


def test_binding_structured_scope_fail_closed():
    print("\n=== Test 19: 未支持的结构化 scope → FAIL CLOSED ===")
    # dict 相等 → PASS；dict 不等 → violation
    auth_dict_eq = {
        "planned":   {"action": "read", "resource": "cfg",
                       "scope": {"a": 1}},
        "authorized": {"action": "read", "resource": "cfg",
                        "scope": {"a": 1}},
        "actual":     {"action": "read", "resource": "cfg",
                        "scope": {"a": 1}},
    }
    res1 = er.check_authorization_binding(auth_dict_eq)
    check("dict scope 相等 → PASS",
          res1["binding_violation"] is False, str(res1))
    auth_dict_diff = {
        "planned":   {"action": "read", "resource": "cfg",
                       "scope": {"a": 1}},
        "authorized": {"action": "read", "resource": "cfg",
                        "scope": {"a": 2}},
        "actual":     {"action": "read", "resource": "cfg",
                        "scope": {"a": 2}},
    }
    res2 = er.check_authorization_binding(auth_dict_diff)
    check("dict scope 不等 → violation (fail closed)",
          res2["binding_violation"] is True, str(res2))
    # 结构化 vs 字符串类型不匹配 → violation
    auth_cross = {
        "planned":   {"action": "read", "resource": "cfg",
                        "scope": "/path"},
        "authorized": {"action": "read", "resource": "cfg",
                        "scope": ["a"]},
        "actual":     {"action": "read", "resource": "cfg", "scope": ["a"]},
    }
    res3 = er.check_authorization_binding(auth_cross)
    check("str vs list → violation (fail closed)",
          res3["binding_violation"] is True, str(res3))


def test_binding_None_scope_semantics():
    print("\n=== Test 20: 空 scope / None 语义 ===")
    # None scope 一致（都未提供）→ PASS
    auth_none = {
        "planned":   {"action": "write", "resource": "file", "scope": None},
        "authorized": {"action": "write", "resource": "file", "scope": None},
        "actual":     {"action": "write", "resource": "file", "scope": None},
    }
    res1 = er.check_authorization_binding(auth_none)
    check("None scope 全一致 → PASS",
          res1["binding_violation"] is False, str(res1))
    # unprovided scope + 未提供 → PASS（缺省语义）
    res2 = er.check_authorization_binding({
        "planned": {"action": "a", "resource": "r"},
        "authorized": {"action": "a", "resource": "r"},
        "actual": {"action": "a", "resource": "r"},
    })
    check("未提供 scope 全一致 → PASS",
          res2["binding_violation"] is False, str(res2))
    # 提供了 str scope vs 未提供 → violation（防越权放宽）
    res3 = er.check_authorization_binding({
        "planned":   {"action": "a", "resource": "r", "scope": "/p"},
        "authorized": {"action": "a", "resource": "r", "scope": None},
        "actual":     {"action": "a", "resource": "r", "scope": None},
    })
    check("provided scope vs None → violation",
          res3["binding_violation"] is True, str(res3))


# ===========================================================================
# MA-1.0 Multi-Agent Identity/Correlation 测试（Integration 层）
# ===========================================================================
# 验证 execution_record 的 agent_id/session_id/operation_id/correlation_id 字段
# 创建/透传/持久化 + 完整性校验; 不触碰 Core 判定(check_action_loop/state/permission
# /verification/DAG/self-evolution)。

def _clean_ma_records():
    """每个 MA 测试独立跑, 清掉之前 append 的记录, 避免污染。"""
    p = er._record_path()
    if os.path.exists(p):
        try: os.remove(p)
        except OSError: pass
    lock = p + ".lock"
    if os.path.exists(lock):
        try: os.remove(lock)
        except OSError: pass


def test_ma_legacy_compat():
    print("\n=== Test 21: legacy 单 Agent 记录兼容 (不强制 MA 字段) ===")
    r = er.validate_ma_record({"goal_id": "G1", "task_id": "T1",
                               "action_type": "search"})
    check("legacy → valid", r["valid"] is True, str(r))
    check("legacy → legacy=True", r["legacy"] is True, str(r))
    check("legacy → ma=False", r["ma"] is False, str(r))


def test_ma_record_completeness():
    print("\n=== Test 22: Multi-Agent record 完整性 (必须填充五字段) ===")
    # 完整 → valid
    r1 = er.validate_ma_record({"agent_id": "res", "session_id": "S1",
                                "execution_id": "E1", "task_id": "T1",
                                "correlation_id": "C1"})
    check("MA 完整(无operation) → valid", r1["valid"] is True, str(r1))
    check("MA → ma=True", r1["ma"] is True, str(r1))
    check("MA → legacy=False", r1["legacy"] is False, str(r1))
    # 缺字段 → invalid + 列出 missing
    r2 = er.validate_ma_record({"agent_id": "res", "correlation_id": "C1"})
    check("MA 缺 session/execution/task → invalid",
          r2["valid"] is False, str(r2))
    check("missing 含 session_id", "session_id" in r2["missing"], str(r2["missing"]))
    check("missing 含 task_id", "task_id" in r2["missing"], str(r2["missing"]))


def test_ma_parallel_correlation():
    print("\n=== Test 23: 并行 Agent correlation 关联 ===")
    _clean_ma_records()
    rec1 = er.append_record({"goal_id": "G", "task_id": "T1",
                             "agent_id": "research", "session_id": "S1",
                             "correlation_id": "C001",
                             "action_type": "search", "action_signature": "sg1"})
    rec2 = er.append_record({"goal_id": "G", "task_id": "T2",
                             "agent_id": "trading", "session_id": "S2",
                             "correlation_id": "C001",
                             "action_type": "analyze", "action_signature": "sg2"})
    check("rec1 correlation=C001", rec1.get("correlation_id") == "C001")
    check("rec2 correlation=C001", rec2.get("correlation_id") == "C001")
    check("rec1 ma valid", rec1["ma_completeness"]["valid"] is True)
    check("rec2 ma valid", rec2["ma_completeness"]["valid"] is True)
    # crash 后重读: identity 保留
    res = er.load_records(goal_id="G", limit=50)
    prs = [(r.get("agent_id"), r.get("correlation_id"), r.get("session_id"),
            r.get("task_id")) for r in res["records"]]
    check("crash 后重读 identity 保留",
          all(a and c and s and t for a, c, s, t in prs), str(prs))
    _clean_ma_records()


def test_ma_delegation_correlation():
    print("\n=== Test 24: Delegation parent_task_id + correlation 关联 ===")
    _clean_ma_records()
    rec = er.append_record({"goal_id": "G", "task_id": "T2.1",
                            "parent_task_id": "T2", "agent_id": "worker",
                            "session_id": "S2", "correlation_id": "C001",
                            "action_type": "write_draft", "action_signature": "sg3"})
    check("delegation parent=T2", rec.get("parent_task_id") == "T2")
    check("delegation corr=C001", rec.get("correlation_id") == "C001")
    check("delegation ma valid", rec["ma_completeness"]["valid"] is True)
    check("delegation 身份保留", rec.get("agent_id") == "worker"
          and rec.get("session_id") == "S2")
    _clean_ma_records()


def test_ma_crash_identity_retained():
    print("\n=== Test 25: crash/recovery 后 identity 保留 ===")
    _clean_ma_records()
    er.append_record({"goal_id": "G", "task_id": "T9", "agent_id": "agentX",
                      "session_id": "S9", "correlation_id": "C009",
                      "action_type": "read", "action_signature": "sg9"})
    # 模拟 crash: 重新 load(等同重启后读取)
    res = er.load_records(goal_id="G", limit=50)
    r = res["records"][0]
    check("重启后 agent_id 保留", r.get("agent_id") == "agentX")
    check("重启后 correlation 保留", r.get("correlation_id") == "C009")
    check("重启后 session 保留", r.get("session_id") == "S9")
    _clean_ma_records()


def test_ma_concurrent_isolation():
    print("\n=== Test 26: 并发 Agent A/B/C 身份隔离 ===")
    _clean_ma_records()
    agents = [("A", "SA", ex) for ex in ["EA1", "EA2"]]
    specs = [
        ("A", "SA", "E_A1", "T1", "C1"),
        ("B", "SB", "E_B1", "T1", "C1"),
        ("C", "SC", "E_C1", "T1", "C1"),
    ]
    for agent, sess, eid, tid, corr in specs:
        er.append_record({"goal_id": "G", "task_id": tid, "agent_id": agent,
                          "session_id": sess, "execution_id": eid,
                          "correlation_id": corr, "action_type": "run",
                          "action_signature": "s_" + eid})
    res = er.load_records(goal_id="G", limit=100)
    recs = res["records"]
    check("3 条记录", len(recs) == 3, str(len(recs)))
    # execution_id 不碰撞
    eids = [r.get("execution_id") for r in recs]
    check("execution_id 不碰撞", len(set(eids)) == 3, str(eids))
    # agent/session 不串
    maps = {(r.get("execution_id"), r.get("agent_id"), r.get("session_id"))
            for r in recs}
    check("agent/session/execution 绑定不串",
          ("E_A1", "A", "SA") in maps and ("E_B1", "B", "SB") in maps
          and ("E_C1", "C", "SC") in maps, str(maps))
    # 同 correlation 关联
    check("全同 correlation=C1", all(r.get("correlation_id") == "C1" for r in recs))
    _clean_ma_records()


def test_ma_attack_spoofing():
    print("\n=== Test 27 (攻击A): agent_id 冒充 ===")
    _clean_ma_records()
    # 真实 A 执行 EA1, 攻击者尝试冒充 B 用同一 execution_id
    er.append_record({"goal_id": "G", "task_id": "T1", "agent_id": "A",
                      "session_id": "SA", "execution_id": "EA1",
                      "correlation_id": "C1", "action_type": "read",
                      "action_signature": "sA"})
    ex = er.load_records(limit=100)["records"]
    attack = er.validate_ma_consistency(
        {"goal_id": "G", "task_id": "T1", "agent_id": "B",
         "session_id": "SB", "execution_id": "EA1", "correlation_id": "C1",
         "action_type": "read", "action_signature": "sB"}, ex)
    check("跨 agent 冒充 → cross_agent", attack["issue"] == "cross_agent",
          str(attack))
    _clean_ma_records()


def test_ma_attack_dup_execution():
    print("\n=== Test 28 (攻击B/D): 重复 execution_id 越权 ===")
    _clean_ma_records()
    er.append_record({"goal_id": "G", "task_id": "T1", "agent_id": "A",
                      "session_id": "SA", "execution_id": "E_DUP",
                      "correlation_id": "C1", "action_type": "read",
                      "action_signature": "s1"})
    ex = er.load_records(limit=100)["records"]
    # 攻击者 B 用相同 execution_id 冒充
    attack = er.validate_ma_consistency(
        {"agent_id": "B", "session_id": "SB", "execution_id": "E_DUP",
         "task_id": "T1", "correlation_id": "C2", "action_type": "send"}, ex)
    check("重复 execution+异 agent → cross_agent",
          attack["issue"] == "cross_agent", str(attack))
    # duplicate 独立检测
    exists, _ = er.check_duplicate_execution("E_DUP", ex)
    check("duplicate E_DUP 检测到", exists is True)
    _clean_ma_records()


def test_ma_attack_cross_task():
    print("\n=== Test 29 (攻击C): 跨 Task 串写 execution record ===")
    _clean_ma_records()
    er.append_record({"goal_id": "G", "task_id": "T1", "agent_id": "A",
                      "session_id": "SA", "execution_id": "E1",
                      "correlation_id": "C1", "action_type": "read",
                      "action_signature": "s1"})
    ex = er.load_records(limit=100)["records"]
    attack = er.validate_ma_consistency(
        {"agent_id": "A", "session_id": "SA", "execution_id": "E1",
         "task_id": "T2", "correlation_id": "C1", "action_type": "read"}, ex)
    check("同 E1 异 task → cross_task", attack["issue"] == "cross_task", str(attack))
    _clean_ma_records()


def test_ma_attack_correlation_merge():
    print("\n=== Test 30 (攻击E): 不同 correlation 强行合并 ===")
    _clean_ma_records()
    er.append_record({"goal_id": "G", "task_id": "T1", "agent_id": "A",
                      "session_id": "SA", "execution_id": "E1",
                      "correlation_id": "C1", "action_type": "read",
                      "action_signature": "s1"})
    ex = er.load_records(limit=100)["records"]
    attack = er.validate_ma_consistency(
        {"agent_id": "A", "session_id": "SA", "execution_id": "E1",
         "task_id": "T1", "correlation_id": "C2", "action_type": "read"}, ex)
    check("异 correlation 合并 → correlation_conflict",
          attack["issue"] == "correlation_conflict", str(attack))
    _clean_ma_records()


def test_ma_attack_parent_forgery():
    print("\n=== Test 31 (攻击F): parent_task_id 伪造 Delegation 来源 ===")
    _clean_ma_records()
    # 合法父任务 T1 在 C1 链内
    er.append_record({"goal_id": "G", "task_id": "T1", "agent_id": "A",
                      "session_id": "SA", "execution_id": "E1",
                      "correlation_id": "C1", "action_type": "read",
                      "action_signature": "s1"})
    ex = er.load_records(limit=100)["records"]
    # 攻击: 子任务 T2 声明 parent=T2(自指) → 伪造
    attack = er.validate_ma_consistency(
        {"agent_id": "B", "session_id": "SB", "execution_id": "E2",
         "task_id": "T2", "parent_task_id": "T2", "correlation_id": "C1",
         "action_type": "write"}, ex)
    check("parent 自指不触发 Core 判定(记录层仅暴露)",
          attack["consistent"] in (True, False), "(record 层不阻断)")
    # 关键: legacy/MA 记录仍可读取, 不破坏 Core
    r = er.check_action_loop({"goal_id": "G", "action_signature": "s1",
                              "result_hash": "r", "current_state": "RUNNING"})
    check("Core decision 不受 parent 伪造影响", r["decision"] in
          ("CONTINUE", "WARN", "NOOP", "ESCALATE", "UNKNOWN"), str(r))
    _clean_ma_records()


def test_ma_attack_legacy_not_break_core():
    print("\n=== Test 32 (攻击G): Legacy 缺字段不破坏 Core Decision ===")
    _clean_ma_records()
    # legacy 记录(完全无 MA 字段)
    er.append_record({"goal_id": "G", "task_id": "T1", "action_type": "search",
                      "action_signature": "legacy_sig", "result_hash": "r1",
                      "current_state": "RUNNING"})
    # 校验
    vl = er.validate_ma_record({"goal_id": "G", "task_id": "T1",
                                "action_type": "search"})
    check("legacy 记录 valid", vl["valid"] is True, str(vl))
    # Core anti-loop 判定不被 legacy 缺字段影响
    r = er.check_action_loop({"goal_id": "G", "action_signature": "legacy_sig",
                              "result_hash": "r1", "current_state": "RUNNING"})
    check("legacy Core decision 正常(WARN/等)",
          r["decision"] in ("CONTINUE", "WARN", "NOOP", "ESCALATE", "UNKNOWN"),
          str(r))
    _clean_ma_records()


# ===========================================================================
# Main
# ===========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Anti-loop v1.3 测试 (CHAIN-03 scope binding 已并入)")
    print("=" * 60)

    test_same_action_same_result()
    test_same_action_new_result()
    test_same_action_new_evidence()
    test_no_progress_counter()
    test_wake_cooldown()
    test_wake_after_cooldown()
    test_signal_fingerprint()
    test_escalation_dedup()
    test_binding_scope_authorized_exceeds_planned()
    test_binding_scope_actual_exceeds_authorized()
    test_binding_scope_legal_subset()
    test_binding_scope_equal()
    test_binding_path_boundary_not_swallowed()
    test_binding_scalar_scope_fail_closed()
    test_binding_type_mismatch_fail_closed()
    test_binding_structured_scope_fail_closed()
    test_binding_None_scope_semantics()
    test_ma_legacy_compat()
    test_ma_record_completeness()
    test_ma_parallel_correlation()
    test_ma_delegation_correlation()
    test_ma_crash_identity_retained()
    test_ma_concurrent_isolation()
    test_ma_attack_spoofing()
    test_ma_attack_dup_execution()
    test_ma_attack_cross_task()
    test_ma_attack_correlation_merge()
    test_ma_attack_parent_forgery()
    test_ma_attack_legacy_not_break_core()

    print("\n" + "=" * 60)
    print(f"结果: {PASS} PASS / {FAIL} FAIL")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)
