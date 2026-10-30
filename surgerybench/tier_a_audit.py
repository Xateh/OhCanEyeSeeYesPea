"""Read-only Tier A v1 audit; does not import the generator, DFS or old harness."""
import argparse
from collections import Counter
import hashlib
import json
from math import prod
from pathlib import Path

from .common import canonical, digest
from .temporal_check import schema_errors, check_schedule, check_certificate
from .temporal_oracle import enumerate_schedules
from .temporal_text import parse, render

VERSION = 'tier-a-original-synthetic-v1'
BASE = 'e3f9dbe19381a43bd39c64343ce32966d15dce9e'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_instance(i):
    """Cheap declared envelope check before oracle minute-domain preprocessing."""
    require(isinstance(i, dict), 'instance must be object')
    require(i.get('days') == 1 and type(i['days']) is int, 'one day only')
    for kind in ('patients', 'rooms', 'surgeons'):
        require(isinstance(i.get(kind), list) and 1 <= len(i[kind]) <= 2,
                'resource/job count outside envelope')
    require(not schema_errors(i), 'invalid temporal schema')
    for p in i['patients']:
        require(0 <= p['release'] <= p['due'] <= 10, 'time bounds exceed 10')
        require(1 <= p['duration'] <= 10 and len(p['eligible_rooms']) <= 2,
                'duration/eligibility outside envelope')
    for kind in ('rooms', 'surgeons'):
        for r in i[kind]:
            require(r['gap'] <= 10 and r['budgets'][0] <= 10, 'resource bound exceeds 10')
            require(len(r['calendar'][0]) <= 2, 'too many windows')
            require(all(b <= 10 for a, b in r['calendar'][0]), 'window exceeds 10')
    bound = prod((p['due'] - p['release'] - p['duration'] + 1)
                 * len(p['eligible_rooms']) if p['due'] - p['release'] >= p['duration'] else 0
                 for p in i['patients'] if p['mandatory'])
    require(bound <= 100, 'assignment product exceeds 100')
    return bound


def audit(directory):
    """Validate hashes, separation, lineage and independent finite evidence."""
    try:
        return _audit(Path(directory))
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError('malformed Tier A package') from exc


def _audit(directory):
    names = {'tier-a-model.jsonl', 'tier-a-gold.jsonl', 'coverage.json', 'manifest.json'}
    require({p.name for p in directory.iterdir()} == names, 'unexpected package files')
    for name in names:
        p = directory / name
        require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 1048576,
                'file outside audit size/type bounds')
    manifest = json.loads((directory / 'manifest.json').read_text())
    require(set(manifest) == {'version', 'cases', 'old_harness_compatible', 'files'}, 'manifest shape')
    require(manifest['version'] == VERSION and manifest['old_harness_compatible'] is False, 'format version')
    require(set(manifest['files']) == names - {'manifest.json'}, 'manifest file set')
    for name, sha in manifest['files'].items():
        require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha, 'file hash mismatch')
    def rows(name):
        return [json.loads(s) for s in (directory / name).read_text().splitlines()]
    model, gold = rows('tier-a-model.jsonl'), rows('tier-a-gold.jsonl')
    require(type(manifest['cases']) is int and 1 <= len(gold) == len(model) == manifest['cases'] <= 24,
            'case count outside envelope')
    coverage = json.loads((directory / 'coverage.json').read_text())
    require(set(coverage) == {'version', 'split_policy', 'cases'}, 'coverage shape')
    require(coverage['version'] == VERSION and coverage['split_policy'] ==
            'provisional_review_only_no_independence_claim', 'provisional split policy')
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob('*.py'))}
    ids, families, ledger, counts = set(), {}, [], Counter()
    max_bound = max_examined = 0
    for m, g in zip(model, gold):
        require(set(m) == {'case_id', 'text'}, 'model/gold separation')
        require(set(g) == {'case_id', 'version', 'family', 'split', 'tags', 'label',
                'certification', 'arithmetic', 'instance', 'instance_sha256',
                'text_sha256', 'lineage', 'evidence'}, 'gold shape')
        require(isinstance(g['case_id'], str) and m['case_id'] == g['case_id']
                and g['case_id'] not in ids, 'duplicate/mismatched case IDs')
        ids.add(g['case_id'])
        require(g['version'] == VERSION, 'gold version')
        require(g['lineage'] == dict(source='original_synthetic', method='hand_designed',
                reviewed_base=BASE, code_sha256=code), 'lineage mismatch')
        require(isinstance(g['arithmetic'], str) and bool(g['arithmetic'].strip()), 'missing arithmetic anchor')
        require(isinstance(g['family'], str) and bool(g['family']), 'missing family')
        require(isinstance(g['tags'], list) and g['tags'] and
                all(isinstance(t, str) and t for t in g['tags']), 'invalid coverage tags')
        require(g['split'] == 'provisional_review', 'unapproved split')
        require(families.setdefault(g['family'], g['split']) == g['split'], 'relative split leakage')
        i = g['instance']
        bound = validate_instance(i)
        require(digest(i) == g['instance_sha256'], 'instance hash mismatch')
        require(hashlib.sha256(m['text'].encode()).hexdigest() == g['text_sha256'], 'text hash mismatch')
        require(parse(m['text']) == i and render(i) == m['text'], 'text/instance mismatch')
        oracle = enumerate_schedules(i, limit=10000)
        require(oracle.get('complete') is True and oracle['status'] == g['label'], 'unresolved/wrong label')
        require(len(oracle['solutions']) <= 100 and oracle['examined'] <= bound, 'oracle envelope mismatch')
        e = g['evidence']
        require(set(e) == {'witness', 'optional_witness', 'certificate', 'oracle'}, 'evidence shape')
        require(e['oracle'] == dict(complete=True, limit=10000, product_upper_bound=bound,
                examined=oracle['examined'], solution_count=len(oracle['solutions'])), 'oracle receipt mismatch')
        for witness in oracle['solutions']:
            require(not check_schedule(i, witness), 'oracle witness rejected by independent checker')
        if g['label'] == 'FEASIBLE':
            require(g['certification'] == 'not_applicable' and e['certificate'] is None, 'feasible certification')
            require(isinstance(e['witness'], list) and not check_schedule(i, e['witness']), 'invalid/missing witness')
        else:
            require(g['label'] == 'INFEASIBLE' and e['witness'] is None
                    and e['optional_witness'] is None, 'negative evidence shape')
            if g['certification'] == 'pair_order_impossible':
                require(check_certificate(i, e['certificate']), 'invalid compact certificate')
            else:
                require(g['certification'] == 'oracle_only' and e['certificate'] is None,
                        'unsupported certification')
        if e['optional_witness'] is not None:
            require(not check_schedule(i, e['optional_witness']), 'invalid optional-present witness')
            optional = {p['id'] for p in i['patients'] if not p['mandatory']}
            require(bool(optional & {r['patient'] for r in e['optional_witness']}), 'optional witness omits optional jobs')
        counts[g['label'] + '/' + g['certification']] += 1
        max_bound, max_examined = max(max_bound, bound), max(max_examined, oracle['examined'])
        ledger.append({k: g[k] for k in ('case_id', 'family', 'split', 'tags', 'label', 'certification', 'arithmetic')})
    require(coverage['cases'] == ledger, 'coverage ledger mismatch')
    return dict(audit='PASS', version=VERSION, instances=len(gold), families=len(families),
                complete_oracle_checks=len(gold), counts=dict(sorted(counts.items())),
                max_product_upper_bound=max_bound, max_examined=max_examined)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    print(canonical(audit(parser.parse_args().directory)))
