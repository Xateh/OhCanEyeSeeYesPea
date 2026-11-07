from copy import deepcopy
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import paired_runner as runner
import benchmark_datasets as catalog
from solver_interface import MergedSolver,LIMITS
from tier_a_input_view import RAW_FRAGMENT,VIEW_FRAGMENT
from surgerybench.temporal_text import parse
import test_tier_a_contract as legacy
ROOT=Path(__file__).resolve().parents[1]
GOLD=[json.loads(s) for s in (ROOT/'fixtures/tier-a-original-synthetic-v1/tier-a-gold.jsonl').read_text().splitlines()]
def cid(prefix):return next(g['case_id'] for g in GOLD if g['case_id'].startswith(prefix))
def spec():return [dict(kind='tier-a-v1',directory=str(ROOT/'fixtures/tier-a-original-synthetic-v1'),plan=legacy.plan())]
def config(ids=None):return dict(version=runner.VERSION,provider_revision='offline-script-v1',case_ids=ids or [cid('room-gap-5')],repetitions=1,seed=7,shuffle_cases=True,order='case_then_arm',token_limit=1000,wall_seconds=10,tool_call_limit=4,retry_limit=0,spending_ceiling=1,currency='USD',solver_revision=MergedSolver.revision,solver_limits=LIMITS)
USAGE=dict(input_tokens=2,output_tokens=3,cost_usd=0)
class Fixture:
 offline=True;revision='offline-script-v1';seen=[]
 def respond(self,messages,tools,limits):
  self.seen.append(deepcopy((messages,tools,limits)))
  if tools:
   if not any(m['role']=='tool' for m in messages):return dict(type='tool_call',name='csp',arguments={'instance':parse(messages[1]['content'].replace(VIEW_FRAGMENT,RAW_FRAGMENT))},usage=USAGE)
   r=json.loads(messages[-1]['content']);output={k:v for k,v in r.items() if k in ('status','schedule','certificate')}
   return dict(type='final',raw=json.dumps(output),usage=USAGE)
  return dict(type='final',raw=json.dumps({'status':'FEASIBLE','schedule':[dict(patient='B',day=0,start=0,room='r0'),dict(patient='A',day=0,start=3,room='r0')]}),usage=USAGE)
