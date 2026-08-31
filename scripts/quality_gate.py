#!/usr/bin/env python3
"""Phase 1 repository quality gate.

Runs deterministic local checks only. It does not install dependencies, access the
network, mutate repository data, or replace OpenClaw's runtime/approval boundary.
"""

from __future__ import print_function

import os
import py_compile
import subprocess
import sys
import tempfile


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TESTS = [
    ("workspace paths", ["skills/_lib/test_workspace.py"], False),
    ("runtime migration", ["docs/tests/scripts/migrate_runtime_state_test.py"], False),
    ("governance pipeline", ["docs/tests/scripts/governance_pipeline_test.py"], False),
    ("release contract", ["docs/tests/scripts/release_contract_test.py"], False),
    ("shared transitions", ["skills/_lib/test_transitions.py"], False),
    ("orchestrator", ["skills/orchestrator/scripts/test_orchestrator.py"], False),
    ("proactive anti-loop", ["skills/proactive/scripts/test_anti_loop.py"], False),
    ("heartbeat maintenance", ["skills/proactive/scripts/test_maintenance.py"], False),
    ("self-evolution", ["skills/self-evolution/scripts/self_test.py"], True),
    ("multi-agent protocol", ["docs/tests/scripts/ma_regression.py"], False),
    ("protocol compliance", ["docs/tests/scripts/compliance.py"], False),
]


def run(label, args, posix_only):
    print("\n== {} ==".format(label), flush=True)
    if posix_only and os.name == "nt":
        print("SKIPPED: test requires POSIX fcntl; Linux CI runs it.")
        return None
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run([sys.executable] + args, cwd=REPO, env=env)
    if completed.returncode:
        print("FAILED: {} (exit {})".format(label, completed.returncode))
        return False
    return True


def check_syntax():
    """Compile every tracked-source Python file without writing into the tree."""
    ok = True
    with tempfile.TemporaryDirectory(prefix="agent_os_syntax_") as tmp:
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in (".git", ".agent-os", "__pycache__")]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                source = os.path.join(root, filename)
                target = os.path.join(tmp, "{}.pyc".format(abs(hash(source))))
                try:
                    py_compile.compile(source, cfile=target, doraise=True)
                except py_compile.PyCompileError as exc:
                    ok = False
                    print(exc.msg)
    return ok


def main():
    print("Agent OS Phase 1 quality gate")
    print("Python: {}".format(sys.version.split()[0]))

    print("\n== Python syntax ==", flush=True)
    syntax_ok = check_syntax()

    results = [("Python syntax", syntax_ok)]
    results.extend((label, run(label, args, posix_only))
                   for label, args, posix_only in TESTS)

    failed = [label for label, ok in results if ok is False]
    print("\n== Summary ==")
    for label, ok in results:
        status = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        print("[{}] {}".format(status, label))
    if failed:
        print("Quality gate failed: {}".format(", ".join(failed)))
        return 1
    print("Quality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
