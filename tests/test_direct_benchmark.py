from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import json,tempfile,unittest,hashlib
import direct_benchmark as d
import direct_api_providers as api

def settings():return json.loads((d.ROOT/'docs/direct-api-settings.example.json').read_text())
class Reply:
 def __init__(self,answer):self.answer=answer;self.calls=[];self.seen=[]
 def call(self,prompt,budget):
  self.seen.append(prompt);r=dict(raw_model_text=self.answer if type(self.answer) is str else d.canonical(self.answer),response_complete=True,error=None,usage={'input_tokens':1,'output_tokens':1,'cost_estimate_usd':0},elapsed_seconds=0,fixture_not_model=True);self.calls.append(r);return r
class DirectTests(unittest.TestCase):
 def setUp(self):
  self.block=patch('socket.create_connection',side_effect=AssertionError('network forbidden'));self.block.start();self.addCleanup(self.block.stop)
  self.c=settings();self.plan,self.cases=d.make_plan(d.demo_specs(),self.c)
 def slot(self,arm,case=None):return next(s for s in self.plan['slots'] if s['arm']==arm and (case is None or s['case_id']==case))
 def test_one_baseline_call_zero_solver_and_valid_original_evidence(self):
  g=next(g for g in self.cases.values() if g['label']=='FEASIBLE');p=Reply({'type':'final','output':{'status':'FEASIBLE','schedule':g['evidence']['witness']}})
  row=d.attempt(self.slot('no_tools',g['case_id']),g,self.c,p,lambda:self.fail('no baseline solver'))
  self.assertEqual(len(p.calls),1);self.assertEqual(row['solver_events'],[]);self.assertTrue(row['success']);self.assertNotRegex(p.seen[0],r'(?i)\b(tool|tools|csp)\b')
 def test_one_assisted_call_one_solver_no_post_solver_call(self):
  g=next(g for g in self.cases.values() if g['label']=='FEASIBLE');p=Reply({'type':'tool_call','name':'csp','arguments':{'instance':g['instance']}});seen=[]
  class Solver(d.MergedSolver):
   def invoke(self,args):seen.append(deepcopy(args));return super().invoke(args)
  row=d.attempt(self.slot('csp',g['case_id']),g,self.c,p,Solver)
  self.assertEqual(len(p.calls),1);self.assertEqual(seen,[{'instance':g['instance']}]);self.assertEqual(len(row['solver_events']),1);self.assertTrue(row['success']);self.assertEqual(row['final_output']['schedule'],row['solver_output']['schedule'])
 def test_wrong_translation_is_not_repaired_or_scored_on_translation(self):
  g=next(g for g in self.cases.values() if g['label']=='FEASIBLE');bad=deepcopy(g['instance'])
  for patient in bad['patients']:patient['mandatory']=False
  p=Reply({'type':'tool_call','name':'csp','arguments':{'instance':bad}});row=d.attempt(self.slot('csp',g['case_id']),g,self.c,p)
  self.assertTrue(row['translation_valid']);self.assertTrue(row['format_valid']);self.assertFalse(row['success']);self.assertFalse(row['evidence_success']);self.assertEqual(row['solver_events'][0]['translated_instance_sha256'],d.digest(bad));self.assertEqual(g['instance'],self.cases[g['case_id']]['instance'])
 def test_malformed_fences_duplicate_keys_and_early_final_never_dispatch(self):
  g=next(iter(self.cases.values()))
  for answer in ['{broken','```json\n{}\n```','{"type":"tool_call","type":"final"}',{'type':'final','output':{'status':'UNKNOWN'}},{'type':'tool_call','name':'csp','arguments':{'instance':{'patients':{}}}}]:
   with self.subTest(answer=answer):
    p=Reply(answer);row=d.attempt(self.slot('csp',g['case_id']),g,self.c,p,lambda:self.fail('invalid translation dispatched'));self.assertFalse(row['success']);self.assertTrue(row['error']);self.assertEqual(len(p.calls),1);self.assertEqual(row['solver_events'],[])
 def test_unknown_malformed_solver_and_timeout_are_not_certificates(self):
  g=next(iter(self.cases.values()));p=Reply({'type':'tool_call','name':'csp','arguments':{'instance':g['instance']}})
  for result in [{'status':'UNKNOWN','reason':'bounded'},{'status':'FEASIBLE','schedule':[]},'timeout']:
   class Solver(d.MergedSolver):
    def invoke(self,args):
     if result=='timeout':raise TimeoutError()
     return deepcopy(result)
   row=d.attempt(self.slot('csp',g['case_id']),g,self.c,p,Solver);self.assertFalse(row['success']);self.assertEqual(row['final_output'],{'status':'UNKNOWN'});self.assertEqual(len(row['solver_events']),1)
 def test_full_fixture_preserves_inputs_counts_and_saved_assessment(self):
  directory=d.ROOT/'fixtures/responses-offline-v1/seeded-v2';before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()}
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';summary=d.run(d.demo_specs(),self.c,out);saved=d.assess(out)
   self.assertEqual(summary['by_arm'],saved['by_arm']);self.assertEqual(summary['planned_slots'],8);self.assertEqual(summary['received'],8)
   self.assertEqual(summary['by_arm']['no_tools']['model_calls'],4);self.assertEqual(summary['by_arm']['no_tools']['solver_calls'],0);self.assertEqual(summary['by_arm']['csp']['model_calls'],4);self.assertEqual(summary['by_arm']['csp']['solver_calls'],4);self.assertEqual(summary['by_arm']['csp']['success'],4)
   rows=[json.loads(s) for s in (out/'attempts.jsonl').read_text().splitlines()];rows[0]['success']=not rows[0]['success'];(out/'attempts.jsonl').write_text('\n'.join(d.canonical(r) for r in rows)+'\n')
   with self.assertRaises(ValueError):d.assess(out)
   with self.assertRaises(ValueError):d.run(d.demo_specs(),self.c,out)
  self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()})
 def test_interruption_preserves_all_missing_slots_without_retry(self):
  class Interrupted:
   def call(self,*args):raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run'
   with self.assertRaises(KeyboardInterrupt):d.run(d.demo_specs(),self.c,out,provider=Interrupted())
   result=d.assess(out);self.assertEqual(sum(a['missing'] for a in result['by_arm'].values()),8);self.assertTrue(all(a['cost_estimate_usd'] is None for a in result['by_arm'].values()))
 def test_configured_live_guard_and_legacy_cli_are_explicit(self):
  for changes in [{'provider':'claude_cli'},{'max_output_tokens':2001},{'call_seconds':21},{'mode':'live'},{'total_budget_usd':2.51}]:
   with self.subTest(changes=changes),self.assertRaises(ValueError):d.config(dict(self.c,**changes))
  specs=d.demo_specs();specs[0]['plan']['planned_case_ids']=specs[0]['plan']['planned_case_ids'][:-1]
  with self.assertRaises(ValueError):d.make_plan(specs,self.c)
 def test_identical_case_prefix_no_gold_metadata_and_counterbalance(self):
  self.assertEqual(self.plan,d.make_plan(d.demo_specs(),self.c)[0]);self.assertEqual([s['arm'] for s in self.plan['slots'][::2]].count('csp'),2)
  for g in self.cases.values():
   for arm in ['no_tools','csp']:
    p=d.prompt(g['text'],arm);self.assertTrue(p.startswith(g['text']+'\n\n'));self.assertNotIn(g['case_id'],p);self.assertNotIn('dataset_identity',p)


 def test_saved_assessment_rejects_missing_outputs_and_raw_join_bypass(self):
  g=next(g for g in self.cases.values() if g['label']=='FEASIBLE')
  for arm in ['no_tools','csp']:
   answer={'type':'final','output':{'status':'FEASIBLE','schedule':g['evidence']['witness']}} if arm=='no_tools' else {'type':'tool_call','name':'csp','arguments':{'instance':g['instance']}}
   row=d.attempt(self.slot(arm,g['case_id']),g,self.c,Reply(answer));self.assertTrue(row['success']);d.summarize(self.plan,self.cases,[row])
   for corruption in ['missing_final','missing_model_and_final','raw_join_bypass','missing_fields']:
    bad=deepcopy(row)
    if corruption=='missing_final':bad['final_output']=None
    else:
     bad.update(model_output=None,final_output=None,solver_output=None,solver_events=[])
     if corruption=='raw_join_bypass':bad.update(success=False,evidence_success=False,format_valid=False)
     if corruption=='missing_fields':bad.pop('model_output');bad.pop('final_output')
    with self.subTest(arm=arm,corruption=corruption),self.assertRaises(ValueError):d.summarize(self.plan,self.cases,[bad])
  # Invalid JSON-envelope content stays a received failure, never disappearing.
  row=d.attempt(self.slot('no_tools',g['case_id']),g,self.c,Reply({'type':'final','output':None}))
  result=d.summarize(self.plan,self.cases,[row]);self.assertEqual(result['received'],1);self.assertEqual(result['by_arm']['no_tools']['success'],0)

