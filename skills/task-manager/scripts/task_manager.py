#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task Manager 纯逻辑层 (V1.0)

OpenClaw Agent Task Operating System 的可运行核心。实现文档【Task Manager
v1.0】中被可以确定性落地的部分：

  --create   创建任务 (标准化 + 去重 + 优先级, §4 §11-15)
  --list     列出任务 (支持状态/优先级过滤, §64)
  --show     查看单个任务
  --update   更新字段 / 状态转换 (§9)
  --assign   分配 Owner/Assignee (§24-25)
  --scan     健康扫描: overdue / stale / waiting / blocked / goal_drift (§49-51)
  --queue    任务队列分布 (§46)
  --metrics  核心指标 (§59)
  --stats    状态机校验 + 结构统计

状态持久化在 memory/tasks.json (JSONL 兼容简单数组)。

与 Proactive / Orchestrator 边界:
  - Proactive 决定"是否值得做" → 通过 --create source=proactive 建任务
  - Orchestrator 决定"怎么做" → 通过 --list 拿 READY 任务, --update 改状态
  - 本 skill 只管"任务是什么、处于什么状态", 不执行具体业务。
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# v1.3 Hardening: 统一 ID + 原子持久化
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "_lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from id_utils import generate_id
from persistence import atomic_write_json
from persistence import FileLock
# v1.4 C1: Task 状态机也收敛到统一中央门（跳转校验 + 事实不变量 + audit）
from transitions import transition as _task_transition

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
VALID_STATUS = [
    "INBOX", "PLANNED", "READY", "RUNNING",
    "WAITING", "BLOCKED", "PAUSED", "RETRYING", "FAILED",
    "COMPLETED", "REVIEW", "ARCHIVED", "CANCELLED",
]

# 合法状态转换 (文档 §9)
VALID_TRANSITIONS = {
    "INBOX": {"PLANNED", "READY", "CANCELLED"},
    "PLANNED": {"READY", "INBOX", "CANCELLED"},
    "READY": {"RUNNING", "WAITING", "BLOCKED", "PAUSED", "CANCELLED", "RETRYING"},
    "RUNNING": {"COMPLETED", "WAITING", "BLOCKED", "PAUSED", "RETRYING", "FAILED", "CANCELLED"},
    "WAITING": {"READY", "BLOCKED", "CANCELLED"},
    "BLOCKED": {"READY", "CANCELLED"},
    "PAUSED": {"READY", "CANCELLED"},
    "RETRYING": {"READY", "RUNNING", "FAILED", "CANCELLED"},
    "FAILED": {"READY", "CANCELLED"},   # 重规划后回 READY
    "COMPLETED": {"REVIEW", "ARCHIVED"},
    "REVIEW": {"ARCHIVED", "READY", "CANCELLED"},
    "ARCHIVED": set(),
    "CANCELLED": set(),
}

PRIORITY_LEVELS = ["P0", "P1", "P2", "P3", "P4"]

# 默认 (文档 §35 §23)
DEFAULT_MAX_RETRIES = 2

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "memory", "tasks.json")


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------
def load_tasks():
    if not os.path.isfile(DATA_PATH):
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        # v1.3 #15: JSON 损坏不得当成空任务 → 标记进入 recovery/error
        raise RuntimeError("tasks.json 损坏, 拒绝当空列表处理: " + str(e))


def save_tasks(tasks):
    # v1.3 #6/#17: 原子写入 (lock + temp + fsync + os.replace)
    atomic_write_json(DATA_PATH, tasks)


def atomic_update_tasks(mutator):
    """P1-2/修复: read→modify→write 真正放进同一把 FileLock 事务。
    用法: atomic_update_tasks(lambda tasks: _create_into(tasks))，
    锁内读 → 改 → 写，杜绝并发 lost update。
    mutator 返回 (新数据, 结果)；异常则锁内回滚不写盘。"""
    with FileLock(DATA_PATH):
        tasks = load_tasks()
        new_tasks, result = mutator(tasks)
        save_tasks(new_tasks)
        return result


def new_task_id():
    # v1.3 #3: UUID 取代秒级时间戳, 防碰撞
    return generate_id("task")


