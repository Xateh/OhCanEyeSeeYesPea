"""Direct v1: one model response per arm; Python owns execution and scoring."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,random,time
import benchmark_datasets as catalog
import paired_runner as legacy
import temporal_validation_v2 as strict
from solver_interface import CheckedSolver,MergedSolver,LIMITS,require,digest
from tier_a_contract import strict_json,canonical,output_verdict
from tier_a_input_view import SHARED,VIEW_FRAGMENT,RAW_FRAGMENT
from study.prompts import FINAL_SHAPE,SYSTEM_V1
from tier_a_completion import well_formed
from surgerybench.temporal_csp import TOOL
from responses_sdk_runner import IDS,DIRECTORY,MANIFEST
from direct_api_providers import APIProvider,body,estimate_reserve,RATE_KEYS
VERSION='direct-python-csp-api-v1'
ASSESSMENT_VERSION='direct-saved-evidence-joins-v2'
TRANSLATE='Return exactly one JSON object and no prose or fences: {"type":"tool_call","name":"csp","arguments":{"instance":INSTANCE}}. Translate every stated hard constraint into schema 1.1 using the actual IDs. This is a translation response; Python executes the supplied instance. Do not return a final answer, history or another invocation. Instance schema: '
ROOT=Path(__file__).resolve().parent
KEYS={'version','mode','provider','model','effort','seed','max_output_tokens','call_seconds','attempt_seconds','attempt_token_limit','call_budget_usd','total_budget_usd','rates'}
def config(value):
 require(type(value) is dict and set(value)==KEYS,'explicit direct settings fields')
 c=deepcopy(value);require(c['version']==VERSION and c['mode'] in ('mock','live'),'version/mode')
 require(c['provider'] in ('mock','openai_api','anthropic_api'),'explicit API provider; legacy CLI is separate')
 require(type(c['model']) is str and 0<len(c['model'])<=128,'explicit model')
 require(c['effort']=='high','explicit high effort profile')
 for k,lo,hi in [('seed',0,2**32-1),('max_output_tokens',1,2000),('call_seconds',1,20),('attempt_seconds',1,45),('attempt_token_limit',1,12000)]:require(type(c[k]) is int and lo<=c[k]<=hi,'bounded '+k)
 for k,maximum in [('call_budget_usd',.2),('total_budget_usd',2.5)]:require(type(c[k]) in (int,float) and math.isfinite(c[k]) and 0<c[k]<=maximum,'explicit software spending bound')
 require(type(c['rates']) is dict and set(c['rates'])==RATE_KEYS and type(c['rates']['source']) is str and bool(c['rates']['source']),'explicit rate identity')
 for k in RATE_KEYS-{'source'}:require(type(c['rates'][k]) in (int,float) and math.isfinite(c['rates'][k]) and c['rates'][k]>=0,'finite nonnegative rates')
 if c['mode']=='live':
  require(c['provider']!='mock' and c['model']!='fixture' and all(c['rates'][k]>0 for k in RATE_KEYS-{'source'}),'unresolved live provider/model/rates')
  require(c['model']=='gpt-6-astra' if c['provider']=='openai_api' else c['model']=='claude-opus-5-5','reviewed model profile')
 return c

def prompt(text,arm):
 require(arm in ('no_tools','csp'),'arm')
 return text+'\n\n'+SHARED+'\n'+(SYSTEM_V1+'\n'+FINAL_SHAPE if arm=='no_tools' else TRANSLATE+canonical(TOOL))

def sources():
 names=set(legacy.source_pins())|{'direct_benchmark.py','direct_api_providers.py','anthropic_sdk_client.py','openai_sdk_client.py','responses_credentials.py','requirements-anthropic-sdk.txt','temporal_validation_v2.py','tools/run_direct_benchmark.py','responses_sdk_runner.py','responses_final_schema.py'}
 return {n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(names)}

def dataset_specs(directory):
 import development_registration as registration
 specs=json.loads((ROOT/'fixtures/responses-offline-v1/datasets.json').read_text())
 specs[0]['directory']=str(Path(directory).resolve())
 specs[0]['plan']['consumer_sha256']=hashlib.sha256(Path(registration.__file__).read_bytes()).hexdigest()
 return specs

def demo_specs():return dataset_specs(ROOT/'fixtures/responses-offline-v1/seeded-v2')

def make_plan(specs,settings):
 c=config(settings);require(type(specs) is list and len(specs)==1 and specs[0]['kind']=='seeded-v2','existing seeded-v2 registration only')
 spec=specs[0];require(spec['plan']['manifest_sha256']==MANIFEST and spec['plan']['planned_case_ids']==IDS and spec['plan']['repetitions']==1,'fixed four-case guard')
 if c['mode']=='live':require(Path(spec['directory']).resolve()==Path(DIRECTORY),'live dataset path unchanged')
 gold,identities=catalog.load(specs);cases={g['case_id']:g for g in gold};require(list(cases)==IDS,'same ordered checked cases')
 reserve=0
 for g in cases.values():
  for arm in ('no_tools','csp'):
   p=prompt(g['text'],arm)
   if c['provider']!='mock':
    request=body(c['provider'],p,c);require(len(canonical(request).encode())<=7500,'serialized request bound');cost=estimate_reserve(request,c);require(cost<=c['call_budget_usd'],'per-call reserve insufficient');reserve+=cost
 require(reserve<=c['total_budget_usd'],'whole-plan conservative reserve insufficient')
 slots=[];offset=random.Random(c['seed']).randrange(2)
 for n,i in enumerate(IDS):
  for arm in (('no_tools','csp') if (n+offset)%2==0 else ('csp','no_tools')):slots.append(dict(case_id=i,repetition=0,arm=arm))
 plan=dict(version=VERSION,config=c,datasets=identities,dataset_specs=deepcopy(specs),slots=slots,source_sha256=sources(),prompt_sha256={i:{a:digest(prompt(g['text'],a)) for a in ('no_tools','csp')} for i,g in cases.items()},case_text_sha256={i:hashlib.sha256(g['text'].encode()).hexdigest() for i,g in cases.items()},limits=dict(max_model_calls=8,max_solver_calls=4,solver=LIMITS,retries=0,workers=1),conservative_reserve_usd=reserve,provisional_settings_not_team_protocol=True)
 plan['run_id']=digest(plan)
 for slot in slots:slot['attempt_id']=digest(dict(run_id=plan['run_id'],slot=slot))
 return plan,cases

class FixtureProvider:
 def __init__(self):self.calls=[]
 def call(self,text,budget):
  from surgerybench.temporal_text import parse
  if text.endswith(SYSTEM_V1+'\n'+FINAL_SHAPE):answer={'type':'final','output':{'status':'UNKNOWN'}}
  else:answer={'type':'tool_call','name':'csp','arguments':{'instance':parse(text.split('\n\n'+SHARED+'\n')[0].replace(VIEW_FRAGMENT,RAW_FRAGMENT))}}
  r=dict(raw_model_text=canonical(answer),response_complete=True,error=None,usage={'input_tokens':0,'output_tokens':0,'cost_estimate_usd':0,'reported':None,'returned_tier':'fixture'},elapsed_seconds=0,fixture_not_model=True)
  self.calls.append(r);return deepcopy(r)

def attempt(slot,g,c,provider,solver_factory=MergedSolver):
 start=time.monotonic();row=dict(**slot,provider_calls=[],solver_events=[],model_output=None,solver_output=None,final_output=None,stage='provider_error',success=False,evidence_success=False,format_valid=False,translation_valid=None,error=None)
 try:
  call=provider.call(prompt(g['text'],slot['arm']),c['call_budget_usd']);row['provider_calls']=[call]
  require(not call.get('error') and call.get('response_complete') and type(call.get('raw_model_text')) is str,'provider response failure')
  row['stage']='model_format_error'
  raw=call['raw_model_text'];require(len(raw.encode())<=65536,'model text cap');answer=strict_json(raw);row['model_output']=answer
  if slot['arm']=='no_tools':
   require(type(answer) is dict and set(answer)=={'type','output'} and answer['type']=='final','baseline final envelope')
   row['final_output']=answer['output'];row['stage']='final'
  else:
   row['stage']='translation_error'
   require(type(answer) is dict and set(answer)=={'type','name','arguments'} and answer['type']=='tool_call' and answer['name']=='csp','translation envelope')
   args=answer['arguments'];require(type(args) is dict and set(args)=={'instance'} and not strict.schema_errors(args['instance']),'strict model-authored instance required')
   row['translation_valid']=True
   checked=CheckedSolver(solver_factory(),MergedSolver.revision,LIMITS);result=checked.invoke(deepcopy(args));row['solver_events']=checked.events;row['solver_output']=result
   row['final_output']={k:v for k,v in result.items() if k in ('status','schedule','certificate')}
   row['stage']='solver_error' if checked.events[-1]['error'] else 'solver_unknown' if result['status']=='UNKNOWN' else 'direct_solver_evidence'
  final=row['final_output'];verdict=output_verdict(g['instance'],canonical(final),final,[]);row['verdict']=verdict;row['format_valid']=well_formed(dict(raw_output=canonical(final),normalized_output=final,normalization_errors=[]));row['evidence_success']=verdict['evidence_valid'] and verdict['status']==g['label']
  if type(final) is dict and final.get('status')=='UNKNOWN' and slot['arm']=='no_tools':row['stage']='model_unknown'
  if not row['evidence_success'] and type(final) is dict and final.get('status')!='UNKNOWN':row['stage']='intended_evidence_invalid'
  row['success']=row['evidence_success'] and row['stage']!='solver_error'
 except Exception as e:row['error']='timeout' if isinstance(e,TimeoutError) else row['stage'];row['success']=False
 row['elapsed_seconds']=time.monotonic()-start
 u=row['provider_calls'][0].get('usage') if row['provider_calls'] else None
 row['cost_estimate_usd']=u.get('cost_estimate_usd') if u else None
 row['budget_unknown']=u is None or row['cost_estimate_usd'] is None or u.get('input_tokens') is None or u.get('output_tokens') is None
 row['budget_violation']=row['elapsed_seconds']>c['attempt_seconds'] or (u is not None and None not in (u.get('input_tokens'),u.get('output_tokens')) and u['input_tokens']+u['output_tokens']>c['attempt_token_limit']) or row['cost_estimate_usd'] is not None and row['cost_estimate_usd']>c['call_budget_usd']
 row['success']&=not row['budget_unknown'] and not row['budget_violation'] and row['error'] is None
 return row

def summarize(plan,cases,receipts):
 expected={s['attempt_id']:s for s in plan['slots']};indexed={}
 for row in receipts:
  require(type(row) is dict and row.get('attempt_id') in expected and row['attempt_id'] not in indexed,'duplicate/unplanned attempt')
  require({'model_output','final_output','solver_output','provider_calls','solver_events','success','evidence_success','format_valid'}<=set(row),'missing recorded stage fields')
  require(all(type(row[k]) is bool for k in ['success','evidence_success','format_valid']),'boolean result flags')
  slot=expected[row['attempt_id']];require(all(row[k]==v for k,v in slot.items()),'attempt routing')
  require(type(row['provider_calls']) is list and len(row['provider_calls'])<=1 and type(row['solver_events']) is list and len(row['solver_events'])<=1,'one call/invocation receipt bound')
  require(slot['arm']=='csp' or not row['solver_events'],'baseline solver forbidden')
  require(row['final_output'] is not None or not any(row[k] for k in ['success','evidence_success','format_valid']),'missing final evidence cannot be credited')
  require(row['model_output'] is not None or (row['final_output'] is None and row['solver_output'] is None and not row['solver_events']),'missing model output cannot support later stages')
  require(row['model_output'] is None or len(row['provider_calls'])==1,'model output requires its provider receipt')
  require((row['solver_output'] is None)==(not row['solver_events']),'solver receipt/result presence')
  g=cases[slot['case_id']]
  if row['provider_calls']:
   call=row['provider_calls'][0]
   if 'request' in call:require(call['request']==body(plan['config']['provider'],prompt(g['text'],slot['arm']),plan['config']),'model-visible request join')
   if not call.get('fixture_not_model') and call.get('raw_response_base64') is not None:
    import base64
    from direct_api_providers import usage,extract
    raw=base64.b64decode(call['raw_response_base64'],validate=True)
    meta=call.get('transport_metadata',{});wire=meta.get('wire',{});eligible=call['response_complete'] and not call['redacted'] and not meta.get('read_error') and wire.get('encoding_supported',wire.get('response_encoding_supported',True))
    if not eligible:require(call['error'] is not None and call['usage'] is None and call['raw_model_text'] is None,'incomplete/unsupported receipt remains failed/unknown')
    if eligible:
     try:envelope=strict_json(raw.decode())
     except (ValueError,UnicodeError):
      require(call['error'] is not None and call['usage'] is None and call['raw_model_text'] is None,'malformed envelope remains failed/unknown');envelope=None
     if envelope is not None:require(call['usage']==usage(plan['config']['provider'],envelope,plan['config']['rates']),'usage/raw receipt join')
     if call['raw_model_text'] is not None:require(call['raw_model_text']==extract(plan['config']['provider'],envelope),'model/raw receipt join')
   raw_text=call.get('raw_model_text')
   try:bounded_text=type(raw_text) is str and len(raw_text.encode())<=65536
   except UnicodeError:bounded_text=False
   if not call.get('error') and call.get('response_complete') and bounded_text:
    try:parsed=strict_json(raw_text)
    except ValueError:require(row['model_output'] is None,'malformed model output/raw join')
    else:require(type(parsed) is type(row['model_output']) and parsed==row['model_output'],'model output/raw join')
   else:require(row['model_output'] is None,'parsed model output without eligible raw response')
  if row['solver_output'] is not None:
   require(slot['arm']=='csp' and len(row['solver_events'])==1,'solver stage identity')
   event=row['solver_events'][0];instance=row['model_output']['arguments']['instance'];require(event['translated_instance_sha256']==digest(instance) and event['result']==row['solver_output'],'translated/result join')
   final={k:v for k,v in row['solver_output'].items() if k in ('status','schedule','certificate')};require(final==row['final_output'],'direct solver evidence join')
   if not event['error']:
    from surgerybench.temporal_check import check_schedule,check_certificate
    if final['status']=='FEASIBLE':require(not check_schedule(instance,final['schedule']),'recorded translated witness')
    elif final['status']=='INFEASIBLE':require(check_certificate(instance,final['certificate']),'recorded translated certificate')
  elif row['final_output'] is not None:require(row['model_output']['output']==row['final_output'],'baseline final join')
  if row['final_output'] is not None:
   v=output_verdict(g['instance'],canonical(row['final_output']),row['final_output'],[]);require(v==row['verdict'],'independent intended-instance verdict');require(row['evidence_success']==(v['evidence_valid'] and v['status']==g['label']),'evidence success cannot be relabelled');require(row['format_valid']==well_formed(dict(raw_output=canonical(row['final_output']),normalized_output=row['final_output'],normalization_errors=[])),'format validity cannot be relabelled')
  u=row['provider_calls'][0].get('usage') if row['provider_calls'] else None
  cost=u.get('cost_estimate_usd') if u else None;c=plan['config']
  unknown=u is None or cost is None or u.get('input_tokens') is None or u.get('output_tokens') is None
  violation=row['elapsed_seconds']>c['attempt_seconds'] or (u is not None and None not in (u.get('input_tokens'),u.get('output_tokens')) and u['input_tokens']+u['output_tokens']>c['attempt_token_limit']) or cost is not None and cost>c['call_budget_usd']
  require(row['cost_estimate_usd']==cost and row['budget_unknown']==unknown and row['budget_violation']==violation,'accounting/limit receipt join')
  require(row['success']==(row['evidence_success'] and row['error'] is None and not row['budget_unknown'] and not row['budget_violation'] and not any(e['error'] for e in row['solver_events'])),'success/checker join')
  indexed[row['attempt_id']]=row
 by_arm={}
 for arm in ('no_tools','csp'):
  slots=[s for s in plan['slots'] if s['arm']==arm];rows=[indexed[s['attempt_id']] for s in slots if s['attempt_id'] in indexed];costs=[r['cost_estimate_usd'] for r in rows if r['cost_estimate_usd'] is not None]
  by_arm[arm]=dict(planned=len(slots),received=len(rows),missing=len(slots)-len(rows),model_calls=sum(len(r['provider_calls']) for r in rows),solver_calls=sum(len(r['solver_events']) for r in rows),success=sum(r['success'] for r in rows),evidence_success=sum(r['evidence_success'] for r in rows),format_valid=sum(r['format_valid'] for r in rows),model_unknown=sum(r['stage']=='model_unknown' for r in rows),solver_unknown=sum(r['stage']=='solver_unknown' for r in rows),errors=sum(r['error'] is not None or r['stage']=='solver_error' for r in rows),known_cost_estimate_usd=sum(costs),cost_estimate_usd=sum(costs) if len(costs)==len(slots) else None,unknown_cost_runs=len(slots)-len(costs),observed_seconds=sum(r['elapsed_seconds'] for r in rows))
 return dict(version=VERSION,assessment_version=ASSESSMENT_VERSION,status='offline_fixture_not_model_results' if plan['config']['mode']=='mock' else 'direct_api_receipts_not_research_acceptance',by_arm=by_arm,planned_slots=len(plan['slots']),received=len(receipts),billed_cost_usd=None,optimality='not_implemented')

def run(specs,settings,directory,*,provider=None,solver_factory=MergedSolver,allow_live=False,key_file=None):
 plan,cases=make_plan(specs,settings);c=plan['config'];out=Path(directory)
 require(not out.exists(),'refuse existing output directory')
 if c['mode']=='live':
  require(allow_live is True and key_file is not None and provider is None,'separate explicit live/key-file opt-in; no injected live provider')
  if c['provider']=='openai_api':
   from responses_credentials import load_key_file
   from openai_sdk_client import sdk_runtime
  else:
   from anthropic_sdk_client import load_key_file,runtime as sdk_runtime
  plan['sdk_identity']=sdk_runtime();plan['run_id']=digest({k:v for k,v in plan.items() if k!='run_id'})
  for slot in plan['slots']:slot['attempt_id']=digest(dict(run_id=plan['run_id'],slot={k:v for k,v in slot.items() if k!='attempt_id'}))
  provider=APIProvider(c,allow_live=True,key_loader=lambda:load_key_file(key_file))
 elif provider is None:
  require(c['provider']=='mock','API mock tests require an injected provider');provider=FixtureProvider()
 out.mkdir(mode=0o700);(out/'plan.json').write_text(canonical(plan)+'\n');receipts=[];spent=0;stop=None
 with (out/'attempts.jsonl').open('x') as stream:
  for slot in plan['slots']:
   if spent+c['call_budget_usd']>c['total_budget_usd']:stop='budget_reserve';break
   row=attempt(slot,cases[slot['case_id']],c,provider,solver_factory)
   if c['mode']=='live' and row['provider_calls'] and row['provider_calls'][0].get('transport_metadata',{}).get('runtime')!=plan['sdk_identity']:row.update(success=False,error='runtime_identity_drift')
   require(len(canonical(row).encode())<=4*1024*1024,'bounded one-call receipt')
   stream.write(canonical(row)+'\n');stream.flush();receipts.append(row)
   if row['cost_estimate_usd'] is not None:spent+=row['cost_estimate_usd']
   if row['budget_unknown'] or row['budget_violation'] or row['stage']=='provider_error' or row['error']=='runtime_identity_drift':stop='unknown_usage_or_operational_budget_stop';break
 result=summarize(plan,cases,receipts);result['stop_reason']=stop;(out/'summary.json').write_text(canonical(result)+'\n');return result

def assess(directory):
 out=Path(directory);require((out/'plan.json').stat().st_size<=4*1024*1024,'plan size cap');plan=strict_json((out/'plan.json').read_text())
 current,cases=make_plan(plan['dataset_specs'],plan['config'])
 # Live SDK identity is recorded evidence, never loaded from account/environment.
 if 'sdk_identity' in plan:
  current['sdk_identity']=plan['sdk_identity'];current['run_id']=digest({k:v for k,v in current.items() if k!='run_id'})
  for slot in current['slots']:slot['attempt_id']=digest(dict(run_id=current['run_id'],slot={k:v for k,v in slot.items() if k!='attempt_id'}))
 require(current==plan,'source/dataset/configuration/plan drift')
 require((out/'attempts.jsonl').stat().st_size<=32*1024*1024,'attempt ledger cap')
 rows=[strict_json(s) for s in (out/'attempts.jsonl').read_text().splitlines()];require(len(rows)<=8,'fixed attempts cap');return summarize(plan,cases,rows)
