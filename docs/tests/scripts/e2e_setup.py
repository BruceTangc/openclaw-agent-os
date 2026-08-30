#!/usr/bin/env python3
"""Agent OS Evolution E2E — isolated V2 test environment setup (v2 protocol).

Creates a throwaway workspace seeded with **V2 Evidence records** in
`.agent-os/evolution/evidence.jsonl`, simulating:
  T1 (2026-08-15): quotation task FAIL — material-utilization check missed
  T2 (2026-08-16): quotation task FAIL — same pattern, second session

The real third failure (T3) is logged by the actual self-evolution v2 discover
CLI in evolution-e2e.sh, which then triggers promotion -> apply -> regression.

V2 protocol (current truth): V2 discover reads ONLY
`.agent-os/evolution/evidence.jsonl` via `_core.query_evidence()` /
`_core.compute_stats()`. It does **NOT** read the V1
`memory/.learning-trail.json`. So the seeds are written as real V2 Evidence
records (using the same `_core.register_evidence()` the runtime uses), not a
legacy trail.

Threshold: promotion requires observation_count >= 3 across >= 2 unique
sessions. With T1/T2/T3 as 3 real Evidence records:
  observation_count  = 3
  unique_sessions    = 3   (e2e-t1, e2e-t2, e2e-t3)
  independent_sources = 2  (user_feedback, verification)
threshold is satisfied.

Fixture uses the canonical unchanged pattern_key `quote-material-utilization`
(no `-correction` / `-check` suffixes) so all three aggregate together.

Isolated: E2E_WS is throwaway (OPENCLAW_WORKSPACE points there); the
production evolution state is never touched.
"""

import json
import os
import shutil
import sys

WS = os.environ.get("E2E_WS", "/tmp/agent-os-e2e-ws")
MEMORY = os.path.join(WS, "memory")

# --- import the real V2 evidence writer (_core.register_evidence) ----------
_REPO = os.path.dirname(os.path.abspath(__file__))  # docs/tests/scripts
# repo root = up 3 (scripts -> tests -> docs -> repo)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_REPO)))
SE = os.path.join(REPO_ROOT, "skills", "self-evolution", "scripts")
LIB = os.path.join(REPO_ROOT, "skills", "_lib")
for _p in (LIB, SE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _core  # noqa: E402


if os.path.exists(WS):
    shutil.rmtree(WS)
os.makedirs(MEMORY, exist_ok=True)


def seed_evidence(eid, summary, source, session, date, verified=False):
    """Write one canonical V2 Evidence record via the runtime's own writer."""
    rec = {
        "id": eid,
        "class": "verification",
        "category": "best_practice" if summary else "correction",
        "summary": summary,
        "details": "",
        "source": source,            # user_feedback (T1/T2) / verification (T3)
        "scope": "skill",
        "target": "quote/skill.md",
        "pattern_key": "quote-material-utilization",
        "problem": "报价流程漏检材料利用率",
        "confidence": 0.8,
        "verified": verified,
        "systemic": True,
        "session": session,          # explicit, NOT default s-YYYYMMDD
        "source_agent": "e2e",
        "logged": date,
        "seen_dates": [date],
    }
    return _core.register_evidence(rec)


# T1 / T2 as real V2 Evidence records (source=user_feedback, distinct sessions)
seed_evidence("EVID-E2E-T1", "报价流程漏检材料利用率（重复失败）",
              "user_feedback", "e2e-t1", "2026-08-15", verified=False)
seed_evidence("EVID-E2E-T2", "报价流程漏检材料利用率（第二次重复失败）",
              "user_feedback", "e2e-t2", "2026-08-16", verified=False)

# Target file that the quote flow checks (unprotected, V2 apply target).
# TOOLS.md is a PROTECTED_EXACT_FILE, so the apply target must NOT be TOOLS.md.
# Use a dedicated quote skill file instead; quote_check.sh verifies the rule lives there.
quote_target = os.path.join(WS, "quote", "skill.md")
os.makedirs(os.path.dirname(quote_target), exist_ok=True)
with open(quote_target, "w", encoding="utf-8") as f:
    # 初始内容必须完全避开「材料利用率」四字（grep 会命中→T1-T3 误 PASS）。
    # 暂以「物料判定」占位，Apply 时才通过 operations 写入真实规则，T4 才能真正 PASS。
    f.write("# quote/skill.md\n\n## Logic\n- 报价流程（当前缺物料判定检查规则）\n")

with open(os.path.join(WS, "SOUL.md"), "w", encoding="utf-8") as f:
    f.write("# SOUL.md\n\n## Boundaries\n")

# T4 regression check: does the quotation flow carry the rule now?
quote_check = os.path.join(WS, "quote_check.sh")
with open(quote_check, "w", encoding="utf-8") as f:
    f.write("#!/usr/bin/env bash\n")
    f.write("# T1-T3 FAIL when the rule is missing; T4 PASS after Apply\n")
    f.write('WS_DIR="${1:-.}"\n')
    f.write('if grep -q "材料利用率" "${WS_DIR}/quote/skill.md" 2>/dev/null; then\n')
    f.write('  echo "PASS: 报价流程包含材料利用率检查"\n')
    f.write("  exit 0\n")
    f.write("else\n")
    f.write('  echo "FAIL: 报价流程缺少材料利用率检查"\n')
    f.write("  exit 1\n")
    f.write("fi\n")
os.chmod(quote_check, 0o755)

# sanity: confirm the two V2 seeds landed and aggregate as expected
st = _core.compute_stats(
    pattern_key="quote-material-utilization", scope="skill", target="quote/skill.md")
print(f"E2E workspace ready: {WS}")
print(f"Seeded stats: obs={st.get('observation_count')} "
      f"sessions={st.get('unique_sessions')} sources={st.get('independent_sources')}")
