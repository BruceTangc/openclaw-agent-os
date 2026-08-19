#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrator 回归测试 (F-002 补强, RVW-20260819-001)

覆盖 AE-5/AV 硬化语义在 orchestrator 侧的落地:
  - 损坏/非法 JSON 输入**不静默返默认**, 而是带 __error 标记 (AE-5 "损坏≠空" 语义)
  - verify_result 门控 (V0→V4 逐级累计, UNKNOWN 不 pass)
  - 删除 dead load_json/save_json 后无残留引用 (F-001)

运行: python3 test_orchestrator.py   (预期 PASS: N / FAIL: 0)
"""
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(os.path.dirname(BASE), "_lib"))

import orchestrator as occ

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS: %s" % name)
    else:
        FAIL += 1
        print("  FAIL: %s  %s" % (name, detail))


def test_dead_functions_removed():
    """F-001: load_json/save_json 死代码已删除, 静默吞损坏的语义缺口不存在。"""
    src = open(os.path.join(BASE, "orchestrator.py"), encoding="utf-8").read()
    check("无 dead load_json 定义", "def load_json" not in src)
    check("无 dead save_json 定义", "def save_json" not in src)


def test_corrupt_input_not_silent():
    """AE-5 语义: 非法 JSON 输入不能静默返默认, 必须带 __error 标记。"""
    r = occ.read_stdin_or_json("{not valid json", "request")
    check("损坏JSON带 __error", isinstance(r, dict) and "__error" in r,
          "got: %r" % (r,))
    check("损坏JSON不静默默认", r.get("_raw") == "{not valid json")
    # 合法输入仍正常解析
    ok = occ.read_stdin_or_json('{"objective": "x"}', "request")
    check("合法JSON正常解析", isinstance(ok, dict) and ok.get("objective") == "x")


def test_verify_unknown_not_pass():
    """I-015/verify 门控: 未知结果不该被判通过。"""
    r = occ.verify_result({"result": "unknown", "tool_success": True}, level="V2")
    check("UNKNOWN-type 不静默 pass", r.get("passed") is False,
          "got passed=%s" % r.get("passed"))


if __name__ == "__main__":
    print("Orchestrator 回归 (F-002 / RVW-20260819-001):")
    test_dead_functions_removed()
    test_corrupt_input_not_silent()
    test_verify_unknown_not_pass()
    print("=" * 40)
    print("结果: %d PASS / %d FAIL" % (PASS, FAIL))
    sys.exit(0 if FAIL == 0 else 1)
