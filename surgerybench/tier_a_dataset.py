"""Separate hand-designed Tier A v1 export. Never calls DFS or pilot builders."""
import argparse
import hashlib
from itertools import combinations
from math import prod
from pathlib import Path

from .common import canonical, digest
from .temporal_check import schema_errors, check_schedule, check_certificate
from .temporal_oracle import enumerate_schedules
from .temporal_text import render

VERSION = 'tier-a-original-synthetic-v1'
BASE = 'e3f9dbe19381a43bd39c64343ce32966d15dce9e'


def cases():
    """Authored labels/arithmetic/witnesses, independent of any solver result."""
    def r(name, end, gap=0, budget=10, windows=None):
        return dict(id=name, gap=gap, budgets=[budget],
                    calendar=[windows if windows is not None else [[0, end]]])
    def p(name, surgeon, duration, release, due, rooms=('r0',), mandatory=True):
        return dict(id=name, surgeon=surgeon, duration=duration, release=release,
                    due=due, eligible_rooms=list(rooms), mandatory=mandatory,
                    priority=1, emergency=False)
    def w(name, start, room='r0'):
        return dict(patient=name, day=0, start=start, room=room)
    rows = []
    def add(key, family, tags, label, arithmetic, jobs, rooms, surgeons, witness=None,
            optional_witness=None):
        rows.append(dict(key=key, family=family, tags=tags.split(), label=label,
                         arithmetic=arithmetic, instance=dict(schema_version='1.1',
                         days=1, day_minutes=1440, patients=jobs, rooms=rooms,
                         surgeons=surgeons), witness=witness,
                         optional_witness=optional_witness))
    for end in (5, 4):
        add(f'room-gap-{end}', 'room-gap', 'positive_room_gap isolated',
            'FEASIBLE' if end == 5 else 'INFEASIBLE',
            f'Two durations 2 plus gap 1 require span 5; available span is {end}.',
            [p('A', 's0', 2, 0, end), p('B', 's1', 2, 0, end)],
            [r('r0', end, gap=1)], [r('s0', end), r('s1', end)],
            [w('A', 0), w('B', 3)] if end == 5 else None)
    add('surgeon-gap', 'surgeon-gap', 'positive_surgeon_gap isolated', 'FEASIBLE',
        'The shared surgeon needs 2+1+2=5 minutes; separate rooms each fit its job.',
        [p('A', 's0', 2, 0, 5), p('B', 's0', 2, 0, 5, ('r1',))],
        [r('r0', 5), r('r1', 5)], [r('s0', 5, gap=1)],
        [w('A', 0), w('B', 3, 'r1')])
    for duration in (3, 2):
        add(f'fragmented-{duration}', 'fragmented-room', 'fragmented_calendar isolated',
            'INFEASIBLE' if duration == 3 else 'FEASIBLE',
            f'Each room window has length 2; required uninterrupted duration is {duration}.',
            [p('A', 's0', duration, 0, 5)],
            [r('r0', 5, windows=[[0, 2], [3, 5]])], [r('s0', 5)],
            [w('A', 0)] if duration == 2 else None)
    add('calendar-intersection', 'calendar-intersection', 'calendar_intersection combined',
        'INFEASIBLE', 'Surgeon [1,4) intersects room [0,2) and [3,5) in lengths 1,1 < duration 2.',
        [p('A', 's0', 2, 0, 5)], [r('r0', 5, windows=[[0, 2], [3, 5]])],
        [r('s0', 5, windows=[[1, 4]])])
    for mandatory in (False, True):
        add('optional-forced' if mandatory else 'optional-omitted', 'optional-load',
            'optional_job isolated' if not mandatory else 'mandatory_pair isolated',
            'INFEASIBLE' if mandatory else 'FEASIBLE',
            'Only A requires 2 minutes when B is optional; forcing both requires 4 in span 2.',
            [p('A', 's0', 2, 0, 2), p('B', 's1', 2, 0, 2, mandatory=mandatory)],
            [r('r0', 2)], [r('s0', 2), r('s1', 2)],
            None if mandatory else [w('A', 0)])
    add('optional-adjacent', 'optional-adjacent', 'optional_job window_boundary isolated',
        'FEASIBLE', 'A [0,2) is mandatory; optional B [2,4) fits exactly, and omission is valid.',
        [p('A', 's0', 2, 0, 2), p('B', 's1', 2, 2, 4, mandatory=False)],
        [r('r0', 4)], [r('s0', 4), r('s1', 4)], [w('A', 0)],
        [w('A', 0), w('B', 2)])
    add('room-budget', 'room-budget', 'daily_budget isolated', 'INFEASIBLE',
        'Two durations 2 total 4 > room daily budget 3; calendar length 6 is sufficient.',
        [p('A', 's0', 2, 0, 6), p('B', 's1', 2, 0, 6)],
        [r('r0', 6, budget=3)], [r('s0', 6), r('s1', 6)])
    for flexible in (True, False):
        eligible = ('r0', 'r1') if flexible else ('r0',)
        add('eligibility-budget-flex' if flexible else 'eligibility-budget-fixed',
            'eligibility-budget', 'eligibility daily_budget combined',
            'FEASIBLE' if flexible else 'INFEASIBLE',
            'Each room budget is 2; two jobs of duration 2 fit separate rooms, but total 4 cannot use r0 alone.',
            [p('A', 's0', 2, 0, 4, eligible), p('B', 's1', 2, 0, 4, eligible)],
            [r('r0', 4, budget=2), r('r1', 4, budget=2)], [r('s0', 4), r('s1', 4)],
            [w('A', 0), w('B', 0, 'r1')] if flexible else None)
    for flexible in (False, True):
        add('eligibility-window-flex' if flexible else 'eligibility-window-fixed',
            'eligibility-window', 'eligibility fragmented_calendar combined',
            'FEASIBLE' if flexible else 'INFEASIBLE',
            'r0 windows each have length 1 < duration 2; r1 [0,4) fits only when eligible.',
            [p('A', 's0', 2, 0, 4, ('r0', 'r1') if flexible else ('r0',))],
            [r('r0', 4, windows=[[0, 1], [3, 4]]), r('r1', 4)], [r('s0', 4)],
            [w('A', 0, 'r1')] if flexible else None)
    add('pair-deadline', 'pair-deadline', 'deadline positive_room_gap combined',
        'INFEASIBLE', 'Ignoring gap: A->E ends E earliest 8>7; E->A ends A earliest 11>10.',
        [p('A', 's0', 4, 0, 10), p('E', 's1', 4, 3, 7)],
        [r('r0', 10, gap=1)], [r('s0', 10), r('s1', 10)])
    return rows


