#!/usr/bin/env python3
"""Fail-closed static package/architecture/schema/legacy gate for Agent OS v2."""
from pathlib import Path
import ast, json, re, sys
ROOT=Path(__file__).resolve().parents[1]; SELF=Path(__file__).resolve(); MUTATION_SELF=(ROOT/'scripts/test_validate_v2.py').resolve(); ACCEPTANCE_MAX=34
required=['SKILL.md','VERSION','MANIFEST.yml','README.md','docs/INSTALL.md','docs/QUICK-START.md','docs/ARCHITECTURE-V2.md','docs/CONTRACTS-V2.md','docs/V1.3-TO-V2-MIGRATION.md','docs/V2-PACKAGE-POLICY.md','docs/OPENCLAW-CAPABILITY-MATRIX-V2.md','docs/V2-IMPLEMENTATION-STATUS.md','protocols/VERIFICATION.md','protocols/EXPERIENCE.md','protocols/EVOLUTION.md','protocols/GOVERNANCE.md','protocols/MULTI-AGENT.md','protocols/NATIVE-FIRST.md','protocols/MODEL-ROBUSTNESS.md','protocols/AUTOMATIC-COVERAGE.md','native/capability-registry.json','native/README.md','schemas/evidence.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json','schemas/agent-identity.schema.json','schemas/verification-result.schema.json','schemas/delegation-trace.schema.json','schemas/capability.schema.json','tests/acceptance-v2.md','scripts/test_validate_v2.py']
errors=[]
for p in required:
    if not (ROOT/p).is_file():errors.append(f'missing: {p}')
def read(p):
    try:return (ROOT/p).read_text(encoding='utf-8')
    except Exception as e:errors.append(f'unreadable {p}: {e}');return ''
def load_json(p):
    try:return json.loads(read(p))
    except Exception as e:errors.append(f'invalid json {p}: {e}');return {}
objs={p:load_json(p) for p in required if p.endswith('.json') and (ROOT/p).exists()}
skill=read('SKILL.md')
for term in ['Verification','Experience','Evolution','Governance','OpenClaw','multi-agent','Fast Path','Deep Path','UNKNOWN','Automatic coverage','C0 IGNORE','C3 DEEP ADAPT','Deduplicate','Evidence != VerificationResult','APPROVED != APPLIED != VERIFIED','Acceptance truth boundary']:
    if term.lower() not in skill.lower():errors.append(f'SKILL missing invariant: {term}')
for forbidden in ['skills','install.sh','HEARTBEAT.prompt.md','docs/tests','docs/archive','docs/schemas','docs/ARCHITECTURE.md','docs/PROTOCOL.md','docs/MEMORY-PROTOCOL.md','docs/HEARTBEAT-CRON-POLICY.md','docs/SKILL-MAP.md']:
    if (ROOT/forbidden).exists():errors.append(f'legacy v1.3 package artifact still present: {forbidden}')
if 'name: agent-os' not in skill:errors.append('root SKILL name must be agent-os')
version=read('VERSION').strip();manifest=read('MANIFEST.yml')
if not version:errors.append('VERSION is empty')
if version and f'version: {version}' not in skill:errors.append('SKILL/VERSION mismatch')
if version and f'version: {version}' not in manifest:errors.append('MANIFEST/VERSION mismatch')
if version and version not in read('README.md'):errors.append('README/VERSION mismatch')
m=re.search(r'^\s*acceptance_scenarios:\s*(\d+)\s*$',manifest,re.M)
if not m or int(m.group(1))!=ACCEPTANCE_MAX:errors.append(f'MANIFEST acceptance_scenarios must be {ACCEPTANCE_MAX}')
accept=read('tests/acceptance-v2.md')
scenario_matches=list(re.finditer(r'^###\s+A(\d+)\b[^\n]*\n',accept,re.M));ids=[int(m.group(1)) for m in scenario_matches]
if ids!=list(range(1,ACCEPTANCE_MAX+1)):errors.append(f'acceptance headings must be exactly A1-A{ACCEPTANCE_MAX} in order; got {ids}')
# Structural-only acceptance audit: prevent hollow scenarios without pretending static CI executes semantics.
for i,mch in enumerate(scenario_matches):
    sid=int(mch.group(1)); end=scenario_matches[i+1].start() if i+1<len(scenario_matches) else accept.find('\n## Model matrix',mch.end())
    if end<0:end=len(accept)
    body=accept[mch.end():end]
    for field in ['Preconditions','Action','Expected','Failure']:
        fm=re.search(rf'^\*\*{field}:\*\*\s*(.+?)\s*$',body,re.M)
        if not fm or not fm.group(1).strip():errors.append(f'A{sid} missing/non-empty {field} field')
