"""Synthetic recorded attempts only. No generator, provider or live runner."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import tier_a_contract as contract

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'fixtures/tier-a-original-synthetic-v1'
GOLD = [json.loads(s) for s in (PACKAGE / 'tier-a-gold.jsonl').read_text().splitlines()]


def plan(repetitions=1):
    return dict(contract_version=contract.CONTRACT, corpus_version=contract.CORPUS,
                repetitions=repetitions, arms=['no_tools', 'csp'], case_use={
                    g['case_id']: 'validation_only' if g['certification'] == 'oracle_only'
                    else 'eligible' for g in GOLD})


def case(prefix):
    return next(g for g in GOLD if g['case_id'].startswith(prefix + '-'))


def receipt(g, output, arm='no_tools', rep=0, **changes):
    result = dict(case_id=g['case_id'], repetition=rep, arm=arm,
                  raw_output=json.dumps(output), normalized_output=deepcopy(output),
                  normalization_errors=[], provider_error=False, tool_error=False,
                  termination='final')
    result.update(changes)
    return result


def good_output(g):
    return (dict(status='FEASIBLE', schedule=deepcopy(g['evidence']['witness']))
            if g['label'] == 'FEASIBLE' else
            dict(status='INFEASIBLE', certificate=deepcopy(g['evidence']['certificate'])))


class TierAContractTests(unittest.TestCase):
    def score(self, receipts, p=None):
        return contract.evaluate(PACKAGE, plan() if p is None else p, receipts)

    def row(self, result, g, arm='no_tools', rep=0):
        return next(r for r in result['rows'] if r['case_id'] == g['case_id']
                    and r['arm'] == arm and r['repetition'] == rep)

    def test_full_synthetic_success_and_exact_denominators(self):
        selected = [g for g in GOLD if g['certification'] != 'oracle_only']
        receipts = [receipt(g, good_output(g), arm, rep)
                    for g in selected for rep in range(2) for arm in contract.ARMS]
        result = self.score(receipts, plan(2))
        for summary in result['by_arm'].values():
            self.assertEqual(summary['planned'], 18)
            self.assertEqual(summary['feasible_schedule_success'], {'numerator': 14, 'denominator': 14})
            self.assertEqual(summary['negative_certified_success'], {'numerator': 4, 'denominator': 4})
            self.assertEqual(summary['evidence_backed_task_success'], {'numerator': 18, 'denominator': 18})
            self.assertFalse(summary['incomplete'])
        self.assertEqual(result['pairs']['both_success'], 18)
        self.assertEqual(len(result['by_family']), 8)
        self.assertEqual(len(result['validation_only_excluded']), 6)

    def test_missing_slots_remain_in_planned_denominators(self):
        g = case('room-gap-5')
        result = self.score([receipt(g, good_output(g))], plan(2))
        a, b = (result['by_arm'][arm] for arm in contract.ARMS)
        self.assertEqual((a['planned'], a['attempted'], a['completed'], a['missing']), (18, 1, 1, 17))
        self.assertEqual(b['missing'], 18)
        self.assertEqual(a['feasible_schedule_success'], {'numerator': 1, 'denominator': 14})
        self.assertTrue(a['incomplete'])
        self.assertEqual(result['pairs']['incomplete'], 18)

    def test_valid_non_gold_witness_and_optional_omission(self):
        g = case('room-gap-5')
        output = good_output(g)
        output['schedule'][0]['start'], output['schedule'][1]['start'] = 3, 0
        self.assertNotEqual(output['schedule'], g['evidence']['witness'])
        optional = case('optional-omitted')
        result = self.score([receipt(g, output), receipt(optional, good_output(optional))])
        self.assertTrue(self.row(result, g)['success'])
        self.assertTrue(self.row(result, optional)['success'])

    def test_optional_inclusion_is_allowed_without_extra_credit(self):
        g = case('optional-adjacent')
        output = dict(status='FEASIBLE', schedule=g['evidence']['optional_witness'])
        result = self.score([receipt(g, output)])
        self.assertTrue(self.row(result, g)['success'])
        self.assertEqual(result['by_arm']['no_tools']['evidence_backed_task_success']['numerator'], 1)

    def test_mistranslated_valid_schedule_fails_intended_instance(self):
        g = case('room-gap-5')
        output = good_output(g)
        output['schedule'][1]['start'] = 2  # valid only if the room gap were mistranslated as zero
        result = self.score([receipt(g, output)])
        row = self.row(result, g)
        self.assertFalse(row['success'])
        self.assertTrue(row['output_error'])
        self.assertTrue(any('gap' in s for s in row['diagnostics']))

    def test_valid_alternate_certificate_order(self):
        g = case('pair-deadline')
        output = good_output(g)
        output['certificate']['patients'].reverse()
        self.assertNotEqual(output['certificate'], g['evidence']['certificate'])
        self.assertTrue(self.row(self.score([receipt(g, output)]), g)['certified_success'])

    def test_bare_negative_only_earns_diagnostic_agreement(self):
        g = case('optional-forced')
        row = self.row(self.score([receipt(g, {'status': 'INFEASIBLE'})]), g)
        self.assertTrue(row['decision_agreement'])
        self.assertTrue(row['output_error'])
        self.assertFalse(row['certified_success'])
        self.assertFalse(row['success'])

    def test_false_unsupported_null_and_malformed_certificates(self):
        g = case('optional-forced')
        for certificate in (None, {}, {'kind': 'solver_exhausted'},
                            {'kind': 'pair_order_impossible', 'patients': ['A', 'A']},
                            {'kind': 'pair_order_impossible', 'patients': ['A', 'missing']},
                            {'kind': 'pair_order_impossible', 'patients': ['A', 'B'], 'proof': True}):
            with self.subTest(certificate=certificate):
                row = self.row(self.score([receipt(g, dict(status='INFEASIBLE', certificate=certificate))]), g)
                self.assertTrue(row['decision_agreement'])
                self.assertTrue(row['output_error'])
                self.assertFalse(row['certified_success'])
        feasible = case('room-gap-5')
        false = dict(status='INFEASIBLE', certificate={'kind': 'pair_order_impossible', 'patients': ['A', 'B']})
        self.assertFalse(self.row(self.score([receipt(feasible, false)]), feasible)['success'])

    def test_output_keys_nulls_and_types_fail_closed(self):
        g = case('room-gap-5')
        invalid = [None, [], 'FEASIBLE', {}, {'status': None}, {'status': 'SAT'},
                   {'status': 'FEASIBLE', 'schedule': None},
                   {'status': 'FEASIBLE', 'schedule': {}},
                   dict(good_output(g), certificate=None),
                   {'status': 'UNKNOWN', 'reason': 'extra'},
                   {'status': 'UNKNOWN', 'schedule': None}]
        boolean_time = good_output(g)
        boolean_time['schedule'][0]['start'] = False
        invalid.append(boolean_time)
        for output in invalid:
            with self.subTest(output=output):
                row = self.row(self.score([receipt(g, output)]), g)
                self.assertTrue(row['output_error'])
                self.assertFalse(row['success'])

    def test_normalization_cannot_repair_raw_evidence(self):
        g = case('room-gap-5')
        good = good_output(g)
        invalid = good_output(g)
        invalid['schedule'][1]['start'] = 2
        for raw, normalized, errors in ((json.dumps(invalid), good, []),
                                        (json.dumps(good), good, ['coerced something']),
                                        ('not JSON', good, []),
                                        ('{"status":"UNKNOWN","status":"FEASIBLE"}', good, []),
                                        ('NaN', None, [])):
            with self.subTest(raw=raw):
                r = receipt(g, good, raw_output=raw, normalized_output=normalized,
                            normalization_errors=errors)
                row = self.row(self.score([r]), g)
                self.assertFalse(row['success'])
                self.assertTrue(row['output_error'])
                self.assertEqual(row['receipt']['raw_output'], raw)

    def test_non_json_normalized_containers_cannot_earn_success(self):
        g = case('room-gap-5')
        good = good_output(g)
        tuple_schedule = deepcopy(good)
        tuple_schedule['schedule'] = tuple(tuple_schedule['schedule'])
        class Object(dict):
            pass
        for normalized in (tuple_schedule, Object(good)):
            with self.subTest(normalized_type=type(normalized)):
                r = receipt(g, good, normalized_output=normalized)
                row = self.row(self.score([r]), g)
                self.assertTrue(row['output_error'])
                self.assertFalse(row['success'])
                self.assertTrue(any('JSON' in s for s in row['diagnostics']))

    def test_malformed_normalized_trees_keep_planned_denominators(self):
        g = case('room-gap-5')
        cycle = {}
        cycle['self'] = cycle
        for normalized in (cycle, {'status': float('nan')}, {'status': float('inf')},
                           {1: 'FEASIBLE'}):
            with self.subTest(normalized_type=type(normalized)):
                r = receipt(g, good_output(g), normalized_output=normalized)
                result = self.score([r])
                row = self.row(result, g)
                self.assertTrue(row['output_error'])
                self.assertFalse(row['success'])
                self.assertEqual(result['by_arm']['no_tools']['planned'], 9)
                self.assertEqual(result['by_arm']['no_tools']['attempted'], 1)

    def test_unknown_abstention_and_operational_errors_are_retained(self):
        g = case('room-gap-5')
        for r in (receipt(g, {'status': 'UNKNOWN'}),
                  receipt(g, None, raw_output=None, normalized_output=None, termination='abstained')):
            result = self.score([r])
            self.assertTrue(self.row(result, g)['unknown'])
            self.assertEqual(result['by_arm']['no_tools']['unknown_rate'], {'numerator': 1, 'denominator': 9})
        for flag in ('provider_error', 'tool_error'):
            r = receipt(g, good_output(g), termination=flag, **{flag: True})
            result = self.score([r])
            row = self.row(result, g)
            self.assertFalse(row['success'])
            self.assertFalse(row['completed'])
            self.assertEqual(result['by_arm']['no_tools'][flag + '_rate'], {'numerator': 1, 'denominator': 9})
            self.assertEqual(result['pairs']['incomplete'], 9)

    def test_matched_pair_buckets_and_missingness(self):
        gs = [g for g in GOLD if g['label'] == 'FEASIBLE'][:4]
        receipts = []
        for n, g in enumerate(gs):
            for arm in contract.ARMS:
                success = n == 0 or (n == 1 and arm == 'no_tools') or (n == 2 and arm == 'csp')
                receipts.append(receipt(g, good_output(g) if success else {'status': 'UNKNOWN'}, arm))
        result = self.score(receipts)
        self.assertEqual(result['pairs'], dict(both_success=1, no_tools_only=1,
                         csp_only=1, neither_success=1, incomplete=5))
        self.assertEqual(sum(result['pairs'].values()), result['planned_pairs'])

    def test_recorded_timeout_counts_as_error_not_missing_or_success(self):
        g = case('room-gap-5')
        r = receipt(g, None, raw_output=None, normalized_output=None,
                    normalization_errors=['provider timeout'], provider_error=True,
                    termination='provider_error')
        result = self.score([r])
        summary = result['by_arm']['no_tools']
        self.assertEqual((summary['planned'], summary['attempted'], summary['missing']), (9, 1, 8))
        self.assertEqual(summary['provider_error_rate']['numerator'], 1)
        self.assertEqual(summary['evidence_backed_task_success']['numerator'], 0)
        self.assertIn('provider timeout', self.row(result, g)['diagnostics'])

    def test_excluded_cases_rejected_and_cannot_enter_any_denominator(self):
        excluded = [g for g in GOLD if g['certification'] == 'oracle_only']
        self.assertEqual(len(excluded), 6)
        for g in excluded:
            with self.assertRaises(ValueError):
                self.score([receipt(g, {'status': 'UNKNOWN'})])
        result = self.score([])
        for summary in result['by_arm'].values():
            self.assertEqual(summary['planned'], 9)
            self.assertEqual(summary['negative_certified_success']['denominator'], 2)
        self.assertEqual(len(result['rows']), 18)

    def test_routing_duplicate_and_metadata_errors_reject_entire_result(self):
        g = case('room-gap-5')
        valid = receipt(g, good_output(g))
        bad = [dict(valid, repetition=True), dict(valid, repetition=1),
               dict(valid, arm='other'), dict(valid, provider_error=0),
               dict(valid, termination='timeout'), dict(valid, normalization_errors=None),
               dict(valid, extra='gold'), dict(valid, termination='abstained'),
               dict(valid, termination='provider_error')]
        for r in bad:
            with self.subTest(receipt=r), self.assertRaises(ValueError):
                self.score([r])
        with self.assertRaises(ValueError):
            self.score([valid, valid])

    def test_plan_version_case_use_and_repetition_are_explicit(self):
        for change in ({'contract_version': 'future'}, {'corpus_version': 'old'},
                       {'repetitions': True}, {'repetitions': 0}, {'repetitions': 11},
                       {'arms': ['csp', 'no_tools']}, {'case_use': {}}, {'accepted_protocol': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.score([], dict(plan(), **change))
        p = plan()
        g = next(g for g in GOLD if g['certification'] == 'oracle_only')
        p['case_use'][g['case_id']] = 'eligible'
        with self.assertRaises(ValueError):
            self.score([], p)

    def test_model_boundary_returns_only_identical_controlled_text(self):
        texts = contract.model_inputs(PACKAGE, plan())
        expected = [g for g in GOLD if g['certification'] != 'oracle_only']
        models = [json.loads(s) for s in (PACKAGE / 'tier-a-model.jsonl').read_text().splitlines()]
        self.assertEqual(texts, tuple(m['text'] for m in models if m['case_id'] in {g['case_id'] for g in expected}))
        self.assertEqual(len(texts), 9)
        self.assertTrue(all(type(text) is str for text in texts))
        for text, g in zip(texts, expected):
            self.assertNotIn(g['case_id'], text)
            self.assertNotIn(g['arithmetic'], text)
            self.assertNotIn('oracle_only', text)

    def test_package_preflight_runs_before_any_scoring_and_input_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'package'
            shutil.copytree(PACKAGE, copied)
            path = copied / 'tier-a-gold.jsonl'
            data = path.read_text().replace('"provisional_review"', '"holdout"')
            path.write_text(data)
            manifest_path = copied / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                contract.evaluate(copied, plan(), [])
            with self.assertRaises(ValueError):
                contract.model_inputs(copied, plan())

    def test_rehashed_auditable_package_still_must_match_frozen_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'package'
            shutil.copytree(PACKAGE, copied)
            gold_path = copied / 'tier-a-gold.jsonl'
            rows = [json.loads(s) for s in gold_path.read_text().splitlines()]
            rows[0]['arithmetic'] += ' Changed review text.'
            gold_path.write_text(''.join(json.dumps(g) + '\n' for g in rows))
            coverage_path = copied / 'coverage.json'
            coverage = json.loads(coverage_path.read_text())
            coverage['cases'][0]['arithmetic'] = rows[0]['arithmetic']
            coverage_path.write_text(json.dumps(coverage))
            manifest_path = copied / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            for path in (gold_path, coverage_path):
                manifest['files'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            self.assertEqual(contract.audit(copied)['audit'], 'PASS')
            with self.assertRaisesRegex(ValueError, 'frozen corpus hash mismatch'):
                contract.evaluate(copied, plan(), [])


if __name__ == '__main__':
    unittest.main()
