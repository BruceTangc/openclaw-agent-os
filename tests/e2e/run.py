#!/usr/bin/env python3
"""Drive Agent OS acceptance scenarios through a real OpenClaw CLI.

This is intentionally outside Agent OS runtime. It is a test harness only.
Default runtime adapter uses: openclaw agent --message <prompt> --json
Override with OPENCLAW_E2E_COMMAND containing {prompt}, e.g.
  OPENCLAW_E2E_COMMAND='openclaw agent --agent main --message {prompt} --json'
"""
from pathlib import Path
import argparse, json, os, shlex, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=Path(__file__).with_name('scenarios.json')
RESULTS=Path(__file__).with_name('results')

def run_cmd(cmd,timeout=180):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
    return p.returncode,p.stdout,p.stderr

def runtime_cmd(prompt):
    template=os.environ.get('OPENCLAW_E2E_COMMAND')
    if template:
        # {prompt} is replaced as one shell token after shlex parsing via sentinel.
        sentinel='__AGENT_OS_E2E_PROMPT__'
        parts=shlex.split(template.replace('{prompt}',sentinel))
        return [prompt if x==sentinel else x for x in parts]
    return ['openclaw','agent','--message',prompt,'--json']

def response_text(stdout):
    try:
        obj=json.loads(stdout)
    except Exception:
        return stdout
    # OpenClaw JSON shape can evolve; collect human text without declaring a private API.
    found=[]
    def walk(x):
        if isinstance(x,str): found.append(x)
        elif isinstance(x,list):
            for v in x: walk(v)
        elif isinstance(x,dict):
            for k,v in x.items():
                if k.lower() in {'text','content','message','output','response','result'}: walk(v)
    walk(obj)
    return '\n'.join(found) or stdout

def judge_text(text,a):
    low=text.lower(); failures=[]
    for x in a.get('required_all',[]):
        if x.lower() not in low: failures.append(f'missing required: {x}')
    anyv=a.get('required_any',[])
    if anyv and not any(x.lower() in low for x in anyv): failures.append(f'missing any of: {anyv}')
    for x in a.get('forbidden',[]):
        if x.lower() in low: failures.append(f'forbidden present: {x}')
    return failures

def run_scenario(s):
    mode=s['mode']; started=time.time(); evidence={}
    if mode=='runtime':
        cmd=runtime_cmd(s['prompt']); code,out,err=run_cmd(cmd)
        text=response_text(out); failures=[] if code==0 else [f'OpenClaw exit={code}']
        failures+=judge_text(text,s.get('assert',{})); evidence={'command':cmd[:-1]+['<prompt>'],'stdout':out,'stderr':err,'response_text':text}
    elif mode=='environment':
        code,out,err=run_cmd(s['command']); failures=[] if code==0 else [f'command exit={code}']
        needle=s.get('assert',{}).get('json_contains')
        if needle and needle.lower() not in out.lower(): failures.append(f'output missing: {needle}')
        evidence={'command':s['command'],'stdout':out,'stderr':err}
    elif mode=='static-schema':
        code,out,err=run_cmd(s['command']); failures=[] if code==s.get('assert',{}).get('exit_code',0) else [f'command exit={code}']
        evidence={'command':s['command'],'stdout':out,'stderr':err}
    else:
        failures=[f'unsupported mode: {mode}']
    return {'id':s['id'],'mode':mode,'verdict':'PASS' if not failures else 'FAIL','failures':failures,'duration_s':round(time.time()-started,3),'evidence':evidence}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--scenario',action='append',help='A9 (repeatable)'); ap.add_argument('--model-label',default=os.environ.get('OPENCLAW_E2E_MODEL','unspecified')); ap.add_argument('--list',action='store_true'); args=ap.parse_args()
    data=json.loads(MANIFEST.read_text(encoding='utf-8')); scenarios=data['scenarios']
    if args.list:
        for s in scenarios: print(s['id'],s['mode']); return 0
    wanted=set(args.scenario or [])
    if wanted: scenarios=[s for s in scenarios if s['id'] in wanted]
    if not scenarios: print('no scenarios selected',file=sys.stderr); return 2
    RESULTS.mkdir(exist_ok=True)
    report={'kind':'agent-os-openclaw-runtime-e2e','model_label':args.model_label,'skill_version':(ROOT/'VERSION').read_text().strip(),'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'results':[]}
    for s in scenarios:
        print(f"[{s['id']}] {s['mode']} ...",flush=True)
        try:r=run_scenario(s)
        except FileNotFoundError as e:r={'id':s['id'],'mode':s['mode'],'verdict':'BLOCKED','failures':[str(e)],'evidence':{}}
        except subprocess.TimeoutExpired:r={'id':s['id'],'mode':s['mode'],'verdict':'BLOCKED','failures':['timeout'],'evidence':{}}
        report['results'].append(r); print(f"  {r['verdict']}"+(f" — {'; '.join(r['failures'])}" if r['failures'] else ''))
    report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime()); path=RESULTS/f'{stamp}-{args.model_label}.json'; path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    counts={v:sum(r['verdict']==v for r in report['results']) for v in ['PASS','FAIL','BLOCKED']}; print(json.dumps(counts)); print(path)
    return 1 if counts['FAIL'] or counts['BLOCKED'] else 0
if __name__=='__main__': raise SystemExit(main())
