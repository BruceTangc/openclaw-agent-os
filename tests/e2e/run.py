#!/usr/bin/env python3
"""Drive Agent OS acceptance scenarios through a real OpenClaw CLI.

The harness is outside Agent OS runtime. Runtime behavioral scenarios are judged
from the final assistant-visible answer only; prompt/envelope text is never an
assertion input. Behavioral verdicts use a second independent evaluator model.
"""
from pathlib import Path
import argparse, json, os, shlex, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=Path(__file__).with_name('scenarios.json')
RESULTS=Path(__file__).with_name('results')
PROMPT_KEYS={'finalprompttext','prompt','input','request','systemprompt','userprompt'}
FINAL_KEYS=('finalAssistantVisibleText','finalResponse','assistantResponse')

def run_cmd(cmd,timeout=180):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
    return p.returncode,p.stdout,p.stderr

def command_from(template,prompt,default):
    if not template:return default
    sentinel='__AGENT_OS_E2E_PROMPT__'; parts=shlex.split(template.replace('{prompt}',sentinel))
    return [prompt if x==sentinel else x for x in parts]

def runtime_cmd(prompt):
    return command_from(os.environ.get('OPENCLAW_E2E_COMMAND'),prompt,['openclaw','agent','--message',prompt,'--json'])

def evaluator_cmd(prompt):
    template=os.environ.get('OPENCLAW_E2E_EVALUATOR_COMMAND') or os.environ.get('OPENCLAW_E2E_COMMAND')
    return command_from(template,prompt,['openclaw','agent','--message',prompt,'--json'])

def response_text(stdout):
    """Extract assistant-visible output, fail closed instead of recursively ingesting envelopes."""
    try:obj=json.loads(stdout)
    except Exception:return stdout.strip()
    def direct(x):
        if not isinstance(x,dict):return None
        lower={str(k).lower():v for k,v in x.items()}
        for key in FINAL_KEYS:
            v=lower.get(key.lower())
            if isinstance(v,str) and v.strip():return v.strip()
        # Common result/message containers, but never prompt-like keys.
        for key in ('result','response','output','message'):
            v=lower.get(key)
            if isinstance(v,str) and v.strip():return v.strip()
            if isinstance(v,dict):
                role=str(v.get('role','')).lower()
                if role in ('assistant',''):
                    for ck in ('content','text'):
                        cv=v.get(ck)
                        if isinstance(cv,str) and cv.strip():return cv.strip()
        return None
    v=direct(obj)
    if v:return v
    candidates=[]
    def walk(x,parent=''):
        if parent.lower() in PROMPT_KEYS:return
        if isinstance(x,list):
            for v in x:walk(v,parent)
        elif isinstance(x,dict):
            role=str(x.get('role','')).lower()
            if role=='assistant':
                for k in ('content','text'):
                    v=x.get(k)
                    if isinstance(v,str) and v.strip():candidates.append(v.strip())
            for k,v in x.items():
                if str(k).lower() not in PROMPT_KEYS:walk(v,str(k))
    walk(obj)
    return candidates[-1] if candidates else ''

def parse_json_object(text):
    text=text.strip()
    if text.startswith('```'):
        lines=text.splitlines(); text='\n'.join(lines[1:-1]).strip()
        if text.lower().startswith('json'):text=text[4:].lstrip()
    try:
        x=json.loads(text); return x if isinstance(x,dict) else None
    except Exception:
        a=text.find('{'); b=text.rfind('}')
        if a>=0 and b>a:
            try:
                x=json.loads(text[a:b+1]); return x if isinstance(x,dict) else None
            except Exception:pass
    return None

def semantic_judge(s,answer):
    rubric=s.get('rubric') or s.get('prompt','')
    prompt=("You are an independent acceptance-test evaluator. Judge ONLY the assistant answer below against the scenario rubric. "
            "Do not judge the test prompt itself. Negated discussion of a prohibited behavior is not a violation. "
            "Return JSON only: {\"verdict\":\"PASS|FAIL|INDETERMINATE\",\"reason\":\"...\"}.\n\n"
            f"SCENARIO {s['id']} RUBRIC:\n{rubric}\n\nASSISTANT ANSWER:\n{answer}")
    code,out,err=run_cmd(evaluator_cmd(prompt))
    if code!=0:return 'INDETERMINATE',f'evaluator exit={code}',{'stdout':out,'stderr':err}
    ev_text=response_text(out); obj=parse_json_object(ev_text)
    if not obj:return 'INDETERMINATE','evaluator returned no parseable JSON',{'stdout':out,'stderr':err,'response_text':ev_text}
    verdict=str(obj.get('verdict','')).upper(); reason=str(obj.get('reason',''))
    if verdict not in {'PASS','FAIL','INDETERMINATE'}:return 'INDETERMINATE','invalid evaluator verdict',{'parsed':obj}
    return verdict,reason,{'parsed':obj,'response_text':ev_text}

