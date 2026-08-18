#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
propose.py — Self-Evolution v2.3 · Propose (Diagnosed → Proposal)

v2.3: Proposal 带 evolution_id，结构化 operations 必须存在。
"""
import argparse
import json
import _core


def build_proposal(cand_id, dgn_id, scope, level, targets, change, expected_metric,
                   baseline, test_plan, operations=None, change_type="file_patch"):
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

    for pid in _core._list_ids("proposal"):
        prev = _core.load_artifact("proposal", pid)
        if prev and prev.get("candidate_id") == cand_id and prev.get("status") in (
                "PROPOSED", "APPROVED", "APPLIED", "REGRESSION", "PROMOTED", "REGRESSED"):
            return prev["id"], "DEDUP_EXISTING_PROPOSAL"

    if _core.is_protected_target(targets):
        raise ValueError("目标 {} 受保护".format(targets))

    ops = json.loads(operations) if operations else None
    if ops is not None:
        _ok, bad = _core.allowed_ops(ops, targets) if isinstance(ops, list) else (False, ["operations 非数组"])
        if not _ok:
            return None, "operations 越界: " + ";".join(bad)

    change_obj = {"summary": change, "type": change_type}
    if ops is not None:
        change_obj["operations"] = ops

    evo_id = cand.get("evolution_id")
    # SE-01/修复: baseline fingerprint 必须在 Proposal 创建时(而非 Apply 时)记录。
    #   这样 Apply 前才能检测“Proposal 创建 → Apply 之间”的外部修改。
    #   --baseline 若未显式提供指纹，则自动采样 targets 当前 SHA-256 作为基准。
    baseline_fps = {}
    if isinstance(baseline, dict):
        baseline_fps = {rel: fp for rel, fp in baseline.items() if fp}
    else:
        baseline_fps = _core.baseline_fingerprints(targets)
    prop = {
        "status": "PROPOSED",
        "evolution_id": evo_id,
        "candidate_id": cand_id,
        "diagnosis_id": dgn_id,
        "scope": scope,
        "level": level,
        "targets": targets,
        "change": change_obj,
        "expected_metric": expected_metric,
        "evidence_refs": cand.get("evidence_refs", []),
        "baseline": baseline,
        # SE-01: 记录 Proposal 创建时的目标文件 SHA-256 基准，Apply 时据此比对。
        "_baseline_fingerprints": baseline_fps,
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
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Propose")
    p.add_argument("--candidate", required=True)
    p.add_argument("--diagnosis", required=True)
    p.add_argument("--scope", default="unknown")
    p.add_argument("--level", choices=_core.LEVELS, default=None)
    p.add_argument("--targets", nargs="+", required=True)
    p.add_argument("--change", required=True)
    p.add_argument("--expected_metric", required=True)
    p.add_argument("--baseline", default="")
    p.add_argument("--test_plan", default="known_failure,normal,boundary")
    p.add_argument("--operations", default=None)
    args = p.parse_args()
    pid, err = build_proposal(args.candidate, args.diagnosis, args.scope,
                              args.level, args.targets, args.change,
                              args.expected_metric, args.baseline, args.test_plan,
                              args.operations)
    if err:
        print(json.dumps({"decision": "REJECT" if "DEDUP" not in err else "DEDUP",
                          "reason": err}, ensure_ascii=False, indent=2))
        return
    prp = _core.load_artifact("proposal", pid)
    print(json.dumps({"decision": "DEDUP_EXISTING_PROPOSAL" if err else "PROPOSAL_CREATED",
                      "proposal_id": pid, "evolution_id": prp.get("evolution_id"),
                      "level": prp.get("level"),
                      "approval_required": prp.get("governance", {}).get("approval_required"),
                      "human_required": prp.get("governance", {}).get("human_required")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
