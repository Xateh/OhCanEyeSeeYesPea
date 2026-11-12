import unittest

from surgerybench.common import read_jsonl
from surgerybench.temporal_benchmark import score
from surgerybench.temporal_check import check_schedule, schema_errors

try:
    from study.ortools_solver import ORToolsAdapter, solve
except ImportError:  # OR-Tools is optional, like matplotlib
    ORToolsAdapter = None


def instance(durations, gap=0, budget=1440, window=(0, 1440), days=1, mandatory=None):
    mandatory = mandatory or [True] * len(durations)
    resource = lambda rid: {'id': rid, 'gap': gap, 'budgets': [budget] * days, 'calendar': [[list(window)]] * days}
    return {'schema_version': '1.1', 'days': days, 'day_minutes': 1440, 'surgeons': [resource('s0')], 'rooms': [resource('r0')],
            'patients': [{'id': f'P{n}', 'mandatory': must, 'surgeon': 's0', 'duration': length, 'release': 0, 'due': days * 1440,
                          'eligible_rooms': ['r0'], 'priority': 1, 'emergency': False}
                         for n, (length, must) in enumerate(zip(durations, mandatory))]}


@unittest.skipIf(ORToolsAdapter is None, 'OR-Tools is not installed')
class ORToolsSolver(unittest.TestCase):
    def test_every_pilot_gold_problem_is_solved_with_checked_evidence(self):
        for gold in read_jsonl('fixtures/arrival-deadline-v1/gold.jsonl'):
            result = solve(gold['instance'])
            self.assertTrue(score(gold, result)['valid'], gold['id'])

    def test_required_gap_is_respected(self):
        tight = instance([10, 10], gap=10, window=(0, 30))
        result = solve(tight)
        self.assertEqual(result['status'], 'FEASIBLE')
        self.assertEqual(check_schedule(tight, result['schedule']), [])

    def test_impossible_gap_without_a_supported_certificate_stays_unknown(self):
        result = solve(instance([10, 10], gap=11, window=(0, 30)))
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(result['proven_infeasible'])

    def test_daily_budget_moves_work_to_another_day(self):
        two_days = instance([10, 10], budget=15, days=2)
        result = solve(two_days)
        self.assertEqual(check_schedule(two_days, result['schedule']), [])
        self.assertEqual(sorted(row['day'] for row in result['schedule']), [0, 1])

    def test_optional_surgery_that_cannot_fit_is_left_out(self):
        result = solve(instance([10, 50], window=(0, 30), mandatory=[True, False]))
        self.assertEqual([row['patient'] for row in result['schedule']], ['P0'])

    def test_malformed_instance_is_rejected(self):
        broken = {**instance([10]), 'schema_version': '1.0'}
        self.assertTrue(schema_errors(broken))
        with self.assertRaises(ValueError):
            solve(broken)

    def test_adapter_accepts_only_a_translated_instance(self):
        with self.assertRaises(ValueError):
            ORToolsAdapter().invoke({'instance': instance([10]), 'gold': True})

    def test_adapter_offers_the_same_tool_as_the_original_solver(self):
        from surgerybench.temporal_csp import CSPAdapter
        self.assertEqual(ORToolsAdapter.tool_definition, CSPAdapter.tool_definition)


if __name__ == '__main__':
    unittest.main()
