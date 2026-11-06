import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tier_a_inputs import VERSION, prepare, fingerprint

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'fixtures/tier-a-original-synthetic-v1'


class InputTests(unittest.TestCase):
    def test_deterministic_and_matched_common_fields(self):
        direct = prepare(CORPUS, 'no_tools', VERSION)
        csp = prepare(CORPUS, 'csp', VERSION)
        self.assertEqual(direct, prepare(CORPUS, 'no_tools', VERSION))
        self.assertEqual(len(direct), 9)
        for a, b in zip(direct, csp):
            self.assertEqual(a['shared_instruction'], b['shared_instruction'])
            self.assertEqual(a['instance_text'], b['instance_text'])
            self.assertEqual(fingerprint(a)['common_sha256'], fingerprint(b)['common_sha256'])
            self.assertNotEqual(a['arm_instruction'], b['arm_instruction'])

    def test_exact_frozen_text_and_eligible_order(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORPUS.iterdir()}
        gold = [json.loads(s) for s in (CORPUS / 'tier-a-gold.jsonl').read_text().splitlines()]
        model = [json.loads(s) for s in (CORPUS / 'tier-a-model.jsonl').read_text().splitlines()]
        expected = [m['text'] for g, m in zip(gold, model) if g['certification'] != 'oracle_only']
        self.assertEqual([p['instance_text'] for p in prepare(CORPUS, 'no_tools', VERSION)], expected)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORPUS.iterdir()})

    def test_model_fields_exclude_privileged_metadata_and_identity(self):
        for payload in prepare(CORPUS, 'csp', VERSION):
            self.assertEqual(set(payload), {'shared_instruction', 'arm_instruction', 'instance_text'})
            text = json.dumps(payload)
            for forbidden in ['case_id', 'oracle_only', 'provisional_review', 'instance_sha256',
                              '82b58812c0b0', 'eligibility-budget-flex-', 'lineage', 'solution_count']:
                self.assertNotIn(forbidden, text)
            identity = fingerprint(payload)
            self.assertEqual(identity['wrapper_version'], VERSION)
            self.assertEqual(identity['instance_text_sha256'], hashlib.sha256(payload['instance_text'].encode()).hexdigest())

    def test_fail_closed_version_arm_and_package(self):
        for arm, version in [('other', VERSION), ('no_tools', None), ('csp', 'old'), ([], VERSION)]:
            with self.assertRaises(ValueError):
                prepare(CORPUS, arm, version)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                prepare(tmp, 'no_tools', VERSION)

    def test_fingerprint_shape_and_return_isolation(self):
        payload = prepare(CORPUS, 'no_tools', VERSION)[0]
        for bad in [dict(payload, case_id='gold'), dict(payload, instance_text=None),
                    dict(payload, shared_instruction='edited')]:
            with self.assertRaises(ValueError):
                fingerprint(bad)
        payload['instance_text'] = 'changed'
        self.assertNotEqual(payload, prepare(CORPUS, 'no_tools', VERSION)[0])
