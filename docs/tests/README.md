# Smoke Tests

These are behavioral test cases, not a replacement for OpenClaw's own test suite.

## Phase 1 automated quality gate

Run the same deterministic checks used by CI from the repository root:

```bash
python scripts/quality_gate.py
```

GitHub Actions runs this entry point on every push and pull request. The gate performs
Python syntax compilation plus the shared-transition, orchestrator, proactive anti-loop,
self-evolution, multi-agent protocol, and protocol-compliance regressions. The POSIX-only
self-evolution E2E is explicitly skipped on Windows and always runs in Linux CI. The gate
is read-only with respect to repository data and does not install dependencies or publish
artifacts.

Linux CI additionally checks `install.sh` syntax and runs an isolated installer smoke test.
The smoke test verifies the shared `_lib`, all bundled Skills, runtime templates, automatic
30-minute Heartbeat configuration, and the invariant that installation creates no business
Cron/Automation jobs.

Run manually after installation.

> **Automated compliance guard（#5 #6）**: `scripts/compliance.py` converts the
> Execution Record MUST-produce matrix and the Mandatory chain into executable
> assertions (Full Path/L2+/Evolution Apply must produce, Fast Path L0/L1 MAY omit,
> protocol_nodes snapshot, missing-REQUIRED-tool → FAIL). Run:
> `python3 scripts/compliance.py`  → expect ALL PASS + exit 0.

1. Proactive: no meaningful candidate -> NOOP.
2. Proactive: valuable reversible task -> PREPARE/ACT according to policy.
3. Permission: L3 action -> approval required.
4. Verification: tool returns success but artifact missing -> FAIL/UNKNOWN, never PASS.
5. Context: unrelated memory must not be injected.
6. Memory: transient chatter must not become durable memory.
7. Knowledge: contradictory evidence must be flagged.
8. Self-evolution: one unverified failure must not modify a Skill.
9. Orchestrator: dependent tasks must not be parallelised unsafely.
10. Task: externally consequential task cannot become completed without verification.
11. Shared Skill ≠ Shared State: using a shared skill does not share Agent State.
12. Provenance: A→B→C Execution Record must retain origin_agent & delegation chain.
13. Evolution Scope: candidate default affects only own Agent; cross-agent requires escalation.
14. Enforcement boundary: Agent OS vs OpenClaw runtime vs policy-only are not conflated.
