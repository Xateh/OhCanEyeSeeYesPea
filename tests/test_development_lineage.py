from copy import deepcopy
import unittest
from development_lineage import describe,ledger
from development_suites_v2 import DEFAULT,candidate


class LineageDescriptorTests(unittest.TestCase):
    def test_ordered_renaming_metadata_and_time_shift(self):
        c=deepcopy(DEFAULT);c.update(patient_count=1,surgeon_count=1,room_count=1)
        a=candidate(c,'parameter_sweep',0);before=deepcopy(a);b=deepcopy(a)
        b['rooms'][0]['id']='room';b['surgeons'][0]['id']='surgeon'
        for kind in ('rooms','surgeons'):
            b[kind][0]['calendar']=[[[x+20,y+20] for x,y in b[kind][0]['calendar'][0]]]
        for p in b['patients']:
            p.update(id='patient',surgeon='surgeon',eligible_rooms=['room'],priority=99,emergency=True)
            p['release']+=20;p['due']+=20
        x,y=describe(a),describe(b)
        self.assertNotEqual(x['exact_sha256'],y['exact_sha256'])
        self.assertEqual(x['normalized_sha256'],y['normalized_sha256'])
        self.assertEqual(x['topology_sha256'],y['topology_sha256'])
        self.assertEqual(a,before)

    def test_numeric_variants_and_mechanisms_keep_broad_parent(self):
        a=candidate(DEFAULT,'scarcity_contention',0);b=deepcopy(a)
        b['rooms'][0]['gap']=1
        x,y=describe(a),describe(b)
        self.assertEqual(x['topology_sha256'],y['topology_sha256'])
        self.assertNotEqual(x['mechanism_sha256'],y['mechanism_sha256'])
        rows=[dict(key='v1/a',population='v1',instance=a),dict(key='v2/b',population='v2',instance=b)]
        result=ledger(rows)
        self.assertEqual(result['cross_population_relationships']['topology']['v1 vs v2']['related_pairs'],1)
        self.assertEqual(len({r['parent_group'] for r in result['records']}),1)
        self.assertEqual(result,ledger(rows))
        with self.assertRaises(ValueError):ledger(rows+rows)
