#!/usr/bin/env python3
import os
import tempfile
from unittest import mock

with tempfile.TemporaryDirectory(prefix="agentos_doctor_") as tmp:
    os.environ["OPENCLAW_WORKSPACE"] = tmp
    os.environ["OPENCLAW_AGENT_ID"] = "doctor-agent"
    import agent_os
    with mock.patch.object(agent_os.shutil, "which", return_value=None):
        report = agent_os.inspect()
    assert report["status"] == "READY_WITH_WARNINGS"
    assert report["agent_id"] == "doctor-agent"
    assert next(x for x in report["checks"] if x["name"] == "core_skills")["status"] == "PASS"
    with open(os.path.join(tmp, "HEARTBEAT.md"), "w", encoding="utf-8") as handle:
        handle.write("python3 skills/proactive/scripts/proactive.py heartbeat\n")
    with mock.patch.object(agent_os.shutil, "which", return_value=None):
        report = agent_os.inspect()
    assert next(x for x in report["checks"] if x["name"] == "heartbeat_entry")["status"] == "PASS"

print("Agent OS doctor tests: PASS")
