"""Narrow four-slot CSP-condition diagnostic; not a no-tools comparison."""
from copy import deepcopy
from pathlib import Path
import json,hashlib,time
import responses_calibration_runner as old
import responses_handoff_runner as restored
import responses_calibration_transport as api
import paired_receipts as retention
from solver_interface import require,digest
from tier_a_contract import canonical,output_verdict
from tier_a_completion import well_formed
VERSION='csp-handoff-comparison-v1'
IDS=[old.IDS[0],old.IDS[2]]
PRIOR=Path('/home/t/tehxa/cs3263-review/balanced-calibration-20261107-4dtyuf13')
def make_plan(live,case_ids=None):
 require(type(live) is bool and (case_ids is None or case_ids==IDS),'exact two-case registration')
 c=json.loads((PRIOR/'settings-final.json').read_text());specs=json.loads((PRIOR/'datasets.json').read_text())
 c.update(version=restored.VERSION,execution_mode='responses_live' if live else 'responses_mock',estimated_cost_ceiling_usd=1.6)
 if not live:
  b=c['provider_binding'];c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','high',2000,20,.2,b['rates'])
 parent,cases=restored.make_plan(specs,c)
 pins=restored.source_pins();pins['handoff_comparison.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 slots=[dict(case_id=i,condition=condition,repetition=0,arm='csp') for i,conditions in zip(IDS,[('old','restored'),('restored','old')]) for condition in conditions]
 p=dict(version=VERSION,execution_config=c,parent_registration=parent,case_ids=IDS,slots=slots,maximum_http_calls=8,maximum_solver_calls=4,source_sha256=pins,ordering='fixed-case-order-balanced-start-condition-v1',conditions={'old':old.VERSION,'restored':restored.VERSION},maximum_planning_reserve_usd=8*((7500+256)*12.5+2000*50)/1000000)
 require(p['maximum_planning_reserve_usd']<=1.6,'whole-plan reserve insufficient')
 p['run_id']=digest(p)
 for s in slots:s['attempt_id']=digest(dict(run_id=p['run_id'],slot=s))
 return p,{i:cases[i] for i in IDS}
def assess(plan,cases,receipts):
 require(plan==make_plan(plan['execution_config']['execution_mode']=='responses_live')[0],'plan/source drift')
 slots=plan['slots'];lookup={s['attempt_id']:s for s in slots};indexed={};rows=[];calls=[]
 for r in receipts:
  require(r['attempt_id'] in lookup and r['attempt_id'] not in indexed,'duplicate/unplanned receipt')
  require(all(r[k]==v for k,v in lookup[r['attempt_id']].items()),'slot mismatch')
  for call in r['provider_calls']:api.validate_record(call,plan['execution_config']['provider_binding'])
  if r['raw_output'] is not None:
   require(bool(r['provider_calls']) and api.output_span(r['provider_calls'][-1]['raw_model_text'])==r['raw_output'],'raw final receipt join')
   require(__import__('tier_a_contract').strict_json(r['raw_output'])==r['normalized_output'],'normalized final join')
  require(len(r['provider_calls'])==len(r['call_accounting']),'call accounting join')
  for call,obs in zip(r['provider_calls'],r['call_accounting']):
   require(old.usage(call.get('observed_usage'))==obs['usage'],'usage join')
  require(len(r['provider_calls'])<=2 and len(r['solver_events'])<=1,'hard per-slot bounds')
  indexed[r['attempt_id']]=r;calls.extend(r['provider_calls'])
 require(len(calls)<=8 and sum(len(r['solver_events']) for r in receipts)<=4,'hard plan bounds')
 for s in slots:
  r=indexed.get(s['attempt_id']);row=dict(**s,missing=r is None,success=False,unknown=False,format_valid=False,complete=False,evidence_success=False)
  if r:
   v=output_verdict(cases[s['case_id']]['instance'],r['raw_output'],r['normalized_output'],r['normalization_errors'])
   cost=old.cost_summary([r]);tokens=r['token_usage'];valid_cost=cost['cost_estimate_usd'] is not None
   violation=r['elapsed_seconds']>45 or tokens is not None and sum(tokens.values())>12000 or any(x['cost_violation'] for x in r['provider_calls'])
   row.update(complete=r['termination']=='final',format_valid=bool(r['normalized_output'] is not None and __import__('responses_final_schema').valid({'type':'final','output':r['normalized_output']})),unknown=v['status']=='UNKNOWN',evidence_success=v['evidence_valid'],termination=r['termination'],provider_error=r['provider_error'],tool_error=r['tool_error'],budget_violation=violation,cost_estimate_usd=cost['cost_estimate_usd'])
   row['success']=row['complete'] and row['evidence_success'] and not r['provider_error'] and not r['tool_error'] and not r['resource_error'] and not violation and valid_cost
  rows.append(row)
 comparisons=[]
 for i in IDS:
  pair={r['condition']:r for r in receipts if r['case_id']==i};item=dict(case_id=i)
  if len(pair)==2:
   a,b=pair['old'],pair['restored'];ac,bc=a['provider_calls'],b['provider_calls']
   item.update(translation_requests_equal=bool(ac and bc and ac[0]['request']==bc[0]['request']),translations_equal=bool(a['solver_events'] and b['solver_events'] and a['solver_events'][0].get('translated_instance_sha256')==b['solver_events'][0].get('translated_instance_sha256')),solver_results_equal=bool(a['solver_events'] and b['solver_events'] and a['solver_events'][0]['result']==b['solver_events'][0]['result']))
   if len(ac)==len(bc)==2:
    x,y=ac[1]['request'],bc[1]['request'];item['final_differing_fields']=[k for k in set(x)|set(y) if x.get(k)!=y.get(k)];item['final_only_instruction_difference']=item['final_differing_fields']==['instructions']
  comparisons.append(item)
 costs=old.cost_summary(receipts)
 return dict(version=VERSION,planned=4,missing=sum(r['missing'] for r in rows),success=sum(r['success'] for r in rows),http_calls=len(calls),solver_calls=sum(len(r['solver_events']) for r in receipts),rows=rows,comparisons=comparisons,**costs)
def execute(plan,cases,directory,provider_factory=None,*,allow_live=False,key_loader=None):
 require(plan==make_plan(plan['execution_config']['execution_mode']=='responses_live')[0],'plan/source drift')
 c=deepcopy(plan['execution_config']);live=c['execution_mode']=='responses_live'
 require(not live or allow_live is True and callable(key_loader),'live requires opt-in and approved loader')
 require(live or callable(provider_factory),'explicit mock factory required')
 out=Path(directory);out.mkdir(mode=0o700);(out/'plan.json').write_text(canonical(plan)+'\n');receipts=[];stop=None
 with (out/'attempts.jsonl').open('x') as stream:
  for slot in plan['slots']:
   costs=old.cost_summary(receipts)
   if receipts and costs['cost_estimate_usd'] is None:stop='unknown_cost';break
   if receipts and any(x.get('error') or x.get('resource_error') or x.get('cost_violation') for r in receipts for x in r['provider_calls']):stop='provider_or_resource_failure';break
   if any(r['tool_error'] for r in receipts):stop='solver_error';break
   runtime=deepcopy(c);runtime['_spending_remaining']=1.6-costs['known_cost_estimate_usd']
   require(runtime['_spending_remaining']>0,'intended spend exhausted')
   engine=old if slot['condition']=='old' else restored
   runtime['version']=engine.VERSION
   factory=provider_factory if not live else lambda:api.ResponsesAdapter(c['provider_binding'],key_loader=key_loader,allow_live=True)
   receipt=engine.attempt(cases[slot['case_id']],slot,runtime,factory,engine.MergedSolver,allow_live=allow_live)
   receipt,line=retention.retain(out,receipt);stream.write(line);stream.flush();receipts.append(receipt)
 summary=assess(plan,cases,receipts);summary['stop_reason']=stop
 (out/'summary.json').write_text(canonical(summary)+'\n');return summary
