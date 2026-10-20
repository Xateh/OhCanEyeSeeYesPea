"""Bounded deterministic export and adversarial audit checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from surgerybench.common import canonical
from surgerybench.tier_a_dataset import build, cases
from surgerybench.tier_a_audit import audit

ROOT = Path(__file__).resolve().parents[1]


class TierACorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'first'
        build(self.out)

    def mutate_gold(self, change):
        path = self.out / 'tier-a-gold.jsonl'
        rows = [json.loads(s) for s in path.read_text().splitlines()]
        change(rows)
        path.write_text(''.join(canonical(r) + '\n' for r in rows))
        manifest = self.out / 'manifest.json'
        data = json.loads(manifest.read_text())
        data['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(canonical(data) + '\n')

    def test_deterministic_and_independently_audited(self):
        other = self.root / 'second'
        build(other)
        result = audit(self.out)
        self.assertEqual(result['instances'], 15)
        self.assertEqual(result['counts'], {'FEASIBLE/not_applicable': 7,
                         'INFEASIBLE/oracle_only': 6,
                         'INFEASIBLE/pair_order_impossible': 2})
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()},
                         {p.name: p.read_bytes() for p in other.iterdir()})
        self.assertEqual(len(cases()), 15)

    def test_refuses_overwrite_and_extra_files(self):
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaises(FileExistsError):
            build(self.out)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
        (self.out / 'unexpected').write_text('x')
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_manifest_corruption(self):
        with (self.out / 'tier-a-model.jsonl').open('a') as f:
            f.write('{}\n')
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_rehashed_wrong_label_rejected(self):
        self.mutate_gold(lambda rows: rows[0].update(label='INFEASIBLE'))
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_rehashed_invalid_witness_rejected(self):
        def change(rows):
            rows[0]['evidence']['witness'][1]['start'] = 2
        self.mutate_gold(change)
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_rehashed_fake_certification_rejected(self):
        def change(rows):
            r = next(r for r in rows if r['certification'] == 'oracle_only')
            r['certification'] = 'pair_order_impossible'
            r['evidence']['certificate'] = {
                'kind': 'pair_order_impossible', 'patients': ['A', 'B']}
        self.mutate_gold(change)
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_rehashed_receipt_and_missing_anchor_rejected(self):
        for kind in ('receipt', 'anchor'):
            with self.subTest(kind=kind):
                def change(rows):
                    if kind == 'receipt':
                        rows[0]['evidence']['oracle']['complete'] = False
                    else:
                        rows[0]['arithmetic'] = ''
                saved = {p.name: p.read_bytes() for p in self.out.iterdir()}
                self.mutate_gold(change)
                with self.assertRaises(ValueError):
                    audit(self.out)
                for name, data in saved.items():
                    (self.out / name).write_bytes(data)

    def test_resource_envelope_rejects_before_oracle(self):
        from surgerybench.tier_a_audit import validate_instance
        i = deepcopy(cases()[0]['instance'])
        i['patients'][0]['due'] = 11
        with self.assertRaises(ValueError):
            validate_instance(i)

    def test_rehashed_lineage_and_instance_hash_rejected(self):
        for kind in ('lineage', 'instance'):
            with self.subTest(kind=kind):
                saved = {p.name: p.read_bytes() for p in self.out.iterdir()}
                def change(rows):
                    if kind == 'lineage':
                        rows[0]['lineage']['source'] = 'unverified'
                    else:
                        rows[0]['instance']['patients'][0]['due'] = 4
                self.mutate_gold(change)
                with self.assertRaises(ValueError):
                    audit(self.out)
                for name, data in saved.items():
                    (self.out / name).write_bytes(data)

    def test_rehashed_model_text_rejected(self):
        path = self.out / 'tier-a-model.jsonl'
        rows = [json.loads(s) for s in path.read_text().splitlines()]
        rows[0]['text'] += 'altered'
        path.write_text(''.join(canonical(r) + '\n' for r in rows))
        manifest = self.out / 'manifest.json'
        data = json.loads(manifest.read_text())
        data['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(canonical(data) + '\n')
        with self.assertRaises(ValueError):
            audit(self.out)

    def test_old_harness_fails_before_provider_or_output(self):
        from surgerybench.temporal_benchmark import run
        def forbidden_provider():
            self.fail('old harness must reject format before provider construction')
        out = self.root / 'not-written.jsonl'
        with self.assertRaises(KeyError):
            run(self.out / 'tier-a-model.jsonl', self.out / 'tier-a-gold.jsonl',
                out, factory=forbidden_provider)
        self.assertFalse(out.exists())

    def test_model_gold_separation_and_original_integrity(self):
        models = [json.loads(s) for s in (self.out / 'tier-a-model.jsonl').read_text().splitlines()]
        self.assertTrue(all(set(r) == {'case_id', 'text'} for r in models))
        # Pinned original fixture bytes, not values generated by the new exporter.
        expected = {
            'gold.jsonl': 'e73a32b562ac7cad957945532dc04b2a886596436f89377dfefc2268aebd84c0',
            'model.jsonl': '6b1238f1e26ed93f1ae6dc50b2d03e6b8273be15610fcd7aaad01aab35c5fbf4',
            'manifest.json': '00f371ff5570ddf2e93983c1ccabe953882d8c93dfc74510a0a8e8c87d848812',
            'summary.json': 'ca5a576c1ab2beab2d216dc6d4f0bcf43b52410131cee91033e0d02d1ed594e9'}
        for name, sha in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / 'fixtures/arrival-deadline-v1' / name).read_bytes()).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main()
