"""Versioned direct Responses paired plans; old CLI runner remains unchanged."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,random,subprocess,time
import benchmark_datasets as catalog
import paired_receipts as retention
from solver_interface import CheckedSolver,MergedSolver,LIMITS,require,digest,limits as solver_limits
from surgerybench.temporal_benchmark import run_arm
from tier_a_contract import strict_json,output_verdict,canonical
from tier_a_completion import well_formed
from tier_a_input_view import SHARED
ARM={'no_tools':'','csp':''}
from study.accounting import attach,known_cost
HANDOFF_FINAL='Phase FINAL: the required checked invocation has completed. Base your final answer only on the supplied checked result: copy its schedule or certificate exactly into the required final envelope. If the result is FEASIBLE, output FEASIBLE with its complete schedule array unchanged. If the result is INFEASIBLE with a supplied certificate, output INFEASIBLE with that certificate object unchanged. Copy no diagnostic fields such as nodes or reason into the answer. If the result is UNKNOWN or reports an error or lacks the required evidence, output UNKNOWN; do not invent or repair evidence. No further invocation is available; do not request another.'
VERSION='responses-checked-handoff-restoration-v1'
IDS=['4110d965feeb8e31e4e94144','53760c24e8a90fdcf4ad402f','b2fe2af990bb7590f6631281','146c9dd291b62b6143c8a656']
DIRECTORY='/home/t/tehxa/cs3263-review/seeded-development-v2-96-20261105'
MANIFEST='d2c880f50dad90ce0593ce03c44e0650a1b7231d89c2ba71c6a529c4cc13af44'
KEYS={'version','provider_revision','case_ids','repetitions','seed','shuffle_cases','order','token_limit','wall_seconds','tool_call_limit','retry_limit','estimated_cost_ceiling_usd','currency','solver_revision','solver_limits'}
def cost_summary(receipts):
 amounts=[];known=[]
 for receipt in receipts:
  observations=receipt['call_accounting'];values=[x['usage'].get('cost_estimate_usd') if x['usage'] else None for x in observations]
  known.extend(x for x in values if known_cost(x))
  amounts.append(sum(values) if values and all(known_cost(x) for x in values) else None)
 return dict(cost_estimate_usd=sum(amounts) if all(x is not None for x in amounts) else None,known_cost_estimate_usd=sum(known),unknown_cost_estimate_runs=sum(x is None for x in amounts),cost_estimate_coverage=[sum(x is not None for x in amounts),len(amounts)])

def config(value):
 require(type(value) is dict and set(value)==KEYS|{'execution_mode','provider_binding'},'exact explicit runner configuration')
 value=deepcopy(value)
 require(value['execution_mode'] in ('responses_mock','responses_live'),'explicit Responses mode required')
 from responses_calibration_transport import validate,VERSION as ADAPTER
 validate(value['provider_binding']);require(value['provider_revision']==ADAPTER,'Responses adapter revision mismatch')
 require(value['execution_mode']!='responses_live' or value['provider_binding']['profile']!='mock-responses-v1','mock model cannot run live')
 require(value['version']==VERSION,'unsupported runner version')
 require(type(value['provider_revision']) is str and 0<len(value['provider_revision'])<=128,'provider revision required')
 ids=value['case_ids'];require(type(ids) is list and 1<=len(ids)<=512 and all(type(x) is str and 0<len(x)<=128 for x in ids) and len(set(ids))==len(ids),'explicit unique case selection')
 for k,lo,hi in [('repetitions',1,10),('seed',0,2**32-1),('token_limit',1,2**31-1),('wall_seconds',1,2**31-1),('tool_call_limit',0,4),('retry_limit',0,0)]:require(type(value[k]) is int and lo<=value[k]<=hi,'unsupported software setting: '+k)
 require(type(value['shuffle_cases']) is bool and value['order']=='counterbalanced_pairs','explicit supported order')
 require(known_cost(value['estimated_cost_ceiling_usd']) and value['estimated_cost_ceiling_usd']>0 and value['currency']=='USD','explicit positive USD whole-plan scheduling ceiling')
 require(type(value['solver_revision']) is str and bool(value['solver_revision']),'solver revision required')
 solver_limits(value['solver_limits'])
 require(value['tool_call_limit']==1 and value['repetitions']==1 and ids==IDS,'mandatory pilot hard slot/tool limits')
 return deepcopy(value)
def source_pins():
 names=['benchmark_datasets.py','solver_interface.py','hard_corpus_registration.py','tier_a_contract.py','tier_a_completion.py','tier_a_input_view.py','tier_a_inputs.py','development_registration.py','development_suites_audit.py','development_suites_v2.py','development_v3_registration.py','surgerybench/temporal_benchmark.py','surgerybench/temporal_check.py','surgerybench/checker.py','surgerybench/temporal_csp.py','study/accounting.py','study/prompts.py','paired_receipts.py','responses_runner.py','responses_transport.py','responses_credentials.py','tools/run_responses_paired.py']
 names.extend(['responses_handoff_runner.py','responses_calibration_runner.py','responses_calibration_transport.py','responses_astra_runner.py','responses_astra_transport.py','responses_structured_runner.py','responses_structured_transport.py','responses_final_schema.py','responses_mandatory_runner.py','responses_phase_runner.py','responses_phase_transport.py'])
 root=Path(__file__).resolve().parent;return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
def make_plan(specs,settings):
 require(type(specs) is list and len(specs)==1 and specs[0]['kind']=='seeded-v2' and Path(specs[0]['directory']).resolve()==Path(DIRECTORY) and specs[0]['plan']['manifest_sha256']==MANIFEST and specs[0]['plan']['planned_case_ids']==IDS,'exact calibration registration required')
 c=config(settings);cases,identities=catalog.load(specs);lookup={g['case_id']:g for g in cases}
 require(set(c['case_ids'])<=set(lookup),'unknown or unregistered selected ID')
 require(all(x['repetitions']==c['repetitions'] for x in identities),'registration/runner repetitions mismatch')
 ids=list(c['case_ids'])
 if c['shuffle_cases']:random.Random(c['seed']).shuffle(ids)
 offset=random.Random(c['seed']).randrange(2)
 slots=[]
 for rep in range(c['repetitions']):
  for position,i in enumerate(ids):
   arms=('no_tools','csp') if (position+rep+offset)%2==0 else ('csp','no_tools')
   slots.extend(dict(case_id=i,repetition=rep,arm=a) for a in arms)
 root=Path(__file__).resolve().parent
 revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
 plan=dict(version=VERSION,mode=c['execution_mode'],config=c,datasets=identities,slots=slots,source_sha256=source_pins(),git_revision=revision,seed_scope='local_case_order_and_initial_arm_offset_only',ordering_version='counterbalanced-position-parity-v1',retention_policy=retention.policy(),instruction_sha256={k:digest(v) for k,v in dict(shared=SHARED,**ARM).items()})
 plan['run_id']=digest(plan)
 for slot in plan['slots']:slot['attempt_id']=digest(dict(run_id=plan['run_id'],slot=slot))
 return plan,{i:lookup[i] for i in c['case_ids']}
def usage(value):
 if type(value) is not dict:return None
 out={k:value.get(k) if type(value.get(k)) is int and value[k]>=0 else None for k in ('input_tokens','output_tokens')}
 out['cost_estimate_usd']=value.get('cost_estimate_usd') if known_cost(value.get('cost_estimate_usd')) else None
 return out
class Bridge:
 def __init__(self,provider,arm,c):
  from responses_calibration_transport import ResponsesAdapter
  require(type(provider) is ResponsesAdapter and provider.binding==c['provider_binding'],'pinned Responses adapter required')
  require(provider.is_mock is (c['execution_mode']=='responses_mock'),'transport/mode mismatch')
  require(getattr(provider,'revision',None)==c['provider_revision'],'provider revision mismatch')
  self.provider,self.arm,self.c=provider,arm,c;self.raw=None;self.normalized=None;self.normalization_errors=[];self.attempt_accounting=[];self.timeout=False;self.started=time.perf_counter()
 def next(self,text,history,tools):
  messages=[dict(role='system',content=SHARED+'\n'+ARM[self.arm]),dict(role='user',content=text)]
  for h in history:
   messages.extend([dict(role='assistant',content=canonical(dict(tool_call=dict(name='csp',arguments=h['arguments'])))),dict(role='tool',name='csp',content=canonical(h['result']))])
  if self.arm=='csp':
   require(len(history)<=1,'one checked result maximum')
   messages[0]['content']+='\n'+('Phase TRANSLATE: translate the original problem into the documented instance and return exactly one csp tool_call object. A final answer is forbidden in this phase.' if not history else HANDOFF_FINAL)
  logged=False;called=False
  try:
   used=sum(sum(x['usage'][k] for k in ('input_tokens','output_tokens')) for x in self.attempt_accounting if x['usage'] and all(type(x['usage'][k]) is int for k in ('input_tokens','output_tokens')))
   require(not self.attempt_accounting or all(x['usage'] and all(x['usage'][k] is not None for k in ('input_tokens','output_tokens','cost_estimate_usd')) for x in self.attempt_accounting),'unknown usage stops further turns')
   require(not any(x.get('cost_violation') or x.get('resource_error') for x in getattr(self.provider,'calls',[])),'prior call allocation/resource violation stops further turns')
   remaining=self.c['wall_seconds']-(time.perf_counter()-self.started)
   if remaining<=0:raise TimeoutError('attempt wall allocation exhausted')
   spent=sum(x['usage']['cost_estimate_usd'] for x in self.attempt_accounting if x['usage'] and x['usage']['cost_estimate_usd'] is not None)
   budget=self.c.get('_spending_remaining',self.c['estimated_cost_ceiling_usd'])-spent
   require(used<self.c['token_limit'] and budget>0,'attempt allocation exhausted')
   called=True
   reply=self.provider.respond(deepcopy(messages),deepcopy(tools),dict(token_limit=self.c['token_limit']-used,wall_seconds=remaining,spending_remaining_usd=budget))
   require(type(reply) is dict,'provider envelope object')
   observed=usage(reply.get('usage'));self.attempt_accounting.append(dict(usage=observed,reason='provider observed report; missing values stay unknown'));logged=True
   require(len(canonical(reply).encode())<=1024*1024,'provider envelope software byte bound')
   if reply.get('type')=='final':
    require(self.arm!='csp' or len(history)==1,'mandatory_csp_early_final')
    require(set(reply)=={'type','raw','usage'} and type(reply['raw']) is str,'final requires raw JSON string and usage')
    self.raw=reply['raw']
    try:self.normalized=strict_json(self.raw)
    except (ValueError,RecursionError):self.normalized=None;self.normalization_errors=['invalid final JSON']
    return dict(type='final',output=deepcopy(self.normalized),usage=observed)
   require(set(reply)=={'type','name','arguments','usage'} and reply['type']=='tool_call' and reply['name']=='csp','unsupported provider/tool envelope')
   require(self.arm=='csp' and len(history)==0,'mandatory_csp_extra_or_forbidden_call')
   return dict(type='tool_call',name='csp',arguments=deepcopy(reply['arguments']),usage=observed)
  except Exception as error:
   if called and not logged:self.attempt_accounting.append(dict(usage=usage(getattr(error,'observed_usage',None)),reason=type(error).__name__))
   if isinstance(error,TimeoutError):self.timeout=True;raise TimeoutError('provider timeout') from None
   raise ValueError('provider contract/execution error: '+type(error).__name__) from None
def attempt(case,slot,c,provider_factory,solver_factory,*,allow_live=False):
 require(c['execution_mode']=='responses_mock' or allow_live is True,'live attempt requires explicit opt-in')
 started=time.perf_counter();bridge=None;checked=None;stage='provider';initial_timeout=False
 try:
  provider=provider_factory();bridge=Bridge(provider,slot['arm'],c)
  if slot['arm']=='csp':
   stage='solver';checked=CheckedSolver(solver_factory(),c['solver_revision'],c['solver_limits'])
  stage='provider'
  row=run_arm(bridge,case['text'],slot['arm'],checked or MergedSolver(),max_calls=c['tool_call_limit']);row=attach(row,bridge)
 except Exception as error:
  initial_timeout=isinstance(error,TimeoutError)
  row=dict(output=None,errors=[dict(stage='provider_or_parse',error=type(error).__name__)],responses=[],tool_calls=[],tool_call_count=0,parsing_or_provider_error=stage=='provider',tool_error=stage=='solver',token_usage=None,token_usage_reason='factory or interface initialization failed',call_accounting=[dict(usage=None,reason=type(error).__name__)])
 elapsed=time.perf_counter()-started;events=checked.events if checked else []
 timeout=initial_timeout or bool(bridge and bridge.timeout) or any(e['timeout'] for e in events)
 provider_error=bool(row['parsing_or_provider_error']);tool_error=bool(row['tool_error']) or any(e['error'] for e in events)
 resource=next((x['resource_error'] for x in getattr(bridge.provider,'calls',[]) if x.get('resource_error')),None) if bridge else None
 termination='resource_bound' if resource else 'final' if bridge and bridge.raw is not None else 'timeout' if timeout else 'provider_error' if provider_error else 'tool_error' if tool_error else 'provider_error'
 return dict(**slot,raw_output=bridge.raw if bridge else None,normalized_output=deepcopy(bridge.normalized) if bridge else None,normalization_errors=list(bridge.normalization_errors) if bridge else [],provider_error=provider_error,tool_error=tool_error,termination=termination,elapsed_seconds=elapsed,token_usage=row['token_usage'],token_usage_reason=row.get('token_usage_reason'),call_accounting=row.get('call_accounting',[]),tool_calls=deepcopy(row['tool_calls']),solver_events=deepcopy(events),provider_calls=deepcopy(getattr(bridge.provider,'calls',[])) if bridge else [],retained_evidence=None,resource_error=next((x['resource_error'] for x in getattr(bridge.provider,'calls',[]) if x.get('resource_error')),None) if bridge else None)
FIELDS={'attempt_id','case_id','repetition','arm','raw_output','normalized_output','normalization_errors','provider_error','tool_error','termination','elapsed_seconds','token_usage','token_usage_reason','call_accounting','tool_calls','solver_events','provider_calls','resource_error','retained_evidence'}
def summarize(plan,cases,receipts):
 c=config(plan['config']);slots={(s['case_id'],s['repetition'],s['arm']) for s in plan['slots']};attempt_ids={(s['case_id'],s['repetition'],s['arm']):s['attempt_id'] for s in plan['slots']}
 require(len(slots)==len(plan['slots'])==len(cases)*c['repetitions']*2,'planned-slot identity')
 require(type(receipts) is list and len(receipts)<=len(slots),'bounded attempt count');indexed={}
 for item in receipts:
  require(type(item) is dict and set(item)==FIELDS,'attempt fields')
  require(type(item['case_id']) is str and type(item['repetition']) is int and type(item['arm']) is str,'routing types')
  key=(item['case_id'],item['repetition'],item['arm']);require(key in slots and key not in indexed,'duplicate/unplanned slot')
  require(item['attempt_id']==attempt_ids[key],'attempt identity mismatch')
  require(type(item['provider_error']) is bool and type(item['tool_error']) is bool,'error flag types')
  require(item['termination'] in ('final','timeout','provider_error','tool_error','resource_bound'),'termination')
  require(type(item['normalization_errors']) is list and all(type(x) is str for x in item['normalization_errors']),'normalization errors')
  n=item['elapsed_seconds'];require(type(n) in (int,float) and 0<=n<10**9 and (type(n) is int or math.isfinite(n)),'elapsed bound/type')
  require(item['raw_output'] is None or type(item['raw_output']) is str and len(item['raw_output'].encode('utf-8','surrogatepass'))<=1024*1024,'raw retention bound')
  require(len(canonical(item).encode())<=retention.EVIDENCE_BYTES+4096,'bounded complete JSON receipt')
  require(item['resource_error'] in (None,'request_bound','envelope_bound','aggregate_receipt_bound','evidence_bound','service_tier_mismatch'),'resource outcome')
  require(item['retained_evidence'] is None or type(item['retained_evidence']) is dict,'retained evidence reference')
  if item['resource_error'] in ('aggregate_receipt_bound','evidence_bound'):
   require(type(item['retained_evidence']) is dict and item['retained_evidence'].get('opaque') is (item['resource_error']=='evidence_bound'),'resource reference/outcome mismatch')
  else:require(item['retained_evidence'] is None,'unexpected retained evidence reference')
  require(type(item['provider_calls']) is list and len(item['provider_calls'])<=5,'provider raw ledger bound')
  observed_resources={x.get('resource_error') for x in item['provider_calls'] if type(x) is dict and x.get('resource_error')}
  require(item['resource_error'] in ('aggregate_receipt_bound','evidence_bound') or observed_resources==({item['resource_error']} if item['resource_error'] else set()),'resource history/outcome mismatch')
  require(type(item['call_accounting']) is list and len(item['call_accounting'])<=5 and all(type(x) is dict and set(x)=={'usage','reason'} and type(x['reason']) is str and (x['usage'] is None or x['usage']==usage(x['usage'])) for x in item['call_accounting']),'usage accounting shape')
  require(item['token_usage'] is None or type(item['token_usage']) is dict and set(item['token_usage'])=={'input_tokens','output_tokens'} and all(type(x) is int and x>=0 for x in item['token_usage'].values()),'token usage shape')
  require(type(item['tool_calls']) is list and type(item['solver_events']) is list and len(item['tool_calls'])==len(item['solver_events'])<=c['tool_call_limit'],'tool history/event bounds')
  require(item['arm']=='csp' or not item['tool_calls'],'no_tools history forbidden')
  for event in item['solver_events']:
   require(type(event) is dict and type(event.get('error')) is bool and type(event.get('timeout')) is bool,'solver event flags')
   require(item['tool_error'] or not event['error'],'contradictory tool error flag')
  if c['execution_mode'] in ('responses_mock','responses_live') and item['provider_calls']:
   require(len(item['provider_calls'])==len(item['call_accounting']),'call allocation/accounting join')
   for call,observation in zip(item['provider_calls'],item['call_accounting']):
    require(type(call) is dict and known_cost(call.get('budget_usd')) and call['budget_usd']>0 and call['budget_usd']<=c['provider_binding']['call_budget_usd'],'recorded call allocation')
    require(usage(call.get('observed_usage'))==observation['usage'],'call usage join')
    cost=observation['usage']['cost_estimate_usd'] if observation['usage'] else None
    require(call.get('cost_violation') is (known_cost(cost) and cost>call['budget_usd']),'call overrun flag mismatch')
  if item['resource_error']!='evidence_bound':
   from responses_calibration_transport import validate_record,output_span
   for call in item['provider_calls']:validate_record(call,c['provider_binding'])
   if item['raw_output'] is not None:
    require(bool(item['provider_calls']) and type(item['provider_calls'][-1].get('raw_model_text')) is str,'raw final HTTP/model-text join')
    text=item['provider_calls'][-1]['raw_model_text'];outer=strict_json(text)
    require(type(outer) is dict and outer.get('type')=='final' and output_span(text)==item['raw_output'],'HTTP/model raw final differs from scored output')
  observations=item['call_accounting'];complete=bool(observations) and all(x['usage'] is not None and all(type(x['usage'][k]) is int for k in ('input_tokens','output_tokens')) for x in observations)
  expected={k:sum(x['usage'][k] for x in observations) for k in ('input_tokens','output_tokens')} if complete else None
  require(item['token_usage']==expected,'token aggregate mismatch');indexed[key]=item
 rows=[];running_known=0
 for slot in plan['slots']:
  key=(slot['case_id'],slot['repetition'],slot['arm']);g=cases[key[0]];r=indexed.get(key)
  out=dict(**slot,family=g['family'],label=g['label'],missing=r is None,execution_terminal=r is not None,answer_complete=False,evidence_success=False,success=False,unknown=False,output_error=False,operational_error=False,budget_violation=False,budget_unknown=False,call_budget_violation=False,resource_bound=False,opaque_evidence=False,timeout=False,status_agreement=False,infeasible_decision=False)
  if r:
   v=output_verdict(g['instance'],r['raw_output'],r['normalized_output'],r['normalization_errors']);out.update(answer_complete=r['termination']=='final' and well_formed(r),evidence_success=v['evidence_valid'] and v['status']==g['label'],unknown=v['status']=='UNKNOWN',output_error=v['output_error'],operational_error=r['provider_error'] or r['tool_error'] or r['termination']!='final' or r['resource_error'] is not None,timeout=r['termination']=='timeout' or any(e['timeout'] for e in r['solver_events']),status_agreement=v['status']==g['label'],infeasible_decision=g['label']=='INFEASIBLE' and v['status']=='INFEASIBLE')
   before_attempt=running_known
   if c['execution_mode'] in ('responses_mock','responses_live'):
    before_call=0
    for call,observation in zip(r['provider_calls'],r['call_accounting']):
     expected=min(c['provider_binding']['call_budget_usd'],(c['estimated_cost_ceiling_usd']-before_attempt)-before_call)
     require(expected>0 and call['budget_usd']==expected,'call allocation differs from plan remainder')
     cost=observation['usage']['cost_estimate_usd'] if observation['usage'] else None
     out['call_budget_violation']|=known_cost(cost) and cost>call['budget_usd']
     if known_cost(cost):before_call+=cost
   out['resource_bound']=r['resource_error'] is not None
   out['opaque_evidence']=r['resource_error']=='evidence_bound'
   running_known+=cost_summary([r])['known_cost_estimate_usd'];tokens=r['token_usage']
   out['budget_violation']=out['call_budget_violation'] or r['elapsed_seconds']>c['wall_seconds'] or tokens is not None and sum(tokens.values())>c['token_limit'] or running_known>c['estimated_cost_ceiling_usd']
   out['budget_unknown']=tokens is None or cost_summary([r])['cost_estimate_usd'] is None
   out['success']=out['evidence_success'] and not out['operational_error'] and not out['budget_violation'] and not out['budget_unknown']
  rows.append(out)
 def group(rs):
  result=dict(planned=len(rs),**{k:sum(bool(r[k]) for r in rs) for k in ('missing','execution_terminal','answer_complete','success','evidence_success','unknown','output_error','operational_error','budget_violation','budget_unknown','call_budget_violation','resource_bound','opaque_evidence','timeout','status_agreement','infeasible_decision')})
  result.update(feasible_planned=sum(r['label']=='FEASIBLE' for r in rs),negative_planned=sum(r['label']=='INFEASIBLE' for r in rs),feasible_success=sum(r['success'] and r['label']=='FEASIBLE' for r in rs),negative_success=sum(r['success'] and r['label']=='INFEASIBLE' for r in rs));return result
 row_index={(r['case_id'],r['repetition'],r['arm']):r for r in rows}
 pairs=dict(both=0,no_tools_only=0,csp_only=0,neither=0,incomplete=0)
 for i in cases:
  for rep in range(c['repetitions']):
   a,b=(row_index[i,rep,arm] for arm in ('no_tools','csp'))
   bucket='incomplete' if not a['answer_complete'] or not b['answer_complete'] else 'both' if a['success'] and b['success'] else 'no_tools_only' if a['success'] else 'csp_only' if b['success'] else 'neither';pairs[bucket]+=1
 by_arm={a:dict(**group([r for r in rows if r['arm']==a]),**cost_summary([r for r in receipts if r['arm']==a])) for a in ('no_tools','csp')}
 for a in by_arm:
  received=[r for r in receipts if r['arm']==a]
  missing=by_arm[a]['planned']-len(received)
  by_arm[a]['cost_estimate_coverage'][1]=by_arm[a]['planned'];by_arm[a]['unknown_cost_estimate_runs']+=missing
  if missing:by_arm[a]['cost_estimate_usd']=None
  known=[r['token_usage'] for r in received if r['token_usage'] is not None]
  by_arm[a].update(token_coverage=[len(known),by_arm[a]['planned']],known_tokens=sum(sum(x.values()) for x in known),tokens_total=sum(sum(x.values()) for x in known) if len(known)==by_arm[a]['planned'] else None,observed_elapsed_seconds=sum(r['elapsed_seconds'] for r in received),tool_calls=sum(len(r['tool_calls']) for r in received),solver_elapsed_seconds=sum(e['elapsed_seconds'] for r in received for e in r['solver_events']),provider_errors=sum(r['provider_error'] for r in received),tool_errors=sum(r['tool_error'] for r in received))
 return dict(version=VERSION,status='mock_responses_not_model_results' if c['execution_mode']=='responses_mock' else 'responses_receipts_not_research_acceptance',cost_basis='estimate_from_pinned_rates_not_billing',billed_cost_usd=None,by_arm=by_arm,pairs=pairs,by_family={f:{a:group([r for r in rows if r['family']==f and r['arm']==a]) for a in ('no_tools','csp')} for f in sorted({r['family'] for r in rows})},rows=rows)
def run(specs,settings,directory,provider_factory=None,solver_factory=MergedSolver,*,allow_live=False,key_loader=None):
 plan,cases=make_plan(specs,settings);c=plan['config']
 if c['execution_mode']=='responses_live':
  require(allow_live is True,'live transport requires separate explicit opt-in')
  from responses_calibration_transport import ResponsesAdapter
  require(callable(key_loader) or provider_factory is not None,'explicit approved key-file loader required')
  if provider_factory is None:provider_factory=lambda:ResponsesAdapter(c['provider_binding'],key_loader=key_loader,allow_live=True)
 require(callable(provider_factory),'explicit provider factory required')
 out=Path(directory);out.mkdir(mode=0o700)
 (out/'plan.json').write_text(canonical(plan)+'\n');receipts=[];stopped=None
 with (out/'attempts.jsonl').open('x') as stream:
  for slot in plan['slots']:
   costs=cost_summary(receipts)
   if receipts and costs['cost_estimate_usd'] is None:stopped='unknown_cost_stopped_new_slots';break
   if receipts and costs['known_cost_estimate_usd']>=c['estimated_cost_ceiling_usd']:stopped='estimated_cost_ceiling_usd_stopped_new_slots';break
   runtime=deepcopy(c);runtime['_spending_remaining']=c['estimated_cost_ceiling_usd']-costs['known_cost_estimate_usd']
   r=attempt(cases[slot['case_id']],slot,runtime,provider_factory,solver_factory,allow_live=allow_live)
   r,line=retention.retain(out,r)
   stream.write(line);stream.flush();receipts.append(r)
   if r['provider_error'] and any(call.get('error') and not call.get('transport_started',True) for call in r['provider_calls']):stopped='pre_transport_failure_stopped_new_slots';break
   if r['resource_error']:stopped='resource_bound_stopped_new_slots';break
   if any(call.get('cost_violation') for call in r['provider_calls']):stopped='call_allocation_overrun_stopped_new_slots';break
 summary=summarize(plan,cases,receipts);summary['stop_reason']=stopped
 (out/'summary.json').write_text(canonical(summary)+'\n');return summary
def assess_saved(specs,directory):
 out=Path(directory);require((out/'plan.json').stat().st_size<=4*1024*1024,'plan bound');plan=strict_json((out/'plan.json').read_text());current,cases=make_plan(specs,plan['config']);require(current==plan,'saved plan/source/dataset drift')
 receipts=retention.read(out,len(plan['slots']))
 return summarize(plan,cases,receipts)
