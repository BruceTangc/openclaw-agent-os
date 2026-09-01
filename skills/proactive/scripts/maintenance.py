#!/usr/bin/env python3
"""Heartbeat maintenance cadence gate (not a scheduler).

OpenClaw owns wakeups. This module only determines which governed maintenance
checks are due and records verified outcomes to prevent duplicate work.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone


LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "_lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
from id_utils import generate_id
from persistence import FileLock, atomic_write_json
from workspace import agent_state_dir, current_agent_id, native_memory_dir
from dispatcher import dispatch


CADENCES = {
    "task_health": timedelta(minutes=30),
    "evolution_state": timedelta(hours=2),
    "memory_governance": timedelta(days=1),
    "ontology_health": timedelta(days=1),
    "vault_sync": timedelta(days=1),
    "weekly_review": timedelta(days=7),
}
RETRY_BASE = timedelta(minutes=30)
RETRY_MAX = timedelta(hours=6)


def now_utc():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def state_path(agent_id=None):
    return os.path.join(agent_state_dir("maintenance", agent_id), "state.json")


def load_state(path):
    if not os.path.isfile(path):
        return {"version": 1, "checks": {}}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("checks", {}), dict):
        raise ValueError("CORRUPTED maintenance state")
    data.setdefault("version", 1)
    data.setdefault("checks", {})
    return data


def retry_delay(count):
    return min(RETRY_BASE * (2 ** (max(1, int(count or 1)) - 1)), RETRY_MAX)


def plan(agent_id=None, at=None):
    at = at or now_utc()
    state = load_state(state_path(agent_id))
    due = []
    for name, cadence in CADENCES.items():
        row = state["checks"].get(name, {})
        last = parse_iso(row.get("last_completed_at"))
        attempted = parse_iso(row.get("last_attempted_at"))
        failures = int(row.get("failure_count", 0) or 0)
        retry_at = attempted + retry_delay(failures) if attempted and failures else None
        if (last is None or at >= last + cadence) and (retry_at is None or at >= retry_at):
            due.append({
                "name": name,
                "operation_id": "maintenance:{}:{}".format(current_agent_id(agent_id), name),
                "last_completed_at": row.get("last_completed_at"),
                "cadence_seconds": int(cadence.total_seconds()),
                "failure_count": failures,
            })
    return {"agent_id": current_agent_id(agent_id), "checked_at": iso(at),
            "due": due, "no_action": not bool(due)}


def record(name, result, agent_id=None, detail="", at=None, attention_fingerprint=""):
    if name not in CADENCES:
        raise ValueError("unknown maintenance check: " + name)
    if result not in ("PASS", "PARTIAL", "FAIL", "UNKNOWN", "SKIPPED"):
        raise ValueError("invalid result: " + result)
    at = at or now_utc()
    path = state_path(agent_id)
    with FileLock(path):
        state = load_state(path)
        row = state["checks"].setdefault(name, {})
        row.update({"last_result": result, "last_detail": detail,
                    "last_operation_id": generate_id("maint")})
        if attention_fingerprint:
            row["last_attention_fingerprint"] = attention_fingerprint
        if result in ("PASS", "SKIPPED"):
            row["last_completed_at"] = iso(at)
            row["failure_count"] = 0
        else:
            row["last_attempted_at"] = iso(at)
            row["failure_count"] = int(row.get("failure_count", 0)) + 1
        atomic_write_json(path, state)
    return row


def run_vault(agent_id=None, at=None):
    """Run due Vault projection maintenance; never performs reverse import."""
    vault = os.environ.get("AGENT_OS_VAULT_DIR", "").strip()
    if not vault:
        record("vault_sync", "SKIPPED", agent_id, "vault_not_configured", at)
        return {"name": "vault_sync", "result": "SKIPPED",
                "reason": "vault_not_configured", "actionable": False}
    due = {row["name"] for row in plan(agent_id, at).get("due", [])}
    if "vault_sync" not in due:
        return {"name": "vault_sync", "result": "SKIPPED", "reason": "not_due"}
    skills_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(skills_root, "agent-os-vault", "scripts", "agent_os_vault.py")
    common = ["--vault", vault]
    if agent_id:
        common += ["--agent", current_agent_id(agent_id)]
    commands = [
        [sys.executable, script, "export", "--sources", "all"] + common,
        [sys.executable, script, "reconcile"] + common,
    ]
    evidence = []
    result = "PASS"
    for command in commands:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace")
        evidence.append({"command": os.path.basename(script) + " " + command[2],
                         "returncode": completed.returncode,
                         "output": (completed.stdout + completed.stderr)[-1000:]})
        if completed.returncode:
            result = "FAIL"
            break
    record("vault_sync", result, agent_id, "export+reconcile", at)
    return {"name": "vault_sync", "result": result, "vault": os.path.realpath(vault),
            "persisted_truth_changes": False, "evidence": evidence,
            "actionable": result != "PASS"}


def _command(relative, *args):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(root, *relative.split("/"))
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    done = subprocess.run([sys.executable, script] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", errors="replace", env=env)
    return {"returncode": done.returncode,
            "output": (done.stdout + done.stderr).strip()[-4000:]}


def _json(evidence):
    try:
        return json.loads(evidence.get("output") or "{}")
    except (TypeError, ValueError):
        return {}


def _memory_audit(at=None):
    at = at or now_utc()
    root = native_memory_dir()
    files = []
    hashes = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not (os.path.isfile(path) and name.endswith(".md")):
                continue
            with open(path, "rb") as handle:
                content = handle.read()
            digest = hashlib.sha256(content).hexdigest()
            row = {"name": name, "bytes": len(content), "sha256": digest}
            files.append(row)
            hashes.setdefault(digest, []).append(name)
    duplicates = [names for names in hashes.values() if len(names) > 1]
    empty = [row["name"] for row in files if row["bytes"] == 0]
    stale_daily = []
    for row in files:
        try:
            day = datetime.strptime(row["name"][:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if at - day >= timedelta(days=90):
            stale_daily.append(row["name"])
    candidates = {"exact_duplicates": duplicates, "empty_files": empty,
                  "daily_older_than_90d": stale_daily}
    return {"memory_file_count": len(files), "candidates": candidates,
            "read_only": True, "auto_modified": False,
            "requires_semantic_review": any(bool(v) for v in candidates.values())}


def _task_findings(data):
    return isinstance(data, dict) and any(bool(data.get(key)) for key in
        ("overdue", "stale", "waiting", "blocked", "goal_drift", "high_value_unfinished"))


def _run_standard(name, at=None):
    if name == "task_health":
        evidence = _command("task-manager/scripts/task_manager.py", "scan")
        data = _json(evidence)
        return evidence, _task_findings(data)
    if name == "evolution_state":
        evidence = _command("self-evolution/scripts/pipeline.py", "scan")
        data = _json(evidence)
        return evidence, bool(data.get("ready_for_review") or data.get("needs_manual_review"))
    if name == "memory_governance":
        audit = _memory_audit(at)
        return {"returncode": 0, "audit": audit}, audit["requires_semantic_review"]
    if name == "ontology_health":
        checks = [_command("ontology/scripts/ontology.py", flag)
                  for flag in ("--validate", "--duplicates", "--contradictions")]
        failed = any(x["returncode"] for x in checks)
        findings = any("merge_candidate" in x["output"] or "(scope:" in x["output"]
                       for x in checks)
        return {"returncode": int(failed), "checks": checks}, failed or findings
    if name == "weekly_review":
        task = _command("task-manager/scripts/task_manager.py", "scan")
        evolution = _command("self-evolution/scripts/discover.py", "--status")
        task_data = _json(task)
        evolution_data = _json(evolution)
        memory = _memory_audit(at)
        failed = bool(task["returncode"] or evolution["returncode"])
        actionable = (failed or _task_findings(task_data)
                      or bool(evolution_data.get("pending_candidates"))
                      or memory["requires_semantic_review"])
        return {"returncode": int(failed), "task": task,
                "evolution": evolution, "memory": memory,
                "summary": {"task_findings": _task_findings(task_data),
                            "pending_evolution": len(evolution_data.get("pending_candidates", [])),
                            "memory_review": memory["requires_semantic_review"]}}, actionable
    raise ValueError("no handler: " + name)


def run_check(name, agent_id=None, at=None):
    if name == "vault_sync":
        return dispatch(name, lambda: run_vault(agent_id, at))
    gate_result = dispatch(name, lambda: {"result": "AUTHORIZED"})
    if gate_result.get("result") == "FAIL":
        return gate_result
    try:
        evidence, actionable = _run_standard(name, at)
        result = "PASS" if evidence.get("returncode", 1) == 0 else "FAIL"
        detail = json.dumps(evidence, ensure_ascii=False)[-4000:]
    except Exception as exc:
        evidence, actionable, result, detail = {"error": str(exc)}, True, "FAIL", str(exc)
    fingerprint = ""
    suppressed = False
    if actionable:
        canonical = json.dumps(evidence, ensure_ascii=True, sort_keys=True,
                               separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        previous = load_state(state_path(agent_id))["checks"].get(name, {})
        suppressed = previous.get("last_attention_fingerprint") == fingerprint
        if suppressed and result == "PASS":
            actionable = False
    record(name, result, agent_id, detail, at, fingerprint)
    return {"name": name, "result": result, "actionable": bool(actionable),
            "suppressed_unchanged": suppressed, "evidence": evidence,
            "permission": gate_result["permission"]}


def run_due(agent_id=None, at=None):
    """Code-driven cadence gate. OpenClaw Heartbeat remains the scheduler."""
    agent = current_agent_id(agent_id)
    target = os.path.join(agent_state_dir("maintenance", agent), "heartbeat-run")
    try:
        with FileLock(target, timeout=0.2):
            results = [run_check(row["name"], agent, at)
                       for row in plan(agent, at)["due"]]
    except TimeoutError:
        return {"agent_id": agent, "status": "BUSY", "results": [],
                "actionable": False, "heartbeat_ok": True}
    actionable = any(x.get("actionable") or x.get("result") == "FAIL" for x in results)
    return {"agent_id": agent, "status": "ATTENTION" if actionable else "OK",
            "results": results, "actionable": actionable,
            "heartbeat_ok": not actionable}


def main():
    parser = argparse.ArgumentParser(description="Agent OS heartbeat maintenance gate")
    parser.add_argument("--agent", default="")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    sub.add_parser("run")
    sub.add_parser("run-vault")
    rec = sub.add_parser("record")
    rec.add_argument("--name", required=True, choices=sorted(CADENCES))
    rec.add_argument("--result", required=True,
                     choices=["PASS", "PARTIAL", "FAIL", "UNKNOWN", "SKIPPED"])
    rec.add_argument("--detail", default="")
    args = parser.parse_args()
    if args.cmd == "plan":
        out = plan(args.agent)
    elif args.cmd == "run":
        out = run_due(args.agent)
    elif args.cmd == "run-vault":
        out = run_vault(args.agent)
    else:
        out = record(args.name, args.result, args.agent, args.detail)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
