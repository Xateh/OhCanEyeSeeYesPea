import unittest,tempfile,json
from pathlib import Path
from copy import deepcopy
import handoff_comparison as d
import test_responses_handoff as fixture
class ComparisonTests(unittest.TestCase):
 def test_registration_and_reproducibility(self):
  p,c=d.make_plan(False);q,_=d.make_plan(False)
  self.assertEqual(p,q);self.assertEqual(len(p['slots']),4)
  self.assertEqual([s['condition'] for s in p['slots']],["old","restored","restored","old"])
  self.assertEqual(set(c),set(d.IDS));self.assertEqual(p['maximum_http_calls'],8)
  with self.assertRaises(ValueError):d.make_plan(False,case_ids=d.IDS[::-1])
 def test_mock_full_flow_and_request_parity(self):
  p,c=d.make_plan(False);seen=[];helper=fixture.HandoffTests()
  def factory():return helper.factory(p['execution_config'],seen)()
  with tempfile.TemporaryDirectory() as t:
   s=d.execute(p,c,Path(t)/'run',factory)
   self.assertEqual(s['planned'],4);self.assertEqual(s['success'],4);self.assertEqual(s['http_calls'],8);self.assertEqual(s['solver_calls'],4)
   self.assertEqual(s['comparisons'][0]['translation_requests_equal'],True)
   self.assertTrue(all(x['final_only_instruction_difference'] for x in s['comparisons']))
 def test_no_live_without_optin_and_no_overwrite(self):
  p,c=d.make_plan(True)
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):d.execute(p,c,Path(t)/'run')
  p,c=d.make_plan(False)
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(FileExistsError):d.execute(p,c,Path(t),lambda:None)
 def test_interruption_retains_denominators(self):
  p,c=d.make_plan(False)
  def stop():raise KeyboardInterrupt()
  with tempfile.TemporaryDirectory() as t:
   o=Path(t)/'run'
   with self.assertRaises(KeyboardInterrupt):d.execute(p,c,o,stop)
   self.assertEqual(d.assess(p,c,[])['missing'],4)

 def test_unknown_and_protocol_failures_are_not_success(self):
  p,c=d.make_plan(False)
  for mode in ['abstain','early','repeat','wrong']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as t:
    f=fixture.HandoffTests().factory(p['execution_config'],[],mode)
    s=d.execute(p,c,Path(t)/'run',f)
    self.assertEqual(s['planned'],4);self.assertEqual(s['success'],0)
    self.assertLessEqual(s['http_calls'],8);self.assertLessEqual(s['solver_calls'],4)
 def test_duplicate_changed_plan_and_tamper_rejected(self):
  p,c=d.make_plan(False);bad=deepcopy(p);bad['maximum_http_calls']=9
  with self.assertRaises(ValueError):d.assess(bad,c,[])
  f=fixture.HandoffTests().factory(p['execution_config'],[])
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'run';d.execute(p,c,out,f)
   rows=[json.loads(x) for x in (out/'attempts.jsonl').read_text().splitlines()]
   with self.assertRaises(ValueError):d.assess(p,c,rows+[rows[0]])
   rows[0]['raw_output']='{}'
   with self.assertRaises(ValueError):d.assess(p,c,rows)
