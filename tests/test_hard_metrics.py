"""Outcome labels and per-size totals, worked out by hand."""
import unittest

from study.hard_metrics import outcome, summarize_size, violation_kind


def run(label, status, valid, size=5, error=None, latency=2.0):
    errors = [{'stage': 'provider_or_parse', 'error': error}] if error else []
    return {'label': label, 'size': size, 'output': {'status': status}, 'errors': errors, 'latency_seconds': latency,
            'parsing_or_provider_error': bool(error), 'token_usage': {'input_tokens': 10, 'output_tokens': 5},
            'score': {'valid': valid, 'violations': [], 'unknown': status == 'UNKNOWN',
                      'output_error': status not in ('FEASIBLE', 'INFEASIBLE', 'UNKNOWN')}}


class OutcomeTests(unittest.TestCase):
    def test_each_outcome(self):
        cases = [(run('FEASIBLE', 'FEASIBLE', True), 'correct'), (run('INFEASIBLE', 'INFEASIBLE', True), 'correct'),
                 (run('FEASIBLE', 'FEASIBLE', False), 'broken_schedule'),
                 (run('INFEASIBLE', 'INFEASIBLE', False), 'bad_proof'),
                 (run('FEASIBLE', 'INFEASIBLE', False), 'false_alarm'),
                 (run('INFEASIBLE', 'FEASIBLE', False), 'missed_conflict'),
                 (run('FEASIBLE', 'UNKNOWN', False), 'gave_up'),
                 (run('FEASIBLE', 'UNKNOWN', False, error='TimeoutExpired: x'), 'timed_out'),
                 (run('FEASIBLE', 'UNKNOWN', False, error='JSONDecodeError: x'), 'unreadable_reply'),
                 (run('FEASIBLE', 'UNKNOWN', False, error='RuntimeError: x'), 'system_error')]
        for given, expected in cases:
            self.assertEqual(outcome(given), expected)

    def test_violations_drop_the_surgery_id(self):
        self.assertEqual(violation_kind('P123: completes after deadline'), 'completes after deadline')
        self.assertEqual(violation_kind('surgeons/s00/day1: clash or required gap'), 'clash or required gap')
        self.assertEqual(violation_kind('missing mandatory patient P1'), 'missing mandatory patient')


class SummaryTests(unittest.TestCase):
    def test_counts_split_by_true_answer_and_keep_failures(self):
        rows = [run('FEASIBLE', 'FEASIBLE', True), run('FEASIBLE', 'UNKNOWN', False),
                run('INFEASIBLE', 'INFEASIBLE', False), run('INFEASIBLE', 'FEASIBLE', False)]
        summary = summarize_size(rows)
        self.assertEqual(summary['fully_correct'][:2], [1, 4])
        self.assertEqual(summary['schedule_success'][:2], [1, 2])
        self.assertEqual(summary['proof_success'][:2], [0, 2])
        self.assertEqual(summary['decision_correct'][:2], [2, 4])
        self.assertEqual(summary['outcomes']['gave_up'], 1)

    def test_a_system_error_is_not_counted_as_a_wrong_decision(self):
        rows = [run('FEASIBLE', 'FEASIBLE', True), run('FEASIBLE', 'UNKNOWN', False, error='RuntimeError: x')]
        summary = summarize_size(rows)
        self.assertEqual(summary['system_failures'], 1)
        self.assertEqual(summary['fully_correct'][:2], [1, 1])


if __name__ == '__main__':
    unittest.main()
