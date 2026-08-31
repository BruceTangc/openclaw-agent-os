#!/usr/bin/env python3
"""Plan or safely copy legacy Skill-local state into the canonical workspace.

Dry-run is the default. ``--apply`` never deletes a source and never overwrites a
different target. Identical targets are treated as idempotent skips.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import shutil
import sys


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO, "skills", "_lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import workspace  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mappings(skills_root, agent_id):
    agent = workspace.current_agent_id(agent_id)
    agent_root = os.path.join(workspace.workspace_root(), ".agent-os", "agents", agent)
    shared_root = os.path.join(workspace.workspace_root(), ".agent-os", "shared")
    return [
        (os.path.join(skills_root, "task-manager", "memory", "tasks.json"),
         os.path.join(agent_root, "tasks", "tasks.json")),
        (os.path.join(skills_root, "proactive", "memory", "queue.json"),
         os.path.join(agent_root, "proactive", "queue.json")),
        (os.path.join(skills_root, "proactive", "memory", "state.json"),
         os.path.join(agent_root, "proactive", "state.json")),
        (os.path.join(skills_root, "proactive", "memory", "execution_records.jsonl"),
         os.path.join(agent_root, "execution", "execution_records.jsonl")),
        (os.path.join(skills_root, "ontology", "memory", "ontology"),
         os.path.join(shared_root, "ontology")),
    ]


def iter_files(source, target):
    if os.path.isfile(source):
        yield source, target
    elif os.path.isdir(source):
        for root, _, files in os.walk(source):
            for name in sorted(files):
                src = os.path.join(root, name)
                rel = os.path.relpath(src, source)
                yield src, os.path.join(target, rel)


def migrate(skills_root, agent_id, apply=False):
    rows = []
    failures = 0
    for source, target in mappings(skills_root, agent_id):
        for src, dst in iter_files(source, target):
            src_hash = sha256(src)
            if os.path.exists(dst):
                if os.path.isfile(dst) and sha256(dst) == src_hash:
                    status = "identical"
                else:
                    status = "conflict"
                    failures += 1
            elif apply:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                status = "copied" if sha256(dst) == src_hash else "verify_failed"
                failures += int(status == "verify_failed")
            else:
                status = "planned"
            rows.append({"source": src, "target": dst, "sha256": src_hash,
                         "status": status})
    return {"mode": "apply" if apply else "dry-run", "agent_id": workspace.current_agent_id(agent_id),
            "workspace": workspace.workspace_root(), "items": rows,
            "failures": failures, "source_deleted": False}


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy Agent OS runtime state")
    parser.add_argument("--skills-root", default=os.path.join(REPO, "skills"))
    parser.add_argument("--workspace")
    parser.add_argument("--agent", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.workspace:
        os.environ["OPENCLAW_WORKSPACE"] = args.workspace
    result = migrate(os.path.realpath(args.skills_root), args.agent, args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