# ---------------------------------------------------------------------------
# 标准化 (文档 §4 §11)
# ---------------------------------------------------------------------------
def normalize_task(data):
    now = utcnow_iso()
    t = {
        "id": data.get("id") or new_task_id(),
        "title": data.get("title", "untitled"),
        "description": data.get("description", ""),
        "source": {
            "type": data.get("source_type", data.get("source", {}).get("type", "user")),
            "id": data.get("source_id") or (data.get("source", {}).get("id") if isinstance(data.get("source"), dict) else None),
        },
        # BE-1 (I-013): 自主任务必须能追溯到恰一个 active Goal 或显式 standalone。
        #   goal_id 若提供则必须非空字符串; 空串/None 视作 standalone(人工一次性任务)。
        #   source=user 不强制 I-013 (人工任务豁免); 其余 source 保持宽松(由调方保证 goal 存在), 仅拒绝非法空引用。
        "goal_id": data.get("goal_id", ""),
        "project_id": data.get("project_id"),
        "parent_task_id": data.get("parent_task_id"),
        "type": data.get("type", ["action"]) if isinstance(data.get("type", ["action"]), list) else [data["type"]],
        "status": "INBOX",
        "priority": {"level": "P2", "score": _f(data.get("priority_score", 50))},
        "owner": data.get("owner", {"type": "user", "id": None}),
        "assignee": data.get("assignee", {"type": None, "id": None}),
        "dependencies": data.get("dependencies", []),
        "blocked_by": data.get("blocked_by", []),
        "due_at": data.get("due_at"),
        "success_conditions": data.get("success_conditions", []),
        "verification_level": data.get("verification_level", "V1"),
        "risk_level": data.get("risk_level", "low"),
        "inputs": data.get("inputs", []),
        "outputs": data.get("outputs", []),
        "context": data.get("context", {}),
        "tags": data.get("tags", []),
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "history": data.get("history", []),
        "retry_count": data.get("retry_count", 0),
        # BE-2 (I-014): 独立 Execution # 历史 (attempt 级), 与 status 覆盖解耦。
        #   executions 记录每次进入 RUNNING 的执行尝试; attempt# = len(executions)+1。
        "executions": data.get("executions", []),
        "recurrence": data.get("recurrence"),
    }
    # 优先级 hint → level
    hint = data.get("priority_hint") or data.get("priority", {}).get("level")
    if hint in PRIORITY_LEVELS:
        t["priority"]["level"] = hint
    # 状态 (AE-7/L-16): create 只允许初始态, 禁止绕过状态机直接落到终态/执行态。
    #   初始态限 INBOX/PLANNED (其余一律走状态机显式转换)。
    st = data.get("status")
    INITIAL_STATES = {"INBOX", "PLANNED"}
    if st is not None:
        if st not in VALID_STATUS:
            raise ValueError("非法状态 %s" % st)
        if st not in INITIAL_STATES:
            raise ValueError("task create 禁止直接以 %s 创建 (初始态仅限 %s)，"
                             "必须通过状态机转换到达" % (st, sorted(INITIAL_STATES)))
        # v1.4 C1: 初始态也走统一中央门 (默认 INBOX → INBOX/PLANNED)。
        #   门内做跳转校验 + audit；create 无派生事实字段需求。
        _task_transition(t, st, kind="task", actor="system",
                         reason="task create 初始态")
    # 记录初始历史
    t["history"].append({
        "timestamp": now, "actor": "system", "action": "created", "reason": "task_create",
    })
    return t


# ---------------------------------------------------------------------------
# 去重 (文档 §12-13)
# ---------------------------------------------------------------------------
def dedup_key(task):
    """生成去重 key: source_id / request_id / title 归一."""
    src_id = (task.get("source") or {}).get("id")
    if src_id:
        return "src:" + str(src_id)
    request_id = (task.get("context") or {}).get("request_id")
    if request_id:
        return "req:" + str(request_id)
    # title 归一 (小写去空格)
    title = re.sub(r"[\s]+", "", str(task.get("title", "")).lower())
    return "title:" + title


def find_duplicate(tasks, task):
    """返回相同活跃任务的索引, 找不到返回 None."""
    dk = dedup_key(task)
    active = {"INBOX", "PLANNED", "READY", "RUNNING", "WAITING", "BLOCKED", "PAUSED", "RETRYING", "REVIEW"}
    for i, t in enumerate(tasks):
        if t.get("status") in active and dedup_key(t) == dk:
            return i
    return None


