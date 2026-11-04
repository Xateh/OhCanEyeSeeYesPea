from copy import deepcopy
import unittest
import tier_a_completion as adapter
from test_tier_a_contract import PACKAGE, plan, case, receipt, good_output
import tier_a_contract as core
from test_tier_a_execution_contract import fixture, SHARED, OUTPUT
import tier_a_execution_contract as execution


class CompletionTests(unittest.TestCase):
    def test_utf8_bytes_not_character_count_controls_completion(self):
        import json
        g = case('room-gap-5')
        output = good_output(g)
        output['schedule'][0]['patient'] = 'é'
        text = json.dumps(output, ensure_ascii=False)
        for size, complete in ((65536, True), (65537, False)):
            with self.subTest(size=size):
                raw = text + ' ' * (size - len(text.encode()))
                self.assertEqual(len(raw.encode()), size)
                self.assertLess(len(raw), size)
                legacy = core.evaluate(PACKAGE, plan(), [receipt(g, output, raw_output=raw),
                    receipt(g, good_output(g), arm='csp')])
                saved = deepcopy(legacy)
                result = adapter.reconcile(legacy)
                self.assertEqual(legacy, saved)
                self.assertEqual(result['rows'][0]['answer_complete'], complete)
                self.assertFalse(result['rows'][0]['success'])
                self.assertEqual(result['completion_pairs']['csp_only'], int(complete))
                self.assertEqual(result['completion_by_arm']['no_tools']['planned'], 9)

    def test_raw_utf8_byte_boundary_through_scorer(self):
        g = case('room-gap-5')
        other = receipt(g, good_output(g), arm='csp')
        for size, complete, bucket in ((65536, True, 'csp_only'), (65537, False, 'incomplete')):
            with self.subTest(size=size):
                text = '{"status":"UNKNOWN"}'
                raw_text = text + ' ' * (size - len(text.encode()))
                r = receipt(g, {'status': 'UNKNOWN'}, raw_output=raw_text)
                legacy = core.evaluate(PACKAGE, plan(), [r, other])
                saved = deepcopy(legacy)
                result = adapter.reconcile(legacy)
                self.assertEqual(legacy, saved)
                self.assertEqual(result['rows'][0]['answer_complete'], complete)
                self.assertEqual(legacy['rows'][0]['output_error'], not complete)
                self.assertTrue(result['rows'][0]['legacy_completed'])
                self.assertEqual(result['completion_pairs'][bucket], 1 if complete else 9)
                self.assertEqual(sum(result['completion_pairs'].values()), 9)
                self.assertEqual(result['by_arm'], legacy['by_arm'])
                self.assertEqual(result['completion_by_arm']['no_tools']['planned'], 9)
                self.assertEqual(result['completion_by_arm']['no_tools']['attempted'], 1)

    def test_answer_boundaries_and_legacy_preservation(self):
        g = case('room-gap-5')
        wrong = good_output(g)
        wrong['schedule'][1]['start'] = 2
        for output, complete in ((None, False), ({'status': 'INFEASIBLE'}, False),
                                 (wrong, True), ({'status': 'UNKNOWN'}, True)):
            with self.subTest(output=output):
                raw = core.evaluate(PACKAGE, plan(), [receipt(g, output)])
                saved = deepcopy(raw)
                result = adapter.reconcile(raw)
                self.assertEqual(raw, saved)
                self.assertEqual(result['rows'][0]['answer_complete'], complete)
                self.assertTrue(result['rows'][0]['legacy_completed'])
                self.assertEqual(result['by_arm'], raw['by_arm'])
                self.assertEqual(result['completion_by_arm']['no_tools']['planned'], 9)

    def test_false_certificate_is_complete_but_unsupported_kind_is_not(self):
        g = case('room-gap-5')
        for kind, complete in (('pair_order_impossible', True), ('exhausted', False)):
            output = dict(status='INFEASIBLE', certificate=dict(kind=kind, patients=['A', 'B']))
            row = adapter.reconcile(core.evaluate(PACKAGE, plan(), [receipt(g, output)]))['rows'][0]
            self.assertEqual(row['answer_complete'], complete)
            self.assertFalse(row['success'])

    def test_abstention_timeout_and_missing(self):
        g = case('room-gap-5')
        for term, complete in (('abstained', True), ('provider_error', False)):
            r = receipt(g, None, raw_output=None, normalized_output=None, termination=term,
                        provider_error=term == 'provider_error')
            result = adapter.reconcile(core.evaluate(PACKAGE, plan(), [r]))
            self.assertEqual(result['rows'][0]['answer_complete'], complete)
            self.assertTrue(result['rows'][0]['execution_terminal'])
            self.assertFalse(result['rows'][1]['execution_terminal'])
            self.assertEqual(sum(result['completion_pairs'].values()), 9)

    def test_budget_failure_and_family_conservation(self):
        m, rows = fixture()
        rows[0]['elapsed_seconds'] = 6
        rows[2]['scoring_receipt']['normalized_output'] = {'status': 'UNKNOWN'}
        base = execution.validate(PACKAGE, m, rows[:-1], SHARED, OUTPUT)['scoring']
        result = adapter.reconcile(base)
        self.assertTrue(result['rows'][0]['answer_complete'])
        self.assertFalse(result['rows'][0]['success'])
        self.assertEqual(result['completion_pairs'], dict(both_success=6, no_tools_only=0,
                         csp_only=1, neither_success=0, incomplete=2))
        for arm, total in result['completion_by_arm'].items():
            for key, value in total.items():
                self.assertEqual(sum(f[arm][key] for f in result['completion_by_family'].values()), value)
