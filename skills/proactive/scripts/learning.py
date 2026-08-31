#!/usr/bin/env python3
"""Deterministic event -> evidence -> governed writeback pipeline.

This is an OpenClaw post-task adapter, not a runtime or scheduler. It performs
only local, reversible writes. Shared promotion, deletion, and evolution apply
remain behind their existing governance/permission gates.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(SKILLS, "_lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
from persistence import FileLock
from workspace import workspace_root, agent_state_dir, shared_state_dir, current_agent_id


def _load(name, relative):
    path = os.path.join(SKILLS, relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


VERIFY = _load("agent_os_verify", "verification-evaluation/scripts/verify.py")
MEMORY = _load("agent_os_memory", "memory-governance/scripts/memory.py")
KNOWLEDGE = _load("agent_os_knowledge", "knowledge-governance/scripts/knowledge.py")
EVO = _load("agent_os_evolution_core", "self-evolution/scripts/_core.py")
DISCOVER = _load("agent_os_discover", "self-evolution/scripts/discover.py")


def _read(raw):
    if raw == "-":
        return json.load(sys.stdin)
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw)


def _utc_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _append_markdown(path, heading, text):
    text = " ".join(str(text).split()).strip()
    if not text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        existing = ""
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                existing = handle.read()
        if text in existing:
            return False
        prefix = "" if existing.endswith("\n") or not existing else "\n"
        needs_heading = heading not in existing
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(prefix)
            if needs_heading:
                handle.write("\n{}\n\n".format(heading))
            handle.write("- {}\n".format(text))
    return True


def _append_jsonl_once(path, row, identity):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        if json.loads(line).get("id") == identity:
                            return False
                    except (ValueError, TypeError):
                        continue
        payload = dict(row)
        payload["id"] = identity
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def _evidence_id(event, learning):
    seed = "|".join(str(x or "") for x in (
        event.get("event_id"), event.get("execution_id"), event.get("task_id"),
        learning.get("pattern_key"), learning.get("problem")))
    return "EVID-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _register_learning(event, verdict):
    learning = event.get("learning") or {}
    required = (learning.get("problem"), learning.get("pattern_key"), learning.get("target"))
    if not all(required):
        return {"decision": "SKIP", "reason": "no_structured_learning"}
    evidence_id = _evidence_id(event, learning)
    if EVO.load_evidence([evidence_id]):
        return {"decision": "DEDUP", "evidence_id": evidence_id}
    agent_id = current_agent_id(event.get("agent_id"))
    rec = {
        "id": evidence_id,
        "source": event.get("source", "verification"),
        "class": learning.get("class", "verification"),
        "problem": learning["problem"], "pattern_key": learning["pattern_key"],
        "target": learning["target"], "scope": learning.get("scope", "AGENT"),
        "confidence": learning.get("confidence", 0.5),
        "impact": learning.get("impact", "low"),
        "systemic": bool(learning.get("systemic", False)),
        "verified": verdict.get("verdict") == "PASS",
        "session": event.get("session_id", ""),
        "source_agent": event.get("source_agent") or agent_id,
        "independent_source": bool(learning.get("independent_source", False)),
        "correlation_id": event.get("correlation_id", ""),
    }
    EVO.register_evidence(rec, runtime_agent_id=agent_id,
                          runtime_session_id=event.get("session_id", ""),
                          runtime_execution_id=event.get("execution_id", ""),
                          runtime_task_id=event.get("task_id", ""))
    scoped = EVO.query_evidence(rec["pattern_key"], rec["scope"], rec["target"],
                                agent_id=agent_id)
    stats = EVO.compute_stats(evids=[row["id"] for row in scoped])
    threshold, reason = DISCOVER._meets_threshold(stats, stats.get("verified_count", 0))
    result = {"decision": "EVIDENCE_RECORDED", "evidence_id": evidence_id,
              "stats": stats, "threshold": reason}
    if threshold:
        candidate = DISCOVER.build_candidate(
            stats, stats.get("evids", []), rec["problem"], rec["scope"],
            rec["target"], rec["pattern_key"], rec["confidence"], rec["impact"],
            agent_id=agent_id, session_id=event.get("session_id", ""),
            execution_id=event.get("execution_id", ""), task_id=event.get("task_id", ""))
        if candidate.get("_dedup"):
            result.update({"candidate_decision": "DEDUP_EXISTING",
                           "candidate_id": candidate["id"]})
        else:
            result.update({"candidate_decision": "CANDIDATE_CREATED",
                           "candidate_id": EVO.save_artifact("candidate", candidate)})
    return result


def _write_memory(event):
    agent_id = current_agent_id(event.get("agent_id"))
    results = []
    for item in event.get("memory_candidates", []) or []:
        decision = MEMORY.govern(item)
        written = False
        if decision["decision"] == "WRITE_DAILY":
            path = os.path.join(workspace_root(), "memory", _utc_date() + ".md")
            written = _append_markdown(path, "## Agent OS Learnings", item.get("text", ""))
        elif decision["decision"] == "PROMOTE_DURABLE":
            path = os.path.join(workspace_root(), "MEMORY.md")
            written = _append_markdown(path, "## Durable Agent OS Learnings", item.get("text", ""))
        elif decision["decision"] in ("MEMORY_CANDIDATE", "USER_PROFILE_CANDIDATE"):
            path = os.path.join(agent_state_dir("memory", agent_id), "candidates.jsonl")
            identity = "MEM-" + hashlib.sha256((agent_id + "|" + str(item.get("text", ""))).encode("utf-8")).hexdigest()[:16]
            written = _append_jsonl_once(path, {"candidate": item, "governance": decision}, identity)
        results.append({"decision": decision, "written": written})
    return results


def _write_knowledge(event):
    rows = []
    agent_id = current_agent_id(event.get("agent_id"))
    for item in event.get("knowledge_candidates", []) or []:
        decision = KNOWLEDGE.govern(item)
        # Knowledge governance classifies; a separate approval/accept step owns
        # truth promotion. This pipeline never silently creates shared truth.
        target = "candidates.jsonl"
        if decision["decision"] != "REJECT":
            scope = decision.get("claim", {}).get("scope", "AGENT")
            root = (shared_state_dir("knowledge") if scope in ("PROJECT", "USER", "GLOBAL")
                    else agent_state_dir("knowledge", agent_id))
            path = os.path.join(root, target)
            claim = decision.get("claim", {})
            identity = "KNW-" + hashlib.sha256((str(claim.get("subject")) + "|" +
                                                  str(claim.get("claim")) + "|" + scope).encode("utf-8")).hexdigest()[:16]
            written = _append_jsonl_once(path, decision, identity)
        else:
            written = False
        rows.append({"decision": decision, "written": written})
    return rows


def ingest(event):
    verdict = VERIFY.verify(event.get("result", {}), event.get("verification_level", "V1"))
    return {"verification": verdict,
            "evolution": _register_learning(event, verdict),
            "memory": _write_memory(event),
            "knowledge": _write_knowledge(event),
            "vault_projection": "next_due_heartbeat",
            "external_side_effects": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="event JSON, @file, or -")
    args = parser.parse_args()
    print(json.dumps(ingest(_read(args.json)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
