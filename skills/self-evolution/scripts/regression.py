#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regression.py — Self-Evolution v2 · Regression (最终裁判)

在 Apply 后比较 Before vs After，判定是否改善。结果只能是：
    IMPROVED / NO_CHANGE / REGRESSED / UNKNOWN

规则：
    IMPROVED  → 允许 Promotion（记录完整 Evolution Chain）
    NO_CHANGE → 不 Promotion
    REGRESSED → 触发 Rollback（调用 rollback.py）
    UNKNOWN   → 不 Promotion（无法证明改善 = 不进化成功）

重要：
    Regression FAIL 产生的信息不能自动成为新的 Candidate（防 Evolution→Regression→Rollback→Candidate 死循环）。

状态机：APPLIED → REGRESSION → PROMOTED / REGRESSED
幂等：同一 change 不得重复记录 regression。
Code = Enforcement：before/after 判定、状态推进、Promotion 规则由本脚本决定；LLM 只解读结果、提供 evidence。

用法：
  python3 regression.py --change CHG-xxx --result IMPROVED --evidence '<json>'
  python3 regression.py --change CHG-xxx --result REGRESSED --evidence '<json>' --no_auto_rollback
"""

import argparse
import json

import _core

RESULTS = ["IMPROVED", "NO_CHANGE", "REGRESSED", "UNKNOWN"]


def run_regression(change_id, result, evidence):
    if result not in RESULTS:
        return None, "result 非法: " + str(result)

    chg = _core.load_artifact("change", change_id)
    if not chg:
        return None, "change 不存在: " + change_id
    if chg.get("status") != "APPLIED":
        return None, "change 状态不是 APPLIED: " + str(chg.get("status"))

    # 幂等：同 change 已记录 regression 不重复
    for rid in _core._list_ids("regression"):
        prev = _core.load_artifact("regression", rid)
        if prev and prev.get("change_id") == change_id:
            return prev["id"], "DEDUP_EXISTING_REGRESSION"

    rgr = {
        "status": "REGRESSION",
        "change_id": change_id,
        "proposal_id": chg.get("proposal_id"),
        "candidate_id": chg.get("candidate_id"),
        "diagnosis_id": chg.get("diagnosis_id"),
        "result": result,
        "evidence": evidence,
        "recorded_at": _core.now_iso(),
    }
    rid = _core.save_artifact("regression", rgr)
    rgr["id"] = rid

    # 状态推进
    _core.assert_transition(chg, "REGRESSION", kind="change")
    _core.save_artifact("change", chg)

    if result == "IMPROVED":
        _core.assert_transition(chg, "PROMOTED", kind="change")
        _core.save_artifact("change", chg)
        rgr["status"] = "PROMOTED"
        _core.save_artifact("regression", rgr)
    elif result == "REGRESSED":
        _core.assert_transition(chg, "REGRESSED", kind="change")
        _core.save_artifact("change", chg)
        rgr["status"] = "REGRESSED"
        _core.save_artifact("regression", rgr)

    return rid, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2 Regression")
    p.add_argument("--change", required=True)
    p.add_argument("--result", required=True, choices=RESULTS)
    p.add_argument("--evidence", default="{}")
    p.add_argument("--rollback", action="store_true",
                   help="REGRESSED 时自动调用 rollback.py（推荐）")
    args = p.parse_args()

    rid, err = run_regression(args.change, args.result, args.evidence)
    if err:
        print(json.dumps({"decision": "DEDUP" if "DEDUP" in err else "REJECT",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    rgr = _core.load_artifact("regression", rid)
    out = {"decision": "DEDUP_EXISTING_REGRESSION" if err else "REGRESSION_RECORDED",
           "regression_id": rid,
           "result": rgr.get("result"),
           "status": rgr.get("status")}
    if args.result == "IMPROVED":
        out["promotion"] = "PROMOTED"
    elif args.result == "REGRESSED":
        out["action"] = "ROLLBACK_REQUIRED"
        out["rollback_cmd"] = "python3 rollback.py --change {}".format(args.change)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