def build(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('preserve prior outputs')
    authored = cases()
    if not 1 <= len(authored) <= 24:
        raise ValueError('case count outside envelope')
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))}
    model, gold, ledger = [], [], []
    for c in authored:
        i = c['instance']
        # Check bounds before invoking the minute-domain oracle.
        if (schema_errors(i) or i['days'] != 1 or not 1 <= len(i['patients']) <= 2
                or not 1 <= len(i['rooms']) <= 2 or not 1 <= len(i['surgeons']) <= 2
                or any(p['due'] > 10 or p['duration'] > 10 for p in i['patients'])
                or any(r['gap'] > 10 or r['budgets'][0] > 10 or len(r['calendar'][0]) > 2
                       for kind in ('rooms', 'surgeons') for r in i[kind])
                or any(b > 10 for kind in ('rooms', 'surgeons') for r in i[kind]
                       for day in r['calendar'] for a, b in day)):
            raise ValueError('instance outside tiny envelope')
        bound = prod(max(0, p['due'] - p['release'] - p['duration'] + 1)
                     * len(p['eligible_rooms']) for p in i['patients'] if p['mandatory'])
        if bound > 100:
            raise ValueError('assignment product exceeds declared 100')
        oracle = enumerate_schedules(i, limit=10000)
        if not oracle.get('complete') or oracle['status'] != c['label']:
            raise ValueError('authored label unresolved or contradicted')
        for witness in oracle['solutions'] + [s for s in (c['witness'], c['optional_witness']) if s is not None]:
            if check_schedule(i, witness):
                raise ValueError('invalid intended-instance witness')
        if c['label'] == 'FEASIBLE' and c['witness'] is None:
            raise ValueError('missing authored witness')
        certificates = [dict(kind='pair_order_impossible', patients=[a['id'], b['id']])
                        for a, b in combinations(i['patients'], 2)]
        cert = next((v for v in certificates if check_certificate(i, v)), None)
        certification = ('not_applicable' if c['label'] == 'FEASIBLE' else
                         'pair_order_impossible' if cert else 'oracle_only')
        case_id = c['key'] + '-' + digest(i)[:12]
        text = render(i)
        model.append(dict(case_id=case_id, text=text))
        row = dict(case_id=case_id, version=VERSION, family=c['family'],
                   split='provisional_review', tags=c['tags'], label=c['label'],
                   certification=certification, arithmetic=c['arithmetic'], instance=i,
                   instance_sha256=digest(i), text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   lineage=dict(source='original_synthetic', method='hand_designed',
                                reviewed_base=BASE, code_sha256=code),
                   evidence=dict(witness=c['witness'], optional_witness=c['optional_witness'],
                                 certificate=cert, oracle=dict(complete=True,
                                 limit=10000, product_upper_bound=bound,
                                 examined=oracle['examined'], solution_count=len(oracle['solutions']))))
        gold.append(row)
        ledger.append({k: row[k] for k in ('case_id', 'family', 'split', 'tags', 'label', 'certification', 'arithmetic')})
    files = {'tier-a-model.jsonl': ''.join(canonical(r) + '\n' for r in model),
             'tier-a-gold.jsonl': ''.join(canonical(r) + '\n' for r in gold),
             'coverage.json': canonical(dict(version=VERSION, split_policy='provisional_review_only_no_independence_claim', cases=ledger)) + '\n'}
    manifest = dict(version=VERSION, cases=len(gold), old_harness_compatible=False,
                    files={k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()})
    destination.mkdir()  # exclusive: a race cannot overwrite an existing directory
    for name, content in files.items():
        (destination / name).write_text(content)
    (destination / 'manifest.json').write_text(canonical(manifest) + '\n')
    return dict(version=VERSION, instances=len(gold))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    print(canonical(build(parser.parse_args().destination)))
