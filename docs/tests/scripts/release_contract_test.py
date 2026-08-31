#!/usr/bin/env python3
"""Release and OpenClaw installer contract consistency checks."""

import os
import re
import subprocess
import sys


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def read(relative):
    with open(os.path.join(REPO, relative), encoding="utf-8") as handle:
        return handle.read()


checks = []


def check(name, condition):
    checks.append((name, bool(condition)))
    print("[{}] {}".format("PASS" if condition else "FAIL", name))


version = read("VERSION").strip()
manifest = read("MANIFEST.yml")
installer = read("install.sh")
readme = read("README.md")
skills_dir = os.path.join(REPO, "skills")
bundled = sorted(name for name in os.listdir(skills_dir)
                 if os.path.isdir(os.path.join(skills_dir, name)) and name != "_lib")
manifest_skills = sorted(re.findall(r"^    - name: (.+)$", manifest, re.M))

check("VERSION is semver", bool(re.fullmatch(r"\d+\.\d+\.\d+", version)))
check("manifest version matches VERSION", "  version: {}\n".format(version) in manifest)
check("manifest contains exactly 11 core skills", len(manifest_skills) == 11)
check("all manifest skills are bundled", set(manifest_skills).issubset(set(bundled)))
check("agent-os-vault is bundled extension", "agent-os-vault" in bundled and "agent-os-vault" not in manifest_skills)
check("installer sets one heartbeat owner", "agents.defaults.heartbeat.agentId" in installer)
check("installer verifies skills by name", 'grep -F "$name"' in installer)
check("installer creates no business cron", not re.search(r"openclaw\s+(?:cron|automations)\s+(?:add|create)", installer))
check("README baseline matches installer", "OpenClaw 2026.7.1 or newer" in readme and 'MIN_VERSION="2026.7.1"' in installer)
child_env = os.environ.copy()
child_env["PYTHONUTF8"] = "1"
child_env["PYTHONIOENCODING"] = "utf-8"
generated = subprocess.run(
    [sys.executable, os.path.join(REPO, "scripts", "gen_manifest.py")],
    cwd=REPO, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
).stdout.decode("utf-8").strip()
check("generated manifest matches committed manifest",
      generated.splitlines() == manifest.strip().splitlines())

failed = [name for name, ok in checks if not ok]
print("\n{} / {} checks passed".format(len(checks) - len(failed), len(checks)))
sys.exit(1 if failed else 0)
