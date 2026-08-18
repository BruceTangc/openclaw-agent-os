#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execution Record — Protocol observability layer (V1.0)

Append-only execution record，回答"这次行为是否符合 Agent OS Protocol、从哪来到哪去"。
每条记录记录一次 action 的完整上下文，供 Anti-loop Progress Gate 判断。

用法:
  execution_record.py log --json '<record>'    # 写入一条记录
  execution_record.py check --json '<check>'   # 判断是否 no-progress
  execution_record.py query --goal <goal_id>   # 查询某 goal 的记录
  execution_record.py stats --goal <goal_id>   # 统计某 goal 的进展

不是 runtime，不是 scheduler，不是 skill。只是 append-only 的记录层。
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "memory")


def _record_path():
    return os.path.join(MEMORY_DIR, "execution_records.jsonl")


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _hash_str(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _stable_hash(data):
    """对 dict 做稳定 hash，排除 volatile fields。"""
    clean = {}
    exclude = {"timestamp", "created_at", "updated_at", "execution_id", "cycle_id"}
    for k, v in sorted(data.items()):
        if k in exclude:
            continue
        clean[k] = v
    return hashlib.sha256(
        json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def load_records(goal_id=None, limit=100):
    """读取记录，可选按 goal_id 过滤。"""
    path = _record_path()
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if goal_id and r.get("goal_id") != goal_id:
                    continue
                records.append(r)
            except Exception:
                continue
    return records[-limit:]


def append_record(record):
    """追加一条记录。"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    record.setdefault("execution_id", "EXE-" + _hash_str(
        json.dumps(record, sort_keys=True) + utcnow_iso()))
    record.setdefault("timestamp", utcnow_iso())
    with open(_record_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


# ---------------------------------------------------------------------------
# Action Signature（deterministic，不依赖 LLM）
# ---------------------------------------------------------------------------
def compute_action_signature(goal_id, task_id, action_type, normalized_target):
    """hash(goal_id + task_id + action_type + normalized_target)
    相同输入 → 相同输出，不依赖 timestamp。"""
    raw = "|".join([
        str(goal_id or ""),
        str(task_id or ""),
        str(action_type or ""),
        str(normalized_target or ""),
    ])
    return _hash_str(raw)


# ---------------------------------------------------------------------------
# Progress Gate（核心 Anti-loop 判断）
# ---------------------------------------------------------------------------
def check_action_loop(current_record, previous_record=None):
    """判断当前 action 是否构成 no-progress loop。

    返回 {
        "decision": CONTINUE | WARN | NOOP | ESCALATE,
        "reason": str,
        "consecutive_no_progress": int,
    }

    规则：
    - same action + same result + no new evidence → no-progress counter + 1
    - same action + different result/evidence → CONTINUE (正常)
    - consecutive_no_progress >= 1 → WARN
    - consecutive_no_progress >= 2 → NOOP
    - consecutive_no_progress >= 3 → ESCALATE
    """
    if not previous_record:
        return {
            "decision": "CONTINUE",
            "reason": "首次执行",
            "consecutive_no_progress": 0,
        }

    same_action = (current_record.get("action_signature") ==
                   previous_record.get("action_signature"))
    same_result = (current_record.get("result_hash") ==
                   previous_record.get("result_hash"))
    same_evidence = (current_record.get("evidence_hash") ==
                     previous_record.get("evidence_hash"))
    same_state = (current_record.get("current_state") ==
                  previous_record.get("current_state"))

    if not same_action:
        return {
            "decision": "CONTINUE",
            "reason": "不同 action",
            "consecutive_no_progress": 0,
        }

    # same action — 检查是否有进展
    has_progress = not same_result or not same_evidence or not same_state

    if has_progress:
        return {
            "decision": "CONTINUE",
            "reason": "同 action 但有新 result/evidence/state",
            "consecutive_no_progress": 0,
        }

    # same action + same result + same evidence + same state → no-progress
    prev_count = previous_record.get("progress", {}).get("no_progress", 0)
    new_count = prev_count + 1

    if new_count >= 3:
        decision = "ESCALATE"
        reason = "连续 %d 次无进展" % new_count
    elif new_count >= 2:
        decision = "NOOP"
        reason = "连续 %d 次无进展" % new_count
    else:
        decision = "WARN"
        reason = "第 %d 次无进展" % new_count

    return {
        "decision": decision,
        "reason": reason,
        "consecutive_no_progress": new_count,
    }


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------
def cmd_log(args):
    record = json.loads(args.json) if args.json else {}
    record.setdefault("action_type", "unknown")
    record.setdefault("action_signature", "")
    record.setdefault("result_hash", "")
    record.setdefault("evidence_hash", "")
    record.setdefault("previous_state", "")
    record.setdefault("current_state", "")
    record.setdefault("goal_id", "")
    record.setdefault("task_id", "")
    record.setdefault("cycle_id", "")
    record.setdefault("parent_task_id", "")
    record.setdefault("attempt", 1)
    record.setdefault("retry_count", 0)
    record.setdefault("progress", {
        "new_evidence": False,
        "new_artifact": False,
        "new_state": False,
        "goal_progress": False,
        "no_progress": 0,
    })
    record.setdefault("decision", "CONTINUE")
    record.setdefault("stop_reason", "")

    result = append_record(record)
    print(json.dumps({"logged": True, "execution_id": result["execution_id"]},
                     ensure_ascii=False))


def cmd_check(args):
    """判断当前 record 是否构成 no-progress loop。"""
    check = json.loads(args.json) if args.json else {}
    goal_id = check.get("goal_id", "")
    action_signature = check.get("action_signature", "")

    # 找同一 goal + 同一 action 的最后一条记录
    records = load_records(goal_id=goal_id, limit=50)
    prev = None
    for r in reversed(records):
        if r.get("action_signature") == action_signature:
            prev = r
            break

    result = check_action_loop(check, prev)
    print(json.dumps(result, ensure_ascii=False))


def cmd_query(args):
    records = load_records(goal_id=args.goal, limit=int(args.limit or 50))
    print(json.dumps({"records": records, "total": len(records)},
                     ensure_ascii=False))


def cmd_stats(args):
    records = load_records(goal_id=args.goal, limit=200)
    if not records:
        print(json.dumps({"total": 0, "no_progress_runs": 0,
                          "escalated": False}, ensure_ascii=False))
        return

    no_progress = sum(1 for r in records
                      if r.get("progress", {}).get("no_progress", 0) > 0)
    escalated = any(r.get("decision") == "ESCALATE" for r in records)
    last_progress = max((r.get("progress", {}).get("no_progress", 0)
                         for r in records), default=0)

    print(json.dumps({
        "total": len(records),
        "no_progress_runs": no_progress,
        "last_no_progress": last_progress,
        "escalated": escalated,
        "goal_ids": list(set(r.get("goal_id") for r in records if r.get("goal_id"))),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Execution Record (V1.0)")
    sub = parser.add_subparsers(dest="cmd")

    p_log = sub.add_parser("log", help="写入一条记录")
    p_log.add_argument("--json", required=True, help="记录 JSON")

    p_check = sub.add_parser("check", help="判断是否 no-progress loop")
    p_check.add_argument("--json", required=True, help="当前 record JSON")

    p_query = sub.add_parser("query", help="查询记录")
    p_query.add_argument("--goal", help="按 goal_id 过滤")
    p_query.add_argument("--limit", default="50")

    p_stats = sub.add_parser("stats", help="统计进展")
    p_stats.add_argument("--goal", help="按 goal_id 过滤")

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    handlers = {"log": cmd_log, "check": cmd_check,
                "query": cmd_query, "stats": cmd_stats}
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
