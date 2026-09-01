#!/usr/bin/env python3
import os
import tempfile
from types import SimpleNamespace
from unittest import mock
from datetime import datetime, timedelta, timezone


with tempfile.TemporaryDirectory(prefix="agentos_maintenance_") as tmp:
    os.environ["OPENCLAW_WORKSPACE"] = tmp
    os.environ["OPENCLAW_AGENT_ID"] = "agent-a"
    import maintenance
    import dispatcher

    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    assert dispatcher.authorize("task_health")["allowed"] is True
    assert dispatcher.authorize("unknown_action")["allowed"] is False
    first = maintenance.plan(at=now)
    assert len(first["due"]) == 6
    assert any(row["name"] == "vault_sync" for row in first["due"])
    maintenance.record("task_health", "PASS", at=now)
    second = maintenance.plan(at=now + timedelta(minutes=29))
    assert not any(row["name"] == "task_health" for row in second["due"])
    third = maintenance.plan(at=now + timedelta(minutes=31))
    assert any(row["name"] == "task_health" for row in third["due"])
    maintenance.record("evolution_state", "FAIL", at=now)
    failed = maintenance.load_state(maintenance.state_path())["checks"]["evolution_state"]
    assert failed["failure_count"] == 1
    assert "last_completed_at" not in failed
    backed_off = maintenance.plan(at=now + timedelta(minutes=29))
    assert not any(row["name"] == "evolution_state" for row in backed_off["due"])
    os.environ["AGENT_OS_VAULT_DIR"] = os.path.join(tmp, "vault")
    with_vault = maintenance.plan(at=now)
    assert any(row["name"] == "vault_sync" for row in with_vault["due"])
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with mock.patch.object(maintenance.subprocess, "run", return_value=completed) as runner:
        synced = maintenance.run_vault(at=now)
    assert synced["result"] == "PASS" and synced["persisted_truth_changes"] is False
    assert runner.call_count == 2
    other = maintenance.state_path("agent-b")
    assert other != maintenance.state_path("agent-a")

with tempfile.TemporaryDirectory(prefix="agentos_heartbeat_") as tmp:
    os.environ["OPENCLAW_WORKSPACE"] = tmp
    os.environ["OPENCLAW_AGENT_ID"] = "agent-heartbeat"
    os.environ.pop("AGENT_OS_VAULT_DIR", None)
    memory_dir = os.path.join(tmp, "memory")
    os.makedirs(memory_dir)
    for name in ("2026-01-01.md", "2026-01-02.md"):
        with open(os.path.join(memory_dir, name), "w", encoding="utf-8") as handle:
            handle.write("same exact memory\n")
    audit = maintenance._memory_audit(now)
    assert audit["requires_semantic_review"] is True
    assert len(audit["candidates"]["exact_duplicates"]) == 1
    assert len(audit["candidates"]["daily_older_than_90d"]) == 2
    clean = {"returncode": 0, "output": "{}"}
    with mock.patch.object(maintenance, "_run_standard", return_value=(clean, False)):
        first_run = maintenance.run_due("agent-heartbeat", at=now)
    assert first_run["heartbeat_ok"] is True
    assert len(first_run["results"]) == 6
    assert next(x for x in first_run["results"] if x["name"] == "vault_sync")["result"] == "SKIPPED"
    with mock.patch.object(maintenance, "_run_standard", return_value=(clean, False)):
        second_run = maintenance.run_due("agent-heartbeat", at=now + timedelta(minutes=1))
    assert second_run["heartbeat_ok"] is True and second_run["results"] == []
    finding = {"returncode": 0, "output": '{"overdue":[{"id":"T1"}]}'}
    with mock.patch.object(maintenance, "_run_standard", return_value=(finding, True)):
        noticed = maintenance.run_check("task_health", "agent-dedup", at=now)
        repeated = maintenance.run_check("task_health", "agent-dedup",
                                         at=now + timedelta(minutes=31))
    assert noticed["actionable"] is True
    assert repeated["actionable"] is False and repeated["suppressed_unchanged"] is True

print("Maintenance cadence and heartbeat integration tests: PASS")
