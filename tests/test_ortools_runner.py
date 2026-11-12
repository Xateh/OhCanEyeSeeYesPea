import json
import tempfile
import unittest
from pathlib import Path

from study.run_ortools import COHORTS, execute, planned_slots


def fake_row(case, gold, repetition, cost=0.01, error=None):
    return {'case_id': case['id'], 'repetition': repetition, 'errors': [{'stage': 'provider_or_parse', 'error': error}] if error else [],
            'responses': [{'usage': {'cost_usd': cost}}], 'parsing_or_provider_error': bool(error)}


class Planning(unittest.TestCase):
    def test_pilot_test_split_mirrors_the_three_recorded_repetitions(self):
        slots = planned_slots('pilot-test')
        self.assertEqual(len(slots), 24)
        self.assertEqual({rep for _, rep in slots}, {0, 1, 2})

    def test_every_cohort_matches_the_recorded_claude_alone_runs(self):
        sizes = {name: len(planned_slots(name)) for name in COHORTS}
        self.assertEqual(sizes, {'pilot-train': 32, 'pilot-validation': 8, 'pilot-test': 24,
                                 'hard-n05': 20, 'hard-n10': 20, 'hard-n20': 20, 'hard-n40': 20, 'hard-n80': 20})


class Execution(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp()) / 'out'

    def lines(self):
        return [json.loads(line) for line in (self.folder / 'runs.jsonl').read_text().splitlines()]

    def test_rows_are_saved_and_a_second_call_only_runs_missing_slots(self):
        slots = planned_slots('pilot-validation')
        execute('pilot-validation', self.folder, budget_usd=1, workers=2, evaluator=fake_row, limit=3)
        execute('pilot-validation', self.folder, budget_usd=1, workers=2, evaluator=fake_row)
        self.assertEqual(sorted((r['case_id'], r['repetition']) for r in self.lines()), sorted((c['id'], rep) for c, rep in slots))

    def test_usage_limit_stops_new_work_but_keeps_the_failed_attempt(self):
        hits = lambda case, gold, rep: fake_row(case, gold, rep, cost=None, error="RuntimeError: You've hit your limit")
        execute('pilot-validation', self.folder, budget_usd=1, workers=2, evaluator=hits)
        self.assertEqual(len(self.lines()), 2)

    def test_spend_limit_stops_new_work(self):
        execute('pilot-validation', self.folder, budget_usd=0.015, workers=1, evaluator=fake_row)
        self.assertEqual(len(self.lines()), 2)


if __name__ == '__main__':
    unittest.main()
