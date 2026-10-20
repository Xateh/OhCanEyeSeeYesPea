"""Eleven hand-authored analytical anchors; no corpus generation or gold inference."""
from copy import deepcopy
from math import prod
import unittest

from surgerybench.temporal_check import schema_errors, check_schedule, check_certificate
from surgerybench.temporal_csp import solve
from surgerybench.temporal_oracle import enumerate_schedules
from surgerybench.temporal_text import render, parse


def resource(name, end, gap=0, budget=10, windows=None):
    return {'id': name, 'gap': gap, 'budgets': [budget],
            'calendar': [windows if windows is not None else [[0, end]]]}


def job(name, surgeon, duration, release, due, room='r0', mandatory=True):
    return {'id': name, 'mandatory': mandatory, 'surgeon': surgeon,
            'duration': duration, 'release': release, 'due': due,
            'eligible_rooms': [room], 'priority': 1, 'emergency': False}


def instance(jobs, rooms, surgeons):
    return {'schema_version': '1.1', 'days': 1, 'day_minutes': 1440,
            'patients': jobs, 'rooms': rooms, 'surgeons': surgeons}


def row(patient, start, room='r0'):
    return {'patient': patient, 'day': 0, 'start': start, 'room': room}


def gap_case(end=5):
    return instance([job('A', 's0', 2, 0, end), job('B', 's1', 2, 0, end)],
                    [resource('r0', end, gap=1)],
                    [resource('s0', end), resource('s1', end)])