coverage=read('protocols/AUTOMATIC-COVERAGE.md')
for term in ['C0 Ignore','C1 Verify','C2 Learn','C3 Deep adapt','Automatic does not mean omniscient','Deduplication','Contradiction','Recall policy']:
    if term.lower() not in coverage.lower():errors.append(f'coverage protocol missing: {term}')
for p in ['SKILL.md','protocols/MULTI-AGENT.md','docs/ARCHITECTURE-V2.md']:
    t=read(p);pos=t.find('if agent_id == "main"')
    if pos>=0 and 'Never' not in t[max(0,pos-160):pos]:errors.append(f'hard-coded main-agent ownership in {p}')
def schema(path):return objs.get(path,{})
def assert_object_schema(path,props,req):
    s=schema(path)
    if s.get('$schema')!='https://json-schema.org/draft/2020-12/schema':errors.append(f'{path}: wrong/missing metaschema')
    if s.get('type')!='object' or s.get('additionalProperties') is not False:errors.append(f'{path}: must be closed object schema')
    if set(s.get('required',[]))!=set(req):errors.append(f'{path}: required fields drift')
    if set(s.get('properties',{}))!=set(props):errors.append(f'{path}: properties drift')
assert_object_schema('schemas/agent-identity.schema.json',['agent_id','kind','root_agent_id','requester_agent_id','parent_agent_id','session_id','parent_session_id','task_id','parent_task_id','delegation_path'],['agent_id','kind','session_id','delegation_path'])
assert_object_schema('schemas/evidence.schema.json',['id','timestamp','source','identity','goal','success_criteria','action','observation','feedback','scope','confidence','provenance'],['id','timestamp','source','identity','goal','success_criteria','action','observation','feedback','scope','confidence','provenance'])
assert_object_schema('schemas/verification-result.schema.json',['id','target','status','criteria_results','reason','confidence'],['id','target','status','criteria_results','reason','confidence'])
assert_object_schema('schemas/experience.schema.json',['id','derived_from','type','situation','action','outcome','lesson','confidence','occurrences','scope','owner_agent_id','team_id','contradicts'],['id','derived_from','type','situation','action','outcome','lesson','confidence','occurrences','scope','owner_agent_id','team_id','contradicts'])
assert_object_schema('schemas/evolution-candidate.schema.json',['id','experience_ids','pattern','hypothesis','target','expected_improvement','proposed_change','confidence','risk','status'],['id','experience_ids','pattern','hypothesis','target','expected_improvement','proposed_change','confidence','risk','status'])
assert_object_schema('schemas/delegation-trace.schema.json',['requester_agent_id','executor_agent_id','root_agent_id','parent_task_id','child_task_id','requester_session_id','executor_session_id','delegated_goal','success_criteria','artifact_refs'],['requester_agent_id','executor_agent_id','root_agent_id','parent_task_id','child_task_id','requester_session_id','executor_session_id','delegated_goal','success_criteria','artifact_refs'])
assert_object_schema('schemas/capability.schema.json',['id','provider','support','version_hint','contract_version','notes'],['id','provider','support','version_hint','contract_version','notes'])
def enum(path,prop,expected):
    got=schema(path).get('properties',{}).get(prop,{}).get('enum')
    if got!=expected:errors.append(f'{path}.{prop}: enum drift: {got}')
