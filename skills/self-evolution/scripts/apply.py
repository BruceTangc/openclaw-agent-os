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

    # 成功：推进到 APPLIED
    change["status"] = "APPLIED"
    change["_applied_files"] = applied
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
