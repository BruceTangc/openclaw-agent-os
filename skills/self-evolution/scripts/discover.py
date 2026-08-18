#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover.py — Self-Evolution v2.1 · Discover (Evidence → Candidate)

职责：
- 消费 Agent OS 的 Evidence（Verification/Evaluation/User Feedback/Proactive/Observation）
- **读 Evidence Store，由代码自算 recurrence/sessions/independent_sources**，
  而不是信任调用者填的声称值（Evidence-driven，不是 Evidence-claimed）
- 判定是否形成 Candidate（是否真实问题 / 重复 / 独立来源 / Agent 自身 / 外部 / 已有方案 / 影响足够）
- 幂等：scope+target+pattern_key 已有候选则不重复创建

Candidate 门槛（默认）：
    recurrence >= 3 AND sessions >= 2
    （允许例外：>=2 个独立高质量已验证 Evidence + 明显系统性问题）

禁止形成 Candidate：
    external_environment / 单次失败 / 用户一次性要求 / 随机网络失败 / 第三方异常 / 单次工具故障

LLM = 模式识别（填 problem/pattern_key/target）；阈值/幂等/统计 = 本脚本（Code = Enforcement）。

用法：
  python3 discover.py --evidence-refs E1 E2 E3        # 读已登记 Evidence 自算统计
  python3 discover.py --evidence '<json>'            # 登记一条 Evidence 到 Store 并自算
  python3 discover.py --candidate '<json>'           # 显式提交 candidate（task-manager Discover+Classify 角色）
  python3 discover.py --status                       # 列出 pending candidates
"""

import argparse
import json
import sys
import uuid

import _core


DEFAULT_RECURRENCE = 3
DEFAULT_SESSIONS = 2
EXTERNAL_COUNT = 2          # 例外路径：独立高质量证据数下限
SYSTEMIC_MIN_VERIFIED = 2   # 例外路径：已验证证据数下限
CONFIDENCE_MIN = 0.5


def _record_allows(rec):
    """单条 Evidence 的硬性排除（外部环境 / 一次性 / 用户临时）。"""
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
    """基于**计算出的统计**判断是否够格成为 Candidate（Code = Enforcement）。"""
    recurrence = stats.get("recurrence", 0)
    sessions = stats.get("sessions", 0)
    independent = stats.get("independent_sources", 0)
    systemic = stats.get("systemic", False)

    # 默认门槛：recurrence>=3 且 sessions>=2
    if recurrence >= DEFAULT_RECURRENCE and sessions >= DEFAULT_SESSIONS:
        return True, "threshold"
    # 例外：>=2 独立高质量已验证证据 + 系统性
    if n_verified >= SYSTEMIC_MIN_VERIFIED and independent >= EXTERNAL_COUNT and systemic:
        return True, "systemic_exception"
    return False, "below_threshold"


def build_candidate(stats, evidence_refs, problem, scope, target, pattern_key,
                    confidence, impact):
    """基于自算 stats 构建 candidate 记录（不信任调用者声称的 recurrence/sessions）。"""
    cand = {
        "status": "CANDIDATE",
        "scope": scope,
        "target": target,
        "pattern_key": pattern_key,
        "problem": problem,
        "evidence_refs": evidence_refs,
        "recurrence": stats.get("recurrence", 0),
        "sessions": stats.get("sessions", 0),
        "independent_sources": stats.get("independent_sources", 0),
        "systemic": stats.get("systemic", False),
        "verified": stats.get("verified_count", 0),
        "confidence": float(confidence or 0),
        "impact": impact or "low",
        "diagnosis_id": None,
        "_stats_source": "computed",   # 标记为代码自算，非调用者声称
    }
    existing = _core.find_candidate(scope, target, pattern_key)
    if existing:
        cand["id"] = existing["id"]
        cand["status"] = existing.get("status", "CANDIDATE")
        cand["_dedup"] = True
    return cand


def _register(raw):
    """把原始 evidence 登记进 Store，带上 session(若缺省则生成) 与 id。返回证据 dict。"""
    rec = dict(raw)
    rec.setdefault("id", "EVID-" + uuid.uuid4().hex[:8])
    if not rec.get("session"):
        rec["session"] = "s-" + _core.today_compact()
    eid = _core.register_evidence(rec)
    return _core.load_evidence([eid])[0]


def cmd_evidence_refs(evids):
    """读已登记 Evidence，自算统计，判定门槛。"""
    if not evids:
        print(json.dumps({"decision": "IGNORE", "reason": "no evidence refs"},
                         ensure_ascii=False, indent=2))
        return
    rows = _core.load_evidence(evids)
    if not rows:
        print(json.dumps({"decision": "IGNORE", "reason": "EVID 不存在: " + str(evids)},
                         ensure_ascii=False, indent=2))
        return
    # 先做单条排除（外部/一次性）
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
                      "stats": stats}, ensure_ascii=False, indent=2))


def cmd_evidence(raw):
    """登记一条 Evidence 到 Store，然后基于该 pattern_key 的历史自算统计判定。"""
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
                      "stats": stats, "registered_evidence": rec.get("id")},
                     ensure_ascii=False, indent=2))


def cmd_candidate(raw):
    """显式提交 candidate（task-manager 等 Discover+Classify 角色的交接点）。

    调用方已是该领域的 Doctor 且给出 explicit candidate 语义（含 self-stated stats），
    这里只做幂等 + 保护目标校验，不做门槛重判（避免把 task-manager 的判定推倒重来）。
    这是 Agent OS 分工里「Proactive/task-manager 可 Discover+Classify，Self-Evolution 负责后续」的落点。
    """
    data = json.loads(raw)
    scope = data.get("scope", "unknown")
    target = data.get("target", "")
    pattern_key = data.get("pattern_key", "")
    if not (target and pattern_key):
        print(json.dumps({"decision": "IGNORE", "reason": "缺少 target/pattern_key"},
                         ensure_ascii=False, indent=2))
        return
    cand = {
        "status": "CANDIDATE",
        "scope": scope, "target": target, "pattern_key": pattern_key,
        "problem": data.get("problem", ""),
        "evidence_refs": data.get("evidence_refs", []) or [data.get("source_agent", "task-manager") + ":evidence"],
        "recurrence": int(data.get("recurrence", 1) or 1),
        "sessions": int(data.get("sessions", 1) or 1),
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
        print(json.dumps({"decision": "DEDUP_EXISTING", "candidate_id": cand["id"]},
                         ensure_ascii=False, indent=2))
        return
    cid = _core.save_artifact("candidate", cand)
    print(json.dumps({"decision": "CANDIDATE_CREATED", "candidate_id": cid},
                     ensure_ascii=False, indent=2))


def cmd_status():
    pending = []
    for cid in _core._list_ids("candidate"):
        rec = _core.load_artifact("candidate", cid)
        if rec and rec.get("status") == "CANDIDATE":
            pending.append(cid)
    print(json.dumps({"pending_candidates": pending}, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Self-Evolution v2.1 Discover")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", metavar="JSON", help="登记一条 Evidence 并自算统计判定")
    g.add_argument("--evidence-refs", nargs="+", metavar="EVID",
                   help="读已登记 Evidence IDs 自算统计判定")
    g.add_argument("--candidate", metavar="JSON", help="显式 candidate 交接（task-manager）")
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
