"""Pinned final-step replay; generation format changes, evaluation never does."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,time
import responses_calibration_transport as api
import responses_final_schema as schema
from tier_a_contract import canonical,strict_json,output_verdict
from solver_interface import require,digest
import handoff_comparison as source
VERSION='frozen-final-schema-replay-v1'
IDS=source.IDS
PRIOR=Path('/home/t/tehxa/cs3263-review/handoff-comparison-v1-20261107-8pdui9gm')
RECEIPT_SHA='8c66f10213408093fbffecddfbf9e5073908a79937e8b9c4a1e8460963f31381'
def register():
 raw=(PRIOR/'run/attempts.jsonl').read_bytes();require(hashlib.sha256(raw).hexdigest()==RECEIPT_SHA,'frozen source receipt changed')
 rows=[strict_json(x) for x in raw.decode().splitlines()];_,loaded=source.make_plan(True);cases={};requests={}
 for i in IDS:
  matches=[r for r in rows if r['case_id']==i and r['condition']=='restored'];require(len(matches)==1,'exact restored source')
  r=matches[0];require(len(r['provider_calls'])==2 and len(r['solver_events'])==1,'source phase count')
  b=r['provider_calls'][1]['request'];require(b['text']==schema.FORMAT and b['model']=='gpt-6-astra' and b['reasoning']=={'effort':'high'} and b['service_tier']=='default' and b['max_output_tokens']==2000 and b['tools']==[],'frozen profile/schema')
  result=r['solver_events'][0]['result'];o={k:v for k,v in result.items() if k in ['status','schedule','certificate']}
  require(o['status']=='FEASIBLE' and schema.valid({'type':'final','output':o}),'actual witness representability')
  require(output_verdict(loaded[i]['instance'],canonical(o),o,[])['evidence_valid'],'intended-instance witness invalid')
  require('copy its schedule or certificate exactly' in b['instructions'] and 'When you have your answer' in b['input'],'final contract missing')
  cases[i]=dict(instance=loaded[i]['instance'],checked_output=o,request=b);requests[i]=deepcopy(b)
 pins=source.restored.source_pins();pins.update({n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ['schema_final_replay.py','handoff_comparison.py']})
 slots=[dict(case_id=i,condition=k,repetition=0) for i,ks in zip(IDS,[('off','on'),('on','off')]) for k in ks]
 plan=dict(version=VERSION,source_receipt_sha256=RECEIPT_SHA,case_ids=IDS,requests=requests,slots=slots,source_sha256=pins,schema_sha256=schema.SHA256,provider_binding=source.make_plan(True)[0]['execution_config']['provider_binding'],maximum_api_calls=4,maximum_solver_calls=0,estimated_cost_ceiling_usd=.8,call_budget_usd=.2,call_seconds=20,attempt_seconds=45,attempt_tokens=12000,request_bytes=7500,evaluation='same_strict_unmodified_json_shape_and_intended_instance_evidence_v1',ordering='fixed-balanced-start-schema-off-on-v1')
 plan['run_id']=digest(plan)
 for s in slots:s['attempt_id']=digest(dict(run_id=plan['run_id'],slot=s))
 reserves=[]
 for s in slots:
  b=body(plan,s['case_id'],s['condition']);n=len(canonical(b).encode());require(n<=7500,'frozen request bound')
  reserves.append(((n+256)*12.5+2000*50)/1000000)
 require(sum(reserves)<=.8 and max(reserves)<=.2,'insufficient reserve')
 return plan,cases
def body(plan,i,condition):
 require(i in IDS and condition in ['on','off'],'exact case/condition')
 b=deepcopy(plan['requests'][i])
 if condition=='off':b.pop('text')
 return b
def grade(text,case):
 result=dict(syntax_valid=False,shape_valid=False,evidence_success=False,unknown=False,status=None)
 try:o=strict_json(text);result['syntax_valid']=True
 except (ValueError,TypeError,RecursionError):return result
 if not schema.valid(o):return result
 output=o['output'];v=output_verdict(case['instance'],canonical(output),output,[])
 result.update(shape_valid=True,evidence_success=v['evidence_valid'],unknown=output['status']=='UNKNOWN',status=output['status']);return result
def invoke(plan,slot,transport,key_loader,is_mock):
 b=body(plan,slot['case_id'],slot['condition']);start=time.perf_counter();reserve=((len(canonical(b).encode())+256)*12.5+2000*50)/1000000
 r=dict(**slot,request=b,endpoint=api.ENDPOINT,is_mock=is_mock,transport_started=False,raw_response=None,raw_model_text=None,observed_usage=None,error=None,elapsed_seconds=None,planning_reserve_usd=reserve)
 try:
  require(reserve<=.2 and len(canonical(b).encode())<=7500,'precredential bound')
  if is_mock:r['transport_started']=True;response=transport(deepcopy(b),20)
  else:
   key=key_loader();r['transport_started']=True;response=api.http_once(b,20,key)
  require(type(response) is tuple and len(response) in [4,5],'HTTP contract')
  code,headers,raw,complete=response[:4];require(type(raw) is bytes,'raw HTTP bytes')
  r.update(http_status=code,response_complete=complete,response_headers={k:v for k,v in headers.items() if k in ['x-request-id','openai-processing-ms','retry-after']},credential_echo_redacted=bool(response[4]) if len(response)==5 else False)
  try:r['raw_response']=raw.decode()
  except UnicodeError:r['raw_response_base64']=__import__('base64').b64encode(raw).decode();raise ValueError('encoding')
  require(complete and len(raw)<=api.retention.ENVELOPE_BYTES,'response bound')
  envelope=strict_json(r['raw_response']);matched=envelope.get('model')=='gpt-6-astra';tier=envelope.get('service_tier')
  r.update(returned_model=envelope.get('model'),returned_tier=tier,response_status=envelope.get('status'),incomplete_details=envelope.get('incomplete_details'),observed_usage=api.observed_usage(envelope.get('usage'),plan['provider_binding']['rates'],matched,tier))
  r['raw_model_text']=api.extract_text(envelope)
  require(matched and tier=='default','model_or_tier')
  require(r['observed_usage']['cost_estimate_usd'] is not None,'unknown_accounting')
  require(code==200 and envelope.get('status')=='completed' and not envelope.get('error'),'provider_status')
 except Exception as e:r['error']='timeout' if isinstance(e,TimeoutError) else type(e).__name__
 finally:r['elapsed_seconds']=time.perf_counter()-start
 return r
def assess(plan,cases,receipts,mode):
 require(plan==register()[0] and mode in ['mock','live'],'plan/source/mode drift');indexed={};slots={s['attempt_id']:s for s in plan['slots']};known=0;unknown=0;rows=[]
 for r in receipts:
  require(r['attempt_id'] in slots and r['attempt_id'] not in indexed,'duplicate/unplanned receipt')
  require(all(r[k]==v for k,v in slots[r['attempt_id']].items()) and r['is_mock'] is (mode=='mock'),'slot/mode mismatch')
  require(r['request']==body(plan,r['case_id'],r['condition']) and r['endpoint']==api.ENDPOINT,'frozen request mismatch')
  if r['raw_response'] is not None and r.get('response_complete') is True:
   try:envelope=strict_json(r['raw_response'])
   except ValueError:envelope=None
   if type(envelope) is dict:
    expected=api.observed_usage(envelope.get('usage'),plan['provider_binding']['rates'],envelope.get('model')=='gpt-6-astra',envelope.get('service_tier'));require(expected==r['observed_usage'],'usage raw join')
    try:text=api.extract_text(envelope)
    except ValueError:text=None
    require(text==r['raw_model_text'],'raw text join')
  indexed[r['attempt_id']]=r
 require(len(indexed)<=4,'HTTP bound')
 for slot in plan['slots']:
  r=indexed.get(slot['attempt_id']);row=dict(**slot,missing=r is None,success=False)
  if r:
   g=grade(r['raw_model_text'],cases[slot['case_id']]);u=r['observed_usage'];cost=u.get('cost_estimate_usd') if u else None
   violation=r['elapsed_seconds']>45 or cost is not None and cost>.2 or u is not None and u['input_tokens'] is not None and u['output_tokens'] is not None and u['input_tokens']+u['output_tokens']>12000
   row.update(**g,error=r['error'],elapsed_seconds=r['elapsed_seconds'],budget_violation=violation,cost_estimate_usd=cost)
   if cost is None:unknown+=1
   else:known+=cost
   operational=r.get('http_status')==200 and r.get('response_complete') is True and r.get('returned_model')=='gpt-6-astra' and r.get('returned_tier')=='default' and r.get('response_status')=='completed' and r['error'] is None
   row['success']=g['evidence_success'] and operational and not violation and cost is not None
  else:unknown+=1
  rows.append(row)
 return dict(version=VERSION,mode=mode,planned=4,http_calls=sum(r['transport_started'] for r in receipts),solver_calls=0,missing=sum(x['missing'] for x in rows),success=sum(x['success'] for x in rows),rows=rows,known_cost_estimate_usd=known,cost_estimate_usd=known if unknown==0 else None,unknown_cost_slots=unknown,billed_cost_usd=None,cost_basis='pinned_rates_estimate_not_billing')
def execute(plan,cases,directory,transport=None,*,allow_live=False,key_loader=None):
 require(plan==register()[0],'plan/source drift');mock=transport is not None
 require(mock or allow_live is True and callable(key_loader),'explicit live credential-use opt-in required')
 out=Path(directory);out.mkdir(mode=0o700);mode='mock' if mock else 'live';(out/'registration.json').write_text(canonical(dict(plan=plan,mode=mode))+'\n');receipts=[];stop=None
 with (out/'calls.jsonl').open('x') as stream:
  for slot in plan['slots']:
   spent=sum(r['observed_usage']['cost_estimate_usd'] for r in receipts if r['observed_usage'] and r['observed_usage']['cost_estimate_usd'] is not None)
   reserve=((len(canonical(body(plan,slot['case_id'],slot['condition'])).encode())+256)*12.5+2000*50)/1000000
   if spent+reserve>.8:stop='insufficient_remaining_reserve';break
   r=invoke(plan,slot,transport,key_loader,mock);stream.write(canonical(r)+'\n');stream.flush();receipts.append(r)
   u=r['observed_usage']
   if u is None or u['cost_estimate_usd'] is None:stop='unknown_accounting';break
   if r.get('returned_tier')!='default' or r.get('returned_model')!='gpt-6-astra':stop='model_or_tier_mismatch';break
   if u['cost_estimate_usd']>.2 or spent+u['cost_estimate_usd']>.8:stop='cost_allocation_violation';break
   if r['error'] is not None:stop='provider_or_response_error';break
 s=assess(plan,cases,receipts,mode);s['stop_reason']=stop;(out/'summary.json').write_text(canonical(s)+'\n');return s
def assess_saved(directory):
 out=Path(directory);saved=strict_json((out/'registration.json').read_text());p,c=register();require(saved['plan']==p,'saved plan mismatch');rows=[strict_json(x) for x in (out/'calls.jsonl').read_text().splitlines()];s=assess(p,c,rows,saved['mode']);s['stop_reason']=strict_json((out/'summary.json').read_text())['stop_reason'] if (out/'summary.json').exists() else 'interrupted_unfinalized';return s
