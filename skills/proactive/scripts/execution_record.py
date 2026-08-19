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

# v1.3 Hardening #9: JSONL 文件锁 + append-only
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from persistence import append_atomic  # noqa: E402

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
    """读取记录，可选按 goal_id 过滤。

    v1.3 #10/#12:
      - 损坏 JSONL 行记录到 corruption/corrupt_lines，不静默跳过。
      - 历史读取失败返回 history_unavailable=True，禁止被当成"首次执行"。
    返回 dict {records, corruption, corrupt_lines, history_unavailable}。
    """
    path = _record_path()
    if not os.path.isfile(path):
        return {"records": [], "corruption": 0, "corrupt_lines": [],
                "history_unavailable": False}
    records = []
    corrupt_lines = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if goal_id and r.get("goal_id") != goal_id:
                        continue
                    records.append(r)
                except Exception:
                    corrupt_lines.append(i)
    except OSError as e:
        # 历史读取失败 → history_unavailable，禁止静默当首次
        return {"records": [], "corruption": 0, "corrupt_lines": [],
                "history_unavailable": True, "error": str(e),
                "goal_id": goal_id}
    return {"records": records[-limit:], "corruption": len(corrupt_lines),
            "corrupt_lines": corrupt_lines, "history_unavailable": False}


def histories_available(goal_id=None):
    """判断该 goal 是否有可用历史 (#12)。"""
    res = load_records(goal_id=goal_id, limit=200)
    if res.get("history_unavailable", False):
        return False
    return len(res.get("records", [])) > 0


