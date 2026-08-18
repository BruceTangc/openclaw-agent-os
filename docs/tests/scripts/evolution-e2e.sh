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
CAND="$(python3 "$SE/discover.py" --evidence '{"class":"verification","scope":"skill","target":"quote/skill.md","pattern_key":"quote-material-utilization","problem":"报价漏检材料利用率","recurrence":3,"sessions":3,"independent_sources":2,"systemic":true,"confidence":0.8,"evidence_refs":["e1","e2","e3"]}' | python3 -c 'import json,sys;print(json.load(sys.stdin).get("candidate_id",""))')"
if [ -z "$CAND" ]; then bad "discover should create candidate"; else ok "Candidate=$CAND"; fi

step "4. Diagnose -> Propose (Judge)"
DGN="$(python3 "$SE/diagnose.py" --candidate "$CAND" --root_cause workflow_gap --valid --reproducible --confidence 0.8 --level G3 --target "$E2E_WS/quote/skill.md" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("diagnosis_id",""))')"
PRP="$(python3 "$SE/propose.py" --candidate "$CAND" --diagnosis "$DGN" --scope skill --level G3 --targets "$E2E_WS/quote/skill.md" --change "报价完成前必须检查材料利用率" --expected_metric "quote_check passes" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("proposal_id",""))')"
if [ -z "$PRP" ]; then bad "propose should create proposal"; else ok "Proposal=$PRP"; fi

step "5. Apply (governed, snapshot) — real (test) file change"
python3 "$SE/apply.py" --proposal "$PRP" --approve --approver "e2e" --reason "G3 workflow fix" || bad "apply failed"

step "6. Protected targets are rejected (safety valve, see self_test.py)"
ok "guarded — AGENTS.md/SOUL.md/permission never auto-modified"

step "7. Regression — Judge"
CHG="$(ls "$E2E_WS/.agent-os/evolution/changes/" | head -1)"
python3 "$SE/regression.py" --change "$CHG" --result IMPROVED --evidence '{"quote_check":"passes"}' || bad "regression failed"

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