import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import responses_mandatory_runner as m
import responses_runner as old
import responses_transport as api
import test_responses_runner as helpers
import test_paired_runner as f
class MandatoryTests(unittest.TestCase):
 def config(self):
  c=helpers.config([f.cid(x) for x in ('room-gap-5','optional-omitted','optional-forced','pair-deadline')]);c['version']=m.VERSION;c['tool_call_limit']=1;return c
 def test_four_cases_twelve_turns_and_intended_evidence(self):
  c=self.config();seen=[]
  with patch('socket.create_connection',side_effect=AssertionError('network blocked')),tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';s=m.run(f.spec(),c,out,helpers.RunnerTests().factory(c,seen));self.assertEqual(len(seen),12);self.assertEqual(s['by_arm']['csp']['success'],4);self.assertEqual(s['by_arm']['csp']['tool_calls'],4);self.assertEqual(m.assess_saved(f.spec(),out)['pairs'],s['pairs'])
   self.assertTrue(all('Mandatory-CSP protocol v1' in b['instructions'] for b in seen if 'Tool definition:' in b['input']))
 def fake(self,c,mode):
  def send(body,timeout):
   is_csp='Tool definition:' in body['input'];history='Your earlier tool calls and their results:' in body['input']
   if not is_csp or mode=='early':text=json.dumps(dict(type='final',output={'status':'UNKNOWN'}))
   elif mode=='invalid':text='{'
   elif mode=='extra' or not history:
    instance=f.parse(body['input'].split('\n\nWhen you have your answer,')[0].replace(f.VIEW_FRAGMENT,f.RAW_FRAGMENT))
    if mode=='bad_translation':instance={}
    text=json.dumps(dict(type='tool_call',name='csp',arguments={'instance':instance}))
   else:text=json.dumps(dict(type='final',output={'status':'UNKNOWN'}))
   return 200,{},json.dumps(dict(model='mock-model',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=text)])],usage=dict(input_tokens=100,output_tokens=20,input_tokens_details={'cached_tokens':0}))).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=send)
 def test_early_final_fails_with_usage_and_full_denominator(self):
  c=self.config()
  with tempfile.TemporaryDirectory() as t:
   s=m.run(f.spec(),c,Path(t)/'r',self.fake(c,'early'));self.assertEqual(s['by_arm']['csp']['success'],0);self.assertEqual(s['by_arm']['csp']['answer_complete'],0);self.assertEqual(s['by_arm']['csp']['planned'],4);self.assertEqual(s['by_arm']['csp']['known_tokens'],480)
 def test_invalid_translation_extra_call_and_unknown_remain_failures(self):
  for mode in ['invalid','bad_translation','extra','unknown']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as t:
    c=self.config();s=m.run(f.spec(),c,Path(t)/'r',self.fake(c,mode));self.assertEqual(s['by_arm']['csp']['success'],0);self.assertLessEqual(s['by_arm']['csp']['tool_calls'],4);self.assertEqual(sum(a['planned'] for a in s['by_arm'].values()),8)
 def test_legacy_configuration_rejected(self):
  with self.assertRaises(ValueError):m.make_plan(f.spec(),helpers.config())
 def test_source_identity_and_order(self):
  c=self.config();p,_=m.make_plan(f.spec(),c);self.assertIn('responses_mandatory_runner.py',p['source_sha256']);self.assertEqual(p,m.make_plan(f.spec(),c)[0]);self.assertEqual([s['arm'] for s in p['slots'][::2]].count('csp'),2)

 def test_hard_pilot_limits(self):
  for k,v in [('tool_call_limit',2),('repetitions',2)]:
   c=self.config();c[k]=v
   with self.assertRaises(ValueError):m.config(c)
