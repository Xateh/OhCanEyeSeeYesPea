"""In-memory synthetic execution receipts; no provider or tool execution."""
from copy import deepcopy
from pathlib import Path
import unittest

import tier_a_contract as scorer
import tier_a_execution_contract as execution

PACKAGE = Path(__file__).resolve().parents[1] / 'fixtures/tier-a-original-synthetic-v1'
SHARED, OUTPUT = 'Synthetic shared instructions.', 'Synthetic output instructions.'


def fixture():
    import json
    gold = [json.loads(s) for s in (PACKAGE / 'tier-a-gold.jsonl').read_text().splitlines()]
    plan = dict(contract_version=scorer.CONTRACT, corpus_version=scorer.CORPUS,
                repetitions=1, arms=list(scorer.ARMS), case_use={g['case_id']:
                'validation_only' if g['certification'] == 'oracle_only' else 'eligible' for g in gold})
    manifest = dict(version=execution.VERSION, status='proposal_only', run_id='synthetic-001',
                    scoring_plan=plan, corpus_hashes=dict(scorer.HASHES),
                    provider_revision='synthetic-provider-v1', model_revision='synthetic-model-v1',
                    **execution.bindings(SHARED, OUTPUT), limits=dict(tokens_per_attempt=100,
                    wall_seconds_per_attempt=5, spending_ceiling_usd='0.01', max_csp_calls=4))
    rows = []
    for g in gold:
        if g['certification'] == 'oracle_only':
            continue
        out = (dict(status='FEASIBLE', schedule=g['evidence']['witness']) if g['label'] == 'FEASIBLE'
               else dict(status='INFEASIBLE', certificate=g['evidence']['certificate']))
        for arm in scorer.ARMS:
            scoring = dict(case_id=g['case_id'], repetition=0, arm=arm,
                           raw_output=json.dumps(out), normalized_output=deepcopy(out),
                           normalization_errors=[], provider_error=False, tool_error=False, termination='final')
            rows.append(dict(attempt_id=f'attempt-{len(rows):02}', run_id=manifest['run_id'],
                        provider_revision=manifest['provider_revision'], model_revision=manifest['model_revision'],
                        **execution.bindings(SHARED, OUTPUT), scoring_receipt=scoring,
                        elapsed_seconds=0.01, usage=dict(input_tokens=2, output_tokens=3),
                        usage_unknown_reason=None, spend_usd='0.0001', spend_unknown_reason=None,
                        termination_cause='completed', tool_calls=[], tool_count=0))
    return manifest, rows


