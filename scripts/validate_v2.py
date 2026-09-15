#!/usr/bin/env python3
"""Static package/architecture/model-robustness gate for Agent OS v2."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
required=[
'SKILL.md','VERSION','MANIFEST.yml','docs/INSTALL.md','docs/QUICK-START.md','docs/ARCHITECTURE-V2.md','docs/CONTRACTS-V2.md','docs/V1.3-TO-V2-MIGRATION.md',
'protocols/VERIFICATION.md','protocols/EXPERIENCE.md','protocols/EVOLUTION.md','protocols/GOVERNANCE.md','protocols/MULTI-AGENT.md','protocols/NATIVE-FIRST.md','protocols/MODEL-ROBUSTNESS.md',
'native/capability-registry.json','native/README.md','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json','tests/acceptance-v2.md']
errors=[]
for p in required:
    if not (ROOT/p).is_file(): errors.append(f'missing: {p}')
for p in ['native/capability-registry.json','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json']:
    try: json.loads((ROOT/p).read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'invalid json {p}: {e}')
skill=(ROOT/'SKILL.md').read_text(encoding='utf-8') if (ROOT/'SKILL.md').exists() else ''
for term in ['Verification','Experience','Evolution','Governance','OpenClaw','multi-agent','Fast Path','Deep Path','UNKNOWN','Conservative defaults']:
    if term.lower() not in skill.lower(): errors.append(f'SKILL missing invariant: {term}')
for forbidden in ['skills/proactive','skills/orchestrator','install.sh','HEARTBEAT.prompt.md']:
    if (ROOT/forbidden).exists(): errors.append(f'legacy v1.3 runtime package still present: {forbidden}')
if 'name: agent-os' not in skill: errors.append('root SKILL name must be agent-os')
if '2.0.0-rc.2' not in skill: errors.append('root SKILL version mismatch')
accept=(ROOT/'tests/acceptance-v2.md').read_text(encoding='utf-8') if (ROOT/'tests/acceptance-v2.md').exists() else ''
for n in range(1,23):
    if f'A{n} ' not in accept: errors.append(f'missing acceptance scenario A{n}')
for p in ['SKILL.md','protocols/MULTI-AGENT.md','docs/ARCHITECTURE-V2.md']:
    t=(ROOT/p).read_text(encoding='utf-8') if (ROOT/p).exists() else ''
    pos=t.find('if agent_id == "main"')
    if pos >= 0 and 'Never' not in t[max(0,pos-160):pos]: errors.append(f'hard-coded main-agent ownership in {p}')
if errors:
    print('Agent OS v2 gate: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('Agent OS v2 gate: PASS')
print(f'checked {len(required)} artifacts, zero-config packaging, model robustness, A1-A22, and JSON contracts')