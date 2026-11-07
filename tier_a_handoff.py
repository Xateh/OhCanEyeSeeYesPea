"""Read-only frozen Tier A inventory; privileged evaluator metadata, never prompts."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from surgerybench.tier_a_audit import audit
from tier_a_contract import CORPUS, HASHES, strict_json


def inventory(directory):
    directory = Path(directory)
    receipt = audit(directory)
    if receipt['version'] != CORPUS or receipt['instances'] != 15:
        raise ValueError('unsupported corpus')
    hashes = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
              for name in HASHES}
    if hashes != HASHES:
        raise ValueError('frozen export identity mismatch')
    rows = [strict_json(line) for line in
            (directory / 'tier-a-gold.jsonl').read_text().splitlines()]
    cases = []
    for row in rows:
        i = row['instance']
        oracle = row['evidence']['oracle']
        cases.append(dict(
            case_id=row['case_id'], family=row['family'], split=row['split'],
            label=row['label'], certification=row['certification'],
            use=('validation_only' if row['certification'] == 'oracle_only'
                 else 'evidence_eligible_development'),
            tags=list(row['tags']), jobs=len(i['patients']),
            rooms=len(i['rooms']), surgeons=len(i['surgeons']),
            product_upper_bound=oracle['product_upper_bound'],
            oracle_complete=oracle['complete']))
    groups = {}
    for case in cases:
        groups.setdefault(case['family'], []).append(case['case_id'])
    return dict(
        inventory_version='tier-a-dataset-handoff-v1', corpus_version=CORPUS,
        audience='privileged_evaluator_only', export_sha256=hashes,
        audit=receipt, cases=cases, construction_groups=groups,
        use_counts=dict(Counter(c['use'] for c in cases)),
        tag_counts=dict(sorted(Counter(t for c in cases for t in c['tags']).items())),
        split_policy='provisional_review; no holdout or cross-corpus independence',
        difficulty_policy='structural descriptors only; no model difficulty claim')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    print(json.dumps(inventory(parser.parse_args().directory), sort_keys=True, indent=2))
