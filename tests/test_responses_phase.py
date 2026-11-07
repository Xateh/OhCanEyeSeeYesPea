import json,tempfile,unittest,re
from pathlib import Path
from unittest.mock import patch
import responses_phase_runner as r
import responses_phase_transport as api
import test_responses_runner as helpers
import test_paired_runner as f
class PhaseTests(unittest.TestCase):
 def config(self):
  c=helpers.config([f.cid('optional-forced'),f.cid('pair-deadline')]);c.update(version=r.VERSION,tool_call_limit=1,provider_revision=api.VERSION,provider_binding=api.binding('mock-model','mock-model','mock-responses-v1','low',2000,20,.08,dict(input_per_million=2,cached_input_per_million=.1,output_per_million=10,source='synthetic')));return c
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
   return 200,{},json.dumps(envelope).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=send)
 def test_actual_requests_baseline_translation_and_final_phases(self):
  c=self.config();seen=[]
  with patch('socket.create_connection',side_effect=AssertionError('blocked')),tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'r';s=r.run(f.spec(),c,out,self.factory(c,seen));self.assertEqual(len(seen),6);self.assertEqual(s['by_arm']['csp']['success'],2);self.assertEqual(s['by_arm']['csp']['tool_calls'],2);self.assertEqual(r.assess_saved(f.spec(),out)['pairs'],s['pairs'])
   for b in seen:
    self.assertEqual(b['tools'],[])
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
  c=self.config();p,cases=r.make_plan(f.spec(),c);self.assertIn('responses_phase_transport.py',p['source_sha256']);self.assertEqual(len(p['slots']),4);self.assertEqual([s['arm'] for s in p['slots'][::2]].count('csp'),1)
