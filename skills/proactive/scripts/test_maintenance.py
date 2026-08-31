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

    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    first = maintenance.plan(at=now)
    assert len(first["due"]) == 5  # vault disabled unless explicitly configured
    assert not any(row["name"] == "vault_sync" for row in first["due"])
    maintenance.record("task_health", "PASS", at=now)
    second = maintenance.plan(at=now + timedelta(minutes=29))
    assert not any(row["name"] == "task_health" for row in second["due"])
    third = maintenance.plan(at=now + timedelta(minutes=31))
    assert any(row["name"] == "task_health" for row in third["due"])
    maintenance.record("evolution_state", "FAIL", at=now)
    failed = maintenance.load_state(maintenance.state_path())["checks"]["evolution_state"]
    assert failed["failure_count"] == 1
    assert "last_completed_at" not in failed
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

print("Maintenance cadence tests: 12 PASS / 0 FAIL")
