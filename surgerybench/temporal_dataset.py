"""24 original-synthetic paired families; bounded arrival/deadline pilot."""
import argparse, hashlib, json, platform, random
from collections import Counter
from copy import deepcopy
from pathlib import Path
from .common import canonical, digest
from .common import revision
from .temporal_check import schema_errors, check_schedule, check_certificate
from .temporal_text import render, parse
from .temporal_oracle import enumerate_schedules, REVISION as ORACLE
GENERATOR = 'arrival-deadline-pilot-v1'
THEMES = ('tight_windows', 'room_contention', 'fixed_surgeon_contention', 'eligible_room_bottleneck')

def fixture(theme, index):
    seed = 326300 + 100 * THEMES.index(theme) + index
    rng = random.Random(seed)
    day = index % 2
    days = day + 1
    offset = rng.randrange(8, 17) * 30
    a, b = (4 + index, 3 + (index + 1) % 6)
    end = offset + a + b + 2
    absolute = day * 1440 + offset

    def resource(rid):
        calendars = [[] for _ in range(days)]
        calendars[day] = [[offset, end]]
        budgets = [0] * days
        budgets[day] = a + b + 2
        return {'id': rid, 'gap': 0, 'budgets': budgets, 'calendar': calendars}
    surgeons = [resource('s0'), resource('s1')]
    rooms = [resource('r0')]
    if theme in ('fixed_surgeon_contention', 'eligible_room_bottleneck'):
        rooms.append(resource('r1'))
    if theme == 'eligible_room_bottleneck':
        rooms.append(resource('r2'))
        surgeons.append(resource('s2'))

    def patient(pid, surgeon, duration, release, due, eligible, emergency):
        return {'id': pid, 'mandatory': True, 'surgeon': surgeon, 'duration': duration, 'release': release, 'due': due, 'eligible_rooms': eligible, 'priority': rng.randrange(1, 6), 'emergency': emergency}
    eligibility = ['r0', 'r1'] if theme == 'fixed_surgeon_contention' else ['r0']
    patients = [patient('A', 's0', a, absolute, absolute + (a if theme == 'tight_windows' else a + b + 2), eligibility, False), patient('E', 's0' if theme == 'fixed_surgeon_contention' else 's1', b, absolute + a - 1, absolute + a + b, eligibility, True)]
    if theme == 'eligible_room_bottleneck':
        patients.append(patient('B', 's2', 2 + index % 3, absolute, absolute + 2 + index % 3, ['r1', 'r2'], False))
    i = {'schema_version': '1.1', 'days': days, 'day_minutes': 1440, 'surgeons': surgeons, 'rooms': rooms, 'patients': patients}
    return (i, seed)

def records():
    rows = []
    for theme in THEMES:
        for index in range(6):
            original, seed = fixture(theme, index)
            family = f'{GENERATOR}-{theme}-{index:02d}'
            split = 'train' if index < 4 else 'validation' if index == 4 else 'test'
            for variant in ('feasible', 'deadline_minus_one'):
                i = deepcopy(original)
                if variant != 'feasible':
                    i['patients'][1]['due'] -= 1
                oracle = enumerate_schedules(i)
                if oracle['status'] == 'UNKNOWN':
                    raise ValueError('oracle limit: do not certify')
                if variant == 'feasible':
                    witness = oracle['solutions'][0]
                    if not not check_schedule(i, witness):
                        raise ValueError('Validation failed: not check_schedule(i, witness)')
                    evidence = {'witness': witness}
                else:
                    if not oracle['status'] == 'INFEASIBLE':
                        raise ValueError("Validation failed: oracle['status'] == 'INFEASIBLE'")
                    cert = {'kind': 'pair_order_impossible', 'patients': ['A', 'E']}
                    if not check_certificate(i, cert):
                        raise ValueError('Validation failed: check_certificate(i, cert)')
                    evidence = {'certificate': cert}
                text = render(i)
                if not parse(text) == i:
                    raise ValueError('Validation failed: parse(text) == i')
                lineage = {'family': family, 'variant': variant, 'seed': seed, 'generator': GENERATOR, 'schema': '1.1', 'code_revision': revision(), 'python': platform.python_version(), 'source': {'kind': 'original_synthetic', 'source_family': family}, 'parent_instance_sha256': digest(original), 'changed_field': None if variant == 'feasible' else 'patients[1].due', 'delta': None if variant == 'feasible' else -1}
                rows.append({'id': digest({'instance': i, 'lineage': lineage})[:24], 'family': family, 'theme': theme, 'split': split, 'lineage': lineage, 'instance': i, 'instance_sha256': digest(i), 'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text, 'label': oracle['status'], 'evidence': evidence, 'oracle': {'revision': ORACLE, 'complete': oracle['complete'], 'assignments_examined': oracle['examined'], 'solution_count': len(oracle['solutions'])}})
    if not len({r['instance_sha256'] for r in rows}) == 48:
        raise ValueError("Validation failed: len({r['instance_sha256'] for r in rows}) == 48")
    return rows

def build(directory):
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError('preserve existing pilot')
    rows = records()
    directory.mkdir(parents=True)
    (directory / 'model.jsonl').write_text(''.join((canonical({'id': r['id'], 'text': r['text']}) + '\n' for r in rows)))
    (directory / 'gold.jsonl').write_text(''.join((canonical({k: v for k, v in r.items() if k != 'text'}) + '\n' for r in rows)))
    summary = {'generator': GENERATOR, 'instances': len(rows), 'base_families': len({r['family'] for r in rows}), 'source': 'original_synthetic', 'counts': dict(sorted(Counter((f"{r['split']}/{r['theme']}/{r['label']}" for r in rows)).items())), 'limitations': ['Tiny controlled-language proof pilot, not a clinical dataset or a real-model evaluation.', 'Six parameterized families per theme; category overlap and small job counts are deliberate. No paraphrase multiplication.', 'No IHTC-derived rows; original corpus v1 remains separate and unchanged.']}
    (directory / 'summary.json').write_text(canonical(summary) + '\n')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}
    (directory / 'manifest.json').write_text(canonical(manifest) + '\n')
    return summary

def audit(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    if not set(manifest) == {'model.jsonl', 'gold.jsonl', 'summary.json'}:
        raise ValueError("Validation failed: set(manifest) == {'model.jsonl', 'gold.jsonl', 'summary.json'}")
    if not {p.name for p in directory.iterdir()} == set(manifest) | {'manifest.json'}:
        raise ValueError("Validation failed: {p.name for p in directory.iterdir()} == set(manifest) | {'manifest.json'}")
    for name, sha in manifest.items():
        if not hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha:
            raise ValueError('Validation failed: hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha')
    model = [json.loads(s) for s in (directory / 'model.jsonl').read_text().splitlines()]
    gold = [json.loads(s) for s in (directory / 'gold.jsonl').read_text().splitlines()]
    if not len(model) == len(gold) == 48:
        raise ValueError('Validation failed: len(model) == len(gold) == 48')
    families = {}
    ids = set()
    hashes = set()
    for m, g in zip(model, gold):
        if not (set(m) == {'id', 'text'} and m['id'] == g['id'] and (g['id'] not in ids)):
            raise ValueError("Validation failed: set(m) == {'id', 'text'} and m['id'] == g['id'] and (g['id'] not in ids)")
        ids.add(g['id'])
        hashes.add(g['instance_sha256'])
        if not (not schema_errors(g['instance']) and digest(g['instance']) == g['instance_sha256']):
            raise ValueError("Validation failed: not schema_errors(g['instance']) and digest(g['instance']) == g['instance_sha256']")
        if not hashlib.sha256(m['text'].encode()).hexdigest() == g['text_sha256']:
            raise ValueError("Validation failed: hashlib.sha256(m['text'].encode()).hexdigest() == g['text_sha256']")
        if not parse(m['text']) == g['instance']:
            raise ValueError("Validation failed: parse(m['text']) == g['instance']")
        if not g['lineage']['source']['kind'] == 'original_synthetic':
            raise ValueError("Validation failed: g['lineage']['source']['kind'] == 'original_synthetic'")
        if g['family'] in families:
            if not families[g['family']] == g['split']:
                raise ValueError("Validation failed: families[g['family']] == g['split']")
        families[g['family']] = g['split']
        oracle = enumerate_schedules(g['instance'])
        if not (oracle['complete'] and oracle['status'] == g['label']):
            raise ValueError("Validation failed: oracle['complete'] and oracle['status'] == g['label']")
        if g['label'] == 'FEASIBLE':
            if not not check_schedule(g['instance'], g['evidence']['witness']):
                raise ValueError("Validation failed: not check_schedule(g['instance'], g['evidence']['witness'])")
        elif not check_certificate(g['instance'], g['evidence']['certificate']):
            raise ValueError("Validation failed: check_certificate(g['instance'], g['evidence']['certificate'])")
    if not (len(families) == 24 and len(hashes) == 48):
        raise ValueError('Validation failed: len(families) == 24 and len(hashes) == 48')
    return {'audit': 'PASS', 'instances': 48, 'families': 24, 'independent_oracle_complete': 48}
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('directory')
    p.add_argument('--audit', action='store_true')
    a = p.parse_args()
    print(json.dumps(audit(a.directory) if a.audit else build(a.directory), sort_keys=True))
