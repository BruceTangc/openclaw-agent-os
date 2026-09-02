#!/usr/bin/env python3
import os
import tempfile
import json

import workspace


def main():
    old = {k: os.environ.get(k) for k in (
        "OPENCLAW_WORKSPACE", "OPENCLAW_WORKSPACE_DIR", "AGENT_OS_WORKSPACE",
        "OPENCLAW_AGENT_ID", "AGENT_OS_AGENT_ID", "OPENCLAW_CONFIG_PATH")}
    try:
        with tempfile.TemporaryDirectory(prefix="agentos_workspace_") as tmp:
            os.environ["OPENCLAW_WORKSPACE"] = tmp
            os.environ["OPENCLAW_AGENT_ID"] = "research/a"
            a = workspace.agent_state_dir("tasks")
            b = workspace.agent_state_dir("tasks", "ops")
            shared = workspace.shared_state_dir("ontology")
            assert a.startswith(os.path.realpath(tmp))
            assert os.path.join("agents", "research-a", "tasks") in a
            assert os.path.join("agents", "ops", "tasks") in b
            assert a != b
            assert os.path.join("shared", "ontology") in shared
            assert workspace.native_memory_dir() == os.path.join(os.path.realpath(tmp), "memory")
            legacy = os.path.join(tmp, "legacy.json")
            canonical = os.path.join(tmp, "new", "state.json")
            assert workspace.prefer_migrated_path(canonical, legacy) == canonical
            with open(legacy, "w", encoding="utf-8") as handle:
                handle.write("legacy")
            assert workspace.prefer_migrated_path(canonical, legacy) == legacy
            os.makedirs(os.path.dirname(canonical), exist_ok=True)
            with open(canonical, "w", encoding="utf-8") as handle:
                handle.write("new")
            assert workspace.prefer_migrated_path(canonical, legacy) == canonical
        for key in ("OPENCLAW_WORKSPACE", "OPENCLAW_WORKSPACE_DIR", "AGENT_OS_WORKSPACE",
                    "OPENCLAW_AGENT_ID", "AGENT_OS_AGENT_ID", "OPENCLAW_CONFIG_PATH"):
            os.environ.pop(key, None)
        with tempfile.TemporaryDirectory(prefix="agentos_identity_") as tmp:
            jarvis = os.path.join(tmp, "workspace-jarvis")
            os.makedirs(os.path.join(jarvis, "skills"))
            config = os.path.join(tmp, "openclaw.json")
            with open(config, "w", encoding="utf-8") as handle:
                json.dump({"agents": {"entries": [
                    {"id": "main", "workspace": os.path.join(tmp, "workspace")},
                    {"id": "jarvis", "workspace": jarvis}],
                    "defaults": {"heartbeat": {"agentId": "jarvis"}}}}, handle)
            os.environ["OPENCLAW_CONFIG_PATH"] = config
            previous = os.getcwd()
            try:
                os.chdir(os.path.join(jarvis, "skills"))
                assert workspace.current_agent_id() == "jarvis"
                assert workspace.workspace_root() == os.path.realpath(jarvis)
                os.environ["OPENCLAW_AGENT_ID"] = "explicit-agent"
                assert workspace.current_agent_id() == "explicit-agent"
            finally:
                os.chdir(previous)
                os.environ.pop("OPENCLAW_CONFIG_PATH", None)
                os.environ.pop("OPENCLAW_AGENT_ID", None)
        print("Workspace path tests: 13 PASS / 0 FAIL")
        return 0
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
