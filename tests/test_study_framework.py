import unittest

from study.framework import csp_on_gold, failure_split, require_planned, rescore, summarize
from surgerybench.common import read_jsonl
from surgerybench.temporal_benchmark import score

GOLD_ROWS = read_jsonl('fixtures/arrival-deadline-v1/gold.jsonl')
FEASIBLE_GOLD = next(g for g in GOLD_ROWS if g['label'] == 'FEASIBLE')
INFEASIBLE_GOLD = next(g for g in GOLD_ROWS if g['label'] == 'INFEASIBLE')
GOOD = {'status': 'FEASIBLE', 'schedule': FEASIBLE_GOLD['evidence']['witness']}
BROKEN = {'status': 'FEASIBLE', 'schedule': []}
UNKNOWN = {'status': 'UNKNOWN'}


def row(gold, output, error=None, usage=(100, 10), seconds=2.0, **extra):
    return {'case_id': gold['id'], 'output': output, 'score': score(gold, output), 'label': gold['label'],
            'errors': [{'stage': 'provider_or_parse', 'error': error}] if error else [],
            'parsing_or_provider_error': bool(error), 'tool_error': False, 'latency_seconds': seconds,
            'token_usage': {'input_tokens': usage[0], 'output_tokens': usage[1]} if usage else None,
            'responses': [], 'tool_calls': [], 'tool_call_count': 0, **extra}


class EvidenceBackedSuccess(unittest.TestCase):
    def test_timeout_stays_in_the_denominator(self):
        rows = [row(FEASIBLE_GOLD, GOOD), row(FEASIBLE_GOLD, UNKNOWN, 'TimeoutExpired: slow', None, 300.0)]
        result = summarize(rows)
        self.assertEqual(result['evidence_backed_success'], [1, 2])
        self.assertEqual(result['timeouts'], [1, 2])
        self.assertEqual(result['unknown'], [1, 2])

    def test_provider_error_stays_in_the_denominator(self):
        result = summarize([row(FEASIBLE_GOLD, UNKNOWN, 'RuntimeError: hit your limit', None)])
        self.assertEqual(result['evidence_backed_success'], [0, 1])
        self.assertEqual(result['provider_errors'], [1, 1])

    def test_broken_schedule_is_not_a_success_even_when_the_status_agrees(self):
        result = summarize([row(FEASIBLE_GOLD, BROKEN)])
        self.assertEqual(result['evidence_backed_success'], [0, 1])
        self.assertEqual(result['status_agreement'], [1, 1])
        self.assertEqual(result['feasible_claim_precision'], [0, 1])

    def test_unproved_infeasible_counts_as_decision_but_not_certified(self):
        result = summarize([row(INFEASIBLE_GOLD, {'status': 'INFEASIBLE'})])
        self.assertEqual(result['infeasible_decision'], [1, 1])
        self.assertEqual(result['certified_infeasible_success'], [0, 1])

    def test_bad_output_counts_as_a_parse_error(self):
        result = summarize([row(FEASIBLE_GOLD, UNKNOWN, 'JSONDecodeError: bad')])
        self.assertEqual(result['parse_errors'], [1, 1])

    def test_f1_treats_only_evidence_backed_claims_as_true_positives(self):
        rows = [row(FEASIBLE_GOLD, GOOD), row(FEASIBLE_GOLD, BROKEN), row(FEASIBLE_GOLD, UNKNOWN)]
        self.assertAlmostEqual(summarize(rows)['f1'], 0.4)


class Cost(unittest.TestCase):
    def test_runs_without_reported_tokens_are_counted_separately(self):
        result = summarize([row(FEASIBLE_GOLD, GOOD), row(FEASIBLE_GOLD, UNKNOWN, 'TimeoutExpired: x', None)])
        self.assertEqual(result['runs_with_tokens'], 1)
        self.assertEqual(result['mean_tokens'], 110)


class Integrity(unittest.TestCase):
    def test_rescore_rejects_a_stored_score_that_disagrees_with_gold(self):
        stored = {**row(FEASIBLE_GOLD, BROKEN), 'score': score(FEASIBLE_GOLD, GOOD)}
        with self.assertRaisesRegex(ValueError, FEASIBLE_GOLD['id']):
            rescore([stored], {FEASIBLE_GOLD['id']: FEASIBLE_GOLD})

    def test_rescore_adds_the_label_without_changing_the_input(self):
        stored = {key: value for key, value in row(FEASIBLE_GOLD, GOOD).items() if key != 'label'}
        result = rescore([stored], {FEASIBLE_GOLD['id']: FEASIBLE_GOLD})
        self.assertEqual(result[0]['label'], 'FEASIBLE')
        self.assertNotIn('label', stored)

    def test_missing_runs_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'planned 2, found 1'):
            require_planned([row(FEASIBLE_GOLD, GOOD)], 2)


class FailureSplit(unittest.TestCase):
    gold = {FEASIBLE_GOLD['id']: FEASIBLE_GOLD}

    def test_wrong_translation_is_blamed_on_translation(self):
        changed = {**FEASIBLE_GOLD['instance'], 'days': 99}
        call = {'arguments': {'instance': changed}, 'result': {'status': 'FEASIBLE'}}
        failed = row(FEASIBLE_GOLD, BROKEN, tool_calls=[call], tool_call_count=1)
        self.assertEqual(failure_split([failed], self.gold)['translation_error'], 1)

    def test_solver_unknown_on_a_faithful_translation_is_blamed_on_the_solver(self):
        call = {'arguments': {'instance': FEASIBLE_GOLD['instance']}, 'result': {'status': 'UNKNOWN'}}
        failed = row(FEASIBLE_GOLD, UNKNOWN, tool_calls=[call], tool_call_count=1)
        self.assertEqual(failure_split([failed], self.gold)['solver_unknown'], 1)

    def test_broken_reply_is_blamed_on_bad_output(self):
        failed = row(FEASIBLE_GOLD, UNKNOWN, 'ValueError: bad reply')
        self.assertEqual(failure_split([failed], self.gold)['bad_output'], 1)

    def test_successful_runs_are_not_failures(self):
        self.assertEqual(sum(failure_split([row(FEASIBLE_GOLD, GOOD)], self.gold).values()), 0)


class CspOnGold(unittest.TestCase):
    def test_solves_gold_with_zero_tokens(self):
        result = summarize(csp_on_gold([FEASIBLE_GOLD]))
        self.assertEqual(result['evidence_backed_success'], [1, 1])
        self.assertEqual(result['mean_tokens'], 0)


if __name__ == '__main__':
    unittest.main()
