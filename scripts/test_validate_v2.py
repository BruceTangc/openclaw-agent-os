#!/usr/bin/env python3
"""Mutation tests for validate_v2.py. Uses an isolated temporary copy; never mutates the checkout."""
from pathlib import Path
import shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[1]

def run(root):
    p=subprocess.run([sys.executable,str(root/'scripts/validate_v2.py')],cwd=root,text=True,capture_output=True)
    return p.returncode,p.stdout+p.stderr

def copy_repo():
    td=tempfile.TemporaryDirectory()
    dst=Path(td.name)/'repo'
    shutil.copytree(ROOT,dst,ignore=shutil.ignore_patterns('.git','__pycache__'))
    return td,dst

def expect(name,mutate,should_pass):
    td,dst=copy_repo()
    try:
        mutate(dst)
        code,out=run(dst)
        ok=(code==0)==should_pass
        print(f'{name}: {"PASS" if ok else "FAIL"}')
        if not ok:
            print(out); return False
        return True
    finally: td.cleanup()

cases=[]
cases.append(('clean',lambda r:None,True))
cases.append(('missing-required',lambda r:(r/'protocols/VERIFICATION.md').unlink(),False))
cases.append(('invalid-json',lambda r:(r/'schemas/experience.schema.json').write_text('{',encoding='utf-8'),False))
cases.append(('legacy-artifact',lambda r:(r/'skills').mkdir(),False))
cases.append(('legacy-literal',lambda r:(r/'tests/fake_legacy.py').write_text('x="skills/self-evolution"\n',encoding='utf-8'),False))
cases.append(('legacy-os-join',lambda r:(r/'tests/fake_legacy.py').write_text('import os\nx=os.path.join("skills","self-evolution")\n',encoding='utf-8'),False))
cases.append(('legacy-path-div',lambda r:(r/'tests/fake_legacy.py').write_text('from pathlib import Path\nx=Path("skills")/"self-evolution"\n',encoding='utf-8'),False))
cases.append(('legacy-constant-add',lambda r:(r/'tests/fake_legacy.py').write_text('a="skills/"\nb="self-evolution"\nx=a+b\n',encoding='utf-8'),False))
cases.append(('unrelated-join',lambda r:(r/'tests/fake_ok.py').write_text('import os\nx=os.path.join("skills2","self-evolution")\n',encoding='utf-8'),True))

ok=all(expect(*c) for c in cases)
if not ok: sys.exit(1)
print(f'validate_v2 mutation suite: PASS ({len(cases)} cases)')
