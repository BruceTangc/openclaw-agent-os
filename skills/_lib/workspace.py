#!/usr/bin/env python3
"""Canonical Agent OS workspace and scope-aware state paths."""

from __future__ import print_function

import os
import re
import json


def _openclaw_config():
    path = (os.environ.get("OPENCLAW_CONFIG_PATH")
            or os.path.expanduser("~/.openclaw/openclaw.json"))
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _agent_entries(config):
    value = config.get("agents", {}).get("entries", {})
    if isinstance(value, list):
        return {str(row.get("id")): row for row in value
                if isinstance(row, dict) and row.get("id")}
    return value if isinstance(value, dict) else {}


def _configured_identity():
    """Resolve the current agent from its configured workspace when env is absent."""
    config = _openclaw_config()
    entries = _agent_entries(config)
    probe = os.path.realpath(os.path.abspath(os.getcwd()))
    matches = []
    for agent_id, row in entries.items():
        raw = row.get("workspace") if isinstance(row, dict) else None
        if not raw:
            continue
        root = os.path.realpath(os.path.abspath(os.path.expanduser(str(raw))))
        if probe == root or probe.startswith(root + os.sep):
            matches.append((len(root), str(agent_id), root))
    if matches:
        _, agent_id, root = max(matches)
        return agent_id, root
    owner = config.get("agents", {}).get("defaults", {}).get("heartbeat", {}).get("agentId")
    row = entries.get(str(owner), {}) if owner else {}
    raw = row.get("workspace") if isinstance(row, dict) else None
    if owner and raw:
        return str(owner), os.path.realpath(os.path.abspath(os.path.expanduser(str(raw))))
    return None, None


def workspace_root():
    raw = (os.environ.get("OPENCLAW_WORKSPACE")
           or os.environ.get("OPENCLAW_WORKSPACE_DIR")
           or os.environ.get("AGENT_OS_WORKSPACE"))
    if not raw:
        _, raw = _configured_identity()
    raw = raw or os.path.expanduser("~/.openclaw/workspace")
    return os.path.realpath(os.path.abspath(os.path.expanduser(raw)))


def _safe_segment(value, fallback):
    value = str(value or fallback).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return value or fallback


def current_agent_id(explicit=None):
    value = (explicit or os.environ.get("OPENCLAW_AGENT_ID")
             or os.environ.get("AGENT_OS_AGENT_ID"))
    if not value:
        value, _ = _configured_identity()
    return _safe_segment(value, "main")


def current_project_id(explicit=None):
    value = explicit or os.environ.get("OPENCLAW_PROJECT_ID") or os.environ.get("AGENT_OS_PROJECT_ID")
    return _safe_segment(value, "default") if value else ""


def agent_state_dir(component, agent_id=None):
    return os.path.join(workspace_root(), ".agent-os", "agents",
                        current_agent_id(agent_id), _safe_segment(component, "state"))


def project_state_dir(component, project_id=None):
    return os.path.join(workspace_root(), ".agent-os", "projects",
                        current_project_id(project_id) or "default",
                        _safe_segment(component, "state"))


def shared_state_dir(component):
    return os.path.join(workspace_root(), ".agent-os", "shared",
                        _safe_segment(component, "state"))


def native_memory_dir():
    return os.path.join(workspace_root(), "memory")


def prefer_migrated_path(canonical, legacy):
    """Use canonical state unless only a legacy path currently exists.

    This compatibility bridge prevents an upgrade from appearing to lose state.
    New installations (neither path exists) always select the canonical path.
    """
    if os.path.exists(canonical):
        return canonical
    if legacy and os.path.exists(legacy):
        return legacy
    return canonical
