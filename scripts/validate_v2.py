#!/usr/bin/env python3
"""Fail-closed static package/architecture/schema/legacy gate for Agent OS v2."""
from pathlib import Path
import ast, json, sys
ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
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

def norm(s): return s.replace('\\','/').replace('//','/').strip('./')
def is_retired(s):
    n=norm(s)
    return any(r in n for r in retired_refs)
def dotted(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute):
        b=dotted(node.value); return f'{b}.{node.attr}' if b else node.attr
    return ''
def const_text(node, env):
    if isinstance(node,ast.Constant) and isinstance(node.value,str): return node.value
    if isinstance(node,ast.Name): return env.get(node.id)
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
        a,b=const_text(node.left,env),const_text(node.right,env)
        return a+b if a is not None and b is not None else None
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
        a,b=const_text(node.left,env),const_text(node.right,env)
        return f'{a}/{b}' if a is not None and b is not None else None
    if isinstance(node,ast.Call) and dotted(node.func) in {'os.path.join','posixpath.join','ntpath.join'}:
        parts=[const_text(a,env) for a in node.args]
        return '/'.join(p.strip('/\\') for p in parts) if parts and all(p is not None for p in parts) else None
    if isinstance(node,ast.Call) and dotted(node.func) in {'Path','pathlib.Path','PurePath','pathlib.PurePath'}:
        parts=[const_text(a,env) for a in node.args]
        return '/'.join(p.strip('/\\') for p in parts) if parts and all(p is not None for p in parts) else None
    if isinstance(node,ast.JoinedStr):
        out=''
        for v in node.values:
            if isinstance(v,ast.Constant) and isinstance(v.value,str): out+=v.value
            elif isinstance(v,ast.FormattedValue):
                x=const_text(v.value,env)
                if x is None: return None
                out+=x
            else: return None
        return out
    return None

def scan_python(path,text):
    try: tree=ast.parse(text,filename=str(path))
    except SyntaxError as e:
        errors.append(f'python parse failure: {path.relative_to(ROOT)}:{e.lineno}: {e.msg}')
        return
    env={}
    # Conservative constant propagation for simple module/function assignments.
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            value=node.value
            v=const_text(value,env) if value is not None else None
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if v is not None:
                for t in targets:
                    if isinstance(t,ast.Name): env[t.id]=v
    seen=set()
    for node in ast.walk(tree):
        v=const_text(node,env)
        if v is not None and is_retired(v):
            key=(getattr(node,'lineno',0),norm(v))
            if key not in seen:
                seen.add(key); errors.append(f'executable legacy reference: {path.relative_to(ROOT)}:{key[0]} -> {key[1]}')

scan_roots=[ROOT/'scripts',ROOT/'tests',ROOT/'.github'/'workflows']
text_ext={'.py','.sh','.ps1','.js','.mjs','.cjs','.ts','.tsx','.yml','.yaml'}
for base in scan_roots:
    if not base.exists(): continue
    for path in base.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in text_ext or path.resolve()==SELF: continue
        try: text=path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            errors.append(f'non-utf8 executable text: {path.relative_to(ROOT)}'); continue
        # Exact textual form catches all runnable languages; Python additionally gets AST folding.
        for ref in retired_refs:
            if ref in norm(text): errors.append(f'executable legacy reference: {path.relative_to(ROOT)} -> {ref}')
        if path.suffix.lower()=='.py': scan_python(path,text)
try:
    ai=json.loads((ROOT/'schemas/agent-identity.schema.json').read_text(encoding='utf-8'))
    if 'UNKNOWN' not in ai['properties']['kind']['enum'] or ai.get('additionalProperties') is not False: errors.append('agent identity schema is not frozen')
    ex=json.loads((ROOT/'schemas/experience.schema.json').read_text(encoding='utf-8'))
    if 'contradicts' not in ex['properties'] or ex.get('additionalProperties') is not False: errors.append('experience schema is not frozen')
    ev=json.loads((ROOT/'schemas/evolution-candidate.schema.json').read_text(encoding='utf-8'))
    if 'experience_ids' not in ev['properties'] or 'experiences' in ev['properties']: errors.append('evolution candidate schema uses stale experience field')
    reg=json.loads((ROOT/'native/capability-registry.json').read_text(encoding='utf-8'))
    if reg.get('runtime_detection') is not False: errors.append('capability registry must not claim runtime detection')
except Exception as e: errors.append(f'contract sentinel failed: {e}')
if errors:
    print('Agent OS v2 gate: FAIL')
    for e in dict.fromkeys(errors): print('-',e)
    sys.exit(1)
print('Agent OS v2 gate: PASS')
print(f'checked {len(required)} canonical artifacts, A1-A30, frozen JSON contracts, declarative native boundary, AST-aware legacy references, and absence of v1.3 package artifacts')