class ProviderTests(unittest.TestCase):
 def config(self,provider):return dict(settings(),provider=provider,model='mock-model')
 def envelope(self,provider,text='{"type":"final","output":{"status":"UNKNOWN"}}'):
  if provider=='openai_api':return dict(model='mock-model',status='completed',service_tier='default',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=text)])],usage=dict(input_tokens=10,output_tokens=2,total_tokens=12,input_tokens_details=dict(cached_tokens=0,cache_write_tokens=0),output_tokens_details=dict(reasoning_tokens=1)))
  return dict(model='mock-model',stop_reason='end_turn',content=[dict(type='text',text=text)],usage=dict(input_tokens=10,output_tokens=2,cache_read_input_tokens=0,cache_creation_input_tokens=0,service_tier='standard',speed='standard',inference_geo='global'))
 def test_both_providers_send_exactly_one_user_message(self):
  for provider in ['openai_api','anthropic_api']:
   c=self.config(provider);seen=[]
   def send(request,timeout):seen.append(request);return 200,{},json.dumps(self.envelope(provider)).encode(),True
   p=api.APIProvider(c,transport=send);r=p.call('exact user prompt',.2)
   self.assertEqual(len(seen),1);self.assertIsNone(r['error']);self.assertNotIn('system',seen[0]);self.assertNotIn('instructions',seen[0]);self.assertEqual(seen[0].get('messages',seen[0].get('input')),[{'role':'user','content':'exact user prompt'}])
 def test_missing_usage_refusal_incomplete_and_errors_do_not_retry(self):
  for provider in ['openai_api','anthropic_api']:
   for fault in ['usage','refusal','incomplete','timeout']:
    seen=[];c=self.config(provider);e=self.envelope(provider)
    if fault=='usage':e.pop('usage')
    elif fault=='refusal':
     if provider=='openai_api':e['output'][0]['content']=[{'type':'refusal','refusal':'synthetic'}]
     else:e['stop_details']={'type':'refusal'}
    elif fault=='incomplete':
     if provider=='openai_api':e['status']='incomplete'
     else:e['stop_reason']='max_tokens'
    def send(*a):
     seen.append(1)
     if fault=='timeout':raise TimeoutError('synthetic-secret-must-not-be-logged')
     return 200,{},json.dumps(e).encode(),True
    r=api.APIProvider(c,transport=send).call('prompt',.2);self.assertEqual(len(seen),1);self.assertNotIn('synthetic-secret',json.dumps(r))
    if fault=='usage':self.assertIsNone(r['usage']['cost_estimate_usd'])
    else:self.assertTrue(r['error'])
 def test_provider_cache_semantics_and_unknown_tier(self):
  rates=dict(input=2,output=10,cache_read=.2,cache_write_short=2.5,cache_write_long=4,source='synthetic')
  e=self.envelope('anthropic_api');e['usage'].update(input_tokens=10,output_tokens=2,cache_read_input_tokens=5,cache_creation_input_tokens=3,cache_creation={'ephemeral_5m_input_tokens':2,'ephemeral_1h_input_tokens':1})
  u=api.usage('anthropic_api',e,rates);self.assertEqual(u['input_tokens'],18);self.assertEqual(u['cost_estimate_usd'],(20+20+1+5+4)/1000000)
  e['usage']['service_tier']='unknown';self.assertIsNone(api.usage('anthropic_api',e,rates)['cost_estimate_usd'])
 def test_network_and_key_loader_are_never_implicit(self):
  for p in ['openai_api','anthropic_api']:
   with self.assertRaises(ValueError):api.APIProvider(self.config(p),key_loader=lambda:self.fail('key read'))
 def test_full_direct_workflow_for_each_api_selection(self):
  for provider in ['openai_api','anthropic_api']:
   c=self.config(provider);plan,cases=d.make_plan(d.demo_specs(),c);seen=[]
   def send(request,timeout):
    seen.append(request);text=request.get('messages',request.get('input'))[0]['content'];g=next(g for g in cases.values() if text.startswith(g['text']))
    if 'Instance schema:' in text:answer={'type':'tool_call','name':'csp','arguments':{'instance':g['instance']}}
    else:
     output={'status':g['label']};output.update({'schedule':g['evidence']['witness']} if g['label']=='FEASIBLE' else {'certificate':g['evidence']['certificate']});answer={'type':'final','output':output}
    return 200,{},json.dumps(self.envelope(provider,d.canonical(answer))).encode(),True
   with tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp)/'run';result=d.run(d.demo_specs(),c,out,provider=api.APIProvider(c,transport=send));self.assertEqual(len(seen),8)
    self.assertEqual(result['by_arm']['no_tools']['success'],4);self.assertEqual(result['by_arm']['csp']['success'],4);self.assertEqual(result['by_arm']['no_tools']['solver_calls'],0);self.assertEqual(result['by_arm']['csp']['solver_calls'],4);self.assertEqual(d.assess(out)['by_arm'],result['by_arm'])

 def test_malformed_provider_envelope_keeps_denominator_and_unknown_cost(self):
  for provider in ['openai_api','anthropic_api']:
   c=self.config(provider)
   p=api.APIProvider(c,transport=lambda *args:(200,{},b'{broken',True))
   with tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp)/'run';result=d.run(d.demo_specs(),c,out,provider=p)
    self.assertEqual(result['received'],1);self.assertEqual(sum(x['missing'] for x in result['by_arm'].values()),7)
    self.assertTrue(all(x['cost_estimate_usd'] is None for x in result['by_arm'].values()));self.assertEqual(result['by_arm'],d.assess(out)['by_arm'])

 def test_unsupported_encoding_valid_json_never_prices_or_scores(self):
  for provider in ['openai_api','anthropic_api']:
   c=self.config(provider)
   def send(*args):return 200,{},json.dumps(self.envelope(provider)).encode(),True,False,{'wire':{'encoding_supported':False}}
   with tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp)/'run';r=d.run(d.demo_specs(),c,out,provider=api.APIProvider(c,transport=send))
    self.assertEqual(r['received'],1);self.assertTrue(all(x['cost_estimate_usd'] is None for x in r['by_arm'].values()));self.assertEqual(r['by_arm'],d.assess(out)['by_arm'])
