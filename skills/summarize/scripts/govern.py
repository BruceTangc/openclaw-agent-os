#!/usr/bin/env python3
"""Route explicit summary candidates through governance without persisting them."""

import argparse
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))


def _load(name, relative):
    path = os.path.join(SKILLS, relative)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MEMORY = _load("agent_os_memory_governance", "memory-governance/scripts/memory.py")
KNOWLEDGE = _load("agent_os_knowledge_governance", "knowledge-governance/scripts/knowledge.py")


def read_input(raw):
    if raw == "-":
        return json.load(sys.stdin)
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw)


def govern_summary(summary):
    integrations = summary.get("integrations") or {}
    memory = integrations.get("memory_candidates") or []
    knowledge = integrations.get("knowledge_candidates") or []
    ontology = integrations.get("ontology_candidates") or {"entities": [], "relations": []}
    warnings = []
    if not isinstance(memory, list):
        warnings.append("memory_candidates_not_list")
        memory = []
    if not isinstance(knowledge, list):
        warnings.append("knowledge_candidates_not_list")
        knowledge = []
    # Deliberately do not promote structured.facts or regex fact_candidates.
    # Only explicit integration candidates have completed summarizer judgment.
    return {
        "memory_decisions": [MEMORY.govern(x) for x in memory if isinstance(x, dict)],
        "knowledge_decisions": [KNOWLEDGE.govern(x) for x in knowledge if isinstance(x, dict)],
        "ontology_candidates": ontology,
        "warnings": warnings,
        "persisted": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON, @file, or - for stdin")
    args = parser.parse_args()
    print(json.dumps(govern_summary(read_input(args.json)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
