#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT = os.path.join(REPO, "scripts", "migrate_runtime_state.py")


def main():
    with tempfile.TemporaryDirectory(prefix="agentos_migrate_") as tmp:
        skills = os.path.join(tmp, "skills")
        workspace = os.path.join(tmp, "workspace")
        source = os.path.join(skills, "task-manager", "memory", "tasks.json")
        os.makedirs(os.path.dirname(source), exist_ok=True)
        with open(source, "w", encoding="utf-8") as handle:
            json.dump([{"id": "task-1"}], handle)

        base = [sys.executable, SCRIPT, "--skills-root", skills,
                "--workspace", workspace, "--agent", "research"]
        dry = subprocess.run(base, capture_output=True, text=True, check=True)
        dry_result = json.loads(dry.stdout)
        assert dry_result["items"][0]["status"] == "planned"
        target = dry_result["items"][0]["target"]
        assert not os.path.exists(target)

        applied = subprocess.run(base + ["--apply"], capture_output=True, text=True, check=True)
        applied_result = json.loads(applied.stdout)
        assert applied_result["items"][0]["status"] == "copied"
        assert os.path.exists(source) and os.path.exists(target)

        again = subprocess.run(base + ["--apply"], capture_output=True, text=True, check=True)
        assert json.loads(again.stdout)["items"][0]["status"] == "identical"

        with open(target, "w", encoding="utf-8") as handle:
            handle.write("different")
        conflict = subprocess.run(base + ["--apply"], capture_output=True, text=True)
        assert conflict.returncode == 1
        assert json.loads(conflict.stdout)["items"][0]["status"] == "conflict"

    print("Runtime migration tests: 10 PASS / 0 FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
