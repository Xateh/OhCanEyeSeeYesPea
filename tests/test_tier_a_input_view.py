import hashlib
from pathlib import Path
import unittest
from tier_a_inputs import prepare as raw_prepare, VERSION as RAW_VERSION
from tier_a_input_view import VERSION, RAW_FRAGMENT, VIEW_FRAGMENT, derive, prepare, bindings

CORPUS = Path(__file__).resolve().parents[1] / 'fixtures/tier-a-original-synthetic-v1'


class InputViewTests(unittest.TestCase):
    def test_exact_authorized_change_only(self):
        raw = raw_prepare(CORPUS, 'no_tools', RAW_VERSION)
        view = prepare(CORPUS, 'no_tools', VERSION)
        self.assertEqual(len(view), 9)
        for a, b in zip(raw, view):
            self.assertEqual(b['instance_text'], a['instance_text'].replace(RAW_FRAGMENT, VIEW_FRAGMENT, 1))
            self.assertEqual(b['instance_text'].replace(VIEW_FRAGMENT, RAW_FRAGMENT, 1), a['instance_text'])
            self.assertNotIn('"patients":["A","E"]', str(b))
            self.assertNotIn('A/E', str(b))
            self.assertEqual(set(b), {'shared_instruction', 'arm_instruction', 'instance_text'})

    def test_equal_common_content_and_separate_identities(self):
        a = prepare(CORPUS, 'no_tools', VERSION)
        b = prepare(CORPUS, 'csp', VERSION)
        x = bindings(CORPUS, 'no_tools', VERSION)
        y = bindings(CORPUS, 'csp', VERSION)
        self.assertEqual(a, prepare(CORPUS, 'no_tools', VERSION))
        for p, q, i, j in zip(a, b, x, y):
            self.assertEqual(p['instance_text'], q['instance_text'])
            self.assertEqual(p['shared_instruction'], q['shared_instruction'])
            self.assertEqual(i['common_sha256'], j['common_sha256'])
            self.assertNotEqual(i['raw_text_sha256'], i['derived_text_sha256'])
            self.assertEqual(i['derived_text_sha256'], hashlib.sha256(p['instance_text'].encode()).hexdigest())
            self.assertNotIn('sha256', str(p))

    def test_fail_closed_on_drift_or_wrong_version(self):
        for text in [None, 'missing', RAW_FRAGMENT + RAW_FRAGMENT]:
            with self.assertRaises(ValueError):
                derive(text)
        for arm, version in [('no_tools', RAW_VERSION), ('other', VERSION)]:
            with self.assertRaises(ValueError):
                prepare(CORPUS, arm, version)

    def test_original_export_bytes_unchanged(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORPUS.iterdir()}
        prepare(CORPUS, 'no_tools', VERSION)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in CORPUS.iterdir()})
