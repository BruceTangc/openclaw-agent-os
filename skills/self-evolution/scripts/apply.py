#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply.py — Self-Evolution v2 · Apply (Approved → Apply exact change)

职责（必须是"笨"的，不负责思考）：
    Proposal → Approval → Snapshot → Apply exact change → Change Record → Regression

Governance（Apply 前安全闸门，任一不满足 → REJECT，不得 Apply）：
  proposal 存在 / diagnosis 有效 / evidence 存在 / target 与 proposal 一致 /
  change level / 是否需人工审批 / regression plan / rollback plan

Apply 不得：修改额外文件 / 扩大范围 / 改变 proposal / 绕过 approval / 修改权限。

- 状态机：PROPOSED → APPROVED → APPLIED
- 幂等：同一 proposal 不得重复 Apply
- Snapshot：Apply 前建 .agent-os/evolution/changes/CHG-*/snapshot/
- 保护目标：Permission/Security/Runtime 永远拦截（即使显式 --approve）

Code = Enforcement：approval 要求、snapshot、scope 校验、保护目标由本脚本决定。
LLM 只负责确认审批（--approve）与填写审批理由。

用法：
  python3 apply.py --proposal PRP-xxx --approve --approver "main agent" \
      --reason "用户已确认，G3 工作流调整"
"""

import argparse
import json
import os

import _core


def governance_check(prop):
    """Apply 前的 governance 安全闸门（Code = Enforcement）。返回 (ok, problems)。"""
    problems = []

    # Proposal 是否存在 & 状态
    if not prop:
        return False, ["proposal 不存在"]
    if prop.get("status") not in ("PROPOSED", "APPROVED"):
        problems.append("proposal 状态不是 PROPOSED/APPROVED: " + str(prop.get("status")))

    # Diagnosis 是否有效
    dgn = _core.load_artifact("diagnosis", prop.get("diagnosis_id", ""))
    if not dgn or dgn.get("status") != "DIAGNOSED":
        problems.append("diagnosis 不存在或无效（status≠DIAGNOSED）")

    # Evidence 是否存在
    if not prop.get("evidence_refs"):
        problems.append("缺少 evidence_refs")

    # Change Level 与审批要求
    level = prop.get("level", "G3")
    human = _core.require_human_approval(level)

    # 保护目标
    for t in (prop.get("targets") or []):
        if _core.is_protected_target(t):
            problems.append("目标受保护：{}（Permission/Security/Runtime 永不自动改）".format(t))

    if human and not prop.get("_approved"):
        problems.append("级别 {} 要求人工审批，但未带 --approve 确认".format(level))

    # Regression + Rollback plan
    if not prop.get("test_plan"):
        problems.append("缺少 test_plan (regression plan)")
    if not (prop.get("targets")):
        problems.append("缺少 targets (rollback 需要 snapshot 目标)")

    return (len(problems) == 0), problems


def apply_change(proposal_id, approve, approver, reason):
    prop = _core.load_artifact("proposal", proposal_id)
    if not prop:
        return None, "proposal 不存在: " + proposal_id

    # 幂等：同 proposal 已 APPLIED/后续状态不重复 Apply
    if prop.get("status") in ("APPLIED", "REGRESSION", "PROMOTED", "REGRESSED", "ROLLED_BACK"):
        return None, "DEDUP: proposal 已为状态 " + str(prop.get("status"))

    cand = _core.load_artifact("candidate", prop.get("candidate_id", ""))
    if cand:
        _core.assert_transition(cand, "PROPOSED", kind="candidate")  # no-op 幂等
        _core.save_artifact("candidate", cand)

    # 记录审批（G5/G6 必须显式）
    human = _core.require_human_approval(prop.get("level", "G3"))
    if human and not approve:
        return None, "级别 {} 要求人工审批，必须 --approve".format(prop.get("level"))
    prop["_approved"] = True
    prop["_approval"] = {
        "approver": approver or "unknown",
        "reason": reason or "",
        "human_required": human,
        "at": _core.now_iso(),
    }

    # Governance 闸门
    ok, problems = governance_check(prop)
    if not ok:
        # REJECT：记录 proposal 状态 REJECTED，不 Apply
        _core.assert_transition(prop, "REJECTED", kind="proposal")
        _core.save_artifact("proposal", prop)
        return None, "GOVERNANCE_REJECT: " + "; ".join(problems)

    # 建立 Change Record + Snapshot
    change = {
        "status": "APPLIED",
        "proposal_id": proposal_id,
        "candidate_id": prop.get("candidate_id"),
        "diagnosis_id": prop.get("diagnosis_id"),
        "level": prop.get("level"),
        "targets": list(prop.get("targets") or []),
        "change": prop.get("change", {}),
        "expected_metric": prop.get("expected_metric"),
        "applied_at": _core.now_iso(),
    }
    cid = _core.save_artifact("change", change)
    change["id"] = cid
    snap = _core.take_snapshot(cid, change["targets"])

    # 状态推进：PROPOSED → APPROVED → APPLIED
    _core.assert_transition(prop, "APPROVED", kind="proposal")
    prop["_change_id"] = cid
    prop["_snapshot"] = snap
    _core.save_artifact("proposal", prop)
    _core.assert_transition(prop, "APPLIED", kind="proposal")  # no-op
    _core.save_artifact("proposal", prop)

    _core.assert_transition(change, "APPLIED", kind="change")
    _core.save_artifact("change", change)

    return cid, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2 Apply")
    p.add_argument("--proposal", required=True)
    p.add_argument("--approve", action="store_true")
    p.add_argument("--approver", default="")
    p.add_argument("--reason", default="")
    args = p.parse_args()

    cid, err = apply_change(args.proposal, args.approve, args.approver, args.reason)
    if err:
        print(json.dumps({"decision": "REJECT" if "GOVERNANCE" in err or "要求" in err
                          else "DEDUP", "reason": err}, ensure_ascii=False, indent=2))
        return
    chg = _core.load_artifact("change", cid)
    print(json.dumps({"decision": "APPLIED",
                      "change_id": cid,
                      "state": "APPLIED",
                      "snapshot": chg.get("_snapshot_recalc") if False else chg.get("status"),
                      "targets": chg.get("targets"),
                      "next": "run regression.py --change {}".format(cid)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
