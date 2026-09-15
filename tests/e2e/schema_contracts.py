#!/usr/bin/env python3
"""Executable A34 JSON-Schema contract test. Requires jsonschema."""
from pathlib import Path
import json, sys
try:
    from jsonschema import Draft202012Validator, RefResolver, ValidationError
except ImportError:
    print('BLOCKED: install jsonschema (python -m pip install jsonschema)',file=sys.stderr); raise SystemExit(2)
ROOT=Path(__file__).resolve().parents[2]; S=ROOT/'schemas'
def load(name): return json.loads((S/name).read_text(encoding='utf-8'))
files=['agent-identity.schema.json','delegation-trace.schema.json','evidence.schema.json','verification-result.schema.json','experience.schema.json','evolution-candidate.schema.json','capability.schema.json']
schemas={n:load(n) for n in files}
store={n:s for n,s in schemas.items()}
def valid(name,obj):
    Draft202012Validator(schemas[name],resolver=RefResolver.from_schema(schemas[name],store=store)).validate(obj)
identity={'agent_id':'agent-1','kind':'PERMANENT','session_id':'s1','delegation_path':[]}
evidence={'id':'ev1','timestamp':'2026-01-01T00:00:00Z','source':'TOOL','identity':identity,'goal':'g','success_criteria':['c'],'action':'a','observation':'o','feedback':None,'scope':'TASK','confidence':0.8,'provenance':['tool:x']}
verification={'id':'vr1','target':'TASK','status':'PASS','criteria_results':[{'criterion':'c','status':'PASS','evidence_ids':['ev1']}],'reason':'supported','confidence':0.8}
experience={'id':'ex1','derived_from':['ev1'],'type':'SUCCESS','situation':'s','action':'a','outcome':'o','lesson':'l','confidence':0.8,'occurrences':1,'scope':'AGENT','owner_agent_id':'agent-1','team_id':None,'contradicts':[]}
evolution={'id':'ec1','experience_ids':['ex1'],'pattern':'p','hypothesis':'h','target':'AGENT','expected_improvement':'i','proposed_change':'c','confidence':0.7,'risk':'LOW','status':'CANDIDATE'}
delegation={'requester_agent_id':'agent-1','executor_agent_id':'agent-2','root_agent_id':'agent-1','parent_task_id':'t1','child_task_id':'t2','requester_session_id':'s1','executor_session_id':'s2','delegated_goal':'g','success_criteria':['c'],'artifact_refs':[]}
capability={'id':'memory','provider':'OPENCLAW_NATIVE','support':'FULL','version_hint':None,'contract_version':'2.0','notes':None}
valids=[('agent-identity.schema.json',identity),('delegation-trace.schema.json',delegation),('evidence.schema.json',evidence),('verification-result.schema.json',verification),('experience.schema.json',experience),('evolution-candidate.schema.json',evolution),('capability.schema.json',capability)]
for n,o in valids: valid(n,o)
invalid=[]
def reject(name,obj,label):
    try: valid(name,obj)
    except ValidationError: return
    invalid.append(label)
x=dict(evidence);x['provenance']='not-an-array';reject('evidence.schema.json',x,'provenance type')
x=dict(evidence);x['source']='ARBITRARY';reject('evidence.schema.json',x,'source enum')
x=dict(evolution);x['experiences']=x.pop('experience_ids');reject('evolution-candidate.schema.json',x,'stale experiences')
x=dict(identity);x['kind']='NOT_A_KIND';reject('agent-identity.schema.json',x,'kind enum')
x=dict(capability);x['extra']=1;reject('capability.schema.json',x,'extra property')
if invalid: print('A34 FAIL:',', '.join(invalid)); raise SystemExit(1)
print('A34 PASS: 7 valid contract objects accepted; 5 drift cases rejected')
