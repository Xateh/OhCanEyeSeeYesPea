from copy import deepcopy
import json,unittest
from pathlib import Path
from solver_interface import CheckedSolver,MergedSolver,LIMITS
from surgerybench.temporal_check import check_schedule
GOLD=[json.loads(s) for s in (Path(__file__).resolve().parents[1]/'fixtures/tier-a-original-synthetic-v1/tier-a-gold.jsonl').read_text().splitlines()]
def case(prefix):return next(g for g in GOLD if g['case_id'].startswith(prefix))
class Plugin:
 revision='synthetic-plugin-v1';schema_version='1.1';supported_limits=LIMITS
 def __init__(self,result=None,error=None):self.result=result;self.error=error;self.calls=0
 def invoke(self,args):
  self.calls+=1
  if self.error:raise self.error
  return deepcopy(self.result)
class SolverTests(unittest.TestCase):
 def test_merged_feasible_and_supported_negative(self):
  for prefix,status in [('room-gap-5','FEASIBLE'),('optional-forced','INFEASIBLE')]:
   s=CheckedSolver(MergedSolver(),MergedSolver.revision,LIMITS);r=s.invoke({'instance':case(prefix)['instance']});self.assertEqual(r['status'],status);self.assertFalse(s.events[-1]['error'])
 def test_optional_omission_is_legal(self):
  s=CheckedSolver(MergedSolver(),MergedSolver.revision,LIMITS);g=case('optional-omitted');r=s.invoke({'instance':g['instance']});self.assertFalse(check_schedule(g['instance'],r['schedule']));self.assertEqual(len(r['schedule']),1)
 def test_malformed_false_unsupported_certificate_is_unknown(self):
  for result in (None,{'status':'INVALID'},{'status':'INFEASIBLE'},{'status':'INFEASIBLE','certificate':{'kind':'unsupported','patients':['A','B']}},{'status':'FEASIBLE','schedule':[]}):
   p=Plugin(result);s=CheckedSolver(p,p.revision,LIMITS);r=s.invoke({'instance':case('room-gap-5')['instance']});self.assertEqual(r['status'],'UNKNOWN');self.assertTrue(s.events[-1]['error'])
 def test_unknown_exhaustion_is_not_infeasible(self):
  p=Plugin({'status':'UNKNOWN','reason':'exhausted_without_supported_certificate','search_exhausted':True,'nodes':1});s=CheckedSolver(p,p.revision,LIMITS);self.assertEqual(s.invoke({'instance':case('room-gap-5')['instance']})['status'],'UNKNOWN');self.assertFalse(s.events[-1]['error'])
 def test_timeout(self):
  p=Plugin(error=TimeoutError());s=CheckedSolver(p,p.revision,LIMITS);self.assertEqual(s.invoke({'instance':case('room-gap-5')['instance']})['status'],'UNKNOWN');self.assertTrue(s.events[-1]['timeout'])
 def test_version_limits_and_gold_argument_rejected(self):
  p=Plugin({'status':'UNKNOWN','reason':'synthetic'})
  for revision,limit in [('wrong',LIMITS),(p.revision,dict(max_nodes=100001,seconds=2)),(p.revision,dict(max_nodes=1,seconds=float('nan'))),(p.revision,dict(max_nodes=1,seconds=1))]:
   with self.assertRaises(ValueError):CheckedSolver(p,revision,limit)
  s=CheckedSolver(p,p.revision,LIMITS);s.invoke({'instance':case('room-gap-5')['instance'],'gold':True});self.assertEqual(p.calls,0)
