#!/usr/bin/env python3
"""Dependency-free YAML subset for generated Obsidian frontmatter."""

import json


def safe_dump(value, allow_unicode=True, sort_keys=False, default_flow_style=False):
    del allow_unicode, default_flow_style
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys, indent=2)


def _scalar(raw):
    raw = raw.strip()
    if not raw:
        return ""
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        lowered = raw.lower()
        if lowered in ("true", "false"):
            return lowered == "true"
        if lowered in ("null", "none", "~"):
            return None
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw.strip("\"'")


def safe_load(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass
    result, current = {}, None
    for original in text.splitlines():
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current:
            if not isinstance(result.get(current), list):
                result[current] = []
            result[current].append(_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        current = key.strip()
        result[current] = _scalar(raw) if raw.strip() else []
    return result
