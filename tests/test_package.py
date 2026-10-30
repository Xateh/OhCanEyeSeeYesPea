"""Packaged fixture/provenance checks; requires no external source corpus."""
import hashlib
import unittest
from pathlib import Path
from collections import Counter, defaultdict
from surgerybench.common import read_jsonl
from surgerybench.temporal_text import parse

ROOT=Path(__file__).resolve().parents[1]

class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold=read_jsonl(ROOT/'fixtures/arrival-deadline-v1/gold.jsonl')
        cls.model=read_jsonl(ROOT/'fixtures/arrival-deadline-v1/model.jsonl')
    def test_original_synthetic_only(self):
        self.assertEqual(len(self.gold),48)
        self.assertTrue(all(r['lineage']['source']['kind']=='original_synthetic' for r in self.gold))
    def test_model_has_no_gold_fields(self):
        self.assertTrue(all(set(r)=={'id','text'} for r in self.model))
    def test_split_families(self):
        families=defaultdict(set)
        for r in self.gold: families[r['family']].add(r['split'])
        self.assertEqual(len(families),24); self.assertTrue(all(len(s)==1 for s in families.values()))
        self.assertEqual(Counter(r['split'] for r in self.gold),{'train':32,'validation':8,'test':8})
    def test_text_matches_intended_instance(self):
        for m,g in zip(self.model,self.gold):
            self.assertEqual(m['id'],g['id']); self.assertEqual(parse(m['text']),g['instance'])
    def test_manifest_identity(self):
        self.assertEqual(hashlib.sha256((ROOT/'fixtures/arrival-deadline-v1/manifest.json').read_bytes()).hexdigest(),'00f371ff5570ddf2e93983c1ccabe953882d8c93dfc74510a0a8e8c87d848812')
    def test_balanced_certified_labels(self):
        self.assertEqual(Counter(r['label'] for r in self.gold),{'FEASIBLE':24,'INFEASIBLE':24})

if __name__=='__main__': unittest.main()
