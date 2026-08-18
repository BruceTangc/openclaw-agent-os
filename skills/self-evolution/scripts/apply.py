#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply.py — Self-Evolution v2.3 · Apply (Proposal → Governance → Snapshot → Patch → Verify)

v2.3: SNAPSHOTTED/APPLYING 状态、evolution_id、Crash Recovery 支持。
"""
import argparse
import json
import _core


def governance_check(prop):
    problems = []
    if not prop:
        return False, ["proposal 不存在"]
    if prop.get("status") not in ("PROPOSED", "APPROVED"):
        problems.append("proposal 状态不是 PROPOSED/APPROVED: " + str(prop.get("status")))
    dgn = _core.load_artifact("diagnosis", prop.get("diagnosis_id", ""))
    if not dgn or dgn.get("status") != "DIAGNOSED":
        problems.append("diagnosis 不存在或无效")
    if not prop.get("evidence_refs"):
        problems.append("缺少 evidence_refs")
    level = prop.get("level", "G3")
    human = _core.require_human_approval(level)
    for t in (prop.get("targets") or []):
        if _core.is_protected_target(t):
            problems.append("目标受保护：{}".format(t))
    if human and not prop.get("_approved"):
        problems.append("级别 {} 要求人工审批".format(level))
    if not prop.get("test_plan"):
        problems.append("缺少 test_plan")
    if not (prop.get("targets")):
        problems.append("缺少 targets")
    ops = (prop.get("change") or {}).get("operations")
    if ops is None:
        problems.append("change.operations 缺失（v2.3 要求结构化精确变更）")
    else:
        _ok, bad = _core.allowed_ops(ops, prop.get("targets") or [])
        if not _ok:
            problems.append("operations 越出 targets: " + ";".join(bad))
    return (len(problems) == 0), problems


def apply_change(proposal_id, approve, approver, reason):
    prop = _core.load_artifact("proposal", proposal_id)
    if not prop:
        return None, "proposal 不存在: " + proposal_id
    if prop.get("status") in ("APPLIED", "REGRESSION", "PROMOTED", "REGRESSED", "ROLLED_BACK"):
        return None, "DEDUP: proposal 已为状态 " + str(prop.get("status"))

    cand = _core.load_artifact("candidate", prop.get("candidate_id", ""))
    if cand:
        _core.assert_transition(cand, "PROPOSED", kind="candidate")
        _core.save_artifact("candidate", cand)

    human = _core.require_human_approval(prop.get("level", "G3"))
    if human and not approve:
        return None, "级别 {} 要求人工审批".format(prop.get("level"))
    prop["_approved"] = True
    prop["_approval"] = {"approver": approver or "unknown", "reason": reason or "",
                         "human_required": human, "at": _core.now_iso()}

    ok, problems = governance_check(prop)
    if not ok:
        _core.assert_transition(prop, "REJECTED", kind="proposal")
        _core.save_artifact("proposal", prop)
        return None, "GOVERNANCE_REJECT: " + "; ".join(problems)

    evo_id = prop.get("evolution_id")
    with _core.apply_lock():
        return _apply_change_locked(prop, evo_id, approve, approver, reason)


def _apply_change_locked(prop, evo_id, approve, approver, reason):
    """#32: Apply 全程持 lock；#31: 记录 expected fingerprint；#33: apply→verify→regression。"""
    proposal_id = prop.get("id")
    ws_ctx = _core.WorkspaceContext()

    # v2.3: 创建 Change Record（含 workspace identity + evolution_id）
    change = {"status": "SNAPSHOTTED", "evolution_id": evo_id,
              "proposal_id": proposal_id, "candidate_id": prop.get("candidate_id"),
              "diagnosis_id": prop.get("diagnosis_id"),
              "level": prop.get("level"),
              "targets": list(prop.get("targets") or []),
              "change": prop.get("change", {}),
              "expected_metric": prop.get("expected_metric"),
              "applied_at": _core.now_iso(),
              "workspace": {"root": ws_ctx.root, "identity": ws_ctx.root}}
    cid = _core.save_artifact("change", change)
    change["id"] = cid

    # Snapshot
    snap = _core.take_snapshot(cid, change["targets"])
    change["_snapshot"] = snap
    # #31: 记录 Apply 前基准 fingerprint（expected 的对照起点）
    change["_baseline_fingerprints"] = _core.baseline_fingerprints(change["targets"])

    # P1-6/修复: Apply 前拿“当前文件”重新 hash 与 baseline 比较。
    #   若 baseline 记录后文件已被他人修改（≠ baseline），则拒绝 apply，
    #   不覆盖外部修改。这是 #31/#32 “防止别人修改后覆盖”的最后一道防线。
    base_fp = change["_baseline_fingerprints"] or {}
    pre_verify_ok = True
    pre_mismatch = []
    if base_fp:
        for rel, fp in base_fp.items():
            cur = _core._idutil_fingerprint(_core.ws_abs(rel))
            if cur != fp:
                pre_verify_ok = False
                pre_mismatch.append((rel, fp, cur))
    if not pre_verify_ok:
        change["status"] = "APPLY_FAILED"
        change["apply_error"] = "baseline fingerprint 变化(外部修改)，拒绝覆盖: " + str(pre_mismatch[:5])
        _core.save_artifact("change", change)
        _core.restore_snapshot(cid)
        return None, "APPLY_FAILED: baseline 变化(外部已修改目标文件)，拒绝覆盖: " + str([m[0] for m in pre_mismatch])

    _core.save_artifact("change", change)

    # v2.3: 状态推进到 APPLYING（crash recovery 可检测此状态）
    _core.assert_transition(change, "APPLYING", kind="change")
    _core.save_artifact("change", change)

    # 执行结构化 patch
    ops = (prop.get("change") or {}).get("operations") or []
    try:
        applied = _core.apply_patch(ops)
    except Exception as e:
        change["status"] = "APPLY_FAILED"
        change["apply_error"] = str(e)
        _core.assert_transition(change, "APPLY_FAILED", kind="change")
        _core.save_artifact("change", change)
        _core.restore_snapshot(cid)
        return None, "APPLY_FAILED + RESTORED: " + str(e)

    # 成功：#31 记录实际变更文件的 expected fingerprint；#32/#33 立即做后置校验
    change["_applied_files"] = applied
    change["_expected_fingerprints"] = _core.record_applied_fingerprints(cid, applied)
    _verify_ok, _mismatch = _core.validate_applied_files(cid)
    if not _verify_ok:
        # P1-7/修复: verify FAIL 不得 APPLIED。必须回滚到 APPLY_FAILED，
        #   而不是写了 verify_error 后 still APPLIED。
        change["status"] = "APPLY_FAILED"
        change["verify_error"] = "expected_fingerprint_mismatch: " + str(_mismatch)
        change["verify"] = {"fingerprint_ok": False, "mismatches": _mismatch}
        _core.restore_snapshot(cid)
        _core.save_artifact("change", change)
        return None, "APPLY_FAILED + POST_VERIFY_MISMATCH + RESTORED: " + str(_mismatch)
    # #33: apply→verify→regression 链路，Apply 只推进到 APPLIED；后续 regression.py 负责
    #      APPLIED→MONITORING→VALIDATED/REGRESSED。verify 已在此完成指纹一致性确认。
    change["status"] = "APPLIED"
    change["verify"] = {"fingerprint_ok": True, "mismatches": []}
    _core.assert_transition(change, "APPLIED", kind="change")
    _core.save_artifact("change", change)

    # Proposal 状态推进
    _core.assert_transition(prop, "APPROVED", kind="proposal")
    prop["_change_id"] = cid
    prop["_snapshot"] = snap
    _core.save_artifact("proposal", prop)
    _core.assert_transition(prop, "APPLIED", kind="proposal")
    _core.save_artifact("proposal", prop)

    return cid, None



