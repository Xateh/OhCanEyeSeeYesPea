"""Paired metrics on hand-built rows with answers worked out by hand."""
import unittest

from study.metrics import failure_kind, mcnemar_exact, normalize_instance, paired_buckets, summarize_arm, translation_status, wilson


def row(case, arm, feasible=None, certified=None, decision=None, status='FEASIBLE', rep=0, **extra):
    base = {'case_id': case, 'arm': arm, 'repetition': rep, 'family': 'fam', 'output': {'status': status},
            'tool_calls': [], 'errors': [], 'parsing_or_provider_error': False, 'tool_error': False,
            'latency_seconds': 2.0, 'token_usage': None, 'responses': [],
            'score': {'feasible_schedule_success': feasible, 'infeasible_certified_success': certified,
                      'infeasible_decision_correct': decision, 'unknown': status == 'UNKNOWN',
                      'output_error': status not in ('FEASIBLE', 'INFEASIBLE', 'UNKNOWN')}}
    return {**base, **extra}


class StatsTests(unittest.TestCase):
    def test_wilson_interval_stays_inside_zero_and_one(self):
        low, high = wilson(8, 8)
        self.assertLess(low, 1)
        self.assertEqual(high, 1)

    def test_wilson_with_no_observations_is_uninformative(self):
        self.assertEqual(wilson(0, 0), (0.0, 1.0))

    def test_mcnemar_exact_matches_hand_calculation(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(5, 0), 0.0625)
        self.assertAlmostEqual(mcnemar_exact(1, 5), 0.21875)


class ClassificationTests(unittest.TestCase):
    def test_kinds(self):
        cases = [(row('a', 'x', feasible=True), 'success'),
                 (row('a', 'x', certified=True, decision=True, status='INFEASIBLE'), 'success'),
                 (row('a', 'x', feasible=False), 'invalid_schedule'),
                 (row('a', 'x', feasible=False, status='INFEASIBLE'), 'wrong_decision'),
                 (row('a', 'x', certified=False, decision=False, status='FEASIBLE'), 'wrong_decision'),
                 (row('a', 'x', certified=False, decision=True, status='INFEASIBLE'), 'invalid_certificate'),
                 (row('a', 'x', feasible=False, status='UNKNOWN'), 'unknown'),
                 (row('a', 'x', feasible=False, status='nonsense'), 'output_error'),
                 (row('a', 'x', feasible=False, status='UNKNOWN', parsing_or_provider_error=True), 'provider_error')]
        for given, expected in cases:
            self.assertEqual(failure_kind(given), expected)


class TranslationTests(unittest.TestCase):
    GOLD = {'patients': [{'id': 'A', 'eligible_rooms': ['r1', 'r0']}, {'id': 'B', 'eligible_rooms': []}],
            'rooms': [], 'surgeons': []}

    def test_normalize_ignores_listing_order_only(self):
        shuffled = {'patients': [{'id': 'B', 'eligible_rooms': []}, {'id': 'A', 'eligible_rooms': ['r0', 'r1']}],
                    'rooms': [], 'surgeons': []}
        self.assertEqual(normalize_instance(shuffled), normalize_instance(self.GOLD))

    def test_status_labels(self):
        call = lambda instance: {'name': 'csp', 'arguments': {'instance': instance}}
        self.assertEqual(translation_status(row('a', 'csp'), self.GOLD), 'no_tool_call')
        self.assertEqual(translation_status(row('a', 'csp', tool_calls=[call(self.GOLD)]), self.GOLD), 'exact')
        self.assertEqual(translation_status(row('a', 'csp', tool_calls=[call({'x': 1})]), self.GOLD), 'mismatch')

    def test_the_last_call_is_the_one_that_counts(self):
        call = lambda instance: {'name': 'csp', 'arguments': {'instance': instance}}
        tried = row('a', 'csp', tool_calls=[call({'x': 1}), call(self.GOLD)])
        self.assertEqual(translation_status(tried, self.GOLD), 'exact')


class SummaryTests(unittest.TestCase):
    def test_denominators_are_split_by_true_label_and_failures_stay_counted(self):
        rows = [row('a', 'x', feasible=True), row('b', 'x', feasible=False, status='UNKNOWN'),
                row('c', 'x', certified=True, decision=True, status='INFEASIBLE'),
                row('d', 'x', certified=False, decision=True, status='INFEASIBLE')]
        summary = summarize_arm(rows)
        self.assertEqual(summary['feasible_success'][:2], [1, 2])
        self.assertEqual(summary['certified_success'][:2], [1, 2])
        self.assertEqual(summary['decision_correct'][:2], [2, 2])
        self.assertEqual(summary['overall_success'][:2], [2, 4])
        self.assertEqual(summary['failure_kinds'], {'invalid_certificate': 1, 'success': 2, 'unknown': 1})

    def test_unknown_token_totals_stay_unknown(self):
        self.assertIsNone(summarize_arm([row('a', 'x', feasible=True)])['tokens_total'])

    def test_cost_sums_every_response(self):
        rows = [row('a', 'x', feasible=True, responses=[{'usage': {'cost_usd': 0.5}}, {'usage': {'cost_usd': 0.25}}])]
        self.assertEqual(summarize_arm(rows)['cost_usd'], 0.75)


class PairTests(unittest.TestCase):
    def test_buckets_pair_by_case_and_repetition(self):
        rows = [row('a', 'no_tools', feasible=True), row('a', 'csp', feasible=True),
                row('b', 'no_tools', feasible=False), row('b', 'csp', feasible=True),
                row('c', 'no_tools', feasible=True), row('c', 'csp', feasible=False),
                row('d', 'no_tools', feasible=False), row('d', 'csp', feasible=False),
                row('a', 'no_tools', feasible=False, rep=1)]
        self.assertEqual(paired_buckets(rows), {'both': 1, 'no_tools_only': 1, 'csp_only': 1, 'neither': 1, 'incomplete': 1})


if __name__ == '__main__':
    unittest.main()
