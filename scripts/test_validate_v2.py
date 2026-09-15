#!/usr/bin/env python3
"""Mutation tests for validate_v2.py. Uses an isolated temporary copy; never mutates the checkout."""
from pathlib import Path
import json, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]

def run(root):
    p=subprocess.run([sys.executable,str(root/'scripts/validate_v2.py')],cwd=root,text=True,capture_output=True)
    return p.returncode,p.stdout+p.stderr

def copy_repo():
    td=tempfile.TemporaryDirectory(); dst=Path(td.name)/'repo'
    shutil.copytree(ROOT,dst,ignore=shutil.ignore_patterns('.git','__pycache__'))
    return td,dst

def expect(name,mutate,should_pass):
    td,dst=copy_repo()
    try:
        mutate(dst); code,out=run(dst); ok=(code==0)==should_pass
        print(f'{name}: {"PASS" if ok else "FAIL"}')
        if not ok: print(out); return False
        return True
    finally: td.cleanup()

def mutate_json(rel,fn):
    def m(r):
        p=r/rel; obj=json.loads(p.read_text(encoding='utf-8')); fn(obj); p.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    return m

def drop_a34(r):
    p=r/'tests/acceptance-v2.md'; t=p.read_text(encoding='utf-8'); i=t.index('### A34 '); p.write_text(t[:i],encoding='utf-8')
def duplicate_a10(r):
    p=r/'tests/acceptance-v2.md'; t=p.read_text(encoding='utf-8'); p.write_text(t.replace('### A11 ','### A10 ',1),encoding='utf-8')
def bad_version(r):
    (r/'VERSION').write_text('9.9.9-bad\n',encoding='utf-8')

def bad_evidence_source(o): o['properties']['source']['enum'].append('ANYTHING')
def open_experience(o): o['additionalProperties']=True
def remove_evolution_field(o): o['properties'].pop('risk',None)
def bad_confidence(o): o['properties']['confidence']['maximum']=100
def bad_identity_ref(o): o['properties']['identity']={'type':'object'}

cases=[
('clean',lambda r:None,True),
('missing-required',lambda r:(r/'protocols/VERIFICATION.md').unlink(),False),
('invalid-json',lambda r:(r/'schemas/experience.schema.json').write_text('{',encoding='utf-8'),False),
('legacy-artifact',lambda r:(r/'skills').mkdir(),False),
('legacy-literal',lambda r:(r/'tests/fake_legacy.py').write_text('x="skills/self-evolution"\n',encoding='utf-8'),False),
('legacy-os-join',lambda r:(r/'tests/fake_legacy.py').write_text('import os\nx=os.path.join("skills","self-evolution")\n',encoding='utf-8'),False),
('legacy-path-div',lambda r:(r/'tests/fake_legacy.py').write_text('from pathlib import Path\nx=Path("skills")/"self-evolution"\n',encoding='utf-8'),False),
('legacy-constant-add',lambda r:(r/'tests/fake_legacy.py').write_text('a="skills/"\nb="self-evolution"\nx=a+b\n',encoding='utf-8'),False),
('unrelated-join',lambda r:(r/'tests/fake_ok.py').write_text('import os\nx=os.path.join("skills2","self-evolution")\n',encoding='utf-8'),True),
('missing-a34',drop_a34,False),
('duplicate-acceptance-id',duplicate_a10,False),
('version-drift',bad_version,False),
('schema-enum-drift',mutate_json('schemas/evidence.schema.json',bad_evidence_source),False),
('schema-open-object',mutate_json('schemas/experience.schema.json',open_experience),False),
('schema-field-drift',mutate_json('schemas/evolution-candidate.schema.json',remove_evolution_field),False),
('schema-confidence-drift',mutate_json('schemas/verification-result.schema.json',bad_confidence),False),
('schema-ref-drift',mutate_json('schemas/evidence.schema.json',bad_identity_ref),False),
]
ok=all(expect(*c) for c in cases)
if not ok: sys.exit(1)
print(f'validate_v2 mutation suite: PASS ({len(cases)} cases)')