def _retry_from_change(change_id):
    """#34: 崩溃恢复 re-apply。Change=APPLYING 中断时复用其 operations 重新 apply。

    只用于 recovery.py 的 SAFE_TO_RETRY 路径；通过 Proposal 重新进入既有链路，
    必要时在 lock 保护下补 apply 后置校验。失败不抛异常，返回描述字符串。
    """
    try:
        chg = _core.load_artifact("change", change_id)
        if not chg:
            return "RETRY_FAILED: change 不存在"
        proposal_id = chg.get("proposal_id", "")
        if not proposal_id:
            return "RETRY_MANUAL: change 缺 proposal_id，无法自动重试"
        prop = _core.load_artifact("proposal", proposal_id)
        if not prop:
            return "RETRY_MANUAL: proposal 不存在: " + str(proposal_id)
        if prop.get("status") not in ("PROPOSED", "APPROVED", "APPLIED"):
            return "RETRY_SKIP: proposal 状态 " + str(prop.get("status"))
        with _core.apply_lock():
            # P1-8/修复: apply 前重新验证 baseline fingerprint。
            #   若 Apply 中断期间目标文件已被外部修改(≠ baseline)，拒绝重新 patch，
            #   不覆盖外部修改。
            baseline = chg.get("_baseline_fingerprints") or {}
            if baseline:
                for rel, fp in baseline.items():
                    cur = _core._idutil_fingerprint(_core.ws_abs(rel))
                    if cur != fp:
                        # F-RVW-002/修复: baseline 变化(中断期外部修改)是确定性失败，
                        #   需将 change 落盘为 APPLY_FAILED 并停止自动重试，
                        #   否则下次启动 recovery 会再次进入此分支形成无限重试循环。
                        chg["status"] = "APPLY_FAILED"
                        chg["verify_error"] = (
                            "baseline 变化(Apply 中断期间目标文件已被外部修改)，拒绝覆盖: "
                            + rel)
                        _core._core_save_artifact("change", chg)
                        return ("RETRY_FAILED: baseline 变化(Apply 中断期间目标文件已被外部"
                                "修改)，拒绝覆盖: " + rel)
            ops = (prop.get("change") or {}).get("operations") or []
            applied = _core.apply_patch(ops)
            chg["_applied_files"] = applied
            chg["_expected_fingerprints"] = _core.record_applied_fingerprints(
                change_id, applied)
            ok, mism = _core.validate_applied_files(change_id)
            chg["verify"] = {"fingerprint_ok": ok, "mismatches": mism}
            _core._core_save_artifact("change", chg)
            return "RETRYED files=" + str(len(applied)) + " fingerprint_ok=" + str(ok)
    except Exception as e:
        return "RETRY_FAILED: {}".format(str(e))


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Apply")
    p.add_argument("--proposal", required=True)
    p.add_argument("--approve", action="store_true")
    p.add_argument("--approver", default="")
    p.add_argument("--reason", default="")
    args = p.parse_args()
    cid, err = apply_change(args.proposal, args.approve, args.approver, args.reason)
    if err:
        print(json.dumps({"decision": "REJECT" if any(k in err for k in
                          ("GOVERNANCE", "要求", "APPLY_FAILED")) else "DEDUP",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    chg = _core.load_artifact("change", cid)
    print(json.dumps({"decision": "APPLIED", "change_id": cid, "state": "APPLIED",
                      "evolution_id": chg.get("evolution_id"),
                      "applied_files": chg.get("_applied_files"),
                      "targets": chg.get("targets"),
                      "next": "run regression.py --change {}".format(cid)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
