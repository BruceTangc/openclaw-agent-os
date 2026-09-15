#!/usr/bin/env python3
"""Static architecture gate for Agent OS v2. No third-party dependencies."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
required=[
'SKILL.md','docs/ARCHITECTURE-V2.md','docs/CONTRACTS-V2.md','docs/V1.3-TO-V2-MIGRATION.md',
'protocols/VERIFICATION.md','protocols/EXPERIENCE.md','protocols/EVOLUTION.md','protocols/GOVERNANCE.md','protocols/MULTI-AGENT.md','protocols/NATIVE-FIRST.md',
'native/capability-registry.json','native/README.md','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json','tests/acceptance-v2.md']
errors=[]
for p in required:
    if not (ROOT/p).is_file(): errors.append(f'missing: {p}')
for p in ['native/capability-registry.json','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json']:
    try: json.loads((ROOT/p).read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'invalid json {p}: {e}')
skill=(ROOT/'SKILL.md').read_text(encoding='utf-8') if (ROOT/'SKILL.md').exists() else ''
for term in ['Verification','Experience','Evolution','Governance','OpenClaw','multi-agent']:
    if term.lower() not in skill.lower(): errors.append(f'SKILL missing invariant: {term}')
# Guard against the most dangerous architectural regression.
for p in ['SKILL.md','protocols/MULTI-AGENT.md','docs/ARCHITECTURE-V2.md']:
    t=(ROOT/p).read_text(encoding='utf-8') if (ROOT/p).exists() else ''
    if 'if agent_id == "main"' in t and 'Never' not in t[max(0,t.find('if agent_id == "main"')-100):t.find('if agent_id == "main"')]:
        errors.append(f'hard-coded main-agent ownership in {p}')
if errors:
    print('Agent OS v2 gate: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('Agent OS v2 gate: PASS')
print(f'checked {len(required)} required artifacts and stable JSON contracts')
