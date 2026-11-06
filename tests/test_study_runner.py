"""Runner flow with the offline mock, so no model is called."""
import tempfile
import unittest

from surgerybench.temporal_benchmark import MockProvider
from study.run_iteration import execute, select_cases


class RunnerTests(unittest.TestCase):
    def test_selecting_a_split_never_returns_another_split(self):
        cases, gold = select_cases('test', None)
        self.assertEqual(len(cases), 8)
        self.assertEqual({gold[c['id']]['split'] for c in cases}, {'test'})

    def test_every_case_produces_a_pair_for_each_repetition(self):
        cases, gold = select_cases('test', 2)
        work = [(c, rep) for rep in range(2) for c in cases]
        with tempfile.TemporaryDirectory() as scratch:
            rows, skipped, _ = execute(work, gold, MockProvider, scratch, 2, budget_usd=1)
        self.assertEqual((len(rows), skipped), (8, 0))
        self.assertEqual({r['repetition'] for r in rows}, {0, 1})
        self.assertEqual({r['arm'] for r in rows}, {'no_tools', 'csp'})

    def test_a_used_up_budget_skips_work_and_reports_it(self):
        cases, gold = select_cases('test', 2)
        with tempfile.TemporaryDirectory() as scratch:
            rows, skipped, _ = execute([(c, 0) for c in cases], gold, MockProvider, scratch, 1, budget_usd=0)
        self.assertEqual((rows, skipped), ([], 2))


if __name__ == '__main__':
    unittest.main()
