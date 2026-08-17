#!/usr/bin/env bash
# Agent OS P0/P3 — Evolution E2E closed-loop test
#
# Scenario: quotation skill repeatedly misses the material-utilization check.
# Chain: T1/T2 FAIL (seeded history across 2 sessions) -> T3 real evidence
#        -> Discover + Classify -> Propose -> Promote(Apply) -> Regression
#        -> T4 PASS (proves the next task actually improved).
#
# Isolated workspace: never touches the production learning trail.
# Usage: E2E_WS=/tmp/agent-os-e2e-ws bash docs/tests/scripts/evolution-e2e.sh

set -u
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LEARN="$REPO_DIR/skills/self-evolution/scripts/learn.py"
E2E_WS="${E2E_WS:-/tmp/agent-os-e2e-ws-$$}"
export E2E_WS
export OPENCLAW_WORKSPACE="$E2E_WS"

PASS=0
FAIL=0
step() { echo; echo "═══ $* ═══"; }
ok()   { echo "  ✅ $*"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); }

step "0. Setup isolated workspace"
python3 "$REPO_DIR/docs/tests/scripts/e2e_setup.py"

step "1. T1 (2026-08-15) — quotation task: material-utilization check MISSING"
if bash "$E2E_WS/quote_check.sh" "$E2E_WS" >/dev/null 2>&1; then
  bad "T1 should FAIL"
else
  ok "T1 FAIL as expected -> Evidence #1 (seeded)"
fi

step "2. T2 (2026-08-16) — same failure, second session"
if bash "$E2E_WS/quote_check.sh" "$E2E_WS" >/dev/null 2>&1; then
  bad "T2 should FAIL"
else
  ok "T2 FAIL as expected -> Evidence #2 (seeded)"
fi

step "3. T3 (2026-08-17) — third failure, log REAL evidence via learn.py"
python3 "$LEARN" --log correction "报价第三次漏检材料利用率（确认是固定流程缺口）" \
  --area tooling --pattern-key quote-material-utilization-correction \
  --source user_feedback --priority high
python3 "$LEARN" --log best_practice "报价完成前必须检查材料利用率" \
  --area tooling --pattern-key quote-material-utilization-check \
  --source user_feedback --priority high
if bash "$E2E_WS/quote_check.sh" "$E2E_WS" >/dev/null 2>&1; then
  bad "T3 pre-apply should still FAIL"
else
  ok "T3 FAIL as expected -> threshold reached (3+ occurrences, 3 sessions)"
fi

step "4. Discover + Classify -> Candidate -> Propose (Judge)"
python3 "$LEARN" --propose

step "5. Promote -> execute Apply (real file change)"
python3 "$LEARN" --promote

step "6. Verify safe files were NOT auto-modified (correction -> SOUL.md)"
if grep -q "报价完成前必须检查材料利用率" "$E2E_WS/SOUL.md" 2>/dev/null; then
  bad "SOUL.md must NOT be auto-written (safety valve)"
else
  ok "SOUL.md untouched — persona/security files require human approval"
fi

step "7. Regression — T4: re-run the quotation task after Apply"
if bash "$E2E_WS/quote_check.sh" "$E2E_WS" >/dev/null 2>&1; then
  ok "T4 PASS — rule is now in TOOLS.md, quotation flow improved"
else
  bad "T4 should PASS after Apply"
fi

step "8. Trail end-state"
python3 "$LEARN" --status

echo
echo "══════════════ RESULT ══════════════"
echo "  PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "  E2E CONCLUSION: Evolution loop works — Evidence -> Candidate -> Apply -> next task improved."
  exit 0
else
  echo "  E2E FAILED"
  exit 1
fi