enum('schemas/agent-identity.schema.json','kind',['ROOT','PERMANENT','SPECIALIST','SUBAGENT','ACP','UNKNOWN']);enum('schemas/evidence.schema.json','source',['TOOL','ENVIRONMENT','USER','AGENT','TEST','REVIEW','NATIVE_EVENT']);enum('schemas/evidence.schema.json','scope',['RUN','SESSION','TASK','DELEGATION']);enum('schemas/verification-result.schema.json','target',['RUN','TASK','DELEGATION','USER_OUTCOME']);enum('schemas/verification-result.schema.json','status',['PASS','PARTIAL','FAIL','UNKNOWN']);enum('schemas/experience.schema.json','type',['SUCCESS','FAILURE','WORKFLOW','TOOL','DELEGATION','USER_INTERACTION']);enum('schemas/experience.schema.json','scope',['AGENT','TEAM','SHARED']);enum('schemas/evolution-candidate.schema.json','target',['AGENT','TEAM','SKILL','WORKFLOW','SHARED_PROTOCOL']);enum('schemas/evolution-candidate.schema.json','risk',['LOW','MEDIUM','HIGH','CRITICAL']);enum('schemas/evolution-candidate.schema.json','status',['CANDIDATE','REVIEW','APPROVED','REJECTED','APPLIED','VERIFIED']);enum('schemas/capability.schema.json','provider',['OPENCLAW_NATIVE','OPENCLAW_OFFICIAL_PLUGIN','AGENT_OS_ADAPTER','AGENT_OS_FALLBACK']);enum('schemas/capability.schema.json','support',['FULL','PARTIAL','NONE'])
if schema('schemas/evidence.schema.json').get('properties',{}).get('identity',{}).get('$ref')!='agent-identity.schema.json':errors.append('evidence.identity must reference agent identity schema')
for p in ['schemas/evidence.schema.json','schemas/verification-result.schema.json','schemas/experience.schema.json','schemas/evolution-candidate.schema.json']:
    c=schema(p).get('properties',{}).get('confidence',{})
    if c.get('minimum')!=0 or c.get('maximum')!=1:errors.append(f'{p}.confidence must be 0..1')
reg=objs.get('native/capability-registry.json',{})
if reg.get('runtime_detection') is not False:errors.append('capability registry must not claim runtime detection')
if reg.get('registry_kind')!='declarative-boundary':errors.append('capability registry must remain declarative-boundary')
retired_refs=['skills/proactive','skills/task-manager','skills/orchestrator','skills/self-evolution','skills/context-orchestration','skills/summarize','skills/memory-governance','skills/knowledge-governance','skills/verification-evaluation','skills/permission-security','skills/agent-os-vault']
def norm(s):return s.replace('\\','/').replace('//','/').strip('./')
def is_retired(s):return any(r in norm(s) for r in retired_refs)
def dotted(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):
        b=dotted(node.value);return f'{b}.{node.attr}' if b else node.attr
    return ''
def const_text(node,env):
    if isinstance(node,ast.Constant) and isinstance(node.value,str):return node.value
    if isinstance(node,ast.Name):return env.get(node.id)
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):
        a,b=const_text(node.left,env),const_text(node.right,env);return a+b if a is not None and b is not None else None
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
        a,b=const_text(node.left,env),const_text(node.right,env);return f'{a}/{b}' if a is not None and b is not None else None
    if isinstance(node,ast.Call) and dotted(node.func) in {'os.path.join','posixpath.join','ntpath.join','Path','pathlib.Path','PurePath','pathlib.PurePath'}:
        parts=[const_text(a,env) for a in node.args];return '/'.join(p.strip('/\\') for p in parts) if parts and all(p is not None for p in parts) else None
    return None
def scan_python(path,text):
    try:tree=ast.parse(text,filename=str(path))
    except SyntaxError as e:errors.append(f'python parse failure: {path.relative_to(ROOT)}:{e.lineno}: {e.msg}');return
    env={}
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            v=const_text(node.value,env) if node.value is not None else None;targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if v is not None:
                for t in targets:
                    if isinstance(t,ast.Name):env[t.id]=v
    for node in ast.walk(tree):
        v=const_text(node,env)
        if v is not None and is_retired(v):errors.append(f'executable legacy reference: {path.relative_to(ROOT)}:{getattr(node,"lineno",0)} -> {norm(v)}')
for base in [ROOT/'scripts',ROOT/'tests',ROOT/'.github'/'workflows']:
    if not base.exists():continue
    for path in base.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in {'.py','.sh','.ps1','.js','.mjs','.cjs','.ts','.tsx','.yml','.yaml'} or path.resolve() in {SELF,MUTATION_SELF}:continue
        try:text=path.read_text(encoding='utf-8')
        except UnicodeDecodeError:errors.append(f'non-utf8 executable text: {path.relative_to(ROOT)}');continue
        for ref in retired_refs:
            if ref in norm(text):errors.append(f'executable legacy reference: {path.relative_to(ROOT)} -> {ref}')
        if path.suffix.lower()=='.py':scan_python(path,text)
if errors:
    print('Agent OS v2 gate: FAIL')
    for e in dict.fromkeys(errors):print('-',e)
    sys.exit(1)
print('Agent OS v2 gate: PASS')
print(f'checked {len(required)} canonical artifacts, structured A1-A{ACCEPTANCE_MAX} specs, frozen schema contracts, version/manifest coherence, declarative native boundary, AST-aware legacy references, and absence of v1.3 package artifacts; runtime acceptance is NOT implied')
