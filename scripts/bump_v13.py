#!/usr/bin/env python3
"""v1.3 版本统一脚本（P0）：11 个 skill + 根文档版本收口。
只替换明确目标串，不动历史存档（DEEP-AUDIT/FINALIZE/SCRIPTS-AUDIT）与 compatibility 说明。
"""
import json, re, sys
from pathlib import Path

ROOT = Path("/tmp/agent-os")

# 目标替换：key -> (old, new) 列表
REPLACEMENTS = [
    ('"protocol_version": "1.2"', '"protocol_version": "1.3"'),
    ("protocol_version: \"1.2\"", "protocol_version: \"1.3\""),
    ("protocol_version: \"1.2\"        # 或 \"1.3\"", "protocol_version: \"1.3\""),
    ("version: 1.2.0", "version: 1.3.0"),
    ('"version": "1.2.0"', '"version": "1.3.0"'),
    ("Agent OS v1.2", "Agent OS v1.3"),
]

def apply_text(text: str) -> tuple[str, int]:
    count = 0
    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
            count += text.count(new)  # approximate; fine for our use
    return text, count

changed_files = []

def process_file(p: Path):
    if p.suffix == ".json":
        # JSON: 只改 version 字段与 description 里的 v1.2
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return
        orig = json.dumps(data, ensure_ascii=False)
        if data.get("version") == "1.2.0":
            data["version"] = "1.3.0"
        desc = data.get("description", "")
        if "Agent OS v1.2" in desc:
            data["description"] = desc.replace("Agent OS v1.2", "Agent OS v1.3")
        new = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if new != orig + "\n":
            p.write_text(new, encoding="utf-8")
            changed_files.append(str(p))
        return
    # 文本文件：frontmatter 与正文
    text = p.read_text(encoding="utf-8")
    new_text, cnt = apply_text(text)
    if new_text != text:
        p.write_text(new_text, encoding="utf-8")
        changed_files.append(str(p))

# 1) skills/*/SKILL.md + _meta.json
for d in sorted((ROOT / "skills").iterdir()):
    if d.is_dir():
        for f in [d / "SKILL.md", d / "_meta.json"]:
            if f.exists():
                process_file(f)

# 2) 根文档（排除历史存档与测试产物）
ROOT_FILES = [
    "AGENTS.md", "README.md", "RUNNING-GUIDE.md",
    "docs/README.md", "docs/AGENTS-TEMPLATE.md",
    "docs/PROTOCOL.md", "docs/DECISION-PROTOCOL.md", "docs/ACTION-PROTOCOL.md",
    "docs/VERIFICATION-PROTOCOL.md", "docs/MEMORY-PROTOCOL.md",
    "docs/EVOLUTION-PROTOCOL.md", "docs/HEARTBEAT-CRON-POLICY.md",
    "docs/PROTOCOL-CHECKLIST.md", "docs/SKILL-INTEGRATION.md",
    "docs/ARCHITECTURE.md", "docs/INSTALL.md", "docs/COMPATIBILITY.md",
    "docs/OPERATIONS.md", "docs/schemas/execution-record.md",
    "docs/tests/README.md", "docs/tests/cases.md", "docs/tests/evolution-e2e.md",
    "docs/tests/agent-session-e2e.md",
]
for rel in ROOT_FILES:
    p = ROOT / rel
    if p.exists():
        process_file(p)

print(f"changed {len(changed_files)} files:")
for f in changed_files:
    print("  ", f)
