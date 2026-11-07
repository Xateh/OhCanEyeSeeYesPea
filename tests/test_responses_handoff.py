import json,tempfile,unittest,sys,subprocess
from pathlib import Path
from copy import deepcopy
import responses_handoff_runner as r
import responses_calibration_runner as old
import responses_calibration_transport as api
import test_responses_calibration as fixture
from tier_a_contract import canonical
from surgerybench.temporal_text import parse
from tier_a_input_view import VIEW_FRAGMENT,RAW_FRAGMENT
from solver_interface import MergedSolver,LIMITS
class HandoffTests(unittest.TestCase):
 def config(self):c=fixture.config();c['version']=r.VERSION;return c
 def factory(self,c,seen,mode='copy'):
  _,cases=r.make_plan(fixture.specs(),c)
  def send(body,timeout):
   seen.append(deepcopy(body));case=next(x for x in cases.values() if body['input'].startswith(x['text']))
   if 'Phase TRANSLATE:' in body['instructions']:
    out={'type':'tool_call','name':'csp','arguments':{'instance':parse(case['text'].replace(VIEW_FRAGMENT,RAW_FRAGMENT))}}
    if mode=='mistranslate':
     for patient in out['arguments']['instance']['patients']:patient['mandatory']=False
    if mode=='early':out={'type':'final','output':{'status':'UNKNOWN'}}
   elif 'Phase FINAL:' in body['instructions']:
    history=json.loads(body['input'].split('Your earlier tool calls and their results:\n')[1].split('\n\nWhen you have your answer')[0]);result=history[0]['result'];out={'type':'final','output':{k:v for k,v in result.items() if k in ['status','schedule','certificate']}}
    if mode=='abstain':out={'type':'final','output':{'status':'UNKNOWN'}}
    if mode=='repeat':out={'type':'tool_call','name':'csp','arguments':history[0]['submitted_instance']}
    if mode=='wrong' and out['output']['status']=='FEASIBLE':out['output']['schedule'][0]['start']=1000000
    if mode=='wrong' and out['output']['status']=='INFEASIBLE':out['output']['certificate']['patients']=['wrong1','wrong2']
   else:out={'type':'final','output':{'status':'UNKNOWN'}}
   u=dict(input_tokens=100,output_tokens=30,total_tokens=130,input_tokens_details={'cached_tokens':0,'cache_write_tokens':0},output_tokens_details={'reasoning_tokens':0})
   return 200,{},json.dumps(dict(model='mock-model',service_tier='default',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=json.dumps(out))])],usage=u)).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=send)
 def test_serialized_parity_only_final_instruction_changes(self):
  c=self.config();seen=[];before=[]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);s=r.run(fixture.specs(),c,p/'new',self.factory(c,seen));o=old.run(fixture.specs(),dict(c,version=old.VERSION),p/'old',self.factory(c,before));self.assertEqual(len(seen),12);self.assertEqual(s['by_arm']['csp']['success'],4)
   rows=[json.loads(x) for x in (p/'new/attempts.jsonl').read_text().splitlines()]
   for a,b in zip(seen,before):
    if 'Phase FINAL:' in a['instructions']:
     self.assertNotEqual(a['instructions'],b['instructions']);self.assertEqual({k:v for k,v in a.items() if k!='instructions'},{k:v for k,v in b.items() if k!='instructions'});self.assertIn('copy its schedule or certificate exactly',a['instructions'])
    else:self.assertEqual(a,b)
    self.assertNotIn('OPENAI_API_KEY',canonical(a));self.assertTrue(all(cid not in canonical(a) for cid in r.IDS))
   for row in rows:
    if row['arm']=='csp':self.assertEqual(row['normalized_output'],{k:v for k,v in row['solver_events'][0]['result'].items() if k in ['status','schedule','certificate']})
   self.assertEqual(r.assess_saved(fixture.specs(),p/'new')['pairs'],s['pairs'])
 def test_model_abstention_not_automatically_promoted(self):
  c=self.config()
  with tempfile.TemporaryDirectory() as tmp:
   s=r.run(fixture.specs(),c,Path(tmp)/'r',self.factory(c,[],'abstain'));self.assertEqual(s['by_arm']['csp']['unknown'],4);self.assertEqual(s['by_arm']['csp']['success'],0)
 def test_wrong_final_early_and_repeated_invocations_fail(self):
  c=self.config()
  for mode in ['early','repeat','wrong']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    s=r.run(fixture.specs(),c,Path(tmp)/'r',self.factory(c,[],mode));self.assertEqual(s['by_arm']['csp']['success'],0);self.assertEqual(s['by_arm']['csp']['planned'],4);self.assertLessEqual(s['by_arm']['csp']['tool_calls'],4)
 def test_unknown_error_and_invalid_solver_results_fail_closed(self):
  c=self.config()
  for value in [{},[],{'status':'FEASIBLE','schedule':[]},{'status':'INFEASIBLE','certificate':{}},{'status':'UNKNOWN','reason':'bounded_search'}, {'status':'FEASIBLE','schedule':[],'certificate':{}},None]:
   class Plugin:
    revision=MergedSolver.revision;schema_version='1.1';supported_limits=LIMITS
    def invoke(self,arguments):return deepcopy(value)
   with self.subTest(value=value),tempfile.TemporaryDirectory() as tmp:
    s=r.run(fixture.specs(),c,Path(tmp)/'r',self.factory(c,[]),Plugin);self.assertEqual(s['by_arm']['csp']['success'],0);self.assertEqual(s['by_arm']['csp']['unknown'],4);self.assertEqual(s['by_arm']['csp']['planned'],4)
 def test_original_v3_trace_copy_contract(self):
  source=(__import__('responses_fixture').ROOT/'frozen-cli-v3-prompts.txt').read_text();self.assertIn('copy its schedule or ',source);self.assertIn('copy its schedule or certificate exactly',r.HANDOFF_FINAL)
  rows=[json.loads(s) for d in ['03-train-format-example-v3','04-validation-v3','05-test-v3'] for s in (Path('study/results')/d/'runs.jsonl').read_text().splitlines()];cs=[x for x in rows if x['arm']=='csp'];self.assertEqual(len(cs),64);self.assertTrue(all(x['output']=={k:v for k,v in x['tool_calls'][-1]['result'].items() if k in ['status','schedule','certificate']} for x in cs))
 def test_checked_evidence_from_wrong_translation_rejected_on_intended(self):
  c=self.config()
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'r';s=r.run(fixture.specs(),c,p,self.factory(c,[],'mistranslate'));self.assertEqual(s['by_arm']['csp']['success'],0);rows=[json.loads(x) for x in (p/'attempts.jsonl').read_text().splitlines()]
   for row in rows:
    if row['arm']=='csp':self.assertEqual(row['solver_events'][0]['result']['status'],'FEASIBLE');self.assertEqual(row['normalized_output'],{'status':'FEASIBLE','schedule':[]})
 def test_actual_two_abstention_receipts_still_have_admissible_evidence(self):
  from tier_a_contract import output_verdict
  _,cases=r.make_plan(fixture.specs(),self.config());rows=[json.loads(x) for x in (fixture.SPEC_PATH/'run/attempts.jsonl').read_text().splitlines()];n=0
  for row in rows:
   if row['arm']=='csp' and cases[row['case_id']]['label']=='FEASIBLE':
    n+=1;self.assertEqual(row['normalized_output'],{'status':'UNKNOWN'});o={k:v for k,v in row['solver_events'][0]['result'].items() if k in ['status','schedule','certificate']};self.assertTrue(fixture.schema_ok(fixture.SCHEMA,{'type':'final','output':o}));self.assertTrue(output_verdict(cases[row['case_id']]['instance'],canonical(o),o,[])['evidence_valid'])
  self.assertEqual(n,2)
