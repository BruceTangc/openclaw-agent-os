#!/usr/bin/env python3
import os
import tempfile

import workspace


def main():
    old = {k: os.environ.get(k) for k in (
        "OPENCLAW_WORKSPACE", "OPENCLAW_WORKSPACE_DIR", "AGENT_OS_WORKSPACE",
        "OPENCLAW_AGENT_ID", "AGENT_OS_AGENT_ID")}
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
        print("Workspace path tests: 10 PASS / 0 FAIL")
        return 0
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
