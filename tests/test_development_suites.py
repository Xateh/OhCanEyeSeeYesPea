from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from development_suites import DEFAULT, settings, candidate, validate, build


def config(**changes):
    return dict(deepcopy(DEFAULT), candidates_per_suite=2, **changes)


def simple(patients=1, horizon=2, gap=0):
    c=config(patient_count=patients, room_count=1, surgeon_count=patients, horizon_minutes=horizon)
    i=candidate(c, 'scarcity_contention', 0)
    for r in i['rooms']+i['surgeons']:
        r.update(calendar=[[[0,horizon]]], budgets=[horizon], gap=0)
    i['rooms'][0]['gap']=gap
    for p in i['patients']:
        p.update(duration=1, release=0, due=horizon, mandatory=True, eligible_rooms=['r0'])
    return c,i


class DevelopmentSuiteTests(unittest.TestCase):
    def test_seed_count_scarcity_and_determinism(self):
        c=config(patient_count=4, surgeon_count=1)
        i=candidate(c, 'combined_constraints', 7)
        self.assertEqual(i,candidate(c,'combined_constraints',7))
        self.assertEqual(len(i['patients']),4)
        self.assertEqual(len(i['surgeons']),1)
        self.assertNotEqual(i,candidate(dict(c,seed=c['seed']+1),'combined_constraints',7))

    def test_actual_adapter_feasible_and_certified_negative(self):
        c,i=simple()
        v=validate(i,c)
        self.assertEqual((v['admission'],v['gold_label']),('accepted','FEASIBLE'))
        self.assertEqual(v['tool']['status'],'FEASIBLE')
        c,i=simple(patients=2,horizon=1)
        v=validate(i,c)
        self.assertEqual((v['admission'],v['gold_label']),('accepted','INFEASIBLE'))
        self.assertEqual(v['certificate']['kind'],'pair_order_impossible')

    def test_oracle_negative_tool_unknown_is_quarantined(self):
        c,i=simple(patients=2,horizon=2,gap=1)
        v=validate(i,c)
        self.assertEqual(v['gold_label'],'INFEASIBLE')
        self.assertEqual(v['proposed_use'],'validation_only')
        self.assertEqual(v['tool']['status'],'UNKNOWN')
        self.assertEqual(v['admission'],'quarantined')
        self.assertIsNone(v['certificate'])

    def test_bounds_and_incomplete_oracle_fail_closed(self):
        for c in [dict(config(),seed=True),dict(config(),patient_count=0),dict(config(),extra=1),
                  dict(config(),patient_count=16,room_count=16)]:
            with self.assertRaises(ValueError):
                settings(c)
        c,i=simple()
        with patch('development_suites.CSPAdapter') as adapter:
            v=validate(i,dict(c,oracle_product_cap=1))
            self.assertEqual(v['admission'],'rejected')
            adapter.assert_not_called()
            v=validate(i,dict(c,oracle_assignment_limit=1))
            self.assertEqual(v['gold_label'],'UNKNOWN')
            self.assertEqual(v['admission'],'quarantined')
            adapter.assert_not_called()

    def test_false_tool_witness_quarantined(self):
        c,i=simple()
        with patch('development_suites.CSPAdapter') as adapter:
            adapter.return_value.invoke.return_value={'status':'FEASIBLE','schedule':[]}
            self.assertEqual(validate(i,c)['admission'],'quarantined')

    def test_deterministic_exports_and_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            report=build(config(),a)
            build(config(),b)
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},
                             {p.name:p.read_bytes() for p in b.iterdir()})
            self.assertEqual(sum(report['admissions'].values()),12)
            manifest=json.loads((a/'manifest.json').read_text())
            for name,h in manifest['files'].items():
                self.assertEqual(hashlib.sha256((a/name).read_bytes()).hexdigest(),h)
            for row in map(json.loads,(a/'model.jsonl').read_text().splitlines()):
                self.assertEqual(set(row),{'case_id','text'})
                self.assertNotIn('"patients":["A","E"]',row['text'])
            with self.assertRaises(FileExistsError):
                build(config(),a)
