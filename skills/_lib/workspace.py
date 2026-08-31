#!/usr/bin/env python3
"""Canonical Agent OS workspace and scope-aware state paths."""

from __future__ import print_function

import os
import re


def workspace_root():
    raw = (os.environ.get("OPENCLAW_WORKSPACE")
           or os.environ.get("OPENCLAW_WORKSPACE_DIR")
           or os.environ.get("AGENT_OS_WORKSPACE")
           or os.path.expanduser("~/.openclaw/workspace"))
    return os.path.realpath(os.path.abspath(os.path.expanduser(raw)))


def _safe_segment(value, fallback):
    value = str(value or fallback).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return value or fallback


def current_agent_id(explicit=None):
    return _safe_segment(
        explicit or os.environ.get("OPENCLAW_AGENT_ID")
        or os.environ.get("AGENT_OS_AGENT_ID"), "main")


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