def run_scenario(s):
    mode=s['mode']; started=time.time(); evidence={}; failures=[]; verdict='PASS'
    if mode=='runtime':
        cmd=runtime_cmd(s['prompt']); code,out,err=run_cmd(cmd); answer=response_text(out)
        evidence={'command':cmd[:-1]+['<prompt>'],'stdout':out,'stderr':err,'assistant_visible_text':answer}
        if code!=0: verdict='BLOCKED'; failures=[f'OpenClaw exit={code}']
        elif not answer: verdict='BLOCKED'; failures=['no assistant-visible response could be isolated']
        else:
            jv,reason,je=semantic_judge(s,answer); evidence['evaluator']=je; evidence['evaluator_reason']=reason
            verdict='PASS' if jv=='PASS' else ('FAIL' if jv=='FAIL' else 'BLOCKED')
            if verdict!='PASS':failures=[reason or jv]
    elif mode=='environment':
        code,out,err=run_cmd(s['command']); failures=[] if code==0 else [f'command exit={code}']
        needle=s.get('assert',{}).get('json_contains')
        if needle and needle.lower() not in out.lower():failures.append(f'output missing: {needle}')
        evidence={'command':s['command'],'stdout':out,'stderr':err}; verdict='PASS' if not failures else 'FAIL'
    elif mode=='static-schema':
        code,out,err=run_cmd(s['command']); failures=[] if code==s.get('assert',{}).get('exit_code',0) else [f'command exit={code}']
        evidence={'command':s['command'],'stdout':out,'stderr':err}; verdict='PASS' if not failures else 'FAIL'
    else: verdict='BLOCKED'; failures=[f'unsupported mode: {mode}']
    return {'id':s['id'],'mode':mode,'verdict':verdict,'failures':failures,'duration_s':round(time.time()-started,3),'evidence':evidence}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--scenario',action='append'); ap.add_argument('--model-label',default=os.environ.get('OPENCLAW_E2E_MODEL','unspecified')); ap.add_argument('--list',action='store_true'); args=ap.parse_args()
    scenarios=json.loads(MANIFEST.read_text(encoding='utf-8'))['scenarios']
    if args.list:
        for s in scenarios:print(s['id'],s['mode'])
        return 0
    wanted=set(args.scenario or [])
    if wanted:scenarios=[s for s in scenarios if s['id'] in wanted]
    if not scenarios:print('no scenarios selected',file=sys.stderr);return 2
    RESULTS.mkdir(exist_ok=True)
    report={'kind':'agent-os-openclaw-runtime-e2e','model_label':args.model_label,'skill_version':(ROOT/'VERSION').read_text().strip(),'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'results':[]}
    for s in scenarios:
        print(f"[{s['id']}] {s['mode']} ...",flush=True)
        try:r=run_scenario(s)
        except FileNotFoundError as e:r={'id':s['id'],'mode':s['mode'],'verdict':'BLOCKED','failures':[str(e)],'evidence':{}}
        except subprocess.TimeoutExpired:r={'id':s['id'],'mode':s['mode'],'verdict':'BLOCKED','failures':['timeout'],'evidence':{}}
        report['results'].append(r);print(f"  {r['verdict']}"+(f" — {'; '.join(r['failures'])}" if r['failures'] else ''))
    report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());stamp=time.strftime('%Y%m%d-%H%M%S',time.gmtime());path=RESULTS/f'{stamp}-{args.model_label}.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    counts={v:sum(r['verdict']==v for r in report['results']) for v in ['PASS','FAIL','BLOCKED']};print(json.dumps(counts));print(path)
    return 1 if counts['FAIL'] or counts['BLOCKED'] else 0
if __name__=='__main__':raise SystemExit(main())
