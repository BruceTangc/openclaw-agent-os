#!/usr/bin/env python3
"""Pure memory writeback governance; returns decisions and never writes memory."""

import argparse
import json
import re
import sys


SECRET = re.compile(r"(?i)(api[_ -]?key|access[_ -]?token|password|secret|private[_ -]?key)\s*[:=]")


def _num(value, default=0.0, integer=False):
    try:
        number = float(value)
        return max(0, int(number)) if integer else max(0.0, min(1.0, number))
    except (TypeError, ValueError):
        return default


def read_input(raw):
    if raw == "-":
        return json.load(sys.stdin)
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw)


def govern(item):
    text = str(item.get("text", "")).strip()
    reasons = []
    if not text:
        return {"decision": "REJECT", "target_layer": "none", "reasons": ["empty"]}
    if item.get("sensitive") or SECRET.search(text):
        return {"decision": "DENY_SECRET", "target_layer": "secret_store", "reasons": ["sensitive"]}
    if item.get("explicit_delete"):
        return {"decision": "ASK_DELETE", "target_layer": item.get("existing_layer", "unknown"),
                "requires_permission": True, "reasons": ["explicit_delete_requires_gate"]}
    if item.get("redundant"):
        return {"decision": "SKIP_DUPLICATE", "target_layer": "none", "reasons": ["redundant"]}
    explicit = bool(item.get("explicit_remember"))
    provenance = bool(item.get("provenance") or item.get("source"))
    confidence = _num(item.get("confidence"), 0.0)
    stable = bool(item.get("stable"))
    useful = bool(item.get("useful"))
    sessions = _num(item.get("independent_sessions"), 0, integer=True)
    if item.get("conflict"):
        reasons.append("conflict_preserved")
    if explicit and item.get("kind") in ("preference", "constraint", "user_fact"):
        decision, layer = "USER_PROFILE_CANDIDATE", "user-profile"
    elif item.get("expires") or item.get("time_sensitive"):
        decision, layer = "WRITE_DAILY", "daily"
    elif stable and useful and provenance and confidence >= 0.75 and sessions >= 2:
        decision, layer = "PROMOTE_DURABLE", "durable"
    elif explicit or (useful and provenance):
        decision, layer = "MEMORY_CANDIDATE", "daily"
    else:
        decision, layer = "KEEP_SESSION", "session"
    reasons.extend(["provenance" if provenance else "missing_provenance",
                    "stable" if stable else "not_stable"])
    return {"decision": decision, "target_layer": layer, "reasons": reasons,
            "status": "disputed" if item.get("conflict") else "candidate",
            "requires_permission": False,
            "routes": {"knowledge": item.get("kind") == "reusable_fact",
                       "ontology": bool(item.get("entities") or item.get("relations"))}}


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
