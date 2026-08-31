#!/usr/bin/env python3
"""Heartbeat maintenance cadence gate (not a scheduler).

OpenClaw owns wakeups. This module only determines which governed maintenance
checks are due and records verified outcomes to prevent duplicate work.
"""

import argparse
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
from workspace import agent_state_dir, current_agent_id


CADENCES = {
    "task_health": timedelta(minutes=30),
    "evolution_state": timedelta(hours=2),
    "memory_governance": timedelta(days=1),
    "ontology_health": timedelta(days=1),
    "vault_sync": timedelta(days=1),
    "weekly_review": timedelta(days=7),
}


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


def enabled(name):
    if name == "vault_sync":
        return bool(os.environ.get("AGENT_OS_VAULT_DIR"))
    return True


def plan(agent_id=None, at=None):
    at = at or now_utc()
    state = load_state(state_path(agent_id))
    due = []
    for name, cadence in CADENCES.items():
        if not enabled(name):
            continue
        row = state["checks"].get(name, {})
        last = parse_iso(row.get("last_completed_at"))
        if last is None or at >= last + cadence:
            due.append({
                "name": name,
                "operation_id": "maintenance:{}:{}".format(current_agent_id(agent_id), name),
                "last_completed_at": row.get("last_completed_at"),
                "cadence_seconds": int(cadence.total_seconds()),
            })
    return {"agent_id": current_agent_id(agent_id), "checked_at": iso(at),
            "due": due, "no_action": not bool(due)}


def record(name, result, agent_id=None, detail="", at=None):
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
        return {"name": "vault_sync", "result": "SKIPPED", "reason": "vault_not_configured"}
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
            "persisted_truth_changes": False, "evidence": evidence}


def main():
    parser = argparse.ArgumentParser(description="Agent OS heartbeat maintenance gate")
    parser.add_argument("--agent", default="")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    sub.add_parser("run-vault")
    rec = sub.add_parser("record")
    rec.add_argument("--name", required=True, choices=sorted(CADENCES))
    rec.add_argument("--result", required=True,
                     choices=["PASS", "PARTIAL", "FAIL", "UNKNOWN", "SKIPPED"])
    rec.add_argument("--detail", default="")
    args = parser.parse_args()
    if args.cmd == "plan":
        out = plan(args.agent)
    elif args.cmd == "run-vault":
        out = run_vault(args.agent)
    else:
        out = record(args.name, args.result, args.agent, args.detail)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
