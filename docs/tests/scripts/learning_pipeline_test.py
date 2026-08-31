#!/usr/bin/env python3
"""End-to-end event -> evidence -> candidate -> memory -> Vault projection."""

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LEARNING = os.path.join(REPO, "skills", "proactive", "scripts", "learning.py")
VAULT = os.path.join(REPO, "skills", "agent-os-vault", "scripts", "agent_os_vault.py")
passed = failed = 0


def check(name, condition):
    global passed, failed
    passed += int(bool(condition))
    failed += int(not condition)
    print("[{}] {}".format("PASS" if condition else "FAIL", name))


with tempfile.TemporaryDirectory(prefix="agentos_learning_") as workspace:
    vault = os.path.join(workspace, "vault")
    env = os.environ.copy()
    env.update({"OPENCLAW_WORKSPACE": workspace, "OPENCLAW_AGENT_ID": "main",
                "AGENT_OS_VAULT_DIR": vault, "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8"})
    event = None
    for index, session in enumerate(("s1", "s2", "s3"), 1):
        event = {
            "event_id": "event-{}".format(index), "source": "verification",
            "agent_id": "main", "session_id": session, "execution_id": "exec-{}".format(index),
            "task_id": "task-{}".format(index), "verification_level": "V2",
            "result": {"tool_success": True, "output": "ok", "success_condition_met": True},
            "learning": {"problem": "reusable test pattern", "pattern_key": "pipeline-test",
                         "target": "test-skill", "scope": "AGENT", "confidence": 0.9,
                         "impact": "medium", "systemic": True},
            "memory_candidates": [{"text": "Always verify the pipeline artifact.",
                                   "stable": True, "useful": True, "source": "verification",
                                   "confidence": 0.9, "independent_sessions": 2}],
            "knowledge_candidates": [{"subject": "pipeline", "claim": "verification is required",
                                      "source_type": "source_stated", "evidence": ["event-{}".format(index)],
                                      "confidence": 0.9, "scope": "PROJECT"}],
        }
        run = subprocess.run([sys.executable, LEARNING, "--json", json.dumps(event)],
                             env=env, capture_output=True, text=True, encoding="utf-8")
        check("learning ingest {} exits 0".format(index), run.returncode == 0)

    evidence_file = os.path.join(workspace, ".agent-os", "evolution", "evidence.jsonl")
    candidate_dir = os.path.join(workspace, ".agent-os", "evolution", "candidates")
    check("three evidence records persisted", os.path.isfile(evidence_file) and
          len([x for x in open(evidence_file, encoding="utf-8") if x.strip()]) == 3)
    check("threshold creates evolution candidate", os.path.isdir(candidate_dir) and
          any(name.endswith(".json") for name in os.listdir(candidate_dir)))
    durable = os.path.join(workspace, "MEMORY.md")
    check("durable memory written", os.path.isfile(durable) and "Always verify" in open(durable, encoding="utf-8").read())
    knowledge = os.path.join(workspace, ".agent-os", "shared", "knowledge", "candidates.jsonl")
    check("knowledge remains governed candidate", os.path.isfile(knowledge))
    check("no knowledge truth auto-created", not os.path.exists(os.path.join(
          workspace, ".agent-os", "shared", "knowledge", "claims.jsonl")))

    duplicate = subprocess.run([sys.executable, LEARNING, "--json", json.dumps(event)],
                               env=env, capture_output=True, text=True, encoding="utf-8")
    duplicate_out = json.loads(duplicate.stdout)
    check("event evidence is idempotent", duplicate_out["evolution"]["decision"] == "DEDUP")
    check("durable memory is deduplicated", open(durable, encoding="utf-8").read().count("Always verify") == 1)
    check("knowledge candidate is deduplicated", len([x for x in open(knowledge, encoding="utf-8") if x.strip()]) == 1)

    export = subprocess.run([sys.executable, VAULT, "export", "--sources", "evidence", "memory",
                             "--vault", vault, "--agent", "main"], env=env,
                            capture_output=True, text=True, encoding="utf-8")
    check("Vault projection exits 0", export.returncode == 0)
    evidence_vault = os.path.join(vault, "evolution", "evidence")
    check("Vault contains evidence", os.path.isdir(evidence_vault) and len(os.listdir(evidence_vault)) == 3)
    check("Vault contains durable memory", os.path.isdir(os.path.join(vault, "memory", "durable")))

print("\n{} / {} checks passed".format(passed, passed + failed))
sys.exit(1 if failed else 0)
