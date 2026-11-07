"""Seeded original-synthetic development candidates; no provider or frozen-file writes."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import platform
import subprocess
from itertools import combinations
import time
from surgerybench.temporal_check import schema_errors, check_schedule, check_certificate
from surgerybench.temporal_oracle import enumerate_schedules, REVISION as ORACLE
from surgerybench.temporal_csp import CSPAdapter
from surgerybench.temporal_text import render, parse
from tier_a_input_view import derive

VERSION = 'seeded-development-suites-v1'
SUITES = ('scarcity_contention', 'fragmented_gap', 'eligibility_budget',
          'optional_load', 'combined_constraints', 'parameter_sweep')
DEFAULT = dict(seed=326305, candidates_per_suite=16, patient_count=3,
               surgeon_count=2, room_count=2, horizon_minutes=8,
               oracle_product_cap=100, oracle_assignment_limit=10000,
               preprocessing_cap=100000, suites=list(SUITES))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def settings(value):
    if type(value) is not dict or set(value) != set(DEFAULT):
        raise ValueError('exact settings keys required')
    for key in set(DEFAULT) - {'suites'}:
        if type(value[key]) is not int:
            raise ValueError('integer setting required: ' + key)
    if not (0 <= value['seed'] < 2**32 and 1 <= value['candidates_per_suite'] <= 32
            and 1 <= value['horizon_minutes'] <= 10
            and 1 <= value['oracle_product_cap'] <= 100
            and 1 <= value['oracle_assignment_limit'] <= 10000
            and 1 <= value['preprocessing_cap'] <= 100000):
        raise ValueError('unsupported bounded settings')
    if any(not 1 <= value[k] <= 16 for k in ('patient_count', 'surgeon_count', 'room_count')):
        raise ValueError('count outside this implementation profile 1..16')
    suites = value['suites']
    if type(suites) is not list or not suites or any(type(s) is not str or s not in SUITES for s in suites) or len(set(suites)) != len(suites):
        raise ValueError('unique supported suite names required')
    if len(suites) * value['candidates_per_suite'] > 128:
        raise ValueError('at most 128 candidates per bounded build')
    if value['patient_count'] * value['room_count'] * 1440 > value['preprocessing_cap']:
        raise ValueError('minute-domain preprocessing bound')
    return deepcopy(value)


def candidate(config, suite, ordinal):
    # Independent per-candidate RNG avoids order-dependent acceptance sampling.
    rng = random.Random(int(sha(canonical([VERSION, config['seed'], suite, ordinal])), 16))
    h = config['horizon_minutes']
    fragmented = suite in ('fragmented_gap', 'combined_constraints') and h >= 3
    budgets = suite in ('eligibility_budget', 'combined_constraints')
    gaps = suite in ('fragmented_gap', 'combined_constraints')
    optional = suite in ('optional_load', 'combined_constraints')
    def resource(name):
        mid = h // 2
        windows = [[0, mid], [mid + 1, h]] if fragmented and mid + 1 < h else [[0, h]]
        return dict(id=name, gap=rng.randrange(2) if gaps else 0,
                    budgets=[rng.randint(1, h) if budgets else h], calendar=[windows])
    rooms = [resource('r'+str(n)) for n in range(config['room_count'])]
    surgeons = [resource('s'+str(n)) for n in range(config['surgeon_count'])]
    patients = []
    for n in range(config['patient_count']):
        duration = rng.randint(1, min(3, h))
        release = rng.randint(0, h-duration)
        due = min(h, release+duration+rng.randrange(2))
        eligible = ['r0'] if suite == 'scarcity_contention' else sorted(rng.sample(
            [r['id'] for r in rooms], rng.randint(1, min(2, len(rooms)))))
        patients.append(dict(id='j'+str(n), mandatory=(n == 0 or not optional or rng.random() < .65),
                             surgeon='s'+str(n % len(surgeons)), duration=duration,
                             release=release, due=due, eligible_rooms=eligible,
                             priority=1, emergency=False))
    return dict(schema_version='1.1', days=1, day_minutes=1440,
                rooms=rooms, surgeons=surgeons, patients=patients)


def validate(instance, config):
    config = settings(config)
    errors = schema_errors(instance)
    if errors:
        return dict(admission='rejected', reason='schema', diagnostics=errors)
    if (instance['days'] != 1 or len(instance['patients']) != config['patient_count']
            or len(instance['rooms']) != config['room_count']
            or len(instance['surgeons']) != config['surgeon_count']):
        return dict(admission='rejected', reason='profile_shape')
    for resource in instance['rooms']+instance['surgeons']:
        if (len(resource['calendar'][0]) > 2
                or any(b > config['horizon_minutes'] for a,b in resource['calendar'][0])):
            return dict(admission='rejected', reason='calendar_profile')
    bound = 1
    for p in instance['patients']:
        if p['mandatory']:
            bound *= max(0, p['due']-p['release']-p['duration']+1)*len(p['eligible_rooms'])
    if bound > config['oracle_product_cap']:
        return dict(admission='rejected', reason='product_bound', product_upper_bound=bound)
    raw = render(instance)
    if parse(raw) != instance:
        raise ValueError('raw roundtrip mismatch')
    text = derive(raw)
    oracle = enumerate_schedules(instance, limit=config['oracle_assignment_limit'])
    if not oracle.get('complete'):
        return dict(admission='quarantined', reason='oracle_UNKNOWN', gold_label='UNKNOWN', oracle=oracle)
    for witness in oracle['solutions']:
        if check_schedule(instance, witness):
            raise ValueError('oracle/checker contradiction')
    gold = oracle['status']
    try:
        tool = CSPAdapter().invoke({'instance': deepcopy(instance)})
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        tool = dict(status='UNKNOWN', reason='tool_error', diagnostic=type(error).__name__)
    witness = oracle['solutions'][0] if gold == 'FEASIBLE' else None
    certificate = tool.get('certificate')
    certified = tool.get('status') == 'INFEASIBLE' and check_certificate(instance, certificate)
    valid_tool = ((gold == 'FEASIBLE' and tool.get('status') == 'FEASIBLE'
                   and not check_schedule(instance, tool.get('schedule')))
                  or (gold == 'INFEASIBLE' and certified))
    use = 'evidence_eligible' if gold == 'FEASIBLE' or certified else 'validation_only'
    return dict(admission='accepted' if valid_tool else 'quarantined',
                reason='validated' if valid_tool else 'required_tool_validation_unresolved_or_contradictory',
                gold_label=gold, proposed_use=use, product_upper_bound=bound,
                raw_text_sha256=sha(raw), text_sha256=sha(text), text=text,
                witness=witness, certificate=certificate if certified else None,
                oracle=dict(complete=True, examined=oracle['examined'],
                            solution_count=len(oracle['solutions'])), tool=tool)


def factors(i):
    return dict(room_gap=any(r['gap'] > 0 for r in i['rooms']),
                surgeon_gap=any(r['gap'] > 0 for r in i['surgeons']),
                fragmented=any(len(r['calendar'][0]) > 1 for r in i['rooms']+i['surgeons']),
                optional=any(not p['mandatory'] for p in i['patients']),
                flexible=any(len(p['eligible_rooms']) > 1 for p in i['patients']),
                budget_bottleneck=any(r['budgets'][0] < sum(p['duration'] for p in i['patients'] if p['mandatory']) for r in i['rooms']))


def build(value, destination):
    config = settings(value)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('preserve existing outputs')
    began = time.monotonic()
    records = []
    for suite in config['suites']:
        for ordinal in range(config['candidates_per_suite']):
            if time.monotonic()-began > 40:
                raise TimeoutError('bounded build stopped before export')
            i = candidate(config, suite, ordinal)
            v = validate(i, config)
            records.append(dict(case_id=sha(canonical([VERSION, suite, ordinal, i]))[:24],
                                suite=suite, ordinal=ordinal, instance=i, factors=factors(i),
                                construction_group='related-development-not-holdout', **v))
    accepted = [r for r in records if r['admission'] == 'accepted']
    model = ''.join(canonical(dict(case_id=r['case_id'], text=r['text']))+'\n' for r in accepted)
    gold = ''.join(canonical({k:v for k,v in r.items() if k != 'text'})+'\n' for r in accepted)
    diagnostic = ''.join(canonical(r)+'\n' for r in records if r['admission'] != 'accepted')
    coverage = dict(version=VERSION, settings=config, candidates=len(records),
                    admissions=dict(Counter(r['admission'] for r in records)),
                    labels=dict(Counter(r.get('gold_label', 'unlabelled') for r in records)),
                    accepted_labels=dict(Counter(r['gold_label'] for r in accepted)),
                    proposed_uses=dict(Counter(r.get('proposed_use', 'unassigned') for r in records)),
                    accepted_factor_counts={k:sum(r['factors'][k] for r in accepted) for k in factors(records[0]['instance'])},
                    all_factor_counts={k:sum(r['factors'][k] for r in records) for k in factors(records[0]['instance'])})
    pairs=list(combinations(sorted(factors(records[0]['instance'])), 2))
    coverage['accepted_interactions']={a+'+'+b:sum(r['factors'][a] and r['factors'][b] for r in accepted) for a,b in pairs}
    coverage['missing_accepted_interactions']=[k for k,v in coverage['accepted_interactions'].items() if not v]
    files={'model.jsonl':model, 'gold.jsonl':gold, 'diagnostics.jsonl':diagnostic,
           'coverage.json':canonical(coverage)+'\n'}
    source_paths=['development_suites.py', 'tier_a_input_view.py', 'surgerybench/temporal_csp.py',
                  'surgerybench/temporal_check.py', 'surgerybench/checker.py',
                  'surgerybench/temporal_oracle.py', 'surgerybench/temporal_text.py']
    root=Path(__file__).resolve().parent
    manifest=dict(python_version=platform.python_version(),
                  baseline_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
                  version=VERSION, source='original_synthetic', split='development_review',
                  old_harness_compatible=False, oracle_revision=ORACLE,
                  adapter_revision=CSPAdapter.revision, adapter_entrypoint='CSPAdapter.invoke',
                  adapter_limits=dict(max_nodes=100000, seconds=2),
                  source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in source_paths},
                  files={p:sha(s) for p,s in files.items()},
                  sampling='independent per-candidate Python random.Random with SHA256-derived seed',
                  lineage='related to existing pilot/Tier A/tests; not independent holdout')
    files['manifest.json']=canonical(manifest)+'\n'
    destination.mkdir()
    for name, content in files.items():
        (destination/name).write_text(content)
    return coverage


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination')
    parser.add_argument('--settings', required=True)
    args=parser.parse_args()
    print(canonical(build(json.loads(Path(args.settings).read_text()), args.destination)))
