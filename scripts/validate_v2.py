#!/usr/bin/env python3
"""Static package/architecture/model/coverage/schema/legacy gate for Agent OS v2."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
required=[
'SKILL.md','VERSION','MANIFEST.yml','docs/INSTALL.md','docs/QUICK-START.md','docs/ARCHITECTURE-V2.md','docs/CONTRACTS-V2.md','docs/V1.3-TO-V2-MIGRATION.md','docs/V2-PACKAGE-POLICY.md','docs/OPENCLAW-CAPABILITY-MATRIX-V2.md','docs/V2-IMPLEMENTATION-STATUS.md',
'protocols/VERIFICATION.md','protocols/EXPERIENCE.md','protocols/EVOLUTION.md','protocols/GOVERNANCE.md','protocols/MULTI-AGENT.md','protocols/NATIVE-FIRST.md','protocols/MODEL-ROBUSTNESS.md','protocols/AUTOMATIC-COVERAGE.md',
'native/capability-registry.json','native/README.md','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json','schemas/verification-result.schema.json','schemas/delegation-trace.schema.json','schemas/capability.schema.json','tests/acceptance-v2.md']
errors=[]
for p in required:
    if not (ROOT/p).is_file(): errors.append(f'missing: {p}')
json_files=['native/capability-registry.json','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json','schemas/verification-result.schema.json','schemas/delegation-trace.schema.json','schemas/capability.schema.json']
for p in json_files:
    try: json.loads((ROOT/p).read_text(encoding='utf-8'))
    except Exception as e: errors.append(f'invalid json {p}: {e}')
skill=(ROOT/'SKILL.md').read_text(encoding='utf-8') if (ROOT/'SKILL.md').exists() else ''
for term in ['Verification','Experience','Evolution','Governance','OpenClaw','multi-agent','Fast Path','Deep Path','UNKNOWN','Automatic coverage','C0 IGNORE','C3 DEEP ADAPT','Deduplicate']:
    if term.lower() not in skill.lower(): errors.append(f'SKILL missing invariant: {term}')
for forbidden in ['skills','install.sh','HEARTBEAT.prompt.md','docs/tests','docs/archive','docs/schemas','docs/ARCHITECTURE.md','docs/PROTOCOL.md','docs/MEMORY-PROTOCOL.md','docs/HEARTBEAT-CRON-POLICY.md','docs/SKILL-MAP.md']:
    if (ROOT/forbidden).exists(): errors.append(f'legacy v1.3 package artifact still present: {forbidden}')
if 'name: agent-os' not in skill: errors.append('root SKILL name must be agent-os')
if '2.0.0-rc.3' not in skill: errors.append('root SKILL version mismatch')
accept=(ROOT/'tests/acceptance-v2.md').read_text(encoding='utf-8') if (ROOT/'tests/acceptance-v2.md').exists() else ''
for n in range(1,31):
    if f'A{n} ' not in accept: errors.append(f'missing acceptance scenario A{n}')
coverage=(ROOT/'protocols/AUTOMATIC-COVERAGE.md').read_text(encoding='utf-8') if (ROOT/'protocols/AUTOMATIC-COVERAGE.md').exists() else ''
for term in ['C0 Ignore','C1 Verify','C2 Learn','C3 Deep adapt','Automatic does not mean omniscient','Deduplication','Contradiction','Recall policy']:
    if term.lower() not in coverage.lower(): errors.append(f'coverage protocol missing: {term}')
for p in ['SKILL.md','protocols/MULTI-AGENT.md','docs/ARCHITECTURE-V2.md']:
    t=(ROOT/p).read_text(encoding='utf-8') if (ROOT/p).exists() else ''
    pos=t.find('if agent_id == "main"')
    if pos >= 0 and 'Never' not in t[max(0,pos-160):pos]: errors.append(f'hard-coded main-agent ownership in {p}')
retired_refs=['skills/proactive','skills/task-manager','skills/orchestrator','skills/self-evolution','skills/context-orchestration','skills/summarize','skills/memory-governance','skills/knowledge-governance','skills/verification-evaluation','skills/permission-security','skills/agent-os-vault']
scan_roots=[ROOT/'scripts',ROOT/'tests',ROOT/'.github'/'workflows']
text_ext={'.py','.sh','.ps1','.js','.mjs','.cjs','.ts','.tsx','.yml','.yaml'}
for base in scan_roots:
    if not base.exists(): continue
    for path in base.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in text_ext: continue
        try: text=path.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        for ref in retired_refs:
            if ref in text: errors.append(f'executable legacy reference: {path.relative_to(ROOT)} -> {ref}')
# Contract-shape sentinels for known RC3 drift regressions.
try:
    ai=json.loads((ROOT/'schemas/agent-identity.schema.json').read_text())
    if 'UNKNOWN' not in ai['properties']['kind']['enum'] or ai.get('additionalProperties') is not False: errors.append('agent identity schema is not frozen')
    ex=json.loads((ROOT/'schemas/experience.schema.json').read_text())
    if 'contradicts' not in ex['properties'] or ex.get('additionalProperties') is not False: errors.append('experience schema is not frozen')
    ev=json.loads((ROOT/'schemas/evolution-candidate.schema.json').read_text())
    if 'experience_ids' not in ev['properties'] or 'experiences' in ev['properties']: errors.append('evolution candidate schema uses stale experience field')
    reg=json.loads((ROOT/'native/capability-registry.json').read_text())
    if reg.get('runtime_detection') is not False: errors.append('capability registry must not claim runtime detection')
except Exception as e: errors.append(f'contract sentinel failed: {e}')
if errors:
    print('Agent OS v2 gate: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('Agent OS v2 gate: PASS')
print(f'checked {len(required)} canonical artifacts, A1-A30, frozen JSON contracts, declarative native boundary, and absence of v1.3 package artifacts')
