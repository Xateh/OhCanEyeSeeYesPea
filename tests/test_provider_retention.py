"""Offline regressions for call allocations and saved receipt compatibility."""
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
import paired_runner as runner
import claude_pair_adapter as adapter
import test_paired_runner as fixtures
from solver_interface import MergedSolver

class RetentionTests(unittest.TestCase):
 def config(self):
  c=fixtures.config();c.update(execution_mode='claude_live',provider_revision=adapter.VERSION,provider_binding=adapter.binding('synthetic-model','high',3,.01));return c
 def test_call_overrun_below_whole_plan_ceiling(self):
  c=self.config();p,cases=runner.make_plan(fixtures.spec(),c);case=next(iter(cases.values()))
  output={'status':'FEASIBLE','schedule':[dict(patient='B',day=0,start=0,room='r0'),dict(patient='A',day=0,start=3,room='r0')]}
  def transport(*a,**kw):return json.dumps(dict(result=json.dumps(dict(type='final',output=output)),modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.02))
  receipt=runner.attempt(case,p['slots'][0],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),MergedSolver,allow_live=True)
  summary=runner.summarize(p,cases,[receipt]);row=summary['rows'][0]
  self.assertTrue(row['evidence_success']);self.assertLess(summary['by_arm']['no_tools']['known_cost_usd'],c['spending_ceiling'])
  self.assertTrue(row['budget_violation']);self.assertFalse(row['success'])
 def test_large_valid_multiturn_receipt_is_assessable(self):
  c=fixtures.config()
  class Large(fixtures.Fixture):
   def __init__(self):self.calls=[]
   def respond(self,*args):
    reply=super().respond(*args)
    # Same shape as retained transport metadata; each component is below its 1 MiB bound.
    if args[1]:self.calls.append(dict(raw_envelope='x'*700000,raw_model_text='y'*700000,request=dict(stdin='z'*700000)))
    return reply
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';summary=runner.run(fixtures.spec(),c,out,Large)
   receipts=[json.loads(line) for line in (out/'attempts.jsonl').read_text().splitlines()]
   self.assertGreater(len(runner.canonical(receipts[1]).encode()),4*1024*1024)
   self.assertEqual(runner.assess_saved(fixtures.spec(),out)['pairs'],summary['pairs'])
 def test_real_adapter_five_turn_receipt_over_old_bound(self):
  c=self.config();p,cases=runner.make_plan(fixtures.spec(),c);case=next(iter(cases.values()));counts=[]
  def factory():
   turns=[]
   def transport(*a,**kw):
    turns.append(1)
    if len(turns)<=4:message=dict(type='tool_call',name='csp',arguments=dict(instance=case['instance']))
    else:message=dict(type='final',output={'status':'UNKNOWN'})
    return json.dumps(dict(result=' '*400000+json.dumps(message),padding='x'*150000,modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.001))
   return adapter.ClaudePairAdapter(c['provider_binding'],transport)
  slot=p['slots'][1];r=runner.attempt(case,slot,c,factory,MergedSolver,allow_live=True)
  self.assertEqual(len(r['provider_calls']),5);self.assertGreater(len(runner.canonical(r).encode()),4*1024*1024)
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'plan.json').write_text(runner.canonical(p));item,line=runner.retention.retain(out,r);(out/'attempts.jsonl').write_text(line)
   self.assertEqual(runner.assess_saved(fixtures.spec(),out)['pairs'],runner.summarize(p,cases,[item])['pairs'])
 def test_overrun_on_malformed_reply_and_stop_before_next_call(self):
  c=self.config();p,cases=runner.make_plan(fixtures.spec(),c);case=next(iter(cases.values()))
  for malformed in (False,True):
   calls=[]
   def transport(*a,**kw):
    calls.append(1);message='{bad' if malformed else json.dumps(dict(type='tool_call',name='csp',arguments=dict(instance=case['instance'])))
    return json.dumps(dict(result=message,modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.02))
   r=runner.attempt(case,p['slots'][1],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),MergedSolver,allow_live=True)
   result=runner.summarize(p,cases,[r]);self.assertTrue(result['rows'][1]['call_budget_violation']);self.assertEqual(len(calls),1);self.assertEqual(r['call_accounting'][0]['usage']['cost_usd'],.02)
 def test_source_accounting_and_policy_drift_fail_closed(self):
  c=self.config();self.assertIn('study/accounting.py',c['provider_binding']['source_sha256']);self.assertIn('tier_a_contract.py',c['provider_binding']['source_sha256'])
  c['provider_binding']['source_sha256']['study/accounting.py']='0'*64
  with self.assertRaises(ValueError):runner.make_plan(fixtures.spec(),c)
  c=self.config()
  with patch.object(runner.retention,'LINE_BYTES',4096):
   with self.assertRaises(ValueError):runner.make_plan(fixtures.spec(),c)
 def test_recorded_allocation_and_usage_tampering_rejected(self):
  c=self.config();p,cases=runner.make_plan(fixtures.spec(),c);case=next(iter(cases.values()))
  def transport(*a,**kw):return json.dumps(dict(result='{"type":"final","output":{"status":"UNKNOWN"}}',modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.005))
  r=runner.attempt(case,p['slots'][0],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),MergedSolver,allow_live=True)
  r['provider_calls'][0]['budget_usd']=.009
  with self.assertRaises(ValueError):runner.summarize(p,cases,[r])
  r['provider_calls'][0]['budget_usd']=.01;r['provider_calls'][0]['observed_usage']['cost_usd']=0
  with self.assertRaises(ValueError):runner.summarize(p,cases,[r])
 def test_archive_preserves_original_and_retains_denominators(self):
  class Large(fixtures.Fixture):
   def __init__(self):self.calls=[]
   def respond(self,*args):
    reply=super().respond(*args)
    if args[1]:self.calls.append(dict(raw_envelope='x'*700000,raw_model_text='y'*700000,request=dict(stdin='z'*700000)))
    return reply
  with tempfile.TemporaryDirectory() as tmp,patch.object(runner.retention,'LINE_BYTES',1024*1024):
   out=Path(tmp)/'run';result=runner.run(fixtures.spec(),fixtures.config(),out,Large)
   lines=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()];reference=lines[1]
   original=json.loads((out/reference['file']).read_text());self.assertFalse(original['provider_error']);self.assertIsNone(original['resource_error']);self.assertEqual(len(original['provider_calls'][1]['raw_envelope']),700000)
   assessed=runner.assess_saved(fixtures.spec(),out);self.assertEqual(assessed['pairs'],result['pairs']);self.assertEqual(assessed['by_arm']['csp']['resource_bound'],1);self.assertEqual(assessed['by_arm']['csp']['tool_calls'],1);self.assertEqual(assessed['by_arm']['csp']['success'],0);self.assertEqual(assessed['by_arm']['csp']['planned'],1);self.assertEqual(assessed['by_arm']['csp']['answer_complete'],1);self.assertEqual(assessed['by_arm']['csp']['provider_errors'],0)
   body=out/reference['file'];raw=body.read_bytes();body.write_bytes(raw.replace(b'xxxx',b'yyyy',1))
   with self.assertRaises(ValueError):runner.assess_saved(fixtures.spec(),out)
   body.unlink();body.symlink_to(out/'plan.json')
   with self.assertRaises(ValueError):runner.assess_saved(fixtures.spec(),out)
 def test_opaque_evidence_is_retained_but_never_scored_as_success(self):
  class Large(fixtures.Fixture):
   def __init__(self):self.calls=[]
   def respond(self,*args):
    reply=super().respond(*args);self.calls.append(dict(raw_envelope='x'*20000));return reply
  with tempfile.TemporaryDirectory() as tmp,patch.object(runner.retention,'LINE_BYTES',4096),patch.object(runner.retention,'EVIDENCE_BYTES',8192):
   out=Path(tmp)/'run';result=runner.run(fixtures.spec(),fixtures.config(),out,Large)
   row=json.loads((out/'attempts.jsonl').read_text());reference=row['retained_evidence']
   self.assertTrue(reference['opaque']);original=json.loads((out/reference['file']).read_text());self.assertEqual(len(original['provider_calls'][0]['raw_envelope']),20000)
   summary=runner.assess_saved(fixtures.spec(),out);self.assertEqual(summary['pairs'],result['pairs']);self.assertEqual(summary['by_arm']['no_tools']['success'],0);self.assertEqual(summary['by_arm']['csp']['missing'],1);self.assertEqual(result['stop_reason'],'resource_bound_stopped_new_slots');self.assertEqual(summary['by_arm']['no_tools']['opaque_evidence'],1)
   row['resource_error']=None;(out/'attempts.jsonl').write_text(runner.canonical(row)+'\n')
   with self.assertRaises(ValueError):runner.assess_saved(fixtures.spec(),out)
 def test_request_refused_before_transport_and_oversize_envelope_retained(self):
  for field in ('REQUEST_BYTES','ENVELOPE_BYTES'):
   with patch.object(runner.retention,field,128):
    c=self.config();p,cases=runner.make_plan(fixtures.spec(),c);case=next(iter(cases.values()));calls=[]
    def transport(*a,**kw):
     calls.append(1);return json.dumps(dict(result='{"type":"final","output":{"status":"UNKNOWN"}}',padding='x'*200,modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.005))
    r=runner.attempt(case,p['slots'][0],c,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),MergedSolver,allow_live=True)
    self.assertEqual(r['termination'],'resource_bound');self.assertEqual(len(calls),0 if field=='REQUEST_BYTES' else 1)
    self.assertEqual(r['provider_calls'][0]['resource_error'],'request_bound' if field=='REQUEST_BYTES' else 'envelope_bound')
    self.assertEqual(runner.summarize(p,cases,[r])['by_arm']['no_tools']['resource_bound'],1)
    if field=='ENVELOPE_BYTES':self.assertIn('x'*200,r['provider_calls'][0]['raw_envelope']);self.assertIsNone(r['token_usage'])
    else:self.assertEqual(r['token_usage'],dict(input_tokens=0,output_tokens=0))
 def test_run_stops_after_reported_call_overrun_without_replacement(self):
  c=self.config();calls=[]
  def transport(*a,**kw):
   calls.append(1);return json.dumps(dict(result='{"type":"final","output":{"status":"UNKNOWN"}}',modelUsage={'synthetic-model':{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=.02))
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';summary=runner.run(fixtures.spec(),c,out,lambda:adapter.ClaudePairAdapter(c['provider_binding'],transport),allow_live=True)
   self.assertEqual(len(calls),1);self.assertEqual(summary['stop_reason'],'call_allocation_overrun_stopped_new_slots');self.assertEqual(summary['by_arm']['no_tools']['call_budget_violation'],1);self.assertEqual(summary['by_arm']['csp']['missing'],1)
   self.assertEqual(runner.assess_saved(fixtures.spec(),out)['pairs'],summary['pairs'])
