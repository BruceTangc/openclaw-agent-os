#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover.py — Self-Evolution v2.3 · Discover (Evidence → Candidate)

v2.3 变更：
- compute_stats 返回 observation_count/unique_sessions（不再叫 recurrence/sessions）
- Candidate 记录带 evolution_id
- Evidence 只允许外部来源写入（_core 内置检查）
"""
import argparse
import json
import sys
import uuid

import _core


DEFAULT_OBSERVATION_COUNT = 3
DEFAULT_UNIQUE_SESSIONS = 2
EXTERNAL_COUNT = 2
SYSTEMIC_MIN_VERIFIED = 2


def _record_allows(rec):
    src = str(rec.get("class", "")) + " " + str(rec.get("category", ""))
    cue = (str(rec.get("tags", "")) + " " + str(rec.get("problem", "")) +
           " " + str(rec.get("source", "")) + " " + str(rec.get("source_agent", "")))
    combined = (src + " " + cue).lower()
    ex = ["external_environment", "network", "third_party", "timeout", "rate_limit",
          "503", "server_error", "intermittent", "transient", "network_fail"]
    ot = ["one_time", "one-off", "single", "temporary", "user_asked_once",
          "user_requirement", "user_request", "manual"]
    if any(k in combined for k in ex):
        return False, "external_environment"
    if any(k in combined for k in ot):
        return False, "one_time_or_user_requirement"
    return True, None


def _meets_threshold(stats, n_verified):
    obs = stats.get("observation_count", 0)
    sessions = stats.get("unique_sessions")
    independent = stats.get("independent_sources", 0)
    systemic = stats.get("systemic", False)
    if obs >= DEFAULT_OBSERVATION_COUNT and (sessions is not None and sessions >= DEFAULT_UNIQUE_SESSIONS):
        return True, "threshold"
    if n_verified >= SYSTEMIC_MIN_VERIFIED and independent >= EXTERNAL_COUNT and systemic:
        return True, "systemic_exception"
    return False, "below_threshold"


def build_candidate(stats, evidence_refs, problem, scope, target, pattern_key,
                    confidence, impact, agent_id=None, session_id=None,
                    execution_id=None, task_id=None):
    evo_id = _core.gen_evolution_id()
    cand = {
        "status": "CANDIDATE",
        "evolution_id": evo_id,
        "scope": scope,
        "target": target,
        "pattern_key": pattern_key,
        "problem": problem,
        "evidence_refs": evidence_refs,
        # MA-1.0 Integration#3: Candidate Agent 归属。保留"这个问题是谁发现的",
        #   供 Evolution 判断 Agent-specific vs Shared 及 scope 越权（Research 只能改
        #   自己的 Skill）。单 Agent/legacy 允许缺省。
        "agent_id": str(agent_id or ""),
        "session_id": str(session_id or ""),
        "execution_id": str(execution_id or ""),
        "task_id": str(task_id or ""),
        "observation_count": stats.get("observation_count", 0),
        "unique_executions": stats.get("unique_executions", 0),
        "unique_sessions": stats.get("unique_sessions"),
        "independent_sources": stats.get("independent_sources", 0),
        "systemic": stats.get("systemic", False),
        "verified": stats.get("verified_count", 0),
        "confidence": float(confidence or 0),
        "impact": impact or "low",
        "diagnosis_id": None,
        "_stats_source": "computed",
    }
    existing = _core.find_candidate(scope, target, pattern_key)
    if existing:
        cand["id"] = existing["id"]
        cand["status"] = existing.get("status", "CANDIDATE")
        cand["_dedup"] = True
    return cand


def _register(raw):
    rec = dict(raw)
    rec.setdefault("id", "EVID-" + uuid.uuid4().hex[:8])
    if not rec.get("session"):
        rec["session"] = "s-" + _core.today_compact()
    eid = _core.register_evidence(rec)
    return _core.load_evidence([eid])[0]


def cmd_evidence_refs(evids):
    if not evids:
        print(json.dumps({"decision": "IGNORE", "reason": "no evidence refs"},
                         ensure_ascii=False, indent=2))
        return
    rows = _core.load_evidence(evids)
    if not rows:
        print(json.dumps({"decision": "IGNORE", "reason": "EVID 不存在: " + str(evids)},
                         ensure_ascii=False, indent=2))
        return
    for r in rows:
        _ok, reason = _record_allows(r)
        if not _ok:
            print(json.dumps({"decision": "IGNORE", "reason": reason,
                              "evidence": r.get("id")}, ensure_ascii=False, indent=2))
            return
    stats = _core.compute_stats(evids=evids)
    n_verified = stats.get("verified_count", 0)
    ok, reason = _meets_threshold(stats, n_verified)
    if not ok:
        print(json.dumps({"decision": "IGNORE", "reason": reason,
                          "stats": stats}, ensure_ascii=False, indent=2))
        return
    first = rows[0]
    cand = build_candidate(
        stats, stats.get("evids", []),
        first.get("problem", ""),
        first.get("scope", "unknown"), first.get("target", ""),
        first.get("pattern_key", ""),
        first.get("confidence", 0), first.get("impact", "low"))
    if cand.get("_dedup"):
        print(json.dumps({"decision": "DEDUP_EXISTING", "candidate_id": cand["id"],
                          "stats": stats}, ensure_ascii=False, indent=2))
        return
    cid = _core.save_artifact("candidate", cand)
    print(json.dumps({"decision": "CANDIDATE_CREATED", "candidate_id": cid,
                      "evolution_id": cand.get("evolution_id"),
                      "stats": stats}, ensure_ascii=False, indent=2))


def cmd_evidence(raw):
    ev = json.loads(raw)
    _ok, reason = _record_allows(ev)
    if not _ok:
        print(json.dumps({"decision": "IGNORE", "reason": reason},
                         ensure_ascii=False, indent=2))
        return
    rec = _register(ev)
    pattern_key = rec.get("pattern_key", "")
    scope = rec.get("scope", "unknown")
    target = rec.get("target", "")
    if not (pattern_key and target):
        print(json.dumps({"decision": "IGNORE",
                          "reason": "缺少 pattern_key/target，无法归并"},
                         ensure_ascii=False, indent=2))
        return
    stats = _core.compute_stats(pattern_key=pattern_key, scope=scope, target=target)
    n_verified = stats.get("verified_count", 0)
    ok, reason = _meets_threshold(stats, n_verified)
    if not ok:
        print(json.dumps({"decision": "IGNORE", "reason": reason,
                          "stats": stats, "registered_evidence": rec.get("id")},
                         ensure_ascii=False, indent=2))
        return
    cand = build_candidate(
        stats, stats.get("evids", []),
        rec.get("problem", ""), scope, target, pattern_key,
        rec.get("confidence", 0), rec.get("impact", "low"))
    if cand.get("_dedup"):
        print(json.dumps({"decision": "DEDUP_EXISTING", "candidate_id": cand["id"],
                          "stats": stats}, ensure_ascii=False, indent=2))
        return
    cid = _core.save_artifact("candidate", cand)
    print(json.dumps({"decision": "CANDIDATE_CREATED", "candidate_id": cid,
                      "evolution_id": cand.get("evolution_id"),
                      "stats": stats, "registered_evidence": rec.get("id")},
                     ensure_ascii=False, indent=2))


def cmd_candidate(raw):
    data = json.loads(raw)
    scope = data.get("scope", "unknown")
    target = data.get("target", "")
    pattern_key = data.get("pattern_key", "")
    if not (target and pattern_key):
        print(json.dumps({"decision": "IGNORE", "reason": "缺少 target/pattern_key"},
                         ensure_ascii=False, indent=2))
        return
    evo_id = _core.gen_evolution_id()
    cand = {
        "status": "CANDIDATE",
        "evolution_id": evo_id,
        "scope": scope, "target": target, "pattern_key": pattern_key,
        "problem": data.get("problem", ""),
        "evidence_refs": data.get("evidence_refs", []) or [
            data.get("source_agent", "task-manager") + ":evidence"],
        "observation_count": int(data.get("observation_count", 1) or 1),
        "unique_sessions": int(data.get("unique_sessions", 1) or 1),
        "independent_sources": int(data.get("independent_sources", 1) or 1),
        "systemic": bool(data.get("systemic", False)),
        "confidence": float(data.get("confidence", 0) or 0),
        "impact": data.get("impact", "medium"),
        "diagnosis_id": None,
        "_via": "candidate_handoff",
    }
    existing = _core.find_candidate(scope, target, pattern_key)
    if existing:
        cand["id"] = existing["id"]
        cand["status"] = existing.get("status", "CANDIDATE")
        cand["_dedup"] = True
        print(json.dumps({"decision": "DEDUP_EXISTING", "candidate_id": cand["id"],
                          "evolution_id": existing.get("evolution_id")},
                         ensure_ascii=False, indent=2))
        return
    cid = _core.save_artifact("candidate", cand)
    print(json.dumps({"decision": "CANDIDATE_CREATED", "candidate_id": cid,
                      "evolution_id": evo_id}, ensure_ascii=False, indent=2))


def cmd_status():
    pending = []
    for cid in _core._list_ids("candidate"):
        rec = _core.load_artifact("candidate", cid)
        if rec and rec.get("status") == "CANDIDATE":
            pending.append(cid)
    print(json.dumps({"pending_candidates": pending}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.3 Discover")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", metavar="JSON")
    g.add_argument("--evidence-refs", nargs="+", metavar="EVID")
    g.add_argument("--candidate", metavar="JSON")
    g.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.status:
        cmd_status()
    elif args.evidence:
        cmd_evidence(args.evidence)
    elif args.evidence_refs:
        cmd_evidence_refs(args.evidence_refs)
    elif args.candidate:
        cmd_candidate(args.candidate)


if __name__ == "__main__":
    main()
