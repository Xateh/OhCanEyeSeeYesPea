import unittest

from study.ortools_report import paired


def row(case, success, arm=None, repetition=0):
    score = {'feasible_schedule_success': success, 'infeasible_certified_success': None}
    return {'case_id': case, 'repetition': repetition, 'score': score, **({'arm': arm} if arm else {})}


class Pairing(unittest.TestCase):
    def test_pairs_claude_alone_with_claude_plus_ortools_on_the_same_slot(self):
        alone = [row('a', True), row('b', False), row('c', True)]
        with_solver = [row('a', True, 'csp'), row('b', True, 'csp'), row('c', False, 'csp')]
        self.assertEqual(paired(alone, with_solver), {'both': 1, 'no_tools_only': 1, 'csp_only': 1, 'neither': 0, 'incomplete': 0})

    def test_a_missing_partner_is_counted_as_incomplete(self):
        result = paired([row('a', True), row('b', True)], [row('a', True, 'csp')])
        self.assertEqual(result['incomplete'], 1)

    def test_inputs_are_not_changed(self):
        alone = [row('a', True)]
        paired(alone, [row('a', True, 'csp')])
        self.assertNotIn('arm', alone[0])


if __name__ == '__main__':
    unittest.main()
