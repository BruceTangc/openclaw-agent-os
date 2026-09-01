#!/usr/bin/env python3
"""Unified read-only Agent OS status/doctor command."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))
LIB = os.path.join(SKILLS, "_lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
from workspace import agent_state_dir, current_agent_id, workspace_root
import maintenance

CORE = (
    "context-orchestration", "knowledge-governance", "memory-governance",
    "ontology", "orchestrator", "permission-security", "proactive",
    "self-evolution", "summarize", "task-manager", "verification-evaluation",
)


def _check(name, status, detail, evidence=None):
    row = {"name": name, "status": status, "detail": detail}
    if evidence is not None:
        row["evidence"] = evidence
    return row


def inspect(agent_id=None):
    agent = current_agent_id(agent_id)
    profile = os.environ.get("AGENT_OS_PROFILE", "active").strip().lower() or "active"
    root = workspace_root()
    checks = []
    missing = [name for name in CORE if not os.path.isfile(os.path.join(SKILLS, name, "SKILL.md"))]
    checks.append(_check("core_skills", "FAIL" if missing else "PASS",
                         "missing=" + ",".join(missing) if missing else "11 core skills present"))
    state = maintenance.state_path(agent)
    try:
        data = maintenance.load_state(state)
        rows = data.get("checks", {})
        latest = max((r.get("last_completed_at", "") for r in rows.values()), default="")
        checks.append(_check("maintenance_state", "PASS" if rows else "WARN",
                             "checks={} latest={}".format(len(rows), latest or "never"), state))
    except Exception as exc:
        checks.append(_check("maintenance_state", "FAIL", str(exc), state))
    vault = os.environ.get("AGENT_OS_VAULT_DIR", "").strip()
    vault_status = "PASS" if vault and os.path.isdir(vault) else ("FAIL" if vault else "SKIP")
    checks.append(_check("vault", vault_status,
                         vault if vault else "AGENT_OS_VAULT_DIR not configured"))
    evo = os.path.join(root, ".agent-os", "evolution", "candidates")
    pending = len([x for x in os.listdir(evo) if x.endswith(".json")]) if os.path.isdir(evo) else 0
    checks.append(_check("evolution", "PASS", "candidate_artifacts={}".format(pending), evo))
    executable = shutil.which("openclaw")
    checks.append(_check("openclaw_cli", "PASS" if executable else "WARN",
                         executable or "not available in current PATH"))
    if executable and profile == "active":
        def config(key):
            done = subprocess.run([executable, "config", "get", key],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", errors="replace")
            return done.returncode, done.stdout.strip().strip('"')
        heartbeat_path = "agents.entries.{}.heartbeat".format(agent)
        every_rc, every = config(heartbeat_path + ".every")
        prompt_rc, prompt = config(heartbeat_path + ".prompt")
        cadence_ok = every_rc == 0 and every not in ("", "0", "0m", "false")
        prompt_ok = prompt_rc == 0 and "proactive.py heartbeat" in prompt
        checks.append(_check("heartbeat_prompt", "PASS" if prompt_ok else "FAIL",
                             heartbeat_path + (" configured" if prompt_ok else " missing Agent OS entry")))
        checks.append(_check("heartbeat_cadence", "PASS" if cadence_ok else "FAIL",
                             every or "<empty>"))
    elif executable:
        checks.append(_check("heartbeat", "SKIP", "basic profile does not configure heartbeat"))
    failed = [row for row in checks if row["status"] == "FAIL"]
    warned = [row for row in checks if row["status"] == "WARN"]
    return {"status": "FAILED" if failed else ("READY_WITH_WARNINGS" if warned else "READY"),
            "agent_id": agent, "profile": profile, "workspace": root,
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "state_dir": agent_state_dir("maintenance", agent), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description="Agent OS runtime diagnostics")
    parser.add_argument("command", choices=("status", "doctor"))
    parser.add_argument("--agent", default="")
    args = parser.parse_args()
    report = inspect(args.agent)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if args.command == "doctor" and report["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