def ordered_dedup(items):
    """#16: 保序去重 (list of hashable)。"""
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def merge_tasks(existing, new):
    """合并 (文档 §13): 保留最早创建, 最高优先级, 最严格 deadline, 合并来源."""
    merged = dict(existing)
    merged["title"] = existing.get("title") or new.get("title")
    merged["description"] = existing.get("description") or new.get("description")
    # 来源引用合并 (#16: 保序去重)
    srcs = []
    for s in [existing.get("source"), new.get("source")]:
        if s and s.get("id"):
            srcs.append(s["id"])
    srcs = ordered_dedup(srcs)
    if srcs:
        merged["source"] = {"type": "merged", "id": "|".join(srcs)}
    # 优先级: 取更高
    if new["priority"]["level"] < existing["priority"]["level"]:
        merged["priority"]["level"] = new["priority"]["level"]
    # deadline: 取更早
    if new.get("due_at") and (not existing.get("due_at") or new["due_at"] < existing["due_at"]):
        merged["due_at"] = new["due_at"]
    # 依赖合并 (#16: 保序去重)
    merged["dependencies"] = ordered_dedup(
        list(existing.get("dependencies", [])) + list(new.get("dependencies", [])))
    merged["context"] = {**existing.get("context", {}), **new.get("context", {})}
    merged["history"].append({
        "timestamp": utcnow_iso(), "actor": "system",
        "action": "merged", "reason": "duplicate_merge",
    })
    return merged


# ---------------------------------------------------------------------------
# 优先级计算 (文档 §15)
# ---------------------------------------------------------------------------
def compute_priority(task):
    """综合评分 → P0-P4."""
    score = (
        task.get("priority", {}).get("score", 50)
        - task.get("priority", {}).get("effort_penalty", 0)
        - task.get("priority", {}).get("risk_penalty", 0)
    )
    # 超期/停滞 → 提高 (老化加权 §47 §50)
    if task.get("_aging_bonus"):
        score += task["_aging_bonus"]
    score = max(0, min(100, score))
    if score >= 90: level = "P0"
    elif score >= 70: level = "P1"
    elif score >= 40: level = "P2"
    elif score >= 20: level = "P3"
    else: level = "P4"
    return {"level": level, "score": score}


