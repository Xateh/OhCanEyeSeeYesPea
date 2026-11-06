"""Runner stopping rules, using a fake evaluator so no model is called."""
import unittest

from study.run_hard import execute, hit_usage_limit


def fake(error=None, cost=0.5):
    def evaluator(case, gold):
        errors = [{'stage': 'provider_or_parse', 'error': error}] if error else []
        return {'case_id': case['id'], 'errors': errors, 'responses': [{'usage': {'cost_usd': cost}}]}
    return evaluator


CASES = [{'id': str(i)} for i in range(6)]
GOLD = {c['id']: {} for c in CASES}


class RunnerTests(unittest.TestCase):
    def test_all_cases_run_within_budget(self):
        rows, skipped, _ = execute(CASES, GOLD, 2, 100, fake())
        self.assertEqual((len(rows), skipped), (6, 0))

    def test_spend_limit_stops_new_work(self):
        rows, skipped, _ = execute(CASES, GOLD, 2, 1, fake())
        self.assertEqual((len(rows), skipped), (2, 4))

    def test_usage_limit_stops_new_work(self):
        rows, skipped, _ = execute(CASES, GOLD, 2, 100, fake("RuntimeError: You've hit your 5-hour limit"))
        self.assertEqual((len(rows), skipped), (2, 4))

    def test_ordinary_errors_do_not_stop_the_run(self):
        self.assertFalse(hit_usage_limit({'errors': [{'error': 'TimeoutExpired: x'}]}))


if __name__ == '__main__':
    unittest.main()
