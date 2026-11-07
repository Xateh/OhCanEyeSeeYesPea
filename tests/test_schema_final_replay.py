import json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import schema_final_replay as d
from responses_fixture import configure
configure()
class ReplayTests(unittest.TestCase):
 def test_frozen_pair_parity_and_checked_evidence(self):
  p,c=d.register();self.assertEqual(len(p['slots']),4);self.assertEqual(p,d.register()[0])
  self.assertEqual([s['condition'] for s in p['slots']],['off','on','on','off'])
  for i in d.IDS:
   a=d.body(p,i,'on');b=d.body(p,i,'off');a.pop('text');self.assertEqual(a,b)
   self.assertTrue(d.grade(d.canonical({'type':'final','output':c[i]['checked_output']}),c[i])['evidence_success'])
 def test_identical_strict_evaluation(self):
  p,c=d.register();case=c[d.IDS[0]];o=deepcopy(case['checked_output']);o['schedule'][0]['start']=1000000
  result=d.grade(d.canonical({'type':'final','output':o}),case);self.assertTrue(result['shape_valid']);self.assertFalse(result['evidence_success'])
  for text in ['{','```json\n{}\n```','{}',d.canonical({'type':'final','output':{'status':'UNKNOWN'}})]:
   self.assertFalse(d.grade(text,case)['evidence_success'])
 def fake(self,p,c,mode='valid'):
  def send(body,timeout):
   case=next(x for x in c.values() if body['input']==x['request']['input']);out={'type':'final','output':case['checked_output']}
   envelope=dict(model='gpt-6-astra',service_tier='fast' if mode=='tier' else 'default',status='incomplete' if mode=='incomplete' else 'completed',incomplete_details=None,output=[dict(type='message',role='assistant',content=[dict(type='refusal',refusal='synthetic')] if mode=='refusal' else [dict(type='output_text',text=json.dumps(out))])],usage=None if mode=='usage' else dict(input_tokens=100,output_tokens=30,total_tokens=130,input_tokens_details={'cached_tokens':0,'cache_write_tokens':0},output_tokens_details={'reasoning_tokens':0}))
   return 200,{},json.dumps(envelope).encode(),True
  return send
 def test_mock_four_calls_zero_solver_and_reassessment(self):
  p,c=d.register()
  with patch('solver_interface.MergedSolver.invoke',side_effect=AssertionError('solver forbidden')),tempfile.TemporaryDirectory() as t:
   out=Path(t)/'run';s=d.execute(p,c,out,transport=self.fake(p,c));self.assertEqual(s['success'],4);self.assertEqual(s['http_calls'],4);self.assertEqual(s['solver_calls'],0)
   self.assertEqual(d.assess_saved(out),s)
 def test_failures_and_missing_usage_preserve_denominators(self):
  p,c=d.register()
  for mode in ['tier','usage','refusal','incomplete']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as t:
    s=d.execute(p,c,Path(t)/'run',transport=self.fake(p,c,mode));self.assertEqual(s['planned'],4);self.assertEqual(s['success'],0);self.assertLessEqual(s['http_calls'],4)
    if mode in ['tier','usage']:self.assertEqual(s['missing'],3)
 def test_live_optin_overwrite_and_source_drift(self):
  p,c=d.register()
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):d.execute(p,c,Path(t)/'run')
   with self.assertRaises(FileExistsError):d.execute(p,c,Path(t),transport=self.fake(p,c))
   bad=deepcopy(p);bad['slots'][0]['condition']='other'
   with self.assertRaises(ValueError):d.execute(bad,c,Path(t)/'bad',transport=self.fake(p,c))

 def test_interruption_and_tampered_receipt(self):
  p,c=d.register()
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'run'
   def stop(*args):raise KeyboardInterrupt()
   with self.assertRaises(KeyboardInterrupt):d.execute(p,c,out,transport=stop)
   self.assertEqual(d.assess_saved(out)['missing'],4)
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'run';d.execute(p,c,out,transport=self.fake(p,c))
   r=json.loads((out/'calls.jsonl').read_text().splitlines()[0]);r['raw_model_text']='{}'
   with self.assertRaises(ValueError):d.assess(p,c,[r],'mock')