class RunnerTests(unittest.TestCase):
 def setUp(self):Fixture.seen=[]
 def test_saved_run_matched_text_alternate_witness_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';result=runner.run(spec(),config(),out,Fixture)
   self.assertEqual(result['pairs']['both'],1);self.assertEqual(result['by_arm']['no_tools']['success'],1)
   self.assertEqual(Fixture.seen[0][0][1]['content'],Fixture.seen[1][0][1]['content'])
   for messages,tools,limits in Fixture.seen:
    self.assertNotIn(cid('room-gap-5'),json.dumps(messages));self.assertNotIn('case_id',json.dumps(messages));self.assertEqual(set(limits),{'token_limit','wall_seconds','spending_remaining_usd'})
   self.assertEqual(runner.assess_saved(spec(),out)['pairs'],result['pairs'])
   with self.assertRaises(FileExistsError):runner.run(spec(),config(),out,Fixture)
 def test_plan_seed_duplicate_ids_and_preflight_before_factory(self):
  c=config([cid('room-gap-5'),cid('optional-omitted')]);p,g=runner.make_plan(spec(),c);self.assertEqual(p,runner.make_plan(spec(),c)[0]);self.assertEqual(len(p['slots']),4)
  def forbidden():self.fail('provider must not be constructed')
  for changes in (dict(provider_revision=None),dict(case_ids=['unknown']),dict(case_ids=[c['case_ids'][0]]*2),dict(retry_limit=1)):
   with tempfile.TemporaryDirectory() as tmp:
    with self.assertRaises(ValueError):runner.run(spec(),dict(c,**changes),Path(tmp)/'run',forbidden)
 def test_unknown_usage_stops_without_shrinking_plan(self):
  class Unknown(Fixture):
   def respond(self,*args):return dict(type='final',raw='{"status":"UNKNOWN"}',usage=None)
  with tempfile.TemporaryDirectory() as tmp:
   r=runner.run(spec(),config(),Path(tmp)/'run',Unknown)
   self.assertEqual(r['by_arm']['no_tools']['planned'],1);self.assertEqual(r['by_arm']['csp']['missing'],1);self.assertIsNone(r['by_arm']['no_tools']['cost_usd']);self.assertEqual(r['pairs']['incomplete'],1)
 def test_malformed_timeout_wrong_evidence_and_duplicates(self):
  c=config();p,cases=runner.make_plan(spec(),c)
  class Bad(Fixture):
   def respond(self,*args):return dict(type='final',raw='{broken',usage=USAGE)
  a=runner.attempt(next(iter(cases.values())),p['slots'][0],c,Bad,MergedSolver)
  class Timeout(Fixture):
   def respond(self,*args):raise TimeoutError()
  b=runner.attempt(next(iter(cases.values())),p['slots'][1],c,Timeout,MergedSolver)
  r=runner.summarize(p,cases,[a,b]);self.assertEqual(r['pairs']['incomplete'],1);self.assertEqual(r['by_arm']['csp']['timeout'],1)
  with self.assertRaises(ValueError):runner.summarize(p,cases,[a,a])
  self.assertEqual(runner.summarize(p,cases,[])['by_arm']['no_tools']['missing'],1)
 def test_mistranslated_instance_never_gets_gold_repair(self):
  class Wrong(Fixture):
   def respond(self,messages,tools,limits):
    r=super().respond(messages,tools,limits)
    if r['type']=='tool_call':r['arguments']['instance']['patients'][1]['mandatory']=False
    return r
  with tempfile.TemporaryDirectory() as tmp:
   r=runner.run(spec(),config([cid('optional-forced')]),Path(tmp)/'run',Wrong)
   self.assertEqual(r['by_arm']['csp']['success'],0);self.assertEqual(r['by_arm']['csp']['tool_errors'],0);self.assertEqual(r['by_arm']['csp']['output_error'],1)
 def test_bare_negative_only_gets_diagnostic_agreement(self):
  class Bare(Fixture):
   def respond(self,*args):return dict(type='final',raw='{"status":"INFEASIBLE"}',usage=USAGE)
  with tempfile.TemporaryDirectory() as tmp:
   r=runner.run(spec(),config([cid('optional-forced')]),Path(tmp)/'run',Bare)
   for a in r['by_arm'].values():self.assertEqual(a['success'],0);self.assertEqual(a['infeasible_decision'],1);self.assertEqual(a['answer_complete'],0)
 def test_tool_limit_and_forbidden_tool_are_failures(self):
  class Forever(Fixture):
   def respond(self,messages,tools,limits):return dict(type='tool_call',name='csp',arguments={'instance':parse(messages[1]['content'].replace(VIEW_FRAGMENT,RAW_FRAGMENT))},usage=USAGE)
  with tempfile.TemporaryDirectory() as tmp:
   r=runner.run(spec(),config(),Path(tmp)/'run',Forever)
   self.assertEqual(r['by_arm']['no_tools']['tool_calls'],0);self.assertEqual(r['by_arm']['no_tools']['success'],0);self.assertEqual(r['by_arm']['csp']['tool_calls'],4);self.assertEqual(r['by_arm']['csp']['success'],0)
 def test_budget_adjustment_preserves_evidence_and_denominators(self):
  c=config();p,cases=runner.make_plan(spec(),c);a=runner.attempt(next(iter(cases.values())),p['slots'][0],c,Fixture,MergedSolver)
  for change in ('elapsed','tokens','spend'):
   b=deepcopy(a)
   if change=='elapsed':b['elapsed_seconds']=11
   elif change=='tokens':b['call_accounting'][0]['usage'].update(input_tokens=1001);b['token_usage']['input_tokens']=1001
   else:b['call_accounting'][0]['usage']['cost_usd']=2
   r=runner.summarize(p,cases,[b]);self.assertEqual(r['by_arm']['no_tools']['planned'],1);self.assertEqual(r['by_arm']['no_tools']['evidence_success'],1);self.assertEqual(r['by_arm']['no_tools']['success'],0);self.assertEqual(r['by_arm']['no_tools']['budget_violation'],1)
 def test_saved_interruption_and_tampering_fail_closed(self):
  c=config();p,cases=runner.make_plan(spec(),c)
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'plan.json').write_text(json.dumps(p));(d/'attempts.jsonl').write_text('')
   r=runner.assess_saved(spec(),d);self.assertEqual(r['pairs']['incomplete'],1)
   (d/'attempts.jsonl').write_text('{broken\n')
   with self.assertRaises(ValueError):runner.assess_saved(spec(),d)
 def test_nonoffline_provider_is_not_called(self):
  class Live(Fixture):
   offline=False
   def respond(self,*args):self.fail('not allowed')
  with tempfile.TemporaryDirectory() as tmp:
   r=runner.run(spec(),config(),Path(tmp)/'run',Live)
   self.assertEqual(r['by_arm']['no_tools']['success'],0);self.assertEqual(r['by_arm']['csp']['missing'],1)
 def test_attempt_identity_and_tool_flag_contradiction_rejected(self):
  c=config();p,cases=runner.make_plan(spec(),c);g=next(iter(cases.values()));a=runner.attempt(g,p['slots'][1],c,Fixture,MergedSolver)
  wrong=dict(a,attempt_id='other-run')
  with self.assertRaises(ValueError):runner.summarize(p,cases,[wrong])
  altered=deepcopy(a);altered['solver_events'][0]['error']=True;altered['tool_error']=False
  with self.assertRaises(ValueError):runner.summarize(p,cases,[altered])
 def test_real_interruption_retains_plan_and_factory_timeout(self):
  def interrupt():raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run'
   with self.assertRaises(KeyboardInterrupt):runner.run(spec(),config(),out,interrupt)
   self.assertEqual(runner.assess_saved(spec(),out)['pairs']['incomplete'],1)
  def timeout():raise TimeoutError()
  c=config();p,cases=runner.make_plan(spec(),c);r=runner.attempt(next(iter(cases.values())),p['slots'][0],c,timeout,MergedSolver)
  self.assertEqual(r['termination'],'timeout')
 def test_well_formed_final_after_tool_timeout_is_complete_not_successful(self):
  class TimeoutSolver:
   revision=MergedSolver.revision;schema_version='1.1';supported_limits=LIMITS
   def invoke(self,args):raise TimeoutError()
  with tempfile.TemporaryDirectory() as tmp:
   result=runner.run(spec(),config(),Path(tmp)/'run',Fixture,TimeoutSolver)
   c=result['by_arm']['csp'];self.assertEqual(c['answer_complete'],1);self.assertEqual(c['success'],0);self.assertEqual(c['timeout'],1);self.assertEqual(c['tool_errors'],1)
