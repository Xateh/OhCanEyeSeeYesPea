"""Checks that a 100% score means something: tampered answers must fail."""
from copy import deepcopy
import unittest

from surgerybench.common import read_jsonl
from surgerybench.temporal_benchmark import score

RUNS = 'study/results/05-test-v3/runs.jsonl'
GOLD = 'fixtures/arrival-deadline-v1/gold.jsonl'


class TamperingTests(unittest.TestCase):
    def setUp(self):
        self.gold = {g['id']: g for g in read_jsonl(GOLD)}
        self.rows = read_jsonl(RUNS)

    def test_every_recorded_test_answer_really_passes_the_checker(self):
        self.assertTrue(all(score(self.gold[r['case_id']], r['output'])['valid'] for r in self.rows))

    def test_moving_a_surgery_past_its_deadline_fails(self):
        for row in self.rows:
            if self.gold[row['case_id']]['label'] != 'FEASIBLE':
                continue
            tampered = deepcopy(row['output'])
            tampered['schedule'][-1]['start'] += 10000
            self.assertFalse(score(self.gold[row['case_id']], tampered)['valid'])

    def test_claiming_a_solvable_problem_is_impossible_fails(self):
        claim = {'status': 'INFEASIBLE', 'certificate': {'kind': 'pair_order_impossible', 'patients': ['A', 'E']}}
        for gold in self.gold.values():
            if gold['label'] == 'FEASIBLE':
                self.assertFalse(score(gold, claim)['valid'])

    def test_a_certificate_naming_an_unknown_surgery_fails(self):
        claim = {'status': 'INFEASIBLE', 'certificate': {'kind': 'pair_order_impossible', 'patients': ['A', 'Z']}}
        for gold in self.gold.values():
            self.assertFalse(score(gold, claim)['valid'])


if __name__ == '__main__':
    unittest.main()