def append_record(record):
    """追加一条记录 (v1.3 #9: 文件锁 + append-only)。"""
    record.setdefault("execution_id", "EXE-" + _hash_str(
        json.dumps(record, sort_keys=True) + utcnow_iso()))
    record.setdefault("timestamp", utcnow_iso())
    append_atomic(_record_path(), record)
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
def check_action_loop(current_record, previous_record=None,
                      previous_available=True):
    """判断当前 action 是否构成 no-progress loop。

    v1.3 #11: progress 维度含 result/evidence/state/artifact/goal_progress，
             任一变化即 PROGRESS。
    v1.3 #12: previous_available=False (历史读失败) → UNKNOWN，
             禁止静默当首次执行 CONTINUE。
    v1.3 #13: same action + same input + same evidence + same state + same
             strategy → no-progress counter +1。

    返回 {decision, reason, consecutive_no_progress, [history_unavailable]}。
    decision ∈ CONTINUE | WARN | NOOP | ESCALATE | UNKNOWN
    """
    if not previous_available:
        return {
            "decision": "UNKNOWN",
            "reason": "history_unavailable: 历史读取失败或无法确认",
            "consecutive_no_progress": 0,
            "history_unavailable": True,
        }

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
    same_strategy = (current_record.get("strategy") ==
                     previous_record.get("strategy"))
    same_input = (current_record.get("input_hash") ==
                  previous_record.get("input_hash"))
    # BE-3 (Action→Observation 对应): observation 变化 = 可观测结果变化, 算 progress。
    same_observation = (current_record.get("observation_hash") ==
                        previous_record.get("observation_hash"))

    prev_prog = previous_record.get("progress", {}) or {}
    cur_prog = current_record.get("progress", {}) or {}
    # v1.3 #11: 新维度
    new_artifact = cur_prog.get("new_artifact", False)
    goal_progress = cur_prog.get("goal_progress", False)
    new_state_flag = cur_prog.get("new_state", False)
    same_artifact = (prev_prog.get("new_artifact", False) == new_artifact)
    same_goal_progress = (prev_prog.get("goal_progress", False) == goal_progress)
    # BE-4 (Evidence→Verification 来源链): 验证来源独立变化也算 progress。
    new_independent_verif = (current_record.get("verification", {}) or {}).get(
        "independent_source", False)
    prev_independent_verif = (previous_record.get("verification", {}) or {}).get(
        "independent_source", False)

    if not same_action:
        return {
            "decision": "CONTINUE",
            "reason": "不同 action",
            "consecutive_no_progress": 0,
        }

    # same action — 检查是否有进展 (任一维度变化即 progress)
    has_progress = (
        not same_result or not same_evidence or not same_state
        or not same_strategy or not same_input
        or not same_observation
        or new_artifact or not same_artifact
        or goal_progress or not same_goal_progress
        or new_state_flag
        or new_independent_verif != prev_independent_verif
    )

    if has_progress:
        return {
            "decision": "CONTINUE",
            "reason": "同 action 但有新 result/evidence/state/strategy/"
                      "input/artifact/goal_progress",
            "consecutive_no_progress": 0,
        }

    # same action + 全维度无进展 → no-progress
    prev_count = prev_prog.get("no_progress", 0)
    new_count = prev_count + 1

    # BE-6 (State-loop, L2): 状态振荡检测 — 同 action 下反复在同一状态对
    #   (previous_state→current_state) 之间横跳, 即使每次 action 不同也可判定 stall。
    prev_osc = prev_prog.get("state_oscillation", 0)
    cur_state_pair = (str(previous_record.get("current_state", "")) +
                      "->" + str(current_record.get("current_state", "")))
    prev_state_pair = (prev_prog.get("cycle_signature", ""))
    state_loop = (prev_state_pair == cur_state_pair)
    new_osc = (prev_osc + 1) if state_loop else 0

    # BE-5 (Goal Progress Vector, L3): 用 stall_count 记录无进展轮次, 供上层量化。
    stall_count = prev_prog.get("stall_count", 0) + 1

    if state_loop and new_osc >= 3:
        decision = "ESCALATE"
        reason = "State-loop: 在 %s 间振荡 %d 次无进展" % (cur_state_pair, new_osc)
        new_count = new_osc
    elif new_count >= 3:
        decision = "ESCALATE"
        reason = "连续 %d 次无进展" % new_count
    elif new_count >= 2:
        decision = "NOOP"
        reason = "连续 %d 次无进展" % new_count
    elif state_loop:
        decision = "WARN"
        reason = "State-loop 第 %d 次振荡" % new_osc
        new_count = new_osc
    else:
        decision = "WARN"
        reason = "第 %d 次无进展" % new_count

    return {
        "decision": decision,
        "reason": reason,
        "consecutive_no_progress": new_count,
        "state_oscillation": new_osc,
        "stall_count": stall_count,
        "cycle_signature": cur_state_pair,
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
    record.setdefault("input_hash", "")
    record.setdefault("strategy", "")
    record.setdefault("previous_state", "")
    record.setdefault("current_state", "")
    record.setdefault("goal_id", "")
    record.setdefault("task_id", "")
    record.setdefault("cycle_id", "")
    record.setdefault("parent_task_id", "")
    record.setdefault("attempt", 1)
    record.setdefault("retry_count", 0)
    # BE-3 (Action→Observation 对应): observation 记录动作的可观测结果。
    record.setdefault("observation", "")
    record.setdefault("observation_hash", "")
    # BE-4 (Evidence→Verification 来源链): verification 元数据(方法/来源/独立性)。
    record.setdefault("verification", {
        "method": "", "evidence_ref": "", "independent_source": False,
    })
    record.setdefault("progress", {
        "new_evidence": False,
        "new_artifact": False,
        "new_state": False,
        "goal_progress": False,
        "no_progress": 0,
        # BE-5 (Goal Progress Vector, L3): 更细的进展向量。
        "stall_count": 0,
        "cycle_signature": "",
        "last_progress_at": "",
        "progress_count": 0,
        # BE-6 (State-loop, L2): 状态振荡检测计数。
        "state_oscillation": 0,
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

    res = load_records(goal_id=goal_id, limit=50)
    if res.get("history_unavailable", False):
        result = check_action_loop(check, None, previous_available=False)
        print(json.dumps(result, ensure_ascii=False))
        return

    prev = None
    for r in reversed(res.get("records", [])):
        if r.get("action_signature") == action_signature:
            prev = r
            break

    result = check_action_loop(check, prev)
    if res.get("corruption", 0) > 0:
        result["corruption_warning"] = res.get("corruption")
    print(json.dumps(result, ensure_ascii=False))


def cmd_query(args):
    res = load_records(goal_id=args.goal, limit=int(args.limit or 50))
    out = {"records": res.get("records", []),
           "total": len(res.get("records", [])),
           "corruption": res.get("corruption", 0),
           "history_unavailable": res.get("history_unavailable", False)}
    print(json.dumps(out, ensure_ascii=False))


def cmd_stats(args):
    res = load_records(goal_id=args.goal, limit=200)
    records = res.get("records", [])
    if not records:
        print(json.dumps({
            "total": 0, "no_progress_runs": 0, "escalated": False,
            "history_unavailable": res.get("history_unavailable", False),
            "unverified": True,
        }, ensure_ascii=False))
        return

    no_progress = sum(1 for r in records
                      if r.get("progress", {}).get("no_progress", 0) > 0)
    escalated = any(r.get("decision") == "ESCALATE" for r in records)
    unknown = any(r.get("decision") == "UNKNOWN" for r in records)
    last_progress = max((r.get("progress", {}).get("no_progress", 0)
                         for r in records), default=0)

    print(json.dumps({
        "total": len(records),
        "no_progress_runs": no_progress,
        "last_no_progress": last_progress,
        "escalated": escalated,
        "unknown": unknown,
        "corruption": res.get("corruption", 0),
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
