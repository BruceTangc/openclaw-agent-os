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
    def run_config(args, **kwargs):
        key = args[-1]
        values = {
            "agents.defaults.heartbeat.agentId": "doctor-agent",
            "agents.defaults.heartbeat.every": "30m",
            "agents.defaults.heartbeat.prompt": (
                "OPENCLAW_WORKSPACE={} OPENCLAW_AGENT_ID=doctor-agent "
                "python3 /skills/proactive/scripts/proactive.py heartbeat".format(tmp)),
        }
        value = values[key]
        return mock.Mock(returncode=0, stdout=value + "\n", stderr="")
    with mock.patch.object(agent_os.shutil, "which", return_value="/bin/openclaw"), \
         mock.patch.object(agent_os.subprocess, "run", side_effect=run_config):
        report = agent_os.inspect()
    assert report["status"] == "READY_WITH_WARNINGS"
    assert next(x for x in report["checks"] if x["name"] == "heartbeat_prompt")["status"] == "PASS"
    assert next(x for x in report["checks"] if x["name"] == "heartbeat_owner")["status"] == "PASS"
    assert next(x for x in report["checks"] if x["name"] == "heartbeat_cadence")["status"] == "PASS"
    os.environ["AGENT_OS_PROFILE"] = "basic"
    with mock.patch.object(agent_os.shutil, "which", return_value="/bin/openclaw"), \
         mock.patch.object(agent_os.subprocess, "run", side_effect=AssertionError("config must not run")):
        report = agent_os.inspect()
    assert report["status"] == "READY_WITH_WARNINGS"
    assert next(x for x in report["checks"] if x["name"] == "heartbeat")["status"] == "SKIP"
    os.environ.pop("AGENT_OS_PROFILE", None)

print("Agent OS doctor tests: PASS")
