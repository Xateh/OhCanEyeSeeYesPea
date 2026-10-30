"""The harder dataset must be correct by construction and free of positional giveaways."""
import unittest

from surgerybench.temporal_check import check_certificate, check_schedule, schema_errors
from study.hard_dataset import DURATIONS, FEASIBLE, INFEASIBLE, build_pair, neutral_text


class PairTests(unittest.TestCase):
    PAIRS = [build_pair(size, index) for size in (5, 10, 20, 40, 80) for index in range(3)]

    def test_same_seed_gives_identical_problems(self):
        self.assertEqual(build_pair(10, 1), build_pair(10, 1))

    def test_different_seeds_give_different_problems(self):
        self.assertNotEqual(build_pair(10, 1)[0]['instance'], build_pair(10, 2)[0]['instance'])

    def test_instances_are_valid_and_have_the_requested_size(self):
        for feasible, infeasible in self.PAIRS:
            for record in (feasible, infeasible):
                self.assertEqual(schema_errors(record['instance']), [])
                self.assertEqual(len(record['instance']['patients']), record['size'])

    def test_planted_schedule_passes_the_independent_checker(self):
        for feasible, _ in self.PAIRS:
            self.assertEqual(feasible['label'], FEASIBLE)
            self.assertEqual(check_schedule(feasible['instance'], feasible['evidence']['witness']), [])

    def test_planted_conflict_passes_the_independent_checker(self):
        for _, infeasible in self.PAIRS:
            self.assertEqual(infeasible['label'], INFEASIBLE)
            self.assertTrue(check_certificate(infeasible['instance'], infeasible['evidence']['certificate']))

    def test_the_certificate_cannot_prove_the_solvable_twin_impossible(self):
        for feasible, infeasible in self.PAIRS:
            self.assertFalse(check_certificate(feasible['instance'], infeasible['evidence']['certificate']))

    def test_twins_differ_in_exactly_one_deadline(self):
        for feasible, infeasible in self.PAIRS:
            changed = [(a['id'], k) for a, b in zip(feasible['instance']['patients'], infeasible['instance']['patients'])
                       for k in a if a[k] != b[k]]
            self.assertEqual(len(changed), 1)
            self.assertEqual(changed[0][1], 'due')

    def test_conflicting_pairs_vary_between_problems(self):
        pairs = {tuple(i['evidence']['certificate']['patients']) for _, i in self.PAIRS}
        self.assertGreater(len(pairs), 10)

    def test_durations_come_only_from_the_published_table(self):
        for feasible, _ in self.PAIRS:
            self.assertLessEqual({p['duration'] for p in feasible['instance']['patients']}, set(DURATIONS))

    def test_harder_rules_are_actually_used(self):
        for feasible, _ in self.PAIRS:
            instance = feasible['instance']
            self.assertTrue(any(r['gap'] for k in ('rooms', 'surgeons') for r in instance[k]))
            self.assertTrue(any(len(day) > 1 for r in instance['rooms'] for day in r['calendar']))


class TextTests(unittest.TestCase):
    def test_text_no_longer_contains_the_answer_pair_example(self):
        text = neutral_text(build_pair(5, 0)[0]['instance'])
        self.assertNotIn('["A","E"]', text)
        self.assertIn('FIRST_ID', text)

    def test_text_never_contains_the_gold_label(self):
        for record in build_pair(5, 0):
            self.assertNotIn('witness', record['text'])


if __name__ == '__main__':
    unittest.main()
