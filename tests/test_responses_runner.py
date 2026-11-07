from copy import deepcopy
from pathlib import Path
import json,tempfile,unittest,collections
from unittest.mock import patch
import responses_runner as runner
import responses_transport as api
import paired_runner as legacy_runner
import test_paired_runner as fixtures
from surgerybench.temporal_text import parse
from tier_a_input_view import RAW_FRAGMENT,VIEW_FRAGMENT

def config(ids=None):
 c=fixtures.config(ids);c['estimated_cost_ceiling_usd']=c.pop('spending_ceiling')
 c.update(version=runner.VERSION,execution_mode='responses_mock',provider_revision=api.VERSION,provider_binding=api.binding('mock-model','mock-model','mock-responses-v1','low',200,3,.1,dict(input_per_million=2,cached_input_per_million=.2,output_per_million=10,source='synthetic rates')),order='counterbalanced_pairs')
 return c
class RunnerTests(unittest.TestCase):
 def setUp(self):self.block=patch('socket.create_connection',side_effect=AssertionError('network forbidden'));self.block.start();self.addCleanup(self.block.stop)
 def factory(self,c,seen):
  def transport(body,timeout):
   seen.append(deepcopy(body));text=body['input']
   if 'Your earlier tool calls and their results:\n' in text:
    history=json.loads(text.split('Your earlier tool calls and their results:\n')[1]);result=history[-1]['result'];out=dict(type='final',output={k:v for k,v in result.items() if k in ('status','schedule','certificate')})
   elif 'Tool definition:' in text:
    case=text.split('\n\nWhen you have your answer,')[0];out=dict(type='tool_call',name='csp',arguments=dict(instance=parse(case.replace(VIEW_FRAGMENT,RAW_FRAGMENT))))
   else:out=dict(type='final',output={'status':'UNKNOWN'})
   response=dict(id='synthetic',model='mock-model',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=json.dumps(out))])],usage=dict(input_tokens=100,output_tokens=20,input_tokens_details=dict(cached_tokens=0)))
   return 200,{},json.dumps(response).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=transport)
 def test_balanced_reproducible_order_and_both_arm_tool_roundtrip(self):
  ids=[fixtures.cid(x) for x in ('room-gap-5','optional-omitted','optional-forced','pair-deadline')];c=config(ids)
  p,cases=runner.make_plan(fixtures.spec(),c);self.assertEqual(p,runner.make_plan(fixtures.spec(),c)[0]);self.assertEqual(collections.Counter(s['arm'] for s in p['slots'][::2]),{'no_tools':2,'csp':2})
  seen=[]
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';summary=runner.run(fixtures.spec(),c,out,self.factory(c,seen));self.assertEqual(summary['by_arm']['csp']['success'],4);self.assertEqual(summary['by_arm']['no_tools']['unknown'],4);self.assertEqual(len(seen),12)
   self.assertEqual(runner.assess_saved(fixtures.spec(),out)['pairs'],summary['pairs']);self.assertIsNone(summary['billed_cost_usd']);self.assertEqual(summary['cost_basis'],'estimate_from_pinned_rates_not_billing')
   for case in cases.values():
    inputs=[b['input'].split('\n\nWhen you have your answer,')[0] for b in seen if b['input'].startswith(case['text'])];self.assertTrue(inputs);self.assertTrue(all(x==case['text'] for x in inputs))
   self.assertTrue(all(b['tools']==[] for b in seen));self.assertNotIn('Authorization',(out/'plan.json').read_text());self.assertNotIn('OPENAI_API_KEY',(out/'attempts.jsonl').read_text())
   with self.assertRaises(FileExistsError):runner.run(fixtures.spec(),c,out,self.factory(c,[]))
 def test_odd_count_counterbalances_across_repetitions(self):
  c=config([fixtures.cid(x) for x in ('room-gap-5','optional-omitted','optional-forced')]);c['repetitions']=2;spec=fixtures.spec();spec[0]['plan']['repetitions']=2
  p,_=runner.make_plan(spec,c);self.assertEqual(collections.Counter(s['arm'] for s in p['slots'][::2]),{'no_tools':3,'csp':3})
  for cid in c['case_ids']:self.assertEqual({p['slots'][i]['arm'] for i in range(0,len(p['slots']),2) if p['slots'][i]['case_id']==cid},{'no_tools','csp'})
 def test_interruption_and_missing_slots_cost_coverage(self):
  c=config();p,cases=runner.make_plan(fixtures.spec(),c)
  def transport(*a):raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run'
   with self.assertRaises(KeyboardInterrupt):runner.run(fixtures.spec(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=transport))
   s=runner.assess_saved(fixtures.spec(),out);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),2);self.assertTrue(all(x['cost_estimate_usd'] is None for x in s['by_arm'].values()));self.assertEqual(s['pairs']['incomplete'],1)
 def test_legacy_plan_and_source_identity_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'old';old=legacy_runner.run(fixtures.spec(),fixtures.config(),out,fixtures.Fixture)
   self.assertEqual(legacy_runner.assess_saved(fixtures.spec(),out)['pairs'],old['pairs'])
 def test_fail_closed_before_live_loader_or_factory(self):
  c=config();c.update(execution_mode='responses_live',provider_binding=api.binding('gpt-6.1-sol','gpt-6.1-sol','gpt-6.1-sol-text-json-v1','low',200,3,.1,dict(input_per_million=2,cached_input_per_million=.2,output_per_million=10,source='synthetic test rates')))
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):runner.run(fixtures.spec(),c,Path(tmp)/'run',key_loader=lambda:self.fail('must not load'))
   self.assertFalse((Path(tmp)/'run').exists())
 def test_unknown_usage_timeout_and_bad_outputs_keep_planned_failures(self):
  for mode in ('missing','timeout','invalid','native'):
   c=config();calls=[]
   def fake(*a):
    calls.append(1)
    if mode=='timeout':raise TimeoutError()
    response=dict(model='mock-model',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='{broken' if mode=='invalid' else '{"type":"final","output":{"status":"UNKNOWN"}}')])])
    if mode!='missing':response['usage']=dict(input_tokens=100,output_tokens=20,input_tokens_details=dict(cached_tokens=0))
    if mode=='native':response['output']=[dict(type='function_call',name='unapproved')]
    return 200,{},json.dumps(response).encode(),True
   with tempfile.TemporaryDirectory() as tmp:
    out=Path(tmp)/'run';r=runner.run(fixtures.spec(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=fake))
    self.assertEqual(sum(v['planned'] for v in r['by_arm'].values()),2);self.assertEqual(sum(v['success'] for v in r['by_arm'].values()),0);self.assertEqual(runner.assess_saved(fixtures.spec(),out)['pairs'],r['pairs'])
    if mode in ('missing','timeout'):self.assertEqual(len(calls),1);self.assertEqual(sum(v['missing'] for v in r['by_arm'].values()),1)
 def test_wrong_intended_evidence_cannot_be_repaired_by_translation(self):
  c=config();out={'status':'FEASIBLE','schedule':[]}
  def fake(*a):return 200,{},json.dumps(dict(model='mock-model',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=json.dumps(dict(type='final',output=out)))])],usage=dict(input_tokens=100,output_tokens=20,input_tokens_details=dict(cached_tokens=0)))).encode(),True
  with tempfile.TemporaryDirectory() as tmp:
   summary=runner.run(fixtures.spec(),c,Path(tmp)/'run',lambda:api.ResponsesAdapter(c['provider_binding'],transport=fake));self.assertEqual(sum(v['evidence_success'] for v in summary['by_arm'].values()),0)
 def test_limits_cost_and_duplicate_or_source_drift_rejected(self):
  c=config();c['token_limit']=1
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';s=runner.run(fixtures.spec(),c,out,self.factory(c,[]));self.assertTrue(all(row['budget_violation'] for row in s['rows']))
   p=json.loads((out/'plan.json').read_text());_,cases=runner.make_plan(fixtures.spec(),c);rows=[json.loads(line) for line in (out/'attempts.jsonl').read_text().splitlines()]
   with self.assertRaises(ValueError):runner.summarize(p,cases,[rows[0],rows[0]])
   p['source_sha256']['responses_transport.py']='0'*64;(out/'plan.json').write_text(runner.canonical(p))
   with self.assertRaises(ValueError):runner.assess_saved(fixtures.spec(),out)
  c=config();c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','low',200,3,.00001,c['provider_binding']['rates'])
  with tempfile.TemporaryDirectory() as tmp:
   s=runner.run(fixtures.spec(),c,Path(tmp)/'run',self.factory(c,[]));self.assertEqual(sum(v['call_budget_violation'] for v in s['by_arm'].values()),1);self.assertEqual(sum(v['missing'] for v in s['by_arm'].values()),1)
 def test_rehashed_estimate_or_scored_final_cannot_disagree_with_http(self):
  c=config()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';runner.run(fixtures.spec(),c,out,self.factory(c,[]));p=json.loads((out/'plan.json').read_text());_,cases=runner.make_plan(fixtures.spec(),c);rows=[json.loads(line) for line in (out/'attempts.jsonl').read_text().splitlines()]
   altered=deepcopy(rows);r=altered[0];r['call_accounting'][0]['usage']['cost_estimate_usd']=0;r['provider_calls'][0]['observed_usage']['cost_estimate_usd']=0
   with self.assertRaises(ValueError):runner.summarize(p,cases,altered)
   altered=deepcopy(rows);r=next(x for x in altered if x['raw_output'] is not None);r['raw_output']='{"status":"FEASIBLE","schedule":[]}';r['normalized_output']={'status':'FEASIBLE','schedule':[]}
   with self.assertRaises(ValueError):runner.summarize(p,cases,altered)
   r['provider_calls'][-1]['raw_model_text']=json.dumps(dict(type='final',output={'status':'FEASIBLE','schedule':[]}))
   with self.assertRaises(ValueError):runner.summarize(p,cases,altered)
