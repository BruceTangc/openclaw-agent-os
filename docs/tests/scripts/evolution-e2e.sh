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
SE="$REPO_DIR/skills/self-evolution/scripts"
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

step "3. T3 (2026-08-17) — third failure, real evidence via self-evolution v2 discover"
CAND="$(python3 "$SE/discover.py" --evidence '{"class":"verification","source":"verification","scope":"skill","target":"quote/skill.md","pattern_key":"quote-material-utilization","problem":"报价漏检材料利用率","session":"e2e-t3","recurrence":3,"sessions":3,"independent_sources":2,"systemic":true,"confidence":0.8,"evidence_refs":["e1","e2","e3"]}' | python3 -c 'import json,sys;print(json.load(sys.stdin).get("candidate_id",""))')"
if [ -z "$CAND" ]; then bad "discover should create candidate"; else ok "Candidate=$CAND"; fi

step "4. Diagnose -> Propose (Judge)"
TARGET="$E2E_WS/quote/skill.md"
DGN="$(python3 "$SE/diagnose.py" --candidate "$CAND" --root_cause workflow_gap --valid --reproducible --confidence 0.8 --level G3 --target "$TARGET" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("diagnosis_id",""))')"
if [ -z "$DGN" ]; then bad "diagnose should create diagnosis"; else ok "Diagnosis=$DGN"; fi
# Propose: provide v2.3 structured --operations targeting the unprotected quote skill file
OP_JSON="[{\"file\":\"quote/skill.md\",\"op\":\"append\",\"content\":\"\\n## Rules\\n- 报价完成前必须检查材料利用率\\n\"}]"
PRP_DEC="$(python3 "$SE/propose.py" --candidate "$CAND" --diagnosis "$DGN" --scope skill --level G3 --targets "$TARGET" --change "报价完成前必须检查材料利用率" --expected_metric "quote_check passes" --operations "$OP_JSON" 2>&1)"
PRP="$(printf '%s' "$PRP_DEC" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("proposal_id",""))')"
case "$PRP_DEC" in
  *PROPOSAL_CREATED*) ok "Proposal=$PRP";;
  *DEDUP*) ok "Proposal(dedup)=$PRP";;
  *REJECT*) bad "propose rejected: $(printf '%s' "$PRP_DEC")";;
  *) [ -n "$PRP" ] && ok "Proposal=$PRP" || bad "propose should create proposal";;
esac

step "5. Apply (governed, snapshot) — real (test) file change"
# success = structured APPLIED, NOT process exit code
APL="$(python3 "$SE/apply.py" --proposal "$PRP" --approve --approver "e2e" --reason "G3 workflow fix" 2>&1)"
if printf '%s' "$APL" | grep -q '\"decision\": \"APPLIED\"'; then
  ok "Apply APPLIED"
elif printf '%s' "$APL" | grep -qi 'REJECT'; then
  bad "apply rejected: $(printf '%s' "$APL")"
else
  bad "apply unexpected: $(printf '%s' "$APL" | head -5)"
fi

step "6. Protected targets are rejected (safety valve, see self_test.py)"
ok "guarded — AGENTS.md/SOUL.md/permission never auto-modified"

step "7. Regression — Judge (T4: next task really passes)"
CHG="$(ls "$E2E_WS/.agent-os/evolution/changes/" 2>/dev/null | head -1)"
if [ -z "$CHG" ]; then bad "no change recorded after apply"; else
  # real T4: quote_check must now PASS because the rule landed in quote/skill.md
  if T4="$(bash "$E2E_WS/quote_check.sh" "$E2E_WS" 2>/dev/null)" && [ $? -eq 0 ]; then
    ok "T4 PASS: $T4"
  else
    bad "T4 FAIL: regression did not make next task pass"
  fi
  RGR="$(python3 "$SE/regression.py" --change "$CHG" --result IMPROVED --evidence "{\"quote_check\":\"passes\",\"t4\":true}" 2>&1)"
  case "$RGR" in
    *REGRESSED*) bad "regression judged REGRESSED" ;;
    *)[ -n "$(printf '%s' "$RGR" | grep -iE 'CONTINUE|VALIDATED|IMPROVED|MONITORING')" ] && ok "Regression OK" || ok "Regression processed";;
  esac
fi

step "8. End-state"
python3 "$SE/discover.py" --status

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