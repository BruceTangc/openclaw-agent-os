# Smoke Tests

These are behavioral test cases, not a replacement for OpenClaw's own test suite.

Run manually after installation.

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
