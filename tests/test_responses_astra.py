import json,tempfile,unittest,re
from pathlib import Path
from unittest.mock import patch
import responses_astra_runner as r
import responses_astra_transport as api
import test_responses_runner as helpers
import test_paired_runner as f
class AstraTests(unittest.TestCase):
 def config(self):
  c=helpers.config([f.cid('optional-forced'),f.cid('pair-deadline')]);c.update(version=r.VERSION,tool_call_limit=1,provider_revision=api.VERSION,provider_binding=api.binding('mock-model','mock-model','mock-responses-v1','low',2000,20,.08,dict(input_per_million=2,cached_input_per_million=.1,cache_write_30m_per_million=2.5,cache_write_12h_per_million=5,output_per_million=10,source='synthetic')));return c
 def factory(self,c,seen,mode='valid'):
  def send(b,t):
   seen.append(b);phase=b['instructions']
   if 'Phase TRANSLATE' in phase:
    inst=f.parse(b['input'].split('\n\nYou have one tool.')[0].replace(f.VIEW_FRAGMENT,f.RAW_FRAGMENT));out={'type':'tool_call','name':'csp','arguments':{'instance':inst}}
    if mode=='early':out={'type':'final','output':{'status':'UNKNOWN'}}
    if mode=='mismatch':
     for patient in out['arguments']['instance']['patients']:patient['duration']=1
   elif 'Phase FINAL' in phase:
    h=json.loads(b['input'].split('Your earlier tool calls and their results:\n')[1].split('\n\nWhen you have your answer')[0]);result=h[0]['result'];out={'type':'final','output':{k:v for k,v in result.items() if k in ['status','schedule','certificate']}}
    if mode=='extra':out={'type':'tool_call','name':'csp','arguments':h[0]['submitted_instance']}
   else:out={'type':'final','output':{'status':'UNKNOWN'}}
   text='{' if mode=='invalid' and 'Phase TRANSLATE' in phase else json.dumps(out)
   envelope={'model':'mock-model','status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}],'usage':{'input_tokens':100,'output_tokens':30,'input_tokens_details':{'cached_tokens':0}}}
   envelope['service_tier']='default';envelope['usage']['total_tokens']=130;envelope['usage']['input_tokens_details']['cache_write_tokens']=0;envelope['usage']['output_tokens_details']={'reasoning_tokens':0}
   return 200,{},json.dumps(envelope).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=send)
 def test_actual_requests_baseline_translation_and_final_phases(self):
  c=self.config();seen=[]
  with patch('socket.create_connection',side_effect=AssertionError('blocked')),tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'r';s=r.run(f.spec(),c,out,self.factory(c,seen));self.assertEqual(len(seen),6);self.assertEqual(s['by_arm']['csp']['success'],2);self.assertEqual(s['by_arm']['csp']['tool_calls'],2);self.assertEqual(r.assess_saved(f.spec(),out)['pairs'],s['pairs'])
   for b in seen:
    self.assertEqual(b['tools'],[])
    from responses_final_schema import FORMAT
    if 'Phase TRANSLATE:' in b['instructions']:self.assertNotIn('text',b)
    else:self.assertEqual(b['text'],FORMAT)
    if 'Phase TRANSLATE' in b['instructions']:self.assertIn('Tool definition:',b['input']);self.assertNotIn('When you have your answer',b['input'])
    elif 'Phase FINAL' in b['instructions']:self.assertNotIn('Tool definition:',b['input']);self.assertNotIn('To call it reply',b['input']);self.assertIn('"result":',b['input']);self.assertIn('Phase FINAL',b['instructions'])
    else:self.assertIsNone(re.search(r'\b(tool|tools|csp)\b',b['instructions']+' '+b['input'],re.I))
   self.assertNotIn('Authorization',(out/'attempts.jsonl').read_text())
 def test_early_repeat_and_invalid_fail_with_usage_denominators(self):
  for mode in ['early','extra','invalid']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    c=self.config();seen=[];s=r.run(f.spec(),c,Path(tmp)/'r',self.factory(c,seen,mode));self.assertEqual(s['by_arm']['csp']['success'],0);self.assertEqual(s['by_arm']['csp']['planned'],2);self.assertLessEqual(len(seen),6);self.assertLessEqual(s['by_arm']['csp']['tool_calls'],2);self.assertEqual(s['by_arm']['csp']['token_coverage'],[2,2])
 def test_mistranslation_not_sufficient_for_intended_success(self):
  c=self.config();seen=[]
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'r';s=r.run(f.spec(),c,out,self.factory(c,seen,'mismatch'));self.assertEqual(s['by_arm']['csp']['planned'],2);self.assertEqual(s['by_arm']['csp']['success'],0)
   rows=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()];self.assertTrue(any(x['solver_events'] for x in rows))
 def test_missing_slots_on_interruption_and_hard_bounds(self):
  c=self.config()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'r'
   def stop(*a):raise KeyboardInterrupt()
   with self.assertRaises(KeyboardInterrupt):r.run(f.spec(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=stop))
   s=r.assess_saved(f.spec(),out);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),4)
  for key,value in [('repetitions',2),('tool_call_limit',2)]:
   bad=dict(c);bad[key]=value
   with self.assertRaises(ValueError):r.config(bad)
 def test_model_input_and_version_identity(self):
  c=self.config();p,cases=r.make_plan(f.spec(),c);self.assertIn('responses_astra_transport.py',p['source_sha256']);self.assertEqual(len(p['slots']),4);self.assertEqual([s['arm'] for s in p['slots'][::2]].count('csp'),1)
 def test_schema_identity_subset_and_no_answer_specific_values(self):
  from responses_final_schema import SCHEMA,SHA256,valid
  self.assertEqual(self.config()['provider_binding']['final_schema_sha256'],SHA256)
  def walk(x):
   if type(x) is dict:
    if x.get('type')=='object':self.assertFalse(x['additionalProperties']);self.assertEqual(set(x['required']),set(x['properties']))
    for v in x.values():walk(v)
   elif type(x) is list:
    for v in x:walk(v)
  walk(SCHEMA);self.assertNotIn('anyOf',SCHEMA)
  self.assertTrue(valid({'type':'final','output':{'status':'FEASIBLE','schedule':[{'patient':'made_up','day':-10,'start':-1,'room':'unknown'}]}}))
  self.assertFalse(valid({'type':'final','output':{'status':'UNKNOWN','extra':0}}))
  bad=self.config()['provider_binding'];bad['final_schema_sha256']='changed'
  with self.assertRaises(ValueError):api.validate(bad)
 def test_refusal_incomplete_schema_error_timeout_and_bad_final_keep_usage(self):
  for mode in ['refusal','incomplete','schema_error','timeout','badshape','malformed']:
   with self.subTest(mode=mode):
    calls=[]
    def send(body,timeout):
     calls.append(body)
     if mode=='timeout':raise TimeoutError()
     text=json.dumps({'type':'final','output':{'status':'UNKNOWN','extra':'bad'}}) if mode=='badshape' else '{' if mode=='malformed' else json.dumps({'type':'final','output':{'status':'UNKNOWN'}})
     content=[{'type':'refusal','refusal':'synthetic refusal'}] if mode=='refusal' else [{'type':'output_text','text':text}]
     usage=None if mode=='schema_error' else {'input_tokens':100,'output_tokens':30,'input_tokens_details':{'cached_tokens':0}}
     raw={'model':'mock-model','status':'incomplete' if mode=='incomplete' else 'failed' if mode=='schema_error' else 'completed','incomplete_details':{'reason':'max_output_tokens'} if mode=='incomplete' else None,'output':[{'type':'message','role':'assistant','content':content}],'usage':usage}
     raw['service_tier']='default'
     if raw['usage'] is not None:raw['usage'].update(total_tokens=130,output_tokens_details={'reasoning_tokens':0});raw['usage']['input_tokens_details']['cache_write_tokens']=0
     return 400 if mode=='schema_error' else 200,{},json.dumps(raw).encode(),True
    client=api.ResponsesAdapter(self.config()['provider_binding'],transport=send)
    with self.assertRaises((ValueError,TimeoutError)):client.respond([{'role':'system','content':'Answer JSON.'},{'role':'user','content':'synthetic'}],[],{'token_limit':2000,'wall_seconds':20,'spending_remaining_usd':.3})
    self.assertEqual(len(calls),1);record=client.calls[0];api.validate_record(record,client.binding)
    if mode not in ['timeout','schema_error']:self.assertEqual(record['observed_usage']['input_tokens'],100)
 def test_http_schema_rejection_stops_without_retry_and_keeps_all_slots(self):
  c=self.config();calls=[]
  def send(body,timeout):
   calls.append(body);return 400,{},json.dumps({'model':'mock-model','status':'failed','output':[],'error':{'type':'invalid_request_error'},'usage':None}).encode(),True
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'r';s=r.run(f.spec(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=send));self.assertEqual(len(calls),1);self.assertEqual(sum(x['planned'] for x in s['by_arm'].values()),4);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),3)
 def test_phase_rendering_is_byte_identical_to_previous_protocol(self):
  import responses_phase_transport as previous
  from tier_a_contract import canonical
  for tools,history in [([],[]),([{'name':'csp','parameters':{'type':'object'}}],[]),([{'name':'csp'}],[{'arguments':{'instance':{}},'result':{'status':'UNKNOWN'}}])]:
   messages=[{'role':'system','content':'unchanged phase instructions'},{'role':'user','content':'unchanged original problem'}]
   for h in history:messages.extend([{'role':'assistant','content':canonical({'tool_call':{'name':'csp','arguments':h['arguments']}})},{'role':'tool','name':'csp','content':canonical(h['result'])}])
   self.assertEqual(api.render(messages,tools),previous.render(messages,tools))
 def test_astra_high_standard_profile_and_accounting(self):
  rates=dict(input_per_million=10,cached_input_per_million=1,cache_write_30m_per_million=12.5,cache_write_12h_per_million=25,output_per_million=50,source='synthetic official-rate fixture')
  b=api.binding('gpt-6-astra','gpt-6-astra','gpt-6-astra-high-standard-v1','high',2000,20,.2,rates);self.assertEqual(b['service_tier'],'default')
  with self.assertRaises(ValueError):api.binding('gpt-6-astra','gpt-6-astra','gpt-6-astra-high-standard-v1','low',2000,20,.2,rates)
  u={'input_tokens':1000,'output_tokens':100,'total_tokens':1100,'input_tokens_details':{'cached_tokens':200,'cache_write_tokens':300},'output_tokens_details':{'reasoning_tokens':80}}
  self.assertAlmostEqual(api.observed_usage(u,rates,True,'default')['cost_estimate_usd'],.01395)
  for k in ['cache_write_tokens','cached_tokens']:
   bad=json.loads(json.dumps(u));del bad['input_tokens_details'][k];self.assertIsNone(api.observed_usage(bad,rates,True,'default')['cost_estimate_usd'])
  for edit in [{'total_tokens':0},{'input_tokens':True},{'input_tokens':100}]:
   bad=dict(u,**edit);self.assertIsNone(api.observed_usage(bad,rates,True,'default')['cost_estimate_usd'])
  self.assertIsNone(api.observed_usage(u,rates,True,'unrecognized')['cost_estimate_usd'])
 def test_standard_tier_mismatch_stops_with_full_plan(self):
  c=self.config();calls=[]
  def send(body,timeout):
   calls.append(body);self.assertEqual(body['service_tier'],'default');self.assertEqual(body['prompt_cache_options'],{'ttl':'30m'})
   v={'model':'mock-model','service_tier':'fast','status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps({'type':'final','output':{'status':'UNKNOWN'}})}]}],'usage':{'input_tokens':100,'output_tokens':30,'total_tokens':130,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},'output_tokens_details':{'reasoning_tokens':10}}}
   return 200,{},json.dumps(v).encode(),True
  with tempfile.TemporaryDirectory() as tmp:
   s=r.run(f.spec(),c,Path(tmp)/'r',lambda:api.ResponsesAdapter(c['provider_binding'],transport=send));self.assertEqual(len(calls),1);self.assertEqual(sum(x['planned'] for x in s['by_arm'].values()),4);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),3)
 def test_reserve_blocks_before_key_or_http(self):
  c=self.config();b=dict(c['provider_binding']);b['call_budget_usd']=.000001
  client=api.ResponsesAdapter(b,transport=lambda *a:self.fail('must not call'))
  with self.assertRaises(ValueError):client.respond([{'role':'system','content':'JSON'},{'role':'user','content':'test'}],[],{'token_limit':2000,'wall_seconds':20,'spending_remaining_usd':.3})
  self.assertFalse(client.calls[0]['transport_started'])
 def test_total_reserve_and_observed_overrun_stop_new_slots(self):
  c=self.config();c['estimated_cost_ceiling_usd']=.000001
  with tempfile.TemporaryDirectory() as tmp:
   s=r.run(f.spec(),c,Path(tmp)/'r',lambda:api.ResponsesAdapter(c['provider_binding'],transport=lambda *a:self.fail('reserve must stop before HTTP')));self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),3)
  c=self.config();calls=[]
  def send(body,timeout):
   calls.append(body);u={'input_tokens':100,'output_tokens':10000,'total_tokens':10100,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},'output_tokens_details':{'reasoning_tokens':9990}}
   return 200,{},json.dumps({'model':'mock-model','service_tier':'default','status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps({'type':'final','output':{'status':'UNKNOWN'}})}]}],'usage':u}).encode(),True
  with tempfile.TemporaryDirectory() as tmp:
   s=r.run(f.spec(),c,Path(tmp)/'r',lambda:api.ResponsesAdapter(c['provider_binding'],transport=send));self.assertEqual(len(calls),1);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),3)