class ExecutionContractTests(unittest.TestCase):
    def validate(self, manifest, rows):
        return execution.validate(PACKAGE, manifest, rows, SHARED, OUTPUT)

    def test_complete_fixture_is_offline_proposal_not_authorization(self):
        m, rows = fixture()
        result = self.validate(m, rows)
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['planned_arm_attempts'], 18)
        self.assertTrue(result['budget_evidence_complete'])
        self.assertEqual(result['execution_receipts'], rows)
        self.assertEqual(result['manifest'], m)
        self.assertEqual(result['scoring']['by_arm']['csp']['evidence_backed_task_success'],
                         {'numerator': 9, 'denominator': 9})

    def test_missing_or_invalid_budget_fails_closed(self):
        for key in ('tokens_per_attempt', 'wall_seconds_per_attempt', 'spending_ceiling_usd'):
            for value in (None, 0, True, ''):
                m, rows = fixture()
                m['limits'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.validate(m, rows)
        m, rows = fixture()
        del m['limits']['tokens_per_attempt']
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_revision_prompt_and_schema_drift_rejected(self):
        for key in ('provider_revision', 'model_revision', 'consumer_sha256',
                    'shared_prompt_sha256', 'output_prompt_sha256', 'tool_schema_sha256', 'tool_revision'):
            m, rows = fixture()
            rows[0][key] = 'drift'
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(m, rows)
        m, rows = fixture()
        m['consumer_sha256'] = 'drift'
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_missing_revisions_prompt_and_corpus_pins_fail_closed(self):
        for key in ('provider_revision', 'model_revision'):
            for value in (None, '', 'unknown', 'TBD'):
                m, rows = fixture()
                m[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.validate(m, rows)
        m, rows = fixture()
        m['corpus_hashes']['manifest.json'] = 'drift'
        with self.assertRaises(ValueError):
            self.validate(m, rows)
        m, rows = fixture()
        with self.assertRaises(ValueError):
            execution.validate(PACKAGE, m, rows, SHARED + 'drift', OUTPUT)

    def test_termination_and_boolean_token_counts_rejected(self):
        m, rows = fixture()
        rows[0]['termination_cause'] = 'provider_timeout'
        with self.assertRaises(ValueError):
            self.validate(m, rows)
        m, rows = fixture()
        rows[0]['usage']['input_tokens'] = True
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_forbidden_tool_fifth_call_and_count_mismatch_rejected(self):
        for arm, names in (('no_tools', ['csp']), ('csp', ['repair']), ('csp', ['csp'] * 5)):
            m, rows = fixture()
            row = next(r for r in rows if r['scoring_receipt']['arm'] == arm)
            row['tool_calls'] = [dict(name=n, schema_sha256=m['tool_schema_sha256']) for n in names]
            row['tool_count'] = len(names)
            with self.subTest(arm=arm, names=names), self.assertRaises(ValueError):
                self.validate(m, rows)
        m, rows = fixture()
        rows[1]['tool_count'] = 1
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_duplicate_identity_or_scoring_slot_rejected(self):
        m, rows = fixture()
        rows[1]['attempt_id'] = rows[0]['attempt_id']
        with self.assertRaises(ValueError):
            self.validate(m, rows)
        m, rows = fixture()
        rows[1]['scoring_receipt'] = deepcopy(rows[0]['scoring_receipt'])
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_raw_disagreement_retains_scoring_error_and_planned_denominator(self):
        m, rows = fixture()
        rows[0]['normalized_output'] = None  # wrong extension keys fail closed
        with self.assertRaises(ValueError):
            self.validate(m, rows)
        del rows[0]['normalized_output']
        rows[0]['scoring_receipt']['normalized_output'] = {'status': 'UNKNOWN'}
        result = self.validate(m, rows)
        self.assertTrue(result['scoring']['rows'][0]['output_error'])
        self.assertEqual(result['scoring']['by_arm']['no_tools']['planned'], 9)

    def test_unknown_usage_spend_and_missing_attempts_never_imply_budget_verification(self):
        m, rows = fixture()
        rows[0].update(usage=None, usage_unknown_reason='not reported',
                       spend_usd=None, spend_unknown_reason='not reported')
        result = self.validate(m, rows[:-1])
        self.assertFalse(result['budget_evidence_complete'])
        self.assertEqual(result['scoring']['by_arm']['csp']['missing'], 1)
        rows[0]['usage_unknown_reason'] = None
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_token_time_spending_overruns_and_fourth_call_boundary(self):
        for field, value, violation in (('elapsed_seconds', 6, 'wall_clock_limit'),
                                         ('spend_usd', '1', 'batch_spending_ceiling'),
                                         ('usage', {'input_tokens': 101, 'output_tokens': 3}, 'token_limit')):
            m, rows = fixture()
            rows[0][field] = value
            saved = deepcopy(rows)
            with self.subTest(field=field):
                result = self.validate(m, rows)
                row = result['scoring']['rows'][0]
                self.assertEqual(result['execution_receipts'], saved)
                self.assertEqual(rows, saved)
                self.assertTrue(row['budget_error'])
                self.assertIn(violation, row['budget_violations'])
                self.assertFalse(row['success'])
                self.assertFalse(result['budget_compliant'])
                summary = result['scoring']['by_arm']['no_tools']
                self.assertEqual((summary['planned'], summary['attempted'], summary['missing']), (9, 9, 0))
                self.assertEqual(summary['evidence_backed_task_success']['denominator'], 9)
                self.assertEqual(summary['budget_error_rate']['denominator'], 9)
                self.assertEqual(summary['evidence_backed_task_success']['numerator'],
                                 0 if field == 'spend_usd' else 8)
                if field == 'spend_usd':
                    self.assertTrue(all(r['budget_error'] for r in result['scoring']['rows']))
                    self.assertEqual(result['scoring']['pairs']['neither_success'], 9)
        m, rows = fixture()
        rows[1]['tool_calls'] = [dict(name='csp', schema_sha256=m['tool_schema_sha256']) for _ in range(4)]
        rows[1]['tool_count'] = 4
        self.assertFalse(self.validate(m, rows)['execution_authorized'])

    def test_overrun_cannot_retain_certified_negative_success(self):
        m, rows = fixture()
        attempt = next(r for r in rows if r['scoring_receipt']['case_id'].startswith('optional-forced-')
                       and r['scoring_receipt']['arm'] == 'no_tools')
        attempt['elapsed_seconds'] = 6
        result = self.validate(m, rows)
        row = next(r for r in result['scoring']['rows'] if r['case_id'] == attempt['scoring_receipt']['case_id']
                   and r['arm'] == 'no_tools')
        self.assertTrue(row['unadjusted_scorer_success'])
        self.assertTrue(row['decision_agreement'])
        self.assertFalse(row['certified_success'])
        self.assertEqual(result['scoring']['by_arm']['no_tools']['negative_certified_success'],
                         {'numerator': 1, 'denominator': 2})

    def test_correctly_labeled_timeout_is_retained_as_failed_attempt(self):
        m, rows = fixture()
        rows[0].update(termination_cause='provider_timeout', elapsed_seconds=6)
        rows[0]['scoring_receipt'].update(termination='provider_error', provider_error=True,
            raw_output=None, normalized_output=None, normalization_errors=['provider timeout'])
        result = self.validate(m, rows)
        row = result['scoring']['rows'][0]
        self.assertTrue(row['provider_error'])
        self.assertTrue(row['budget_error'])
        self.assertFalse(row['completed'])
        self.assertFalse(row['success'])
        self.assertEqual(result['scoring']['pairs']['incomplete'], 1)
        summary = result['scoring']['by_arm']['no_tools']
        self.assertEqual((summary['planned'], summary['attempted'], summary['missing']), (9, 9, 0))
        self.assertEqual(summary['provider_error_rate'], {'numerator': 1, 'denominator': 9})

    def test_malformed_elapsed_and_negative_usage_still_reject_structure(self):
        for value in (-1, True, float('nan'), None):
            m, rows = fixture()
            rows[0]['elapsed_seconds'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(m, rows)
        m, rows = fixture()
        rows[0]['usage']['input_tokens'] = -1
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_huge_integer_elapsed_is_retained_as_overrun(self):
        m, rows = fixture()
        rows[0]['elapsed_seconds'] = 10 ** 400
        result = self.validate(m, rows)
        row = result['scoring']['rows'][0]
        self.assertTrue(row['budget_error'])
        self.assertFalse(row['success'])
        self.assertIn('wall_clock_limit', row['budget_violations'])
        self.assertEqual(result['scoring']['by_arm']['no_tools']['attempted'], 9)

    def test_execution_module_revision_is_pinned(self):
        import hashlib
        m, rows = fixture()
        self.assertIn('execution_contract_sha256', m)
        self.assertEqual(m['execution_contract_sha256'],
                         hashlib.sha256(Path(execution.__file__).read_bytes()).hexdigest())
        rows[0]['execution_contract_sha256'] = 'drift'
        with self.assertRaises(ValueError):
            self.validate(m, rows)
        m, rows = fixture()
        m['execution_contract_sha256'] = 'drift'
        with self.assertRaises(ValueError):
            self.validate(m, rows)

    def test_unadjusted_success_keeps_original_operational_gating(self):
        m, rows = fixture()
        rows[0]['scoring_receipt']['provider_error'] = True
        result = self.validate(m, rows)
        row = result['scoring']['rows'][0]
        self.assertFalse(row['output_error'])  # checker-valid output is still not operational success
        self.assertFalse(row['unadjusted_scorer_success'])
        self.assertFalse(row['success'])

    def test_budget_adjusted_family_conservation_with_mixed_missingness(self):
        m, rows = fixture()
        rows[0]['elapsed_seconds'] = 6
        rows[1]['usage'] = {'input_tokens': 101, 'output_tokens': 3}
        rows[2].update(usage=None, usage_unknown_reason='not reported')
        rows[4].update(termination_cause='provider_timeout', elapsed_seconds=6)
        rows[4]['scoring_receipt'].update(termination='provider_error', provider_error=True,
            raw_output=None, normalized_output=None, normalization_errors=['provider timeout'])
        result = self.validate(m, rows[:-1])
        self.assertFalse(result['budget_compliant'])
        self.assertFalse(result['budget_evidence_complete'])
        scored = result['scoring']
        self.assertEqual(scored['pairs'], dict(both_success=6, no_tools_only=0,
                         csp_only=0, neither_success=1, incomplete=2))
        self.assertEqual(scored['planned_pairs'], 9)
        for arm, total in scored['by_arm'].items():
            families = [group[arm] for group in scored['by_family'].values()]
            for key in ('planned', 'attempted', 'completed', 'missing'):
                self.assertEqual(sum(group[key] for group in families), total[key])
            for metric, value in total.items():
                if type(value) is dict:
                    for key in ('numerator', 'denominator'):
                        self.assertEqual(sum(group[metric][key] for group in families), value[key])
        self.assertEqual(scored['by_arm']['csp']['missing'], 1)
        self.assertEqual(scored['by_arm']['no_tools']['budget_error_rate'], {'numerator': 2, 'denominator': 9})

    def test_nonfinite_and_exponent_money_are_rejected(self):
        for value in ('NaN', 'Infinity', '1e999999999', '-1', '0.000000001'):
            m, rows = fixture()
            m['limits']['spending_ceiling_usd'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(m, rows)

    def test_spending_subtotal_is_independent_of_caller_decimal_precision(self):
        from decimal import localcontext
        m, rows = fixture()
        for row in rows:
            row['spend_usd'] = '0.00012345'
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(self.validate(m, rows)['known_spend_usd'], '0.00222210')
