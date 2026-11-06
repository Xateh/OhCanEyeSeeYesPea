from copy import deepcopy
import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import claude_pair_adapter as adapter
import paired_runner as runner
import test_paired_runner as existing
from solver_interface import MergedSolver
from surgerybench.temporal_text import parse
from tier_a_input_view import RAW_FRAGMENT,VIEW_FRAGMENT

def config():
 c=existing.config();c.update(execution_mode='claude_live',provider_revision=adapter.VERSION,provider_binding=adapter.binding('synthetic-model','high',3,0.25));return c

def envelope(raw,usage=True,error=False):
 out=dict(result=raw,is_error=error,modelUsage={'synthetic-model':{}})
 if usage:out.update(usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=0.01)
 return json.dumps(out)

class AdapterTests(unittest.TestCase):
 def test_real_transport_boundary_both_arms_and_tool_roundtrip(self):
  seen=[];original=subprocess.run
  def fake(argv,**kw):
   if argv[0]!='claude':return original(argv,**kw)
   seen.append((argv,deepcopy(kw)))
   text=kw['input'];system=argv[argv.index('--system-prompt')+1]
   if 'Tool definition:' in text and 'Your earlier tool calls' not in text:
    case=text.split('\n\nWhen you have your answer,')[0];out=dict(type='tool_call',name='csp',arguments=dict(instance=parse(case.replace(VIEW_FRAGMENT,RAW_FRAGMENT))))
   elif 'Your earlier tool calls' in text:
    history=json.loads(text.split('Your earlier tool calls and their results:\n')[1]);result=history[-1]['result'];out=dict(type='final',output={k:v for k,v in result.items() if k in ('status','schedule','certificate')})
   else:out=dict(type='final',output={'status':'UNKNOWN'})
   return subprocess.CompletedProcess(argv,0,envelope(json.dumps(out)),'')
  with tempfile.TemporaryDirectory() as tmp,patch('study.claude_provider.subprocess.run',side_effect=fake):
   out=Path(tmp)/'run';r=runner.run(existing.spec(),config(),out,allow_live=True)
   self.assertEqual(r['by_arm']['csp']['success'],1);self.assertEqual(r['by_arm']['no_tools']['unknown'],1)
   rows=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
   self.assertEqual([len(x['provider_calls']) for x in rows],[1,2]);self.assertEqual(runner.assess_saved(existing.spec(),out)['pairs'],r['pairs'])
  self.assertEqual(len(seen),3)
  for argv,kw in seen:
   self.assertEqual(argv[argv.index('--tools')+1],'');self.assertEqual(argv[argv.index('--max-budget-usd')+1],'0.25');self.assertLessEqual(kw['timeout'],3);self.assertIn('--strict-mcp-config',argv)
  self.assertEqual(seen[0][1]['input'].split('\n\n')[0],seen[1][1]['input'].split('\n\n')[0])
 def test_optin_and_binding_fail_before_transport(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):runner.run(existing.spec(),config(),Path(tmp)/'run')
   self.assertFalse((Path(tmp)/'run').exists())
  with self.assertRaises(ValueError):adapter.ClaudePairAdapter(config()['provider_binding'])
  p,cases=runner.make_plan(existing.spec(),config())
  with self.assertRaises(ValueError):runner.attempt(next(iter(cases.values())),p['slots'][0],config(),lambda:self.fail('not called'),MergedSolver)
  c=config();c['provider_binding']['serialization']='unknown'
  with self.assertRaises(ValueError):runner.make_plan(existing.spec(),c)
 def test_strict_raw_span_and_fences_duplicate_keys_errors(self):
  raw=' { "type" : "final", "output" : { "status" : "UNKNOWN" } } '
  messages=[dict(role='system',content='shared'),dict(role='user',content='case')]
  limits=dict(token_limit=10,wall_seconds=2,spending_remaining_usd=1)
  for text,okay in [(raw,True),('```json\n'+raw+'\n```',False),('{"type":"final","output":{"status":"UNKNOWN"},"output":{}}',False),('{bad',False)]:
   p=adapter.ClaudePairAdapter(config()['provider_binding'],lambda *a,**k:envelope(text))
   if okay:self.assertEqual(p.respond(messages,[],limits)['raw'],'{ "status" : "UNKNOWN" }')
   else:
    with self.assertRaises(ValueError) as caught:p.respond(messages,[],limits)
    self.assertEqual(caught.exception.observed_usage['cost_usd'],.01)
   self.assertEqual(p.calls[0]['raw_model_text'],text);self.assertEqual(json.loads(p.calls[0]['raw_envelope'])['result'],text)
 def test_provider_errors_usage_and_timeout_partial_retained(self):
  for mode in ('error','missing','timeout'):
   def transport(*a,**k):
    if mode=='timeout':raise subprocess.TimeoutExpired('claude',1,output=b'partial')
    return envelope('{"type":"final","output":{"status":"UNKNOWN"}}',usage=mode!='missing',error=mode=='error')
   p=adapter.ClaudePairAdapter(config()['provider_binding'],transport)
   messages=[dict(role='system',content='shared'),dict(role='user',content='case')];limits=dict(token_limit=10,wall_seconds=2,spending_remaining_usd=1)
   if mode=='missing':self.assertIsNone(p.respond(messages,[],limits)['usage']['input_tokens'])
   else:
    with self.assertRaises((ValueError,TimeoutError)):p.respond(messages,[],limits)
   self.assertEqual(len(p.calls),1)
   if mode=='timeout':self.assertEqual(p.calls[0]['partial_stdout'],'partial')
 def test_invalid_final_keeps_observed_cost_and_planned_slots(self):
  c=config();p,cases=runner.make_plan(existing.spec(),c)
  def factory():return adapter.ClaudePairAdapter(c['provider_binding'],lambda *a,**k:envelope('{bad'))
  receipt=runner.attempt(next(iter(cases.values())),p['slots'][0],c,factory,MergedSolver,allow_live=True)
  self.assertEqual(receipt['call_accounting'][0]['usage']['cost_usd'],.01)
  self.assertEqual(receipt['provider_calls'][0]['raw_model_text'],'{bad')
  r=runner.summarize(p,cases,[receipt]);self.assertEqual(sum(x['planned'] for x in r['by_arm'].values()),2);self.assertEqual(r['by_arm']['csp']['missing'],1)
 def test_missing_usage_stops_followup_tool_turn_and_new_slots(self):
  c=config();_,cases=runner.make_plan(existing.spec(),c);case=next(iter(cases.values()));instance=case['instance'];calls=[]
  def transport(*a,**kw):
   calls.append(1);return envelope(json.dumps(dict(type='tool_call',name='csp',arguments=dict(instance=instance))),usage=False)
  c['order']='arm_then_case'
  c['case_ids']=[case['case_id']]
  def factory():return adapter.ClaudePairAdapter(c['provider_binding'],transport)
  p,cases=runner.make_plan(existing.spec(),c);slot=next(s for s in p['slots'] if s['arm']=='csp')
  r=runner.attempt(case,slot,c,factory,MergedSolver,allow_live=True)
  self.assertEqual(len(calls),1);self.assertTrue(r['provider_error']);self.assertIsNone(r['token_usage']);self.assertEqual(len(r['provider_calls']),1)
 def test_token_and_tool_limits_stop_real_adapter_boundary(self):
  for token_limit,tool_limit in ((1,4),(1000,0)):
   c=config();c.update(token_limit=token_limit,tool_call_limit=tool_limit);p,cases=runner.make_plan(existing.spec(),c);case=next(iter(cases.values()));calls=[]
   def transport(*a,**kw):
    calls.append(1);return envelope(json.dumps(dict(type='tool_call',name='csp',arguments=dict(instance=case['instance']))))
   receipt=runner.attempt(case,p['slots'][1],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),MergedSolver,allow_live=True)
   self.assertEqual(len(calls),1);self.assertIsNone(receipt['raw_output'])
   result=runner.summarize(p,cases,[receipt]);self.assertEqual(result['by_arm']['csp']['success'],0);self.assertEqual(result['by_arm']['no_tools']['missing'],1)
 def test_subprocess_timeout_and_late_return_are_distinct(self):
  c=config();p,cases=runner.make_plan(existing.spec(),c);case=next(iter(cases.values()))
  def timeout(*a,**kw):raise subprocess.TimeoutExpired('claude',kw['timeout_seconds'],output='partial')
  r=runner.attempt(case,p['slots'][0],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],timeout),MergedSolver,allow_live=True)
  self.assertEqual(r['termination'],'timeout');self.assertEqual(r['provider_calls'][0]['partial_stdout'],'partial')
  r['elapsed_seconds']=11
  self.assertTrue(runner.summarize(p,cases,[r])['rows'][0]['budget_violation'])
 def test_interrupted_live_path_retains_plan_no_retry(self):
  c=config();calls=[]
  def transport(*a,**kw):calls.append(1);raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run'
   with self.assertRaises(KeyboardInterrupt):runner.run(existing.spec(),c,out,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),allow_live=True)
   result=runner.assess_saved(existing.spec(),out);self.assertEqual(len(calls),1);self.assertEqual(sum(v['missing'] for v in result['by_arm'].values()),2)
 def test_spending_remaining_and_model_mismatch(self):
  c=config();seen=[]
  def transport(argv,stdin,cwd,timeout_seconds):
   seen.append(argv);return envelope('{"type":"final","output":{"status":"UNKNOWN"}}').replace('synthetic-model','wrong-model')
  a=adapter.ClaudePairAdapter(c['provider_binding'],transport)
  with self.assertRaises(ValueError):a.respond([dict(role='system',content='x'),dict(role='user',content='y')],[],dict(wall_seconds=2,token_limit=100,spending_remaining_usd=.02))
  self.assertEqual(seen[0][seen[0].index('--max-budget-usd')+1],'0.02');self.assertEqual(a.calls[0]['error'],'RuntimeError')
 def test_unset_invalid_or_nonfinite_configuration_rejected(self):
  for amount in (None,True,float('inf'),float('nan'),10**10000,0,-1,'1'):
   with self.assertRaises(ValueError):adapter.binding('synthetic-model','high',3,amount)
  c=config();c['provider_binding']=None
  with self.assertRaises(ValueError):runner.make_plan(existing.spec(),c)
 def test_usage_unknown_is_not_compliant_success(self):
  c=config();p,cases=runner.make_plan(existing.spec(),c);case=next(iter(cases.values()))
  out={'status':'FEASIBLE','schedule':[dict(patient='B',day=0,start=0,room='r0'),dict(patient='A',day=0,start=3,room='r0')]}
  a=lambda:adapter.ClaudePairAdapter(c['provider_binding'],lambda *a,**kw:envelope(json.dumps(dict(type='final',output=out)),usage=False))
  receipt=runner.attempt(case,p['slots'][0],c,a,MergedSolver,allow_live=True);result=runner.summarize(p,cases,[receipt])
  self.assertTrue(result['rows'][0]['evidence_success']);self.assertTrue(result['rows'][0]['budget_unknown']);self.assertFalse(result['rows'][0]['success'])
 def test_nonzero_exit_with_valid_stdout_keeps_usage_but_fails(self):
  a=adapter.ClaudePairAdapter(config()['provider_binding'],allow_live=True)
  raw=envelope('{"type":"final","output":{"status":"UNKNOWN"}}')
  with patch('study.claude_provider.subprocess.run',return_value=subprocess.CompletedProcess(['claude'],7,raw,'diagnostic not saved')):
   with self.assertRaises(ValueError) as caught:a.respond([dict(role='system',content='x'),dict(role='user',content='y')],[],dict(wall_seconds=2,token_limit=100,spending_remaining_usd=1))
  self.assertEqual(caught.exception.observed_usage['cost_usd'],.01);self.assertEqual(a.calls[0]['returncode'],7);self.assertEqual(a.calls[0]['raw_envelope'],raw);self.assertNotIn('diagnostic not saved',json.dumps(a.calls))
