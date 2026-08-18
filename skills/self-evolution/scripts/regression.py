#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regression.py — Self-Evolution v2.3 · Regression (APPLIED → MONITORING → VALIDATED/REGRESSED)

v2.3: MONITORING/VALIDATED 状态、evolution_id 全链路。
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
    if chg.get("status") not in ("APPLIED", "MONITORING"):
        return None, "change 状态不是 APPLIED/MONITORING: " + str(chg.get("status"))

    # 幂等：同 change 已记录 regression 不重复
    for rid in _core._list_ids("regression"):
        prev = _core.load_artifact("regression", rid)
        if prev and prev.get("change_id") == change_id:
            return prev["id"], "DEDUP_EXISTING_REGRESSION"

    evo_id = chg.get("evolution_id")
    rgr = {"status": "REGRESSION", "evolution_id": evo_id,
           "change_id": change_id, "proposal_id": chg.get("proposal_id"),
           "candidate_id": chg.get("candidate_id"),
           "diagnosis_id": chg.get("diagnosis_id"),
           "result": result, "evidence": evidence,
           "recorded_at": _core.now_iso()}
    rid = _core.save_artifact("regression", rgr)
    rgr["id"] = rid

    # v2.3: 状态推进 APPLIED → MONITORING → 结果
    if chg.get("status") == "APPLIED":
        _core.assert_transition(chg, "MONITORING", kind="change")
        _core.save_artifact("change", chg)

    if result == "IMPROVED":
        _core.assert_transition(chg, "VALIDATED", kind="change")
        _core.save_artifact("change", chg)
        _core.assert_transition(chg, "PROMOTED", kind="change")
        _core.save_artifact("change", chg)
        rgr["status"] = "PROMOTED"
        _core.save_artifact("regression", rgr)
    elif result == "REGRESSED":
        _core.assert_transition(chg, "REGRESSED", kind="change")
        _core.save_artifact("change", chg)
        rgr["status"] = "REGRESSED"
        _core.save_artifact("regression", rgr)
        # v2.4: Regression 产生 evolution_event Evidence（"这次修改失败"是重要信号）
        try:
            _core.register_evolution_event("regression", change_id, reason=evidence or "",
                                           regression_id=rid)
        except ValueError as e:
            print(json.dumps({"warning": "regression evidence 未生成: {}".format(e)},
                              ensure_ascii=False))
    # NO_CHANGE / UNKNOWN: 不推进状态

    return rid, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Regression")
    p.add_argument("--change", required=True)
    p.add_argument("--result", required=True, choices=RESULTS)
    p.add_argument("--evidence", default="{}")
    p.add_argument("--rollback", action="store_true")
    args = p.parse_args()
    rid, err = run_regression(args.change, args.result, args.evidence)
    if err:
        print(json.dumps({"decision": "DEDUP" if "DEDUP" in err else "REJECT",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    rgr = _core.load_artifact("regression", rid)
    out = {"decision": "DEDUP_EXISTING_REGRESSION" if err else "REGRESSION_RECORDED",
           "regression_id": rid, "result": rgr.get("result"), "status": rgr.get("status"),
           "evolution_id": rgr.get("evolution_id")}
    if args.result == "IMPROVED":
        out["promotion"] = "PROMOTED"
    elif args.result == "REGRESSED":
        out["action"] = "ROLLBACK_REQUIRED"
        out["rollback_cmd"] = "python3 rollback.py --change {}".format(args.change)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
