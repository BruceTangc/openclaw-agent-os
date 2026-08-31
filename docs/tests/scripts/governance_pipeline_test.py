#!/usr/bin/env python3
"""Functional regression tests for context -> summarize -> governance routing."""

import importlib.util
import os
import sys


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load(name, relative):
    path = os.path.join(REPO, relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context = load("context_governance_test", "skills/context-orchestration/scripts/context.py")
memory = load("memory_governance_test", "skills/memory-governance/scripts/memory.py")
knowledge = load("knowledge_governance_test", "skills/knowledge-governance/scripts/knowledge.py")
summary = load("summary_governance_test", "skills/summarize/scripts/govern.py")

checks = []


def check(name, condition):
    checks.append((name, bool(condition)))
    print("[{}] {}".format("PASS" if condition else "FAIL", name))


selected = context.select({
    "agent_id": "a", "budget_chars": 256,
    "items": [
        {"id": "private-b", "text": "private", "scope": "AGENT", "owner_id": "b"},
        {"id": "left", "text": "A" * 200, "scope": "AGENT", "owner_id": "a",
         "contradiction_group": "g", "source": "s1", "confidence": 1},
        {"id": "right", "text": "B" * 200, "scope": "AGENT", "owner_id": "a",
         "contradiction_group": "g", "source": "s2", "confidence": 1},
    ]})
check("context blocks another agent scope", "private-b" not in [x["id"] for x in selected["selected"]])
check("context preserves both conflict sides", {"left", "right"} == {x["id"] for x in selected["selected"]})
check("context signals expanded retrieval", selected["expand_retrieval"] is True)

check("memory denies secrets", memory.govern({"text": "api_key=abc"})["decision"] == "DENY_SECRET")
check("memory gates deletion", memory.govern({"text": "x", "explicit_delete": True})["requires_permission"])
durable = memory.govern({"text": "stable", "stable": True, "useful": True,
                         "source": "user", "confidence": "0.9", "independent_sessions": "2"})
check("memory promotes qualified durable candidate", durable["decision"] == "PROMOTE_DURABLE")
check("memory tolerates invalid numeric input", memory.govern({"text": "x", "confidence": "bad"})["decision"] == "KEEP_SESSION")

inferred = knowledge.govern({"subject": "x", "claim": "y", "confidence": 1})
check("knowledge caps unsupported inference", inferred["claim"]["confidence"] == 0.4)
check("knowledge rejects malformed claim", knowledge.govern({"claim": "y"})["decision"] == "REJECT")
shared = knowledge.govern({"subject": "x", "claim": "y", "scope": "PROJECT", "source_type": "source_stated"})
check("knowledge gates shared claim", shared["decision"] == "SHARED_CANDIDATE" and shared["requires_governance"])
check("knowledge preserves disputes", knowledge.govern({"subject": "x", "claim": "y", "conflict": True})["claim"]["status"] == "disputed")

empty = summary.govern_summary({"structured": {"facts": [{"subject": "raw", "claim": "unsafe"}]},
                                "integrations": {}})
check("summary does not auto-promote raw facts", empty["knowledge_decisions"] == [])
routed = summary.govern_summary({"integrations": {
    "memory_candidates": [{"text": "remember", "explicit_remember": True}],
    "knowledge_candidates": [{"subject": "s", "claim": "c", "source_type": "user_asserted"}],
    "ontology_candidates": {"entities": [{"id": "e"}], "relations": []}}})
check("summary routes explicit memory candidate", len(routed["memory_decisions"]) == 1)
check("summary routes explicit knowledge candidate", len(routed["knowledge_decisions"]) == 1)
check("summary preserves ontology candidates", routed["ontology_candidates"]["entities"][0]["id"] == "e")
check("governance remains non-persistent", routed["persisted"] is False)

failed = [name for name, ok in checks if not ok]
print("\n{} / {} checks passed".format(len(checks) - len(failed), len(checks)))
sys.exit(1 if failed else 0)
