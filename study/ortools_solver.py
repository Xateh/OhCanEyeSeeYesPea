"""OR-Tools CP-SAT solver with the same tool contract as surgerybench.temporal_csp. Needs ortools.

It receives only the instance the model translated. Every rule the checker enforces becomes a constraint:
one room and start per mandatory surgery inside arrival, deadline and both calendars, no overlap per surgeon
and room per day including the required gap, and daily minute budgets. Optional surgeries are left out.
"""
from itertools import combinations

import ortools
from ortools.sat.python import cp_model

from surgerybench.temporal_check import check_certificate, schema_errors
from surgerybench.temporal_csp import TOOL

REVISION = f'ortools-cp-sat-v1-{ortools.__version__}'
SECONDS = 10.0
WORKERS = 8
DAY = 1440


def pair_certificate(instance, mandatory):
    """The checker only accepts two-surgery proofs, so look for one before searching."""
    for first, second in combinations(mandatory, 2):
        certificate = {'kind': 'pair_order_impossible', 'patients': [first['id'], second['id']]}
        if check_certificate(instance, certificate):
            return certificate
    return None


def windows(instance, patient, day, room):
    """Yield every [earliest, latest] start allowed by both calendars, arrival and deadline."""
    resources = {kind: {r['id']: r for r in instance[kind]} for kind in ('surgeons', 'rooms')}
    for a, b in resources['surgeons'][patient['surgeon']]['calendar'][day]:
        for c, d in resources['rooms'][room]['calendar'][day]:
            earliest = max(a, c, patient['release'] - day * DAY)
            latest = min(b, d, patient['due'] - day * DAY) - patient['duration']
            if earliest <= latest:
                yield earliest, latest


def build(instance, mandatory):
    model = cp_model.CpModel()
    gaps = {(kind, r['id']): r['gap'] for kind in ('surgeons', 'rooms') for r in instance[kind]}
    budgets = {(kind, r['id']): r['budgets'] for kind in ('surgeons', 'rooms') for r in instance[kind]}
    options, intervals, minutes = {}, {}, {}
    for patient in mandatory:
        choices = []
        for day in range(instance['days']):
            for room in patient['eligible_rooms']:
                for earliest, latest in windows(instance, patient, day, room):
                    chosen = model.NewBoolVar('')
                    start = model.NewIntVar(earliest, latest, '')
                    choices.append((chosen, start, day, room))
                    for key in (('surgeons', patient['surgeon']), ('rooms', room)):
                        span = patient['duration'] + gaps[key]
                        intervals.setdefault((*key, day), []).append(model.NewOptionalFixedSizeIntervalVar(start, span, chosen, ''))
                        minutes.setdefault((*key, day), []).append((patient['duration'], chosen))
        if not choices:
            return None, None
        model.AddExactlyOne(chosen for chosen, *_ in choices)
        options[patient['id']] = choices
    for key, spans in intervals.items():
        model.AddNoOverlap(spans)
    for (kind, rid, day), used in minutes.items():
        model.Add(sum(length * chosen for length, chosen in used) <= budgets[(kind, rid)][day])
    return model, options


def solve(instance, seconds=SECONDS):
    errors = schema_errors(instance)
    if errors:
        raise ValueError(errors)
    mandatory = [p for p in instance['patients'] if p['mandatory']]
    certificate = pair_certificate(instance, mandatory)
    if certificate:
        return {'status': 'INFEASIBLE', 'certificate': certificate, 'solver': 'cp-sat'}
    model, options = build(instance, mandatory)
    if model is None:
        return {'status': 'UNKNOWN', 'reason': 'proven_infeasible_without_supported_certificate', 'proven_infeasible': True, 'solver': 'cp-sat'}
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = WORKERS
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = [{'patient': pid, 'day': day, 'start': solver.Value(start), 'room': room}
                    for pid, choices in options.items() for chosen, start, day, room in choices if solver.Value(chosen)]
        return {'status': 'FEASIBLE', 'schedule': schedule, 'solver': 'cp-sat'}
    if status == cp_model.INFEASIBLE:
        return {'status': 'UNKNOWN', 'reason': 'proven_infeasible_without_supported_certificate', 'proven_infeasible': True, 'solver': 'cp-sat'}
    return {'status': 'UNKNOWN', 'reason': 'time_limit', 'solver': 'cp-sat'}


class ORToolsAdapter:
    revision = REVISION
    tool_definition = TOOL

    def invoke(self, arguments):
        if not isinstance(arguments, dict) or set(arguments) != {'instance'}:
            raise ValueError('only a model-translated instance is accepted')
        return solve(arguments['instance'])
