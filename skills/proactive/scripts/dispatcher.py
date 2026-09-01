#!/usr/bin/env python3
"""Fail-closed registry for deterministic heartbeat maintenance actions."""

REGISTRY = {
    "task_health": {"level": "L0", "side_effect": "NONE"},
    "evolution_state": {"level": "L1", "side_effect": "REVERSIBLE_LOCAL_PROPOSAL"},
    "memory_governance": {"level": "L0", "side_effect": "NONE"},
    "ontology_health": {"level": "L0", "side_effect": "NONE"},
    "vault_sync": {"level": "L1", "side_effect": "REVERSIBLE_LOCAL"},
    "weekly_review": {"level": "L0", "side_effect": "NONE"},
}


def authorize(name):
    policy = REGISTRY.get(name)
    if not policy:
        return {"allowed": False, "decision": "DENY", "reason": "unregistered_action"}
    if policy["level"] not in ("L0", "L1"):
        return {"allowed": False, "decision": "DENY", "reason": "level_requires_gate",
                "policy": policy}
    return {"allowed": True, "decision": "AUTO", "reason": "registered_low_risk",
            "policy": policy}


def dispatch(name, runner):
    gate = authorize(name)
    if not gate["allowed"]:
        return {"name": name, "result": "FAIL", "actionable": True,
                "reason": gate["reason"], "permission": gate}
    result = runner()
    if not isinstance(result, dict):
        return {"name": name, "result": "FAIL", "actionable": True,
                "reason": "invalid_handler_result", "permission": gate}
    result.setdefault("name", name)
    result["permission"] = gate
    return result