class TierASemanticsTests(unittest.TestCase):
    def compare(self, i, expected, witnesses=(), certified=False, limit=10000):
        """Compare independent interfaces against the caller's analytical label."""
        self.assertEqual(schema_errors(i), [])
        self.assertEqual(parse(render(i)), i)
        self.assertEqual(i['days'], 1)
        self.assertLessEqual(len(i['patients']), 2)
        self.assertLessEqual(len(i['rooms']), 2)
        self.assertLessEqual(len(i['surgeons']), 2)
        self.assertTrue(all(0 <= p['release'] <= p['due'] <= 10
                            for p in i['patients']))
        # Upper bound ignores calendars/budgets, so does not duplicate the oracle.
        combinations = prod(max(0, p['due'] - p['release'] - p['duration'] + 1)
                            * len(p['eligible_rooms'])
                            for p in i['patients'] if p['mandatory'])
        self.assertLessEqual(combinations, 25)
        self.assertEqual(limit, 10000)
        oracle = enumerate_schedules(i, limit=limit)
        self.assertTrue(oracle.get('complete'), oracle)
        self.assertEqual(oracle['status'], expected, oracle)
        self.assertLessEqual(oracle['examined'], combinations)
        self.assertLessEqual(len(oracle['solutions']), 25)
        for witness in list(witnesses) + oracle['solutions']:
            self.assertEqual(check_schedule(i, witness), [])
        result = solve(i, max_nodes=10000, seconds=1)
        if expected == 'FEASIBLE':
            self.assertEqual(result['status'], 'FEASIBLE', result)
            self.assertEqual(check_schedule(i, result['schedule']), [])
        elif certified:
            self.assertEqual(result['status'], 'INFEASIBLE', result)
            self.assertTrue(check_certificate(i, result['certificate']))
        else:
            self.assertEqual(result['status'], 'UNKNOWN', result)
            self.assertIs(result.get('search_exhausted'), True)
            self.assertEqual(result['reason'], 'exhausted_without_supported_certificate')
            self.assertNotIn('certificate', result)
        return oracle

    def pair_rejected(self, i, a='A', b='B'):
        self.assertFalse(check_certificate(
            i, {'kind': 'pair_order_impossible', 'patients': [a, b]}))

    def test_g1_room_gap_boundary(self):
        # 2 + 1 + 2 = 5: exact fit; adjacency omits the required minute.
        i = gap_case()
        self.compare(i, 'FEASIBLE', [[row('A', 0), row('B', 3)]])
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 2)]))

    def test_g2_gap_only_contradiction(self):
        # Five required span minutes exceed four; without the gap both orders fit.
        i = gap_case(4)
        self.compare(i, 'INFEASIBLE')
        self.pair_rejected(i)

    def test_g3_surgeon_gap_boundary(self):
        # Same 2+1+2 boundary on the surgeon, with independent rooms.
        i = gap_case()
        i['rooms'] = [resource('r0', 5), resource('r1', 5)]
        i['surgeons'] = [resource('s0', 5, gap=1)]
        i['patients'][1].update(surgeon='s0', eligible_rooms=['r1'])
        self.compare(i, 'FEASIBLE', [[row('A', 0), row('B', 3, 'r1')]])
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 2, 'r1')]))

    def test_c1_fragmented_room_cannot_fit_three(self):
        # Two windows of length two cannot contain one nonpreemptive length three.
        i = instance([job('A', 's0', 3, 0, 5)],
                     [resource('r0', 5, windows=[[0, 2], [3, 5]])],
                     [resource('s0', 5)])
        self.compare(i, 'INFEASIBLE')
        self.pair_rejected(i, 'A', 'A')
        self.assertTrue(check_schedule(i, [row('A', 1)]))
        self.assertTrue(check_schedule(i, [dict(row('A', 0), end=2),
                                           dict(row('A', 3), end=4)]))

    def test_c2_resource_intersection_too_short(self):
        # [1,4) intersects each room window in only one minute, less than two.
        i = instance([job('A', 's0', 2, 0, 5)],
                     [resource('r0', 5, windows=[[0, 2], [3, 5]])],
                     [resource('s0', 5, windows=[[1, 4]])])
        self.compare(i, 'INFEASIBLE')
        self.pair_rejected(i, 'A', 'A')
        for start in (0, 1, 3):
            self.assertTrue(check_schedule(i, [row('A', start)]))

    def test_c3_exact_calendar_windows(self):
        # Each two-minute window fits exactly; [1,3) crosses the break.
        i = instance([job('A', 's0', 2, 0, 5)],
                     [resource('r0', 5, windows=[[0, 2], [3, 5]])],
                     [resource('s0', 5)])
        self.compare(i, 'FEASIBLE', [[row('A', 0)], [row('A', 3)]])
        self.assertTrue(check_schedule(i, [row('A', 1)]))

    def test_o1_optional_omission_and_mandatory_counterpart(self):
        # Only A is required; forcing both two-minute jobs into [0,2) is impossible.
        i = instance([job('A', 's0', 2, 0, 2),
                      job('B', 's1', 2, 0, 2, mandatory=False)],
                     [resource('r0', 2)], [resource('s0', 2), resource('s1', 2)])
        self.compare(i, 'FEASIBLE', [[row('A', 0)]])
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 0)]))
        self.pair_rejected(i)
        mandatory = deepcopy(i)
        mandatory['patients'][1]['mandatory'] = True
        self.compare(mandatory, 'INFEASIBLE', certified=True)

    def test_o2_optional_present_and_absent(self):
        # [0,2) and [2,4) are adjacent; B[3,5) misses its deadline/calendar.
        i = instance([job('A', 's0', 2, 0, 2),
                      job('B', 's1', 2, 2, 4, mandatory=False)],
                     [resource('r0', 4)], [resource('s0', 4), resource('s1', 4)])
        self.compare(i, 'FEASIBLE', [[row('A', 0)], [row('A', 0), row('B', 2)]])
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 2), row('B', 2)]))
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 3)]))
        # Oracle covers mandatory feasibility, not all optional-present schedules.
        self.pair_rejected(i)

    def test_b1_budget_only_contradiction(self):
        # Four surgery minutes exceed budget three despite calendar length six.
        i = instance([job('A', 's0', 2, 0, 6), job('B', 's1', 2, 0, 6)],
                     [resource('r0', 6, budget=3)],
                     [resource('s0', 6), resource('s1', 6)])
        self.compare(i, 'INFEASIBLE')
        self.pair_rejected(i)
        self.assertTrue(check_schedule(i, [row('A', 0), row('B', 2)]))

    def test_l1_limits_do_not_prove_infeasibility(self):
        i = gap_case()
        self.assertEqual(schema_errors(i), [])
        self.assertEqual(parse(render(i)), i)
        self.assertEqual(check_schedule(i, [row('A', 0), row('B', 3)]), [])
        oracle = enumerate_schedules(i, limit=0)
        self.assertEqual(oracle['status'], 'UNKNOWN')
        self.assertEqual(oracle['reason'], 'combination_limit')
        self.assertEqual(oracle['examined'], 0)
        self.assertFalse(oracle.get('complete', False))
        self.assertNotIn('solutions', oracle)
        result = solve(i, max_nodes=0, seconds=1)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'search_limit')
        self.assertFalse(result.get('search_exhausted', False))
        self.assertNotIn('certificate', result)

    def test_p1_relaxed_pair_proof_survives_extra_gap(self):
        # A->E ends E >=8>7; E->A ends A >=11>10, even ignoring gap one.
        i = instance([job('A', 's0', 4, 0, 10), job('E', 's1', 4, 3, 7)],
                     [resource('r0', 10, gap=1)],
                     [resource('s0', 10), resource('s1', 10)])
        self.assertTrue(check_certificate(
            i, {'kind': 'pair_order_impossible', 'patients': ['A', 'E']}))
        self.compare(i, 'INFEASIBLE', certified=True)


if __name__ == '__main__':
    unittest.main()
