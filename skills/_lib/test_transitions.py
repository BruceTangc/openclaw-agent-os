#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transitions.py 中央门行为测试。"""
import os
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _LIB)
from transitions import (transition, transition_allowed, assert_transition,
                         register_invariants)

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS:", name)
    else:
        failed += 1
        print("  FAIL:", name)


# Task 状态机
t = {"status": "INBOX", "history": []}
transition(t, "READY", kind="task", actor="orchestrator", reason="ready")
check("task INBOX->READY 合法", t["status"] == "READY")
check("task 记录 transition event",
      any(h.get("action") == "transition" and h.get("to") == "READY"
          for h in t["history"]))

# 非法跳转 READY->COMPLETED (缺合法边 + 缺 completed_at)
try:
    transition(t, "COMPLETED", kind="task")
    check("task READY->COMPLETED 非法应抛", False)
except ValueError as e:
    check("task READY->COMPLETED 非法应抛", "非法状态跳转" in str(e))

# 缺 completed_at 进 COMPLETED 拒绝
t2 = {"status": "RUNNING", "started_at": "2026-01-01T00:00:00Z", "history": []}
try:
    transition(t2, "COMPLETED", kind="task")
    check("task COMPLETED 缺 completed_at 拒绝", False)
except ValueError as e:
    check("task COMPLETED 缺 completed_at 拒绝",
          "缺少必需事实字段" in str(e) and "completed_at" in str(e))

t2["completed_at"] = "2026-01-01T01:00:00Z"
transition(t2, "COMPLETED", kind="task")
check("task 带 completed_at 进 COMPLETED 合法", t2["status"] == "COMPLETED")

# RUNNING 缺 started_at 拒绝
t3 = {"status": "READY", "history": []}
try:
    transition(t3, "RUNNING", kind="task")
    check("task RUNNING 缺 started_at 拒绝", False)
except ValueError as e:
    check("task RUNNING 缺 started_at 拒绝", "缺少必需事实字段" in str(e))
t3["started_at"] = "2026-01-01T00:00:00Z"
transition(t3, "RUNNING", kind="task")
check("task 带 started_at 进 RUNNING 合法", t3["status"] == "RUNNING")

# FAILED 缺 failed_at 拒绝
t4 = {"status": "RUNNING", "started_at": "2026-01-01T00:00:00Z", "history": []}
try:
    transition(t4, "FAILED", kind="task")
    check("task FAILED 缺 failed_at 拒绝", False)
except ValueError:
    check("task FAILED 缺 failed_at 拒绝", True)
t4["failed_at"] = "2026-01-01T01:00:00Z"
transition(t4, "FAILED", kind="task")
check("task 带 failed_at 进 FAILED 合法", t4["status"] == "FAILED")

# Proposal 状态机
p = {"status": "PROPOSED", "history": []}
transition(p, "APPROVED", kind="proposal")
check("proposal PROPOSED->APPROVED 合法", p["status"] == "APPROVED")
try:
    transition(p, "PROMOTED", kind="proposal")
    check("proposal APPROVED->PROMOTED 非法应抛", False)
except ValueError as e:
    check("proposal APPROVED->PROMOTED 非法应抛", "非法状态跳转" in str(e))

# assert_transition 兼容别名
r = {"status": "SNAPSHOTTED", "history": []}
assert_transition(r, "APPLYING", kind="change")
check("assert_transition 兼容(change SNAPSHOTTED->APPLYING)",
      r["status"] == "APPLYING")

# transition_allowed 幂等
check("transition_allowed(src==dst)=True",
      transition_allowed("READY", "READY", "task"))

# register_invariants 扩展
register_invariants("change", {"APPLIED": ["applied_at"]})
c = {"status": "APPLYING", "history": []}
try:
    transition(c, "APPLIED", kind="change")
    check("change APPLIED 缺 applied_at 拒绝(自定义不变量)", False)
except ValueError:
    check("change APPLIED 缺 applied_at 拒绝(自定义不变量)", True)
c["applied_at"] = "2026-01-01T00:00:00Z"
transition(c, "APPLIED", kind="change")
check("change 带 applied_at 进 APPLIED 合法", c["status"] == "APPLIED")

# 非法目标状态
try:
    transition({"status": "INBOX", "history": []}, "BOGUS", kind="task")
    check("task 非法目标状态 BOGUS 拒绝", False)
except ValueError:
    check("task 非法目标状态 BOGUS 拒绝", True)

# 未注册 kind
try:
    transition({"status": "x", "history": []}, "y", kind="nonsense")
    check("未注册 kind 拒绝", False)
except ValueError:
    check("未注册 kind 拒绝", True)

print("\n===== TRANSITIONS GATE TEST =====")
print("PASS: %d\tFAIL: %d" % (passed, failed))
sys.exit(0 if failed == 0 else 1)
