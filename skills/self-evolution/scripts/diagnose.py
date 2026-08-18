#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose.py — Self-Evolution v2.3 · Diagnose (Candidate → Diagnosis)

v2.3: Candidate 带 evolution_id，Diagnosis 继承 evolution_id。
"""
import argparse
import json
import _core

ALLOWED_ROOT_CAUSES = [
    "workflow_gap", "instruction_gap", "evaluation_gap", "knowledge_gap",
    "tool_behavior", "external_environment", "user_requirement", "unknown",
]
CONFIDENCE_MIN = 0.6


def evaluate(cand_id, root_cause, valid, reproducible, external, existing,
             confidence, target, level):
    if root_cause not in ALLOWED_ROOT_CAUSES:
        return None, "root_cause 非法: " + str(root_cause)
    if level not in _core.LEVELS:
        return None, "level 非法: " + str(level)

    cand = _core.load_artifact("candidate", cand_id)
    if not cand:
        return None, "candidate 不存在: " + cand_id
    if cand.get("status") != "CANDIDATE":
        return None, "candidate 状态不是 CANDIDATE: " + str(cand.get("status"))

    evo_id = cand.get("evolution_id")

    if external or root_cause in ("external_environment", "user_requirement"):
        _core.assert_transition(cand, "UNRESOLVED", kind="candidate")
        _core.save_artifact("candidate", cand)
        dgn = {"status": "UNRESOLVED", "evolution_id": evo_id,
               "candidate_id": cand_id, "root_cause": root_cause,
               "valid": False, "reproducible": reproducible, "external_factor": external,
               "existing_solution": existing, "confidence": confidence,
               "target": target, "level": level, "reason": "external_environment_or_user_requirement"}
        did = _core.save_artifact("diagnosis", dgn)
        return did, None

    gates = {"valid": bool(valid), "reproducible": bool(reproducible),
             "external_environment_not": (not external), "no_existing_solution": (not existing),
             "confidence_ok": float(confidence) >= CONFIDENCE_MIN}
    if not all(gates.values()):
        _core.assert_transition(cand, "UNRESOLVED", kind="candidate")
        _core.save_artifact("candidate", cand)
        dgn = {"status": "UNRESOLVED", "evolution_id": evo_id,
               "candidate_id": cand_id, "root_cause": root_cause,
               "valid": bool(valid), "reproducible": bool(reproducible),
               "external_factor": bool(external), "existing_solution": bool(existing),
               "confidence": float(confidence), "target": target, "level": level,
               "reason": "diagnosis_gate_failed", "gates": gates}
        did = _core.save_artifact("diagnosis", dgn)
        return did, None

    if _core.is_protected_target(target):
        raise ValueError("目标 {} 受保护".format(target))

    _core.assert_transition(cand, "DIAGNOSED", kind="candidate")
    _core.save_artifact("candidate", cand)
    dgn = {"status": "DIAGNOSED", "evolution_id": evo_id,
           "candidate_id": cand_id, "root_cause": root_cause,
           "valid": True, "reproducible": True, "external_factor": False,
           "existing_solution": False, "confidence": float(confidence),
           "target": target, "level": level, "reason": "active"}
    did = _core.save_artifact("diagnosis", dgn)
    return did, None


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Diagnose")
    p.add_argument("--candidate", required=True)
    p.add_argument("--root_cause", required=True, choices=ALLOWED_ROOT_CAUSES)
    p.add_argument("--valid", action="store_true")
    p.add_argument("--reproducible", action="store_true")
    p.add_argument("--external", action="store_true")
    p.add_argument("--existing_solution", action="store_true")
    p.add_argument("--confidence", type=float, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--level", required=True, choices=_core.LEVELS)
    args = p.parse_args()
    did, err = evaluate(args.candidate, args.root_cause, args.valid,
                        args.reproducible, args.external, args.existing_solution,
                        args.confidence, args.target, args.level)
    if err:
        print(json.dumps({"decision": "REJECT", "reason": err}, ensure_ascii=False, indent=2))
        return
    dgn = _core.load_artifact("diagnosis", did)
    print(json.dumps({"decision": "DIAGNOSED" if dgn.get("status") == "DIAGNOSED" else "UNRESOLVED",
                      "diagnosis_id": did, "status": dgn.get("status"),
                      "root_cause": dgn.get("root_cause"), "level": dgn.get("level"),
                      "evolution_id": dgn.get("evolution_id")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
