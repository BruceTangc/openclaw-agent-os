#!/usr/bin/env python3
import os
import tempfile

with tempfile.TemporaryDirectory(prefix="agentos_evo_pipeline_") as tmp:
    os.environ["OPENCLAW_WORKSPACE"] = tmp
    target = os.path.join(tmp, "skills", "demo", "SKILL.md")
    os.makedirs(os.path.dirname(target))
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("# Demo\n")
    import _core
    import pipeline
    candidate = {
        "status": "CANDIDATE", "scope": "AGENT", "target": "skills/demo/SKILL.md",
        "pattern_key": "demo-gap", "problem": "demo gap", "confidence": 0.9,
        "evidence_refs": ["EVID-1", "EVID-2", "EVID-3"],
        "automation": {
            "root_cause": "instruction_gap", "target": "skills/demo/SKILL.md",
            "proposed_change": "clarify the deterministic procedure",
            "expected_metric": "known failure passes", "reproducible": True,
            "level": "G3", "test_plan": "known_failure,normal,boundary",
        },
    }
    candidate_id = _core.save_artifact("candidate", candidate)
    result = pipeline.prepare(candidate_id)
    assert result["decision"] == "PROPOSAL_READY_FOR_REVIEW"
    assert result["applied"] is False
    assert result["evaluation"]["verdict"] == "READY_FOR_REVIEW"
    assert pipeline.prepare(candidate_id)["decision"] == "DEDUP"
    pending_id = _core.save_artifact("candidate", {
        "status": "CANDIDATE", "scope": "AGENT", "target": "skills/demo/SKILL.md",
        "pattern_key": "manual-gap", "problem": "needs diagnosis", "confidence": 0.8,
        "evidence_refs": ["EVID-4"], "automation": {},
    })
    scanned = pipeline.scan()
    assert pending_id in scanned["needs_manual_review"]

print("Evolution proposal pipeline tests: PASS")
