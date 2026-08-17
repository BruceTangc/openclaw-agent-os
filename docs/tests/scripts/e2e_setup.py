#!/usr/bin/env python3
"""Agent OS Evolution E2E — isolated test environment setup.

Creates a throwaway workspace with a seeded learning trail simulating:
  T1 (2026-08-15): quotation task FAIL — material-utilization check missed
  T2 (2026-08-16): quotation task FAIL — same pattern, second session

The real third failure (T3) is logged by the actual learn.py CLI in
evolution-e2e.sh, which then triggers promotion -> apply -> regression.

Reason for seeding history: pattern promotion requires >=3 occurrences
across >=2 sessions (v1.3.1 threshold), so a realistic E2E must span
days; two past sessions are seeded with rc=2 each, today's real CLI log
pushes total to >=3 triggering promotion.

Not touching the production trail: E2E_WS/memory/.learning-trail.json
is a separate file (OPENCLAW_WORKSPACE is pointed at E2E_WS).
"""

import json
import os
import shutil

WS = os.environ.get("E2E_WS", "/tmp/agent-os-e2e-ws")
MEMORY = os.path.join(WS, "memory")

if os.path.exists(WS):
    shutil.rmtree(WS)
os.makedirs(MEMORY, exist_ok=True)


def entry(eid, category, pk, summary, logged, rc, dates):
    return {
        "id": eid,
        "type": "learning",
        "category": category,
        "summary": summary,
        "details": "",
        "suggested_action": "",
        "area": "tooling",
        "priority": "high",
        "status": "pending",
        "logged": logged,
        "source": "user_feedback",
        "scope": "AGENT",
        "trusted": True,
        "pattern_key": pk,
        # v1.3.1: seed rc=2 so real T3 log pushes total to >=3
        "recurrence_count": rc,
        "seen_dates": dates,
        "first_seen": dates[0],
        "last_seen": dates[-1],
    }


trail = {
    "version": 3,
    "last_cycle": None,
    "entries": [
        # Pattern A: correction -> SOUL.md target -> safety valve (human approval)
        entry(
            "LRN-E2E-A",
            "correction",
            "quote-material-utilization-correction",
            "报价流程漏检材料利用率（重复失败，模式已确认）",
            "2026-08-16",
            2,
            ["2026-08-15", "2026-08-16"],
        ),
        # Pattern B: best_practice + tooling -> TOOLS.md target -> auto apply
        entry(
            "LRN-E2E-B",
            "best_practice",
            "quote-material-utilization-check",
            "报价完成前必须检查材料利用率",
            "2026-08-16",
            2,
            ["2026-08-15", "2026-08-16"],
        ),
    ],
    "changes": [],
    "watchlist": [],
    "principles": [],
    "graph": {"nodes": [], "edges": []},
    "stats": {
        "total_entries": 2,
        "total_changes": 0,
        "verified_ok": 0,
        "reverted": 0,
        "total_nodes": 0,
        "total_edges": 0,
    },
}

with open(os.path.join(MEMORY, ".learning-trail.json"), "w", encoding="utf-8") as f:
    json.dump(trail, f, indent=2, ensure_ascii=False)

# Target files that execute_promotion may write to
with open(os.path.join(WS, "TOOLS.md"), "w", encoding="utf-8") as f:
    f.write("# TOOLS.md\n\n## Known Gotchas\n")

with open(os.path.join(WS, "SOUL.md"), "w", encoding="utf-8") as f:
    f.write("# SOUL.md\n\n## Boundaries\n")

# T4 regression check: does the quotation flow carry the rule now?
quote_check = os.path.join(WS, "quote_check.sh")
with open(quote_check, "w", encoding="utf-8") as f:
    f.write("#!/usr/bin/env bash\n")
    f.write("# T1-T3 FAIL when the rule is missing; T4 PASS after Apply\n")
    f.write('WS_DIR="${1:-.}"\n')
    f.write('if grep -q "材料利用率" "${WS_DIR}/TOOLS.md" 2>/dev/null; then\n')
    f.write('  echo "PASS: 报价流程包含材料利用率检查"\n')
    f.write("  exit 0\n")
    f.write("else\n")
    f.write('  echo "FAIL: 报价流程缺少材料利用率检查"\n')
    f.write("  exit 1\n")
    f.write("fi\n")
os.chmod(quote_check, 0o755)

print(f"E2E workspace ready: {WS}")
print(f"Seeded: T1 (2026-08-15) + T2 (2026-08-16) failures, trail at {MEMORY}/.learning-trail.json")