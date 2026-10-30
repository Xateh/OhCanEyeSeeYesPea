"""Harder synthetic surgery problems, each built around an answer that is already known.

Durations: 20 evenly spaced, case-weighted quantiles of mean incision-to-closure time from
Korzhenevich, Zander and Bialas (2022), "Surgical case mixes and distributions of perioperative
surgical process durations for German hospitals", doi:10.5281/zenodo.7147921, CC BY 4.0.
Derived from 1,639 procedure groups covering 204,924 recorded surgeries.
"""
from copy import deepcopy
import hashlib
import json
from math import ceil
from pathlib import Path
import random

from surgerybench.common import canonical, digest
from surgerybench.temporal_check import check_certificate, check_schedule
from surgerybench.temporal_text import RULES, render

VERSION = 'hard-synthetic-v1'
OUTPUT = Path('fixtures') / VERSION
FEASIBLE, INFEASIBLE = 'FEASIBLE', 'INFEASIBLE'
SIZES = (5, 10, 20, 40, 80)
PAIRS_PER_SIZE = 10
DURATIONS = (11, 15, 19, 24, 27, 32, 38, 43, 49, 55, 57, 60, 64, 68, 75, 81, 91, 107, 131, 185)
DAY_MINUTES = 1440
SURGEON_HOURS = (480, 1080)
ROOM_WINDOWS = ((480, 720), (750, 1080))
GAPS = (0, 5, 10, 15)
WINDOW_SLACK = 120
BUDGET_SLACK = 60
SURGERIES_PER_ROOM_DAY = 6
STEP = 5
MAX_ATTEMPTS = 200


def neutral_text(instance):
    """Render the problem without the original text's give-away example pair."""
    neutral = RULES.replace('["A","E"]', '["FIRST_ID","SECOND_ID"]')
    return render(instance).replace(RULES, neutral)


def layout(size):
    days = 1 if size <= 10 else 2
    return days, max(2, ceil(size / (SURGERIES_PER_ROOM_DAY * days))), max(2, ceil(size / 4))


def fits(busy, start, end, gap):
    return all(end + gap <= other_start or other_end + gap <= start for other_start, other_end in busy)


def earliest_start(room_busy, surgeon_busy, room_gap, surgeon_gap, duration, lowest):
    for first, last in ROOM_WINDOWS:
        for start in range(max(first, SURGEON_HOURS[0], lowest), min(last, SURGEON_HOURS[1]) - duration + 1, STEP):
            end = start + duration
            if fits(room_busy, start, end, room_gap) and fits(surgeon_busy, start, end, surgeon_gap):
                return start
    return None


def plant_pair(rng, days, surgeons, rooms):
    """Put two back-to-back surgeries with one surgeon, ready to become a hidden conflict."""
    morning_start, morning_end = ROOM_WINDOWS[0]
    first = rng.choice(DURATIONS)
    second = rng.choice([d for d in DURATIONS if first + d <= morning_end - morning_start])
    day, start = rng.randrange(days), rng.randrange(morning_start, morning_end - first - second + 1, STEP)
    room_a, room_b = rng.sample(rooms, 2)
    surgeon = surgeons[0]
    return [dict(duration=first, day=day, start=start, room=room_a, surgeon=surgeon),
            dict(duration=second, day=day, start=start + first, room=room_b, surgeon=surgeon)]


def place_others(rng, count, days, surgeons, rooms, gaps, placed):
    """Fill in remaining surgeries wherever they fit. Returns None if the layout is too full."""
    result = list(placed)
    for _ in range(count):
        duration, surgeon = rng.choice(DURATIONS), rng.choice(surgeons)
        options = []
        for day in rng.sample(range(days), days):
            for room in rng.sample(rooms, len(rooms)):
                busy = lambda key, value: [(p['start'], p['start'] + p['duration']) for p in result
                                           if p['day'] == day and p[key] == value]
                start = earliest_start(busy('room', room), busy('surgeon', surgeon), gaps[room], gaps[surgeon],
                                       duration, 480 + rng.randrange(0, 240, STEP))
                if start is not None:
                    options.append(dict(duration=duration, day=day, start=start, room=room, surgeon=surgeon))
        if not options:
            return None
        result.append(rng.choice(options))
    return result


def resource(rng, identifier, gap, placements, key, days, windows):
    used = [sum(p['duration'] for p in placements if p['day'] == d and p[key] == identifier) for d in range(days)]
    return {'id': identifier, 'gap': gap, 'budgets': [min(DAY_MINUTES, u + rng.randrange(BUDGET_SLACK + 1)) for u in used],
            'calendar': [[list(w) for w in windows] for _ in range(days)]}


def surgery(rng, identifier, placement, rooms, days):
    start = placement['day'] * DAY_MINUTES + placement['start']
    extra = rng.sample([r for r in rooms if r != placement['room']], rng.randrange(0, min(3, len(rooms))))
    return {'id': identifier, 'mandatory': True, 'surgeon': placement['surgeon'], 'duration': placement['duration'],
            'release': max(0, start - rng.randrange(WINDOW_SLACK + 1)),
            'due': min(days * DAY_MINUTES, start + placement['duration'] + rng.randrange(WINDOW_SLACK + 1)),
            'eligible_rooms': sorted([placement['room'], *extra]), 'priority': rng.randrange(1, 4),
            'emergency': rng.random() < 0.1}


def tighten(patients, first_id, second_id, placement, rng):
    """Set the pair's windows so one order fits exactly. The twin then cuts one minute from that."""
    first, second = placement
    start = first['day'] * DAY_MINUTES + first['start']
    release_second = start + rng.randrange(first['duration'])
    total = first['duration'] + second['duration']
    changes = {first_id: {'release': start, 'due': release_second + total - 1},
               second_id: {'release': release_second, 'due': start + total}}
    return [{**p, **changes.get(p['id'], {})} for p in patients]


def attempt(rng, size):
    days, room_count, surgeon_count = layout(size)
    rooms = [f'r{i:02d}' for i in range(room_count)]
    surgeons = [f's{i:02d}' for i in range(surgeon_count)]
    gaps = {**{r: rng.choice(GAPS[1:]) for r in rooms}, surgeons[0]: 0,
            **{s: rng.choice(GAPS) for s in surgeons[1:]}}
    pair = plant_pair(rng, days, surgeons, rooms)
    placed = place_others(rng, size - 2, days, surgeons, rooms, gaps, pair)
    if placed is None:
        return None
    identifiers = [f'P{n:03d}' for n in rng.sample(range(100, 1000), size)]
    patients = [surgery(rng, i, p, rooms, days) for i, p in zip(identifiers, placed)]
    patients = tighten(patients, identifiers[0], identifiers[1], pair, rng)
    instance = {'schema_version': '1.1', 'days': days, 'day_minutes': DAY_MINUTES,
                'surgeons': [resource(rng, s, gaps[s], placed, 'surgeon', days, [SURGEON_HOURS]) for s in surgeons],
                'rooms': [resource(rng, r, gaps[r], placed, 'room', days, ROOM_WINDOWS) for r in rooms],
                'patients': sorted(patients, key=lambda p: p['id'])}
    witness = [{'patient': i, 'day': p['day'], 'start': p['start'], 'room': p['room']} for i, p in zip(identifiers, placed)]
    return instance, witness, identifiers[:2]


def record(size, index, label, instance, evidence):
    text = neutral_text(instance)
    variant = label.lower()
    return {'id': f'hard-n{size:02d}-{index:02d}-{digest(instance)[:10]}', 'family': f'{VERSION}-n{size:02d}-{index:02d}',
            'size': size, 'label': label, 'variant': variant, 'instance': instance, 'evidence': evidence, 'text': text,
            'instance_sha256': digest(instance), 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'split': 'evaluation', 'source': {'kind': 'original_synthetic', 'durations_doi': '10.5281/zenodo.7147921'}}


def build_pair(size, index):
    rng = random.Random(f'{VERSION}-{size}-{index}')
    for _ in range(MAX_ATTEMPTS):
        planted = attempt(rng, size)
        if planted is None:
            continue
        instance, witness, pair = planted
        impossible = deepcopy(instance)
        target = next(p for p in impossible['patients'] if p['id'] == pair[1])
        target['due'] -= 1
        certificate = {'kind': 'pair_order_impossible', 'patients': sorted(pair)}
        if check_schedule(instance, witness) or not check_certificate(impossible, certificate):
            continue
        return (record(size, index, FEASIBLE, instance, {'witness': witness}),
                record(size, index, INFEASIBLE, impossible, {'certificate': certificate}))
    raise RuntimeError(f'no valid problem for size {size}, index {index}')


def build(out=OUTPUT):
    if out.exists():
        raise SystemExit(f'{out} already exists; datasets are never overwritten')
    records = [r for size in SIZES for index in range(PAIRS_PER_SIZE) for r in build_pair(size, index)]
    out.mkdir(parents=True)
    model = ''.join(canonical({'id': r['id'], 'text': r['text']}) + '\n' for r in records)
    gold = ''.join(canonical({k: v for k, v in r.items() if k != 'text'}) + '\n' for r in records)
    (out / 'model.jsonl').write_text(model)
    (out / 'gold.jsonl').write_text(gold)
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in (('model.jsonl', model), ('gold.jsonl', gold))}
    manifest = {'version': VERSION, 'problems': len(records), 'sizes': SIZES, 'pairs_per_size': PAIRS_PER_SIZE, 'files': hashes}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(f'wrote {out}: {len(records)} problems')


if __name__ == '__main__':
    build()