# ---------------------------------------------------------------------------
# 健康扫描 (文档 §49-52)
# ---------------------------------------------------------------------------
def scan_health(tasks, now_iso=None):
    """返回 overdue / stale / waiting / blocked / goal_drift 信号."""
    now = datetime.fromisoformat((now_iso or utcnow_iso()).replace("Z", "+00:00"))
    nonterm = {"COMPLETED", "ARCHIVED", "CANCELLED"}
    result = {"overdue": [], "stale": [], "waiting": [], "blocked": [],
              "goal_drift": [], "high_value_unfinished": []}
    for t in tasks:
        if t.get("status") in nonterm:
            continue
        tid = t["id"]
        # stale 按最近更新时间判断：优先 updated_at，缺省回退 created_at（兼容旧任务）
        last_activity = t.get("updated_at") or t.get("created_at") or utcnow_iso()
        last_activity_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
        age_days = (now - last_activity_dt).total_seconds() / 86400.0
        # overdue
        due = t.get("due_at")
        if due:
            try:
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if due_dt < now:
                    result["overdue"].append({"id": tid, "due_at": due, "title": t.get("title")})
            except Exception:
                pass
        # stale (14 天未更新, 文档 §19)
        if age_days >= 14:
            result["stale"].append({"id": tid, "age_days": round(age_days, 1), "title": t.get("title")})
        # waiting / blocked
        if t.get("status") == "WAITING":
            result["waiting"].append({"id": tid, "title": t.get("title"),
                                      "followup_at": (t.get("context") or {}).get("followup_at")})
        if t.get("status") == "BLOCKED":
            result["blocked"].append({"id": tid, "blocked_by": t.get("blocked_by"), "title": t.get("title")})
        # goal drift: 关联 goal 且 stale
        if t.get("goal_id") and age_days >= 14:
            result["goal_drift"].append({"id": tid, "goal_id": t.get("goal_id"), "title": t.get("title")})
        # 高价值未完成 P0/P1
        if t.get("priority", {}).get("level") in ("P0", "P1"):
            result["high_value_unfinished"].append({"id": tid, "priority": t.get("priority", {}).get("level"),
                                                    "title": t.get("title")})
    return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Task Manager 纯逻辑层")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create", help="创建/合并任务")
    p_create.add_argument("--json", help="task JSON 或 -")
    p_create.add_argument("--merge", action="store_true", help="重复时合并")

    p_list = sub.add_parser("list", help="列出任务")
    p_list.add_argument("--status")
    p_list.add_argument("--priority")
    p_list.add_argument("--limit", type=int, default=50)

    p_show = sub.add_parser("show", help="查看任务")
    p_show.add_argument("--id", required=True)

    p_update = sub.add_parser("update", help="更新字段/状态转换")
    p_update.add_argument("--id", required=True)
    p_update.add_argument("--status", help="目标状态")
    p_update.add_argument("--title")
    p_update.add_argument("--json", help="附加字段 JSON")

    p_assign = sub.add_parser("assign", help="分配")
    p_assign.add_argument("--id", required=True)
    p_assign.add_argument("--role", choices=["owner", "assignee"], default="assignee")
    p_assign.add_argument("--type", default="agent")
    p_assign.add_argument("--to", required=True)

    p_scan = sub.add_parser("scan", help="健康扫描")

    p_queue = sub.add_parser("queue", help="队列分布")

    p_metrics = sub.add_parser("metrics", help="核心指标")

    p_stats = sub.add_parser("stats", help="状态统计/结构校验")

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "create":
        data = read_stdin_or_json(args.json, "task")
        t = normalize_task(data)

        def _create(tasks):
            dup = find_duplicate(tasks, t) if args.merge else None
            if dup is not None:
                merged = merge_tasks(tasks[dup], t)
                tasks[dup] = merged
                return tasks, {"action": "merged", "task": merged}
            t["priority"] = compute_priority(t)   # 重新计算, 拒绝盲从 hint (§65)
            tasks.append(t)
            return tasks, {"action": "created", "task": t}

        # P1-2: read→modify→save 在 atomic_update_tasks 同一把锁内完成
        res = atomic_update_tasks(_create)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.cmd == "list":
        tasks = load_tasks()
        if args.status: tasks = [t for t in tasks if t.get("status") == args.status.upper()]
        if args.priority: tasks = [t for t in tasks if t.get("priority", {}).get("level") == args.priority.upper()]
        tasks = tasks[:args.limit]
        out = [{"id": t["id"], "title": t["title"], "status": t["status"],
                "priority": t["priority"]["level"], "type": t["type"],
                "goal_id": t.get("goal_id"), "created_at": t.get("created_at")} for t in tasks]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "show":
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == args.id:
                print(json.dumps(t, ensure_ascii=False, indent=2))
                return
        print(json.dumps({"error": f"task {args.id} 不存在"}, ensure_ascii=False))
        return

    if args.cmd == "update":
        def _update(tasks):
            for t in tasks:
                if t["id"] == args.id:
                    old = t["status"]
                    if args.status:
                        ns = args.status.upper()
                        if ns not in VALID_STATUS:
                            raise ValueError("非法状态 %s" % ns)
                        # v1.4 C1: 状态变更改走统一中央门。
                        #   transition() 内部做: 非法跳转 raise + 事实不变量校验
                        #   (COMPLETED→completed_at / FAILED→failed_at / RUNNING→started_at)
                        #   + 写入 audit event (history)。
                        #   这里显式设置派生事实字段后交给门校验, 门拒绝则抛异常。
                        extra = {}
                        if ns == "COMPLETED":
                            extra["completed_at"] = utcnow_iso()
                        if ns == "FAILED":
                            extra["failed_at"] = utcnow_iso()
                        if ns == "RUNNING":
                            extra["started_at"] = utcnow_iso()
                        _task_transition(t, ns, kind="task", actor="system",
                                         reason="task update CLI", **extra)
                        # BE-2 (I-014): 进入 RUNNING 时创建独立 execution/attempt 记录。
                        #   每次 RUNNING(含 RETRYING→RUNNING) 记一次 attempt, 编号 attempt# =
                        #   len(executions)+1, 与 status 字段解耦(不再被状态覆盖吞掉执行历史)。
                        if ns == "RUNNING":
                            execs = t.setdefault("executions", [])
                            execs.append({
                                "attempt": len(execs) + 1,
                                "started_at": utcnow_iso(),
                                "from_status": old,
                                "ended_at": None,
                                "outcome": None,
                            })
                        # BE-2 (I-014): 离开 RUNNING 时关闭当前 open attempt (record outcome)。
                        #   RUNNING→终态/等待/失败, 把最近一条 started_at 且未 ended 的 attempt 收口。
                        if old == "RUNNING" and ns != "RUNNING":
                            execs = t.setdefault("executions", [])
                            for ex in reversed(execs):
                                if ex.get("ended_at") is None:
                                    ex["ended_at"] = utcnow_iso()
                                    out_map = {"COMPLETED": "SUCCESS", "FAILED": "FAILURE"}
                                    ex["outcome"] = out_map.get(ns, "INTERRUPTED")
                                    break
                    if args.title:
                        t["title"] = args.title
                    extra = read_stdin_or_json(args.json, "extra") if args.json else {}
                    for k, v in extra.items():
                        if k in ("context", "blocked_by", "dependencies", "outputs", "success_conditions"):
                            t[k] = v
                    if extra.get("priority_score"):
                        t["priority"]["score"] = _f(extra["priority_score"])
                        t["priority"] = compute_priority(t)
                    t["updated_at"] = utcnow_iso()
                    return tasks, {"updated": t["id"], "task": t}
            return tasks, None

        # P1-2: 同一锁内 read→modify→save
        try:
            res = atomic_update_tasks(_update)
        except ValueError as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            sys.exit(1)
        if res is None:
            print(json.dumps({"error": "task %s 不存在" % args.id}, ensure_ascii=False))
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.cmd == "assign":
        def _assign(tasks):
            for t in tasks:
                if t["id"] == args.id:
                    t[args.role] = {"type": args.type, "id": args.to}
                    t["updated_at"] = utcnow_iso()
                    t["history"].append({"timestamp": utcnow_iso(), "actor": "system",
                                         "action": "assigned", "detail": "%s=%s" % (args.role, args.to)})
                    return tasks, {"assigned": t["id"], args.role: t[args.role]}
            return tasks, None

        # P1-2: 同一锁内 read→modify→save
        res = atomic_update_tasks(_assign)
        if res is None:
            print(json.dumps({"error": "task %s 不存在" % args.id}, ensure_ascii=False))
        else:
            print(json.dumps(res, ensure_ascii=False))
        return

    if args.cmd == "scan":
        print(json.dumps(scan_health(load_tasks()), ensure_ascii=False, indent=2))
        return

    if args.cmd == "queue":
        tasks = load_tasks()
        dist = {}
        for t in tasks:
            s = t.get("status", "INBOX")
            dist[s] = dist.get(s, 0) + 1
        print(json.dumps({"total": len(tasks), "by_status": dist}, ensure_ascii=False, indent=2))
        return

    if args.cmd == "metrics":
        tasks = load_tasks()
        total = len(tasks)
        comp = sum(1 for t in tasks if t.get("status") == "COMPLETED")
        fail = sum(1 for t in tasks if t.get("status") == "FAILED")
        health = scan_health(tasks)
        print(json.dumps({
            "total": total,
            "completed": comp,
            "failed": fail,
            "completion_rate": round(comp / total, 2) if total else 0,
            "overdue": len(health["overdue"]),
            "stale": len(health["stale"]),
            "waiting": len(health["waiting"]),
            "blocked": len(health["blocked"]),
        }, ensure_ascii=False, indent=2))
        return

    if args.cmd == "stats":
        tasks = load_tasks()
        bad = []
        for t in tasks:
            s = t.get("status")
            if s not in VALID_STATUS:
                bad.append({"id": t["id"], "reason": f"非法状态 {s}"})
        print(json.dumps({"total": len(tasks), "invalid": bad,
                          "valid_statuses": VALID_STATUS}, ensure_ascii=False, indent=2))
        return


def read_stdin_or_json(raw, label):
    if raw == "-":
        return json.load(sys.stdin)
    if raw is None:
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        return {"__error": f"{label}不是合法JSON: {e}", "_raw": raw}


if __name__ == "__main__":
    main()
