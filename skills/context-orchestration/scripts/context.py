#!/usr/bin/env python3
"""Deterministic minimum-useful context selector; never injects context itself."""

import argparse
import hashlib
import json
import os
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


def _visible(item, req):
    scope = str(item.get("scope", "AGENT")).upper()
    owner = str(item.get("owner_id", ""))
    if scope == "TASK":
        return bool(req.get("task_id")) and owner == str(req.get("task_id"))
    if scope == "AGENT":
        return not owner or owner == str(req.get("agent_id", "main"))
    if scope == "PROJECT":
        return bool(req.get("project_id")) and owner == str(req.get("project_id"))
    return scope in ("USER", "GLOBAL")


def select(req):
    budget = max(256, int(req.get("budget_chars", 4000)))
    time_sensitive = bool(req.get("time_sensitive", False))
    rows, excluded, conflicts, seen = [], [], [], set()
    for item in req.get("items", []):
        text = str(item.get("text", "")).strip()
        iid = item.get("id") or hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        if not text:
            excluded.append({"id": iid, "reason": "empty"})
            continue
        if not _visible(item, req):
            excluded.append({"id": iid, "reason": "scope_denied"})
            continue
        fingerprint = hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
        contradiction = item.get("contradiction_group")
        if fingerprint in seen and not contradiction:
            excluded.append({"id": iid, "reason": "duplicate"})
            continue
        seen.add(fingerprint)
        provenance = 1.0 if item.get("provenance") or item.get("source") else 0.0
        validity = _num(item.get("validity"), 0.5)
        freshness = _num(item.get("freshness"), 0.5)
        confidence = _num(item.get("confidence"), 0.5)
        relevance = _num(item.get("relevance"), 0.5)
        vf = (0.18 * validity + 0.27 * freshness) if time_sensitive else (0.27 * validity + 0.18 * freshness)
        score = 0.25 * provenance + vf + 0.15 * confidence + 0.15 * relevance
        row = dict(item)
        row.update({"id": iid, "text": text, "selection_score": round(score, 4)})
        rows.append(row)
        if contradiction:
            conflicts.append({"group": contradiction, "id": iid})

    rows.sort(key=lambda x: (-x["selection_score"], str(x["id"])))
    selected, used = [], 0
    conflict_groups = {c["group"] for c in conflicts}
    for row in rows:
        size = len(row["text"])
        must_keep = row.get("contradiction_group") in conflict_groups
        # Conflict evidence is atomic: retain every side even when this makes the
        # result exceed the soft budget. Silently keeping only one side is worse.
        if used + size <= budget or must_keep:
            selected.append(row)
            used += size
        else:
            excluded.append({"id": row["id"], "reason": "budget"})
    expand = bool(req.get("confidence_low") or req.get("missing_dependencies")
                  or conflicts or req.get("exhaustive"))
    return {"goal": req.get("goal"), "success_conditions": req.get("success_conditions", []),
            "selected": selected, "conflicts": conflicts, "excluded": excluded,
            "budget_chars": budget, "used_chars": used, "expand_retrieval": expand}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    print(json.dumps(select(read_input(args.json)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
