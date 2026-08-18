#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
propose.py — Self-Evolution v2 · Propose (Diagnosed → Proposal)

职责：把已 DIAGNOSED 的 candidate 转成最小修改 Proposal。
前提：必须先有有效 Diagnosis（DIAGNOSED）。
Proposal 描述「准备如何最小修改」，不模糊。

禁止模糊 Proposal（如「优化 quotation skill」），必须可执行：
  scope/level/targets/change summary/expected_metric/evidence_refs/baseline/test_plan/governance

状态机：DIAGNOSED → PROPOSED（通过）/ 无有效 Diagnosis 则拒绝。
幂等：同一 target+pattern_key 已有 PROPOSED/更前状态则不重复创建。
Code = Enforcement：确定性字段由本脚本生成；LLM 只提供 change summary / test_plan 文本。

用法：
  python3 propose.py --candidate CAND-xxx --diagnosis DGN-xxx \
      --change "在 quotation skill 文件生成步骤之后增加 artifact existence verification" \
      --expected_metric "verification score >= 0.9" --test_plan "known/normal/boundary 用例"
"""

import argparse
import json

import _core


def build_proposal(cand_id, dgn_id, scope, level, targets, change, expected_metric,
                   baseline, test_plan):
    dgn = _core.load_artifact("diagnosis", dgn_id)
    if not dgn:
        return None, "diagnosis 不存在: " + str(dgn_id)
    if dgn.get("status") != "DIAGNOSED":
        return None, "diagnosis 状态不是 DIAGNOSED: " + str(dgn.get("status"))
    if dgn.get("candidate_id") != cand_id:
        return None, "diagnosis.candidate_id 与输入的 candidate 不一致"

    cand = _core.load_artifact("candidate", cand_id)
    if not cand or cand.get("status") != "DIAGNOSED":
        return None, "candidate 不存在或未 DIAGNOSED"

    level = level or dgn.get("level", "G3")
    if level not in _core.LEVELS:
        return None, "level 非法: " + str(level)

    # 幂等：同 target+pattern_key 已有 PROPOSED 不重复建
    for pid in _core._list_ids("proposal"):
        prev = _core.load_artifact("proposal", pid)
        if prev and prev.get("candidate_id") == cand_id and prev.get("status") in (
                "PROPOSED", "APPROVED", "APPLIED", "REGRESSION", "PROMOTED", "REGRESSED"):
            return prev["id"], "DEDUP_EXISTING_PROPOSAL"

    if _core.is_protected_target(targets):
        raise ValueError("目标 {} 受保护，不能进入演进（Permission/Security/Runtime 永不自动改）".format(targets))

    prop = {
        "status": "PROPOSED",
        "candidate_id": cand_id,
        "diagnosis_id": dgn_id,
        "scope": scope,
        "level": level,
        "targets": targets,
        "change": {"summary": change},
        "expected_metric": expected_metric,
        "evidence_refs": cand.get("evidence_refs", []),
        "baseline": baseline,
        "test_plan": {"cases": test_plan},
        "governance": {
            "approval_required": _core.APPROVAL_BY_LEVEL.get(level, "review"),
            "human_required": _core.require_human_approval(level),
        },
    }
    _core.assert_transition(cand, "PROPOSED", kind="candidate")
    _core.save_artifact("candidate", cand)
    pid = _core.save_artifact("proposal", prop)
    return pid, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2 Propose")
    p.add_argument("--candidate", required=True)
    p.add_argument("--diagnosis", required=True)
    p.add_argument("--scope", default="unknown")
    p.add_argument("--level", choices=_core.LEVELS, default=None)
    p.add_argument("--targets", nargs="+", required=True)
    p.add_argument("--change", required=True)
    p.add_argument("--expected_metric", required=True)
    p.add_argument("--baseline", default="")
    p.add_argument("--test_plan", default="known_failure,normal,boundary")
    args = p.parse_args()

    pid, err = build_proposal(args.candidate, args.diagnosis, args.scope,
                              args.level, args.targets, args.change,
                              args.expected_metric, args.baseline, args.test_plan)
    if err:
        print(json.dumps({"decision": "REJECT" if "DEDUP" not in err else "DEDUP",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    prp = _core.load_artifact("proposal", pid)
    print(json.dumps({"decision": "DEDUP_EXISTING_PROPOSAL" if err else "PROPOSAL_CREATED",
                      "proposal_id": pid,
                      "level": prp.get("level"),
                      "approval_required": prp.get("governance", {}).get("approval_required"),
                      "human_required": prp.get("governance", {}).get("human_required")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
