from copy import deepcopy
import unittest
from development_counterfactuals import check,relax


class CounterfactualTests(unittest.TestCase):
    def test_joint_gap_fragmentation_effect(self):
        def r(name,windows,gap=0):return dict(id=name,gap=gap,budgets=[4],calendar=[windows])
        i=dict(schema_version='1.1',days=1,day_minutes=1440,
               rooms=[r('r0',[[0,1],[2,4]],1)],
               surgeons=[r('s0',[[0,4]]),r('s1',[[0,4]])],
               patients=[dict(id=n,surgeon=s,duration=2,release=0,due=4,eligible_rooms=['r0'],
                              mandatory=True,priority=1,emergency=False) for n,s in [('a','s0'),('b','s1')]])
        before=deepcopy(i)
        v=check(i,'room_gap+fragmented')
        self.assertEqual(v['meaning'],'joint_relaxation_only_restores_feasibility')
        self.assertEqual([v['variants'][n]['status'] for n in ['original','relaxA','relaxB','relaxBoth']],
                         ['INFEASIBLE','INFEASIBLE','INFEASIBLE','FEASIBLE'])
        self.assertEqual(i,before)
        self.assertEqual(relax(i,'room_gap+fragmented','relaxA')['rooms'][0]['calendar'],i['rooms'][0]['calendar'])
        with self.assertRaises(ValueError):relax(i,'other','original')

    def test_eligibility_ablation_bound_unknown_not_negative(self):
        def r(name):return dict(id=name,gap=0,budgets=[2],calendar=[[[0,2]]])
        i=dict(schema_version='1.1',days=1,day_minutes=1440,
               rooms=[r('r0'),r('r1'),r('r2')],surgeons=[r('s0'),r('s1'),r('s2')],
               patients=[dict(id='j'+str(n),surgeon='s'+str(n),duration=1,release=0,due=2,
                              eligible_rooms=['r0'],mandatory=True,priority=1,emergency=False) for n in range(3)])
        v=check(i,'low_budget_proxy+flexible')
        self.assertEqual(v['meaning'],'unresolved')
        self.assertEqual(v['variants']['original']['status'],'INFEASIBLE')
        self.assertEqual(v['variants']['relaxB']['status'],'UNKNOWN')
        self.assertEqual(v['variants']['relaxB']['reason'],'product_bound')
