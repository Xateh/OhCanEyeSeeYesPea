import unittest
from copy import deepcopy
import development_interactions_v3 as m

CONFIG=dict(version=m.VERSION,seed=326306,base_variants_per_family=4,families=list(m.FAMILIES))

class InteractionsV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=m.build(CONFIG)
    def test_counts_and_contrasts(self):
        b=self.bundle
        self.assertEqual(b['status'],'complete')
        self.assertEqual(len(b['records']),48)
        self.assertEqual(b['counts'],{'accepted':28,'quarantined':20})
        self.assertEqual(len(b['matrices']),12)
        for x in b['matrices']:
            expected=['INFEASIBLE','INFEASIBLE','INFEASIBLE','FEASIBLE'] if x['family']=='surgeon_gap_fragmented' else ['INFEASIBLE','FEASIBLE','FEASIBLE','FEASIBLE']
            self.assertEqual([x['labels'][v] for v in m.VARIANTS],expected)
    def test_full_replay(self):self.assertEqual(self.bundle,m.build(CONFIG))
    def test_admission(self):
        for r in self.bundle['records']:
            e=r['evidence']
            self.assertTrue(e['oracle']['complete'])
            if r['expected_label']=='INFEASIBLE':
                self.assertEqual(e['admission'],'quarantined')
                self.assertEqual(e['tool']['status'],'UNKNOWN')
            else:self.assertEqual(e['admission'],'accepted')
    def test_inputs(self):
        a=m.model_inputs(self.bundle,'no_tools');b=m.model_inputs(self.bundle,'csp')
        self.assertEqual(len(a),28)
        for x,y in zip(a,b):
            self.assertEqual(set(x),{'shared_instruction','arm_instruction','text'})
            self.assertEqual(x['text'],y['text'])
            self.assertEqual(x['shared_instruction'],y['shared_instruction'])
            self.assertNotIn('"A","E"',x['text'])
    def test_tampering_and_version(self):
        for field,value in [('version','unsupported'),('status','incomplete')]:
            b=deepcopy(self.bundle);b[field]=value
            with self.assertRaises(ValueError):m.audit(b)
        b=deepcopy(self.bundle);b['records'][0]['evidence']['tool']['status']='INFEASIBLE'
        with self.assertRaises(ValueError):m.audit(b)
    def test_settings(self):
        for field,value in [('seed',True),('base_variants_per_family',7),('families',[])]:
            c=deepcopy(CONFIG);c[field]=value
            with self.assertRaises(ValueError):m.settings(c)
    def test_identity(self):
        rows=self.bundle['records']
        self.assertEqual(len({r['case_id'] for r in rows}),48)
        self.assertEqual(len({m.sha(m.canonical(r['instance'])) for r in rows}),48)
