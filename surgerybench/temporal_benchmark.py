"""Identical-NL paired harness: same provider, no tools versus translated CSP."""
import argparse, hashlib, importlib, json, platform, time
from pathlib import Path
from .common import revision, read_jsonl
from .common import canonical, digest
from .temporal_check import check_schedule, check_certificate
from .temporal_csp import CSPAdapter
from .temporal_text import parse


class MockProvider:
    """Controlled-language parser stub, NOT an LLM or evidence of LLM performance."""
    model_revision = 'offline-controlled-language-translator-v1'
    def next(self,text,history,tools):
        if tools and not history:
            return {'type':'tool_call','name':'csp','arguments':{'instance':parse(text)},'usage':None}
        output = {'status':'UNKNOWN'} if not history else {k:v for k,v in history[-1]['result'].items() if k in ('status','schedule','certificate')}
        return {'type':'final','output':output,'usage':None}


def score(gold,output):
    label = gold['label']; status = output.get('status') if isinstance(output,dict) else None
    violations = []; valid = False
    if status=='FEASIBLE':
        violations = check_schedule(gold['instance'],output.get('schedule')); valid = not violations
    elif status=='INFEASIBLE':
        valid = check_certificate(gold['instance'],output.get('certificate'))
        if not valid: violations.append('unverified contradiction against intended instance')
    elif status!='UNKNOWN': violations.append('invalid output schema')
    return {'valid':valid,'violations':violations,'feasible_schedule_success':valid and status=='FEASIBLE' if label=='FEASIBLE' else None,'infeasible_decision_correct':status=='INFEASIBLE' if label=='INFEASIBLE' else None,'infeasible_certified_success':valid and status=='INFEASIBLE' if label=='INFEASIBLE' else None,'unknown':status=='UNKNOWN','output_error':status not in ('FEASIBLE','INFEASIBLE','UNKNOWN')}


def run_arm(provider,text,arm,adapter,max_calls=4):
    history=[]; responses=[]; usage=[]; errors=[]; output={'status':'UNKNOWN'}; started=time.perf_counter()
    for _ in range(max_calls+1):
        received=False
        try:
            message=provider.next(text,list(history),[adapter.tool_definition] if arm=='csp' else [])
            received=True
            responses.append(message)
            usage.append(message.get('usage') if isinstance(message,dict) else None)
            if not isinstance(message,dict): raise ValueError('provider response must be an object')
            if message.get('type')=='final': output=message.get('output'); break
            if arm!='csp' or message.get('type')!='tool_call' or message.get('name')!='csp': raise ValueError('unavailable tool or invalid provider message')
            if len(history)>=max_calls: raise ValueError('tool call limit')
        except Exception as exc:
            if not received: usage.append(None)
            errors.append({'stage':'provider_or_parse','error':f'{type(exc).__name__}: {exc}'}); break
        began=time.perf_counter()
        try: result=adapter.invoke(message.get('arguments'))
        except Exception as exc:
            errors.append({'stage':'tool','error':f'{type(exc).__name__}: {exc}'})
            result={'status':'UNKNOWN','error':str(exc)}
        history.append({'name':'csp','arguments':message.get('arguments'),'result':result,'latency_seconds':time.perf_counter()-began})
    complete=bool(usage) and all(isinstance(u,dict) and all(type(u.get(k)) is int and u[k]>=0 for k in ('input_tokens','output_tokens')) for u in usage)
    return {'output':output,'responses':responses,'tool_calls':history,'tool_call_count':len(history),'latency_seconds':time.perf_counter()-started,'token_usage':{k:sum(u[k] for u in usage) for k in ('input_tokens','output_tokens')} if complete else None,'token_usage_reason':None if complete else 'provider did not report complete token usage','errors':errors,'parsing_or_provider_error':any(e['stage']=='provider_or_parse' for e in errors),'tool_error':any(e['stage']=='tool' for e in errors)}


def run(model_path,gold_path,out,factory=MockProvider,adapter=None):
    if Path(out).exists(): raise FileExistsError('preserve prior runs')
    model=read_jsonl(model_path); gold_rows=read_jsonl(gold_path); gold={r['id']:r for r in gold_rows}
    if len(gold)!=len(gold_rows) or len({r['id'] for r in model})!=len(model): raise ValueError('duplicate IDs')
    if {r['id'] for r in model} != set(gold): raise ValueError('model/gold ID mismatch')
    dataset_sha=hashlib.sha256(Path(model_path).read_bytes()).hexdigest(); gold_sha=hashlib.sha256(Path(gold_path).read_bytes()).hexdigest()
    adapter=adapter or CSPAdapter(); rows=[]; model_revision=None; code_revision=revision()
    for m in model:
        if set(m)!={'id','text'}: raise ValueError('model input must have only id and text')
        g=gold[m['id']]; text_sha=hashlib.sha256(m['text'].encode()).hexdigest()
        if text_sha!=g['text_sha256'] or digest(g['instance'])!=g['instance_sha256']: raise ValueError('integrity mismatch')
        for arm in ('no_tools','csp'):
            provider=factory()
            provider_revision=getattr(provider,'model_revision',None)
            if not isinstance(provider_revision,str) or not provider_revision.strip():
                raise ValueError('exact model revision required: nonempty string')
            if model_revision is None: model_revision=provider_revision
            if model_revision!=provider_revision: raise ValueError('same model required in both arms')
            r=run_arm(provider,m['text'],arm,adapter)
            r.update({'case_id':m['id'],'family':g['family'],'split':g['split'],'arm':arm,'text_sha256':text_sha,'model_revision':model_revision,'tool_revision':adapter.revision if arm=='csp' else None,'code_revision':code_revision,'dataset_revision':dataset_sha,'gold_revision':gold_sha,'python':platform.python_version(),'score':score(g,r['output'])})
            rows.append(r)
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    Path(out).write_text(''.join(canonical(r)+'\n' for r in rows))
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--model',required=True); p.add_argument('--gold',required=True); p.add_argument('--out',required=True); p.add_argument('--provider',help='module:factory; default offline stub')
    a=p.parse_args(); factory=MockProvider
    if a.provider:
        module,name=a.provider.split(':'); factory=getattr(importlib.import_module(module),name)
    rows=run(a.model,a.gold,a.out,factory)
    print(json.dumps({'runs':len(rows),'valid_outputs':sum(r['score']['valid'] for r in rows),'unknown_outputs':sum(r['score']['unknown'] for r in rows),'provider_parse_errors':sum(r['parsing_or_provider_error'] for r in rows),'tool_errors':sum(r['tool_error'] for r in rows),'real_llm_runs':0 if factory is MockProvider else 'provider-dependent'}))
