#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rollback.py — Self-Evolution v2 · Rollback (REGRESSED → ROLLED_BACK)

职责：
    Regression == REGRESSED 时，恢复 Apply 前 Snapshot。
    记录：change_id / rollback_at / reason / regression_id。

重要：
    Rollback 产生的信息不得自动形成新的 Candidate，
    防止 Evolution → Regression → Rollback → Candidate → Evolution → Regression 无限循环。

状态机：REGRESSED → ROLLED_BACK
幂等：同一 change 不得重复 Rollback（已 ROLLED_BACK 则跳过）。

Code = Enforcement：snapshot 恢复、状态推进、防循环由本脚本决定。

用法：
  python3 rollback.py --change CHG-xxx --reason "regression degraded" --regression RGR-xxx
"""

import argparse
import json

import _core


def do_rollback(change_id, reason, regression_id):
    chg = _core.load_artifact("change", change_id)
    if not chg:
        return None, "change 不存在: " + change_id

    # 幂等：已 ROLLED_BACK 不重复
    if chg.get("status") == "ROLLED_BACK":
        return None, "DEDUP_ALREADY_ROLLED_BACK"

    # 状态必须是 REGRESSED 才会被 Rollback（或由回归失败触发的 APPLIED）
    if chg.get("status") not in ("REGRESSED", "APPLIED", "REGRESSION"):
        return None, "change 状态不是 REGRESSED/APPLIED: " + str(chg.get("status"))

    restored = _core.restore_snapshot(change_id)

    # 状态机：REGRESSED → ROLLED_BACK
    _core.assert_transition(chg, "REGRESSED", kind="change")  # no-op 幂等
    _core.assert_transition(chg, "ROLLED_BACK", kind="change")
    chg["rollback"] = {
        "change_id": change_id,
        "rollback_at": _core.now_iso(),
        "reason": reason or "",
        "regression_id": regression_id or "",
        "restored_files": restored,
    }
    _core.save_artifact("change", chg)

    # 若 regression 记录存在，同步标记
    if regression_id:
        rgr = _core.load_artifact("regression", regression_id)
        if rgr:
            rgr["rolled_back_at"] = _core.now_iso()
            _core.save_artifact("regression", rgr)

    return change_id, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2 Rollback")
    p.add_argument("--change", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--regression", default="")
    args = p.parse_args()

    cid, err = do_rollback(args.change, args.reason, args.regression)
    if err:
        print(json.dumps({"decision": "DEDUP" if "DEDUP" in err else "REJECT",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    chg = _core.load_artifact("change", cid)
    print(json.dumps({
        "decision": "DEDUP_ALREADY_ROLLED_BACK" if err else "ROLLED_BACK",
        "change_id": cid,
        "state": chg.get("status"),
        "restored_files": chg.get("rollback", {}).get("restored_files", []),
        "chain": _core.evidence_chain(args.regression) if args.regression else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
