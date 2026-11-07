"""Revision 2: non-secret offline syntax and explicit v2 plan binding; no execution grant."""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
import development_registration as registration
from tier_a_contract import strict_json
VERSION='development-comparison-settings-v2'
KEYS={'version','provider','model_revision','corpus_version','manifest_sha256','case_ids','repetitions',
      'spending_ceiling','currency','spending_scope','token_limit','wall_seconds','tool_call_limit','retry_limit','order','seed'}
PIN_FILES=('development_settings_v1.py','development_registration.py','development_suites_audit.py',
           'development_suites_v2.py','tier_a_contract.py','tier_a_input_view.py','tier_a_inputs.py',
           'surgerybench/temporal_check.py','surgerybench/checker.py','surgerybench/temporal_csp.py',
           'surgerybench/temporal_oracle.py','surgerybench/temporal_text.py')

def need(ok,message):
    if not ok:raise ValueError(message)

def validate(value):
    need(type(value) is dict and set(value)==KEYS,'exact non-secret settings fields required')
    need(value['version']==VERSION,'unsupported settings version')
    for k in ('provider','model_revision','corpus_version'):
        need(type(value[k]) is str and bool(value[k].strip()) and len(value[k])<=128,k+' required as bounded nonempty string')
    h=value['manifest_sha256']
    need(type(h) is str and re.fullmatch('[0-9a-f]{64}',h) is not None,'manifest identity required')
    ids=value['case_ids']
    need(type(ids) is list and 1<=len(ids)<=128,'case_ids requires 1..128 entries, matching registration')
    need(all(type(x) is str and bool(x.strip()) and len(x)<=128 for x in ids),'bounded nonempty case IDs required')
    need(len(set(ids))==len(ids),'duplicate case ID')
    for k,low,high in [('repetitions',1,10),('token_limit',1,2**31-1),('wall_seconds',1,2**31-1),('tool_call_limit',0,4),('retry_limit',0,0),('seed',0,2**32-1)]:
        need(type(value[k]) is int and low<=value[k]<=high,k+' outside software compatibility bounds')
    amount=value['spending_ceiling']
    need(type(amount) in (int,float),'spending_ceiling requires numeric amount')
    need((type(amount) is int or math.isfinite(amount)) and 0<=amount<1000000,'finite nonnegative spending_ceiling below software cap required')
    need(type(value['currency']) is str and value['currency']=='USD','only explicit USD accounting supported')
    need(type(value['spending_scope']) is str and value['spending_scope']=='entire_explicit_plan_all_arms_repetitions','explicit whole-plan spending scope required')
    need(type(value['order']) is str and value['order'] in ('case_then_arm','arm_then_case'),'explicit supported order required')
    return deepcopy(value)

def load(text):
    need(type(text) is str,'JSON text required')
    try:
        need(len(text.encode('utf-8'))<=65536,'bounded JSON settings required')
        return validate(strict_json(text))
    except (TypeError,UnicodeError,RecursionError) as e:
        raise ValueError('malformed settings JSON/type') from e

def source_pins():
    root=Path(__file__).resolve().parent
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in PIN_FILES}

def bind(config,directory,plan,pins):
    c=validate(config)
    need(c['corpus_version']==registration.CORPUS,'unsupported corpus: v3 has separate trusted-local projection, no registration binding')
    need(type(pins) is dict and pins==source_pins(),'explicit interface/checker/tool/prompt source pins mismatch')
    need(type(plan) is dict,'explicit registration plan required')
    for setting,key in [('corpus_version','corpus_version'),('manifest_sha256','manifest_sha256'),('case_ids','planned_case_ids'),('repetitions','repetitions')]:
        need(key in plan and c[setting]==plan[key],'configuration/plan mismatch: '+setting)
    gold,texts,report=registration.preflight(directory,plan)
    return dict(status='offline_bound_not_execution_authorization',config=c,plan=deepcopy(plan),source_sha256=deepcopy(pins),selected_count=len(gold))

def assemble(*args,**kwargs):
    raise ValueError('arbitrary text assembly unsupported; use prepare with explicit audited package/plan/pins')

def prepare(config,directory,plan,pins,arm):
    binding=bind(config,directory,plan,pins)
    need(type(arm) is str and arm in ('no_tools','csp'),'unsupported arm')
    payloads=registration.model_inputs(directory,plan,arm)
    messages=[]
    for p in payloads:
        need(type(p) is dict and set(p)=={'shared_instruction','arm_instruction','instance_text'},'prepared payload fields')
        messages.append(dict(version='provider-neutral-messages-v2',messages=[dict(role='system',content=p['shared_instruction']+'\n'+p['arm_instruction']),dict(role='user',content=p['instance_text'])],tool_policy='none' if arm=='no_tools' else 'pinned-merged-schema-1.1-model-translated-CSP-only'))
    return binding,tuple(messages)
