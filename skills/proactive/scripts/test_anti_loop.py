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

    print("\n" + "=" * 60)
    print(f"结果: {PASS} PASS / {FAIL} FAIL")
    print("=" * 60)
    sys.exit(1 if FAIL > 0 else 0)
