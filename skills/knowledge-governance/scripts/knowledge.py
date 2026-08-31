#!/usr/bin/env python3
"""Pure knowledge claim governance; normalizes and classifies without storage."""

import argparse
import json
import sys


def read_input(raw):
    if raw == "-":
        return json.load(sys.stdin)
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw)


def _num(value, default=0.0):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def govern(item):
    subject, claim = str(item.get("subject", "")).strip(), str(item.get("claim", "")).strip()
    errors = []
    if not subject:
        errors.append("missing_subject")
    if not claim:
        errors.append("missing_claim")
    source_type = item.get("source_type", "model_inferred")
    if source_type not in ("user_asserted", "source_stated", "model_inferred"):
        errors.append("invalid_source_type")
    evidence = item.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence] if evidence else []
    confidence = _num(item.get("confidence"), 0.35 if source_type == "model_inferred" else 0.5)
    freshness = _num(item.get("freshness"), 0.5)
    if source_type == "model_inferred" and not evidence:
        confidence = min(confidence, 0.4)
    conflict = bool(item.get("conflict") or item.get("contradicts"))
    changed_context = bool(item.get("context_changed"))
    if conflict:
        status, validity = "disputed", "uncertain"
    elif freshness < 0.2 and changed_context and not evidence:
        status, validity = "obsolete", "stale"
    else:
        status = item.get("status", "active")
        validity = "verified" if evidence and confidence >= 0.75 else "uncertain"
    scope = str(item.get("scope", "AGENT")).upper()
    shared = scope in ("PROJECT", "USER", "GLOBAL")
    normalized = {"subject": subject, "claim": claim, "evidence": evidence,
                  "confidence": confidence, "freshness": freshness,
                  "validity": validity, "status": status, "source_type": source_type,
                  "scope": scope, "owner_id": item.get("owner_id"),
                  "source_agent_id": item.get("source_agent_id"),
                  "source_task_id": item.get("source_task_id"),
                  "source_execution_id": item.get("source_execution_id")}
    decision = "REJECT" if errors else ("SHARED_CANDIDATE" if shared else "RETAIN")
    return {"decision": decision, "claim": normalized, "errors": errors,
            "requires_governance": shared,
            "routes": {"ontology": bool(item.get("entities") or item.get("relations")),
                       "decision_candidate": confidence >= 0.9 and bool(item.get("action_constraint"))}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    data = read_input(args.json)
    rows = data if isinstance(data, list) else [data]
    print(json.dumps({"decisions": [govern(x) for x in rows]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
