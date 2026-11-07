from copy import deepcopy
import unittest
from development_counterfactuals_v2 import check,lattice,optional_control,relax
from development_suites_v2 import DEFAULT,candidate


class ExtendedCounterfactualTests(unittest.TestCase):
    def test_entire_lattice_not_only_original_feasible(self):
        with self.assertRaises(ValueError):
            lattice(dict(original='INFEASIBLE',relaxA='FEASIBLE',relaxB='INFEASIBLE',relaxBoth='INFEASIBLE'))
        edges=lattice(dict(original='INFEASIBLE',relaxA='UNKNOWN',relaxB='INFEASIBLE',relaxBoth='FEASIBLE'))
        self.assertIn('relaxA->relaxBoth',edges)

    def test_new_relaxation_fields_and_immutability(self):
        i=candidate(DEFAULT,'combined_constraints',0);before=deepcopy(i)
        a=relax(i,'room_gap+surgeon_gap','relaxA')
        self.assertTrue(all(r['gap']==0 for r in a['rooms']))
        self.assertEqual(a['surgeons'],i['surgeons'])
        result=check(i,'low_budget_proxy+room_gap')
        self.assertEqual(set(result['variants']),{'original','relaxA','relaxB','relaxBoth'})
        self.assertEqual(i,before)

    def test_optional_counterpart_is_separate_tightening(self):
        c=deepcopy(DEFAULT);c.update(patient_count=2,surgeon_count=2,room_count=1,horizon_minutes=2,duration_max=1)
        i=candidate(c,'optional_load',1)
        for p in i['patients']:p.update(duration=2,release=0,due=2,eligible_rooms=['r0'])
        i['patients'][1]['mandatory']=False
        for r in i['rooms']+i['surgeons']:r.update(gap=0,budgets=[2],calendar=[[[0,2]]])
        result=optional_control(i)
        self.assertEqual(result['meaning'],'optional_omission_permits_feasibility')
        self.assertEqual(result['original']['status'],'FEASIBLE')
        self.assertEqual(result['mandatory_counterpart']['status'],'INFEASIBLE')
        self.assertFalse(i['patients'][1]['mandatory'])
