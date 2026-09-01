#!/usr/bin/env python3
"""Evidence candidate -> evaluated, approval-gated Skill Proposal adapter.

This adapter may create diagnosis/proposal artifacts. It never applies patches.
"""

import argparse
import json
import os

import _core
import diagnose
import propose


def _existing(candidate_id):
    for ident in _core._list_ids("proposal"):
        row = _core.load_artifact("proposal", ident)
        if row and row.get("candidate_id") == candidate_id:
            return row
    return None


def evaluate_proposal(proposal_id):
    row = _core.load_artifact("proposal", proposal_id)
    checks = {
        "status_proposed": bool(row and row.get("status") == "PROPOSED"),
        "has_evidence": bool(row and row.get("evidence_refs")),
        "has_baseline": bool(row and row.get("_baseline_fingerprints")),
        "has_tests": bool(row and row.get("test_plan", {}).get("cases")),
        "apply_not_performed": bool(row and not row.get("change_id")),
    }
    return {"proposal_id": proposal_id, "checks": checks,
            "verdict": "READY_FOR_REVIEW" if all(checks.values()) else "REJECT"}


def prepare(candidate_id):
    candidate = _core.load_artifact("candidate", candidate_id)
    if not candidate:
        return {"decision": "REJECT", "reason": "candidate_not_found"}
    prior = _existing(candidate_id)
    if prior:
        return {"decision": "DEDUP", "proposal_id": prior["id"],
                "evaluation": evaluate_proposal(prior["id"])}
    if candidate.get("status") != "CANDIDATE":
        return {"decision": "SKIP", "reason": "candidate_not_pending"}
    spec = candidate.get("automation") or {}
    required = ("root_cause", "target", "proposed_change", "expected_metric")
    missing = [key for key in required if not spec.get(key)]
    if missing or not spec.get("reproducible"):
        return {"decision": "SKIP", "reason": "insufficient_structured_diagnosis",
                "missing": missing, "reproducible": bool(spec.get("reproducible"))}
    target = str(spec["target"])
    if not target.startswith("skills/") or _core.is_protected_target(target):
        return {"decision": "REJECT", "reason": "target_not_safe_skill"}
    absolute = _core.ws_abs(target)
    if not _core.is_within_workspace(absolute) or not os.path.isfile(absolute):
        return {"decision": "REJECT", "reason": "target_missing_or_outside_workspace"}
    confidence = float(candidate.get("confidence", 0) or 0)
    diagnosis_id, error = diagnose.evaluate(
        candidate_id, spec["root_cause"], True, True, False, False,
        confidence, target, spec.get("level", "G3"))
    if error:
        return {"decision": "REJECT", "reason": error}
    proposal_id, error = propose.build_proposal(
        candidate_id, diagnosis_id, "skill", spec.get("level", "G3"),
        [target], spec["proposed_change"], spec["expected_metric"],
        "", spec.get("test_plan", "known_failure,normal,boundary"),
        operations=json.dumps(spec["operations"]) if spec.get("operations") else None)
    if error and error != "DEDUP_EXISTING_PROPOSAL":
        return {"decision": "REJECT", "reason": error}
    return {"decision": "PROPOSAL_READY_FOR_REVIEW", "proposal_id": proposal_id,
            "applied": False, "evaluation": evaluate_proposal(proposal_id)}


def scan():
    results = []
    for ident in _core._list_ids("candidate"):
        try:
            candidate = _core.load_artifact("candidate", ident)
            if not candidate or candidate.get("status") != "CANDIDATE":
                continue
            result = prepare(ident)
        except Exception as exc:
            result = {"decision": "REJECT", "candidate_id": ident,
                      "reason": "pipeline_error", "error": str(exc)}
        result.setdefault("candidate_id", ident)
        results.append(result)
    return {"processed": len(results), "results": results,
            "ready_for_review": [x["proposal_id"] for x in results
                                 if x.get("decision") == "PROPOSAL_READY_FOR_REVIEW"],
            "needs_manual_review": [x["candidate_id"] for x in results
                                    if x.get("decision") in ("SKIP", "REJECT")]}


def main():
    parser = argparse.ArgumentParser(description="Governed evolution proposal pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    one = sub.add_parser("prepare")
    one.add_argument("--candidate", required=True)
    args = parser.parse_args()
    out = scan() if args.cmd == "scan" else prepare(args.candidate)
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if out.get("decision") != "REJECT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
