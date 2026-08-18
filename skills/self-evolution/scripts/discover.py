#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
discover.py — Self-Evolution v2 · Discover (Evidence → Candidate)

职责：
- 消费 Agent OS 的 Evidence（Verification/Evaluation/User Feedback/Proactive/Observation）
- 判定是否形成 Candidate（是否真实问题 / 重复 / 独立来源 / Agent 自身 / 外部环境 / 已有方案 / 影响足够）
- 幂等：scope+target+pattern_key 已有候选则不重复创建

Candidate 门槛（默认）：
    recurrence >= 3 AND sessions >= 2
    （允许例外：>=2 个独立高质量已验证 Evidence + 明显系统性问题）

禁止形成 Candidate：
    external_environment / 单次失败 / 用户一次性要求 / 随机网络失败 / 第三方异常 / 单次工具故障

LLM = 模式识别；阈值/幂等判定 = 本脚本（Code = Enforcement）。

用法：
  python3 discover.py --evidence '<json>'         # 单条 Evidence 判定并(可能)建候选
  python3 discover.py --candidate '<json>'        # 直接提交 candidate 原始记录(带证据引用)
  python3 discover.py --status                    # 列出 pending candidates
"""

import argparse
import json
import sys

import _core


DEFAULT_RECURRENCE = 3
DEFAULT_SESSIONS = 2
EXTERNAL_COUNT = 2          # 例外路径：独立高质量证据数下限


def _external_environment(rec):
    src = str(rec.get("class", "")).lower() + " " + str(rec.get("category", "")).lower()
    cue = (str(rec.get("tags", "")).lower() + " " +
           str(rec.get("problem", "")).lower() + " " +
           str(rec.get("source", "")).lower())
    ex = ["external_environment", "api", "network", "third_party", "timeout",
          "rate_limit", "503", "server", "intermittent", "transient", "network_fail"]
    return any(k in (src + " " + cue) for k in ex)


def _one_time(rec):
    cue = (str(rec.get("category", "")).lower() + " " +
           str(rec.get("problem", "")).lower() + " " +
           str(rec.get("source", "")).lower())
    ot = ["one_time", "one-off", "single", "temporary", "user_asked_once",
          "user_requirement", "user_request", "transient", "manual"]
    return any(k in cue for k in ot)


def _meets_threshold(rec):
    """门槛判定（Code = Enforcement，不含 LLM）。"""
    if _external_environment(rec):
        return False, "external_environment"
    if _one_time(rec):
        return False, "one_time_or_user_requirement"

    recurrence = int(rec.get("recurrence", 0) or 0)
    sessions = int(rec.get("sessions", 0) or 0)
    n_evid = len(rec.get("evidence_refs", []) or [])

    # 默认门槛
    if recurrence >= DEFAULT_RECURRENCE and sessions >= DEFAULT_SESSIONS:
        return True, "threshold"
    # 例外：>=2 独立高质量证据 + 系统性
    independent = int(rec.get("independent_sources", 0) or 0)
    systemic = bool(rec.get("systemic", False))
    if n_evid >= EXTERNAL_COUNT and independent >= EXTERNAL_COUNT and systemic:
        return True, "systemic_exception"
    return False, "below_threshold"


def build_candidate(evidence):
    """把 Evidence 归一化成一个 candidate 记录。返回 (candidate_dict, reason)。"""
    scope = evidence.get("scope", "unknown")
    target = evidence.get("target", "")
    pattern_key = evidence.get("pattern_key", "")
    if not (target and pattern_key):
        return None, "缺少 target/pattern_key，无法归并"

    cand = {
        "status": "CANDIDATE",
        "scope": scope,
        "target": target,
        "pattern_key": pattern_key,
        "problem": evidence.get("problem", ""),
        "evidence_refs": evidence.get("evidence_refs", []),
        "recurrence": int(evidence.get("recurrence", 0) or 0),
        "sessions": int(evidence.get("sessions", 0) or 0),
        "independent_sources": int(evidence.get("independent_sources", 0) or 0),
        "systemic": bool(evidence.get("systemic", False)),
        "confidence": evidence.get("confidence", 0.0),
        "impact": evidence.get("impact", "low"),
        "diagnosis_id": None,
    }
    # 幂等：already exists -> 不得重复创建
    existing = _core.find_candidate(scope, target, pattern_key)
    if existing:
        cand["id"] = existing["id"]
        cand["status"] = existing.get("status", "CANDIDATE")
        cand["_dedup"] = True
    return cand, None


def cmd_evidence(raw):
    ev = json.loads(raw)
    ok, reason = _meets_threshold(ev)
    if not ok:
        print(json.dumps({"decision": "IGNORE", "reason": reason}, ensure_ascii=False, indent=2))
        return
    cand, err = build_candidate(ev)
    if err:
        print(json.dumps({"decision": "IGNORE", "reason": err}, ensure_ascii=False, indent=2))
        return
    if cand.get("_dedup"):
        print(json.dumps({"decision": "DEDUP_EXISTING", "candidate_id": cand["id"],
                          "status": cand["status"]}, ensure_ascii=False, indent=2))
        return
    cid = _core.save_artifact("candidate", cand)
    print(json.dumps({"decision": "CANDIDATE_CREATED", "candidate_id": cid},
                     ensure_ascii=False, indent=2))


def cmd_candidate(raw):
    """显式提交 candidate（带已有证据引用）。"""
    data = json.loads(raw)
    cand, err = build_candidate(data)
    if err:
        print(json.dumps({"decision": "IGNORE", "reason": err}, ensure_ascii=False, indent=2))
        return
    if cand.get("_dedup"):
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
    p = argparse.ArgumentParser(description="Self-Evolution v2 Discover")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence", metavar="JSON")
    g.add_argument("--candidate", metavar="JSON")
    g.add_argument("--status", action="store_true")
    args = p.parse_args()
    if args.status:
        cmd_status()
    elif args.evidence:
        cmd_evidence(args.evidence)
    elif args.candidate:
        cmd_candidate(args.candidate)


if __name__ == "__main__":
    main()
