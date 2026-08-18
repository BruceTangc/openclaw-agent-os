#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task Manager 联动层 (V1.1)

实现 Task Manager 与 Proactive / Orchestrator / Ontology / Memory /
Self-Evolution(Learning Bus) 的双向联动, 对应 SKILL.md §1 §56-58 §63-67。

联动方向:
  proactive-to-task      : Proactive Signal → 创建任务 (source=proactive)
  scan-to-proactive      : Task scan 信号 (overdue/stale/blocked/goal_drift) → 反馈 Proactive
  tasks-to-orchestrator  : READY 任务 → orchestration_request (parse/plan)
  result-to-task         : Orchestrator 执行结果 → verify → 任务状态更新
  sync-ontology          : 双向同步任务实体/关系到 Ontology
  sync-memory            : 每日任务摘要写入 memory/YYYY-MM-DD.md
  sync-evolution         : 失败/异常模式 → Self-Evolution 发布进化候选
  all                    : 一键联动 (scan→proactive + sync-ontology + sync-evolution)

用法示例:
  link.py proactive-to-task --signal '{"subject":"项目A停滞","summary":"21天未推进","type":"goal_drift","confidence":0.8}'
  link.py scan-to-proactive --min-level P1
  link.py tasks-to-orchestrator --ready
  link.py result-to-task --json '{"task_id":"task_x","status":"success","summary":"完成","evidence":["out"]}'
  link.py sync-ontology
  link.py sync-memory
  link.py sync-evolution
  link.py all
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.dirname(BASE)

