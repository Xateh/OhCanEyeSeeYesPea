import hashlib
from pathlib import Path
import tempfile
import shutil
import unittest
from tier_a_contract import HASHES
from tier_a_handoff import inventory

CORPUS = Path(__file__).resolve().parents[1] / 'fixtures/tier-a-original-synthetic-v1'


class HandoffTests(unittest.TestCase):
    def test_conservation_and_evidence_use(self):
        result = inventory(CORPUS)
        self.assertEqual(result['export_sha256'], HASHES)
        self.assertEqual(result['use_counts'], {
            'evidence_eligible_development': 9, 'validation_only': 6})
        eligible = [c for c in result['cases'] if c['use'] == 'evidence_eligible_development']
        self.assertEqual(sum(c['label'] == 'FEASIBLE' for c in eligible), 7)
        self.assertEqual(sum(c['certification'] == 'pair_order_impossible' for c in eligible), 2)
        self.assertTrue(all(c['certification'] == 'oracle_only' for c in result['cases']
                            if c['use'] == 'validation_only'))
        self.assertTrue(all(c['oracle_complete'] for c in result['cases']))
        self.assertEqual(max(c['product_upper_bound'] for c in result['cases']), 36)

    def test_groups_and_privileged_boundary(self):
        result = inventory(CORPUS)
        grouped = [i for ids in result['construction_groups'].values() for i in ids]
        self.assertEqual(len(grouped), 15)
        self.assertEqual(len(set(grouped)), 15)
        self.assertEqual(len(result['construction_groups']), 10)
        self.assertTrue(all(c['split'] == 'provisional_review' for c in result['cases']))
        self.assertEqual(result['audience'], 'privileged_evaluator_only')
        self.assertTrue(all(not ({'text', 'instance', 'evidence', 'arithmetic'} & set(c))
                            for c in result['cases']))
        self.assertEqual(result['tag_counts']['positive_room_gap'], 3)

    def test_read_only_and_deterministic(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORPUS.iterdir()}
        self.assertEqual(inventory(CORPUS), inventory(CORPUS))
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in CORPUS.iterdir()})

    def test_corruption_stops_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'corpus'
            shutil.copytree(CORPUS, target)
            with (target / 'tier-a-model.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaises(ValueError):
                inventory(target)

    def test_incomplete_package_stops_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                inventory(tmp)
