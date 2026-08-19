#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rollback.py — Self-Evolution v2.3 · Rollback (REGRESSED → ROLLED_BACK)

v2.3: 全链路状态同步（change + proposal + candidate），Evidence 不删除。
"""
import argparse
import json
import _core


def do_rollback(change_id, reason, regression_id):
    chg = _core.load_artifact("change", change_id)
    if not chg:
        return None, "change 不存在: " + change_id
    if chg.get("status") == "ROLLED_BACK":
        return None, "DEDUP_ALREADY_ROLLED_BACK"
    if chg.get("status") not in ("REGRESSED", "APPLIED", "APPLY_FAILED"):
        return None, "change 状态不允许 Rollback: " + str(chg.get("status"))

    # 恢复文件
    restored = _core.restore_snapshot(change_id)

    # AE-4: change 状态经状态机跳转 (REGRESSED/APPLIED/APPLY_FAILED → ROLLED_BACK)
    try:
        _core.assert_transition(chg, "ROLLED_BACK", kind="change")
    except ValueError as e:
        return None, "rollback 状态跳转被拒: {}".format(e)
    chg["rollback"] = {
        "change_id": change_id, "rollback_at": _core.now_iso(),
        "reason": reason or "", "regression_id": regression_id or "",
        "restored_files": restored}
    _core._core_save_artifact("change", chg)

    # v2.3: 同步更新 proposal 状态
    prp = _core.load_artifact("proposal", chg.get("proposal_id", ""))
    if prp and prp.get("status") in ("APPLIED", "APPROVED", "APPLYING", "SNAPSHOTTED"):
        try:
            _core.assert_transition(prp, "REJECTED", kind="proposal")
        except ValueError:
            prp["status"] = "REJECTED"
            prp["updated_at"] = _core.now_iso()
        _core._core_save_artifact("proposal", prp)

    # v2.3: 同步更新 candidate 状态（标记 regressed，不删除）
    cnd = _core.load_artifact("candidate", chg.get("candidate_id", ""))
    if cnd and cnd.get("status") not in ("REJECTED", "ROLLED_BACK", "UNRESOLVED", "PROMOTED"):
        try:
            _core.assert_transition(cnd, "DIAGNOSED", kind="candidate")
        except ValueError:
            pass
        cnd["status"] = "REJECTED"
        cnd["updated_at"] = _core.now_iso()
        _core._core_save_artifact("candidate", cnd)

    # v2.4: Rollback 产生 evolution_event Evidence（"这次修改失败"本身就是有价值信号）
    try:
        _core.register_evolution_event("rollback", change_id, reason=reason,
                                       regression_id=regression_id)
    except ValueError as e:
        # 状态验证失败不应阻断 rollback 本身，只记录警告
        print(json.dumps({"warning": "rollback evidence 未生成: {}".format(e)},
                          ensure_ascii=False))

    # 更新 regression 记录
    if regression_id:
        rgr = _core.load_artifact("regression", regression_id)
        if rgr:
            rgr["rolled_back_at"] = _core.now_iso()
            _core._core_save_artifact("regression", rgr)

    return change_id, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Rollback")
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
        "change_id": cid, "state": chg.get("status"),
        "evolution_id": chg.get("evolution_id"),
        "restored_files": chg.get("rollback", {}).get("restored_files", []),
        "chain": _core.evidence_chain(args.regression) if args.regression else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