TASK_MGR = os.path.join(BASE, "scripts", "task_manager.py")
PROACTIVE = os.path.join(SKILLS_DIR, "proactive", "scripts", "proactive.py")
ORCH = os.path.join(SKILLS_DIR, "orchestrator", "scripts", "orchestrator.py")
ONTOLOGY = os.path.join(SKILLS_DIR, "ontology", "scripts", "ontology.py")
DISCOVER = os.path.join(SKILLS_DIR, "self-evolution", "scripts", "discover.py")
MEMORY_DIR = os.path.join(os.path.dirname(SKILLS_DIR), "memory")


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd_args, stdin_data=None, timeout=60):
    """运行子命令, 返回 (rc, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable] + cmd_args,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def read_json_stdin_or_file(raw, label):
    """- 表示读 stdin, @file 表示读文件, 否则当 JSON 解析."""
    if raw is None:
        return {}
    if raw == "-":
        return json.load(sys.stdin)
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": label + " 不是合法JSON: " + str(e)}, ensure_ascii=False))
        sys.exit(2)


def tm(args, stdin_data=None):
    return sh([TASK_MGR] + args, stdin_data)


# ---------------------------------------------------------------------------
# 1. Proactive → Task
# ---------------------------------------------------------------------------
def cmd_proactive_to_task(args):
    sig = read_json_stdin_or_file(args.signal, "signal")

    if not sig.get("subject"):
        print(json.dumps({"error": "signal.subject 缺失"}, ensure_ascii=False))
        sys.exit(2)

    import hashlib
    # v1.3: Signal fingerprint (stable, 不用 timestamp)
    fp_raw = "|".join([
        str(sig.get("type", "")),
        str(sig.get("subject", "")),
        str(sig.get("source", "")),
    ])
    fingerprint = hashlib.sha256(fp_raw.encode()).hexdigest()[:16]

    task = {
        "title": sig.get("subject"),
        "description": sig.get("summary", ""),
        "source": {"type": "proactive", "id": sig.get("id") or sig.get("subject")},
        "type": ["proactive"],
        "priority_hint": sig.get("priority_hint"),
        "priority_score": int((sig.get("confidence", 0.5) or 0.5) * 100),
        "context": {
            "signal_id": sig.get("id"),
            "signal_fingerprint": fingerprint,
            "signal_type": sig.get("type", "change"),
            "goal_id": sig.get("goal_id", ""),
            "confidence": sig.get("confidence", 0),
            "urgency": sig.get("urgency", 0),
            "expected_value": sig.get("expected_value", 0),
            "proactive_source": True,
        },
        "tags": ["proactive"],
        "verification_level": "V1",
    }
    rc, out, err = tm(["create", "--json", json.dumps(task, ensure_ascii=False), "--merge"])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    res = json.loads(out)
    print(json.dumps({
        "linked": True,
        "action": res.get("action"),
        "task_id": res.get("task", {}).get("id"),
        "signal_id": sig.get("id"),
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 2. Task → Proactive (scan 信号反馈)
# ---------------------------------------------------------------------------
def cmd_scan_to_proactive(args):
    rc, out, err = tm(["scan"])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    scan = json.loads(out)

    min_score = {"P0": 90, "P1": 70}.get(args.min_level, 0)
    signals = []

    for item in scan.get("overdue", []):
        signals.append({
            "type": "deadline",
            "subject": "任务超期: " + item["title"],
            "summary": "任务 %s 已超过截止时间 %s" % (item["id"], item.get("due_at")),
            "priority_hint": "P1",
        })
    for item in scan.get("stale", []):
        signals.append({
            "type": "goal_drift",
            "subject": "任务停滞: " + item["title"],
            "summary": "任务 %s 已 %s 天未更新" % (item["id"], item.get("age_days")),
            "priority_hint": "P2",
        })
    for item in scan.get("blocked", []):
        signals.append({
            "type": "risk",
            "subject": "任务阻塞: " + item["title"],
            "summary": "任务 %s 被阻塞: %s" % (item["id"], item.get("blocked_by")),
            "priority_hint": "P2",
        })
    for item in scan.get("goal_drift", []):
        signals.append({
            "type": "goal_drift",
            "subject": "目标漂移: " + item["title"],
            "summary": "关联目标 %s 的任务长期未推进" % item.get("goal_id"),
            "priority_hint": "P1",
        })

    if not signals:
        print(json.dumps({"sent": 0, "signals": []}, ensure_ascii=False))
        return

    sent = 0
    for s in signals:
        rc2, out2, err2 = sh(
            [PROACTIVE, "signal", "--json", json.dumps(s, ensure_ascii=False)])
        if rc2 == 0:
            sent += 1
    print(json.dumps({
        "sent": sent,
        "total": len(signals),
        "signals": [s["subject"] for s in signals],
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 3. Task → Orchestrator (READY 任务转请求)
# ---------------------------------------------------------------------------
def cmd_tasks_to_orchestrator(args):
    rc, out, err = tm(["list", "--status", "READY", "--limit", str(args.limit)])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    tasks = json.loads(out) if out else []

    if not tasks:
        print(json.dumps({"requests": [], "total": 0}, ensure_ascii=False))
        return

    requests = []
    for t in tasks:
        req = {
            "objective": t["title"],
            "source": "task-manager",
            "context": {"task_id": t["id"], "goal_id": t.get("goal_id")},
            "constraints": [],
            "priority": {"P0": 1.0, "P1": 0.8, "P2": 0.6, "P3": 0.4, "P4": 0.2}.get(t.get("priority"), 0.5),
            "risk_level": "low",
        }
        # 解析为 orchestration_request
        rc2, out2, err2 = sh([ORCH, "parse", "--json", json.dumps(req, ensure_ascii=False)])
        parsed = json.loads(out2) if rc2 == 0 and out2 else req
        requests.append({
            "task_id": t["id"],
            "title": t["title"],
            "priority": t.get("priority"),
            "request": parsed,
        })

    print(json.dumps({"requests": requests, "total": len(requests)}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 4. Orchestrator → Task (执行结果回写)
# ---------------------------------------------------------------------------
def cmd_result_to_task(args):
    res = read_json_stdin_or_file(args.json, "result")

    task_id = res.get("task_id") or (res.get("execution_result") or {}).get("task_id")
    if not task_id:
        print(json.dumps({"error": "缺 task_id"}, ensure_ascii=False))
        sys.exit(2)

    status = (res.get("status") or (res.get("execution_result") or {}).get("status") or "success").lower()

    # 先做 verify (如果有 result detail)
    veri = None
    detail = res.get("execution_result") or res.get("result") or (res if "outputs" in res or "summary" in res else None)
    if detail and args.verify:
        rc, out, err = sh([ORCH, "verify", "--json", json.dumps(detail, ensure_ascii=False),
                           "--level", args.verify_level])
        veri = json.loads(out) if rc == 0 and out else {"error": err or "verify failed"}

    # 状态映射
    target = {"success": "COMPLETED", "partial": "REVIEW", "failure": "FAILED"}.get(status)
    if not target:
        print(json.dumps({"error": "非法执行状态: " + status}, ensure_ascii=False))
        sys.exit(2)

    extra = {
        "outputs": detail.get("outputs", []) if isinstance(detail, dict) else [],
        "context": {
            "execution_result": (detail.get("summary") if isinstance(detail, dict) else None) or res.get("summary"),
            "verified": veri,
        },
    }

    # 状态机自动中转: READY/PLANNED/INBOX/REVIEW → RUNNING → 目标 (§9)
    rc0, out0, err0 = tm(["show", "--id", task_id])
    cur = None
    if rc0 == 0 and out0:
        try:
            cur = json.loads(out0).get("status")
        except Exception:
            cur = None
    if cur and cur not in ("RUNNING", target):
        allowed_from = {"INBOX", "PLANNED", "READY", "REVIEW", "RETRYING", "WAITING", "PAUSED", "BLOCKED", "FAILED"}
        if cur in allowed_from:
            rc_run, out_run, err_run = tm(["update", "--id", task_id, "--status", "RUNNING"])
            if rc_run != 0:
                print(json.dumps({"error": "无法置为 RUNNING: " + (err_run or out_run)}, ensure_ascii=False))
                sys.exit(rc_run or 1)

    rc, out, err = tm(["update", "--id", task_id, "--status", target,
                       "--json", json.dumps(extra, ensure_ascii=False)])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)

    # Anti-loop 落地 (OPERATIONS.md): 失败时递增 retry_count (§35)
    retry_info = None
    if target == "FAILED":
        rc_r, out_r, err_r = tm(["show", "--id", task_id])
        if rc_r == 0 and out_r:
            try:
                task_data = json.loads(out_r)
                new_rc = int(task_data.get("retry_count", 0)) + 1
                # 更新 retry_count
                tm(["update", "--id", task_id,
                    "--json", json.dumps({"context": {"retry_count": new_rc}}, ensure_ascii=False)])
                retry_info = {"task_id": task_id, "retry_count": new_rc}
                # v1.3: retry_count >= 3 → 仅首次 escalation（防止重复 escalation signal）
                escalated_key = "escalated_at"
                if new_rc >= 3 and not task_data.get("context", {}).get(escalated_key):
                    tm(["update", "--id", task_id,
                        "--json", json.dumps({"context": {escalated_key: utcnow_iso()}},
                                             ensure_ascii=False)])
                    esc = {
                        "type": "risk",
                        "subject": "任务连续失败需升级: " + task_data.get("title", task_id),
                        "summary": "任务 %s 已连续失败 %d 次, 建议人工介入" % (task_id, new_rc),
                        "confidence": 0.9,
                        "priority_hint": "P1",
                    }
                    sh([PROACTIVE, "signal", "--json", json.dumps(esc, ensure_ascii=False)])
                    retry_info["escalated"] = True
            except Exception as e:
                retry_info = {"task_id": task_id, "error": str(e)}

    print(json.dumps({
        "updated": task_id,
        "status": target,
        "task": json.loads(out).get("task"),
        "verification": veri,
        "retry": retry_info,
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 5. Task ↔ Ontology
# ---------------------------------------------------------------------------
def cmd_sync_ontology(args):
    rc, out, err = tm(["list", "--limit", str(args.limit)])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    tasks = json.loads(out) if out else []

    # 幂等: 已存在的 Task 实体跳过创建（L4 修复: 直接读 entities.jsonl, 不解析 print 输出）
    existing = set()
    ent_file = os.path.join(SKILLS_DIR, "ontology", "memory", "ontology", "entities.jsonl")
    try:
        with open(ent_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    eid = (d.get("entity") or {}).get("id") or d.get("id")
                    if eid:
                        existing.add(eid)
                except Exception:
                    continue
    except FileNotFoundError:
        pass

    created = 0
    related = 0
    for t in tasks:
        tid = t["id"]
        if tid in existing:
            continue
        props = {
            "title": t["title"],
            "task_status": t["status"],
            "priority": t.get("priority"),
            "source_type": "task-manager",
        }
        rc2, out2, err2 = sh([ONTOLOGY, "--create-entity", "--type", "Task",
                              "--name", t["title"][:40], "--id", tid,
                              "--props", json.dumps(props, ensure_ascii=False)])
        if rc2 == 0:
            created += 1
            # 关联 goal/project (实体存在才关联, 失败不阻塞)
            if t.get("goal_id"):
                sh([ONTOLOGY, "--relate", "--from", tid, "--pred", "HAS_TASK",
                    "--to", t["goal_id"]])
            if t.get("project_id"):
                sh([ONTOLOGY, "--relate", "--from", tid, "--pred", "PART_OF",
                    "--to", t["project_id"]])
            related += 1

    print(json.dumps({
        "task_total": len(tasks),
        "created_entities": created,
        "relations_added": related,
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 6. Task → Memory (每日摘要)
# ---------------------------------------------------------------------------
def cmd_sync_memory(args):
    rc, out, err = tm(["metrics"])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    metrics = json.loads(out)

    rc2, out2, err2 = tm(["queue"])
    queue = json.loads(out2) if rc2 == 0 and out2 else {}

    today = datetime.now().strftime("%Y-%m-%d")
    mem_file = os.path.join(MEMORY_DIR, today + ".md")
    os.makedirs(MEMORY_DIR, exist_ok=True)

    section = (
        "\n## 📋 任务快照（Task Manager 自动写入）\n\n"
        "- 总任务: {total} | 完成: {completed} | 失败: {failed} | 完成率: {rate}\n"
        "- 超期: {overdue} | 停滞: {stale} | 等待: {waiting} | 阻塞: {blocked}\n"
        "- 队列分布: {dist}\n"
    ).format(
        total=metrics.get("total", 0),
        completed=metrics.get("completed", 0),
        failed=metrics.get("failed", 0),
        rate=metrics.get("completion_rate", 0),
        overdue=metrics.get("overdue", 0),
        stale=metrics.get("stale", 0),
        waiting=metrics.get("waiting", 0),
        blocked=metrics.get("blocked", 0),
        dist=json.dumps(queue.get("by_status", {}), ensure_ascii=False),
    )

    with open(mem_file, "a", encoding="utf-8") as f:
        f.write(section)

    print(json.dumps({"wrote": mem_file, "section": section.strip()}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 7. Task → Self-Evolution (Learning Bus)
# ---------------------------------------------------------------------------
def publish_candidate(scope, pattern_key, problem, confidence, evidence_keyword):
    """task-manager：作为 Discover+Classify 角色，把 learning_candidate 事件
    规范化为 Candidate 记录，交给 Self-Evolution v2 的 discover.py --candidate。

    仅在重复/系统性明显时才上报；discover 侧仍有幂等去重 + 状态机把关。
    target 用 topic 作归并能粒度；若明确指向文件可在调用处传路径。"""
    candidate = {
        "scope": scope or "TASK",
        "target": pattern_key,
        "pattern_key": pattern_key,
        "problem": problem,
        "confidence": float(confidence or 0),
        "evidence_refs": ["task-manager:" + evidence_keyword],
        "recurrence": 1,
        "sessions": 1,
        "independent_sources": 1,
        "systemic": True,
        "impact": "medium",
    }
    rc2, out2, err2 = sh([DISCOVER, "--candidate",
                          json.dumps(candidate, ensure_ascii=False)])
    return rc2, out2, err2


def cmd_sync_evolution(args):
    rc, out, err = tm(["metrics"])
    if rc != 0:
        print(json.dumps({"error": err or out}, ensure_ascii=False))
        sys.exit(rc)
    metrics = json.loads(out)

    published = []
    failed = int(metrics.get("failed", 0))
    total = int(metrics.get("total", 0))

    # 失败任务存在 → 上报进化候选
    if failed > 0 and total > 0:
        rate = failed / total
        if rate >= 0.3:
            topic = "task-manager:失败率过高"
            content = "任务失败率 %.0f%% (%d/%d), 建议复盘失败原因" % (rate * 100, failed, total)
            rc2, out2, err2 = publish_candidate(
                "TASK", topic, content, min(95, int(rate * 100)), "failed_rate")
            if rc2 == 0:
                published.append(topic)

    # 超期/阻塞多 → 上报
    if int(metrics.get("blocked", 0)) >= 3:
        topic = "task-manager:阻塞堆积"
        content = "当前有 %d 个阻塞任务, 建议排查依赖/权限" % int(metrics.get("blocked", 0))
        rc2, out2, err2 = publish_candidate(
            "TASK", topic, content, 70, "blocked")
        if rc2 == 0:
            published.append(topic)

    print(json.dumps({
        "published": published,
        "count": len(published),
    }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 8. all 一键联动
# ---------------------------------------------------------------------------
def cmd_all(args):
    result = {}
    rc, out, err = tm(["scan"])
    result["scan"] = json.loads(out) if rc == 0 and out else {"error": err or out}
    link_script = os.path.abspath(__file__)
    rc1, out1, err1 = sh([link_script, "scan-to-proactive", "--min-level", args.min_level])
    result["proactive_feedback"] = json.loads(out1) if rc1 == 0 and out1 else {"error": err1 or out1}
    rc2, out2, err2 = sh([link_script, "sync-ontology"])
    result["ontology"] = json.loads(out2) if rc2 == 0 and out2 else {"error": err2 or out2}
    rc3, out3, err3 = sh([link_script, "sync-evolution"])
    result["evolution"] = json.loads(out3) if rc3 == 0 and out3 else {"error": err3 or out3}
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Task Manager 联动层 (V1.1)")
    sub = parser.add_subparsers(dest="cmd")

    p1 = sub.add_parser("proactive-to-task", help="Proactive Signal → 任务")
    p1.add_argument("--signal", required=True, help="Signal JSON 或 - 或 @file")

    p2 = sub.add_parser("scan-to-proactive", help="任务 scan 信号 → Proactive")
    p2.add_argument("--min-level", choices=["P0", "P1", "P2"], default="P1")

    p3 = sub.add_parser("tasks-to-orchestrator", help="READY 任务 → Orchestrator 请求")
    p3.add_argument("--limit", type=int, default=10)

    p4 = sub.add_parser("result-to-task", help="Orchestrator 结果 → 任务状态")
    p4.add_argument("--json", required=True, help="result JSON 或 - 或 @file")
    p4.add_argument("--verify", action="store_true", help="先过 orchestrator verify")
    p4.add_argument("--verify-level", default="V2")

    p5 = sub.add_parser("sync-ontology", help="任务实体/关系同步到 Ontology")
    p5.add_argument("--limit", type=int, default=200)

    p6 = sub.add_parser("sync-memory", help="任务摘要写入今日 memory")

    p7 = sub.add_parser("sync-evolution", help="失败/阻塞模式 → Learning Bus")

    p8 = sub.add_parser("all", help="一键联动")
    p8.add_argument("--min-level", choices=["P0", "P1", "P2"], default="P1")

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    handlers = {
        "proactive-to-task": cmd_proactive_to_task,
        "scan-to-proactive": cmd_scan_to_proactive,
        "tasks-to-orchestrator": cmd_tasks_to_orchestrator,
        "result-to-task": cmd_result_to_task,
        "sync-ontology": cmd_sync_ontology,
        "sync-memory": cmd_sync_memory,
        "sync-evolution": cmd_sync_evolution,
        "all": cmd_all,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()