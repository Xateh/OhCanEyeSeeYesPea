"""Frozen offline scoring proposal v1. No runner, provider, tool invocation or writes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from surgerybench.tier_a_audit import audit
from surgerybench.temporal_check import check_schedule, check_certificate

CONTRACT = 'tier-a-offline-contract-proposal-v1'
CORPUS = 'tier-a-original-synthetic-v1'
ARMS = ['no_tools', 'csp']
HASHES = {
    'coverage.json': '4539269cfd31cd52ef720ff111d67b16cd3d2edee2dc17d4a5f747aac4d1196a',
    'manifest.json': '2d7ddcfcdec68036edff952c661837284695fd98450e5965e308cbbf235eac3a',
    'tier-a-gold.jsonl': '357b1efde665c5d9acfc4a7fc270b899a7fee6e1d4465bebcfa8afe64f49b78b',
    'tier-a-model.jsonl': 'b4ccc755542257f25e2b61f4167de7e71327c6e7d51460841c20338588cc4385'}


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def canonical(value):
    def validate(node):
        require(type(node) in (dict, list, str, int, float, bool, type(None)),
                'normalized value must use JSON built-in types only')
        if type(node) is dict:
            require(all(type(key) is str for key in node), 'JSON object keys must be strings')
            for item in node.values():
                validate(item)
        elif type(node) is list:
            for item in node:
                validate(item)
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def preflight(directory, plan):
    """Re-audit and pin the exact reviewed package before any result or prompt."""
    directory = Path(directory)
    audited = audit(directory)
    require(audited['version'] == CORPUS and audited['instances'] == 15,
            'unsupported audited corpus/version')
    blobs = {name: (directory / name).read_bytes() for name in HASHES}
    for name, expected in HASHES.items():
        require(hashlib.sha256(blobs[name]).hexdigest() == expected,
                'frozen corpus hash mismatch: ' + name)
    gold = [strict_json(s) for s in blobs['tier-a-gold.jsonl'].decode().splitlines()]
    model = [strict_json(s) for s in blobs['tier-a-model.jsonl'].decode().splitlines()]
    require(type(plan) is dict and set(plan) == {
        'contract_version', 'corpus_version', 'case_use', 'repetitions', 'arms'}, 'plan keys')
    require(plan['contract_version'] == CONTRACT and plan['corpus_version'] == CORPUS,
            'unsupported plan version')
    require(type(plan['repetitions']) is int and 1 <= plan['repetitions'] <= 10,
            'explicit repetitions must be integer 1..10')
    require(type(plan['arms']) is list and plan['arms'] == ARMS, 'fixed matched arm set/order')
    expected_use = {g['case_id']: ('validation_only' if g['certification'] == 'oracle_only'
                                 else 'eligible') for g in gold}
    require(type(plan['case_use']) is dict and plan['case_use'] == expected_use,
            'case-use manifest must cover all 15; six oracle-only negatives excluded')
    require([g['case_id'] for g in gold] == [m['case_id'] for m in model], 'join order')
    require(all(set(m) == {'case_id', 'text'} and type(m['text']) is str for m in model),
            'model-only schema')
    eligible = [g for g in gold if expected_use[g['case_id']] == 'eligible']
    require(len(eligible) == 9 and sum(g['label'] == 'FEASIBLE' for g in eligible) == 7,
            'frozen eligible composition')
    return gold, model


def model_inputs(directory, plan):
    """Only text crosses the proposed model-input boundary; no IDs or gold."""
    gold, model = preflight(directory, plan)
    eligible = {g['case_id'] for g in gold if g['certification'] != 'oracle_only'}
    return tuple(m['text'] for m in model if m['case_id'] in eligible)


def output_verdict(instance, raw, normalized, normalization_errors):
    """Strict shape plus intended-instance evidence. No coercion/repair."""
    errors = list(normalization_errors)
    parsed = None
    try:
        require(type(raw) is str and len(raw.encode()) <= 65536, 'raw output must be JSON text <=64KiB')
        parsed = strict_json(raw)
        require(canonical(parsed) == canonical(normalized), 'raw/normalized mismatch')
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        errors.append(str(exc))
    status = parsed.get('status') if type(parsed) is dict and not errors else None
    status = status if type(status) is str else None
    valid = False
    if not errors:
        if status == 'FEASIBLE':
            if set(parsed) != {'status', 'schedule'} or type(parsed['schedule']) is not list:
                errors.append('FEASIBLE requires only status and non-null schedule list')
            else:
                errors.extend(check_schedule(instance, parsed['schedule']))
                valid = not errors
        elif status == 'INFEASIBLE':
            if set(parsed) != {'status', 'certificate'} or type(parsed['certificate']) is not dict:
                errors.append('INFEASIBLE requires only status and non-null certificate object')
            elif not check_certificate(instance, parsed['certificate']):
                errors.append('unsupported or invalid intended-instance certificate')
            else:
                valid = True
        elif status == 'UNKNOWN':
            if set(parsed) != {'status'}:
                errors.append('UNKNOWN permits status only')
        else:
            errors.append('unsupported or missing status/object')
    return dict(status=status, evidence_valid=valid, output_error=bool(errors), diagnostics=errors)


def summarize(rows):
    """All denominators are planned rows, including missing and failed receipts."""
    def metric(key, group=rows):
        return dict(numerator=sum(bool(r[key]) for r in group), denominator=len(group))
    feasible = [r for r in rows if r['gold_label'] == 'FEASIBLE']
    negative = [r for r in rows if r['gold_label'] == 'INFEASIBLE']
    return dict(planned=len(rows), attempted=sum(not r['missing'] for r in rows),
                completed=sum(r['completed'] for r in rows), missing=sum(r['missing'] for r in rows),
                incomplete=any(not r['completed'] for r in rows),
                feasible_schedule_success=metric('feasible_success', feasible),
                negative_decision_agreement=metric('decision_agreement', negative),
                negative_certified_success=metric('certified_success', negative),
                evidence_backed_task_success=metric('success'), unknown_rate=metric('unknown'),
                output_error_rate=metric('output_error'), provider_error_rate=metric('provider_error'),
                tool_error_rate=metric('tool_error'), missing_rate=metric('missing'))


def evaluate(directory, plan, receipts):
    """Score synthetic recorded attempts only; no I/O beyond package reads."""
    gold, _ = preflight(directory, plan)
    eligible = [g for g in gold if g['certification'] != 'oracle_only']
    keys = {(g['case_id'], rep, arm) for g in eligible
            for rep in range(plan['repetitions']) for arm in ARMS}
    require(type(receipts) is list and len(receipts) <= len(keys), 'receipt list/size')
    indexed = {}
    fields = {'case_id', 'repetition', 'arm', 'raw_output', 'normalized_output',
              'normalization_errors', 'provider_error', 'tool_error', 'termination'}
    for receipt in receipts:
        require(type(receipt) is dict and set(receipt) == fields, 'receipt keys')
        require(type(receipt['case_id']) is str and type(receipt['arm']) is str
                and type(receipt['repetition']) is int, 'receipt routing types')
        key = (receipt['case_id'], receipt['repetition'], receipt['arm'])
        require(key in keys and key not in indexed, 'unplanned/excluded or duplicate attempt')
        require(type(receipt['normalization_errors']) is list and
                all(type(e) is str and e for e in receipt['normalization_errors']), 'normalization diagnostics')
        require(type(receipt['provider_error']) is bool and type(receipt['tool_error']) is bool,
                'operational flags must be booleans')
        term = receipt['termination']
        require(type(term) is str and term in ('final', 'abstained', 'provider_error', 'tool_error'),
                'termination enum')
        require(term != 'provider_error' or receipt['provider_error'], 'provider termination flag')
        require(term != 'tool_error' or receipt['tool_error'], 'tool termination flag')
        if term == 'abstained':
            require(receipt['raw_output'] is None and receipt['normalized_output'] is None
                    and not receipt['normalization_errors'] and not receipt['provider_error']
                    and not receipt['tool_error'], 'abstention requires explicit nulls and no error flags')
        indexed[key] = receipt
    rows = []
    for g in eligible:
        for rep in range(plan['repetitions']):
            for arm in ARMS:
                key = (g['case_id'], rep, arm)
                receipt = indexed.get(key)
                row = dict(case_id=g['case_id'], repetition=rep, arm=arm, family=g['family'],
                           gold_label=g['label'], missing=receipt is None, completed=False,
                           success=False, feasible_success=False, certified_success=False,
                           decision_agreement=False, unknown=False, output_error=False,
                           provider_error=False, tool_error=False, diagnostics=[], receipt=deepcopy(receipt))
                if receipt is not None:
                    row.update(provider_error=receipt['provider_error'], tool_error=receipt['tool_error'])
                    row['completed'] = receipt['termination'] in ('final', 'abstained')
                    if receipt['termination'] == 'abstained':
                        verdict = dict(status='UNKNOWN', evidence_valid=False, output_error=False,
                                       diagnostics=['explicit metadata abstention; no infeasibility claim'])
                    else:
                        verdict = output_verdict(g['instance'], receipt['raw_output'],
                                                 receipt['normalized_output'], receipt['normalization_errors'])
                    row.update(output_error=verdict['output_error'], diagnostics=verdict['diagnostics'],
                               unknown=verdict['status'] == 'UNKNOWN')
                    row['decision_agreement'] = g['label'] == 'INFEASIBLE' and verdict['status'] == 'INFEASIBLE'
                    operational = row['provider_error'] or row['tool_error'] or not row['completed']
                    backed = verdict['evidence_valid'] and not operational
                    row['feasible_success'] = backed and g['label'] == 'FEASIBLE' and verdict['status'] == 'FEASIBLE'
                    row['certified_success'] = backed and g['label'] == 'INFEASIBLE' and verdict['status'] == 'INFEASIBLE'
                    row['success'] = row['feasible_success'] or row['certified_success']
                rows.append(row)
    by_arm = {arm: summarize([r for r in rows if r['arm'] == arm]) for arm in ARMS}
    families = {family: {arm: summarize([r for r in rows if r['family'] == family and r['arm'] == arm])
                        for arm in ARMS} for family in sorted({g['family'] for g in eligible})}
    pairs = dict(both_success=0, no_tools_only=0, csp_only=0, neither_success=0, incomplete=0)
    lookup = {(r['case_id'], r['repetition'], r['arm']): r for r in rows}
    for g in eligible:
        for rep in range(plan['repetitions']):
            a, b = (lookup[g['case_id'], rep, arm] for arm in ARMS)
            if not a['completed'] or not b['completed']:
                bucket = 'incomplete'
            elif a['success'] and b['success']:
                bucket = 'both_success'
            elif a['success']:
                bucket = 'no_tools_only'
            elif b['success']:
                bucket = 'csp_only'
            else:
                bucket = 'neither_success'
            pairs[bucket] += 1
    revisions = dict(consumer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     corpus_files_sha256=dict(HASHES), checker_package_sha256=deepcopy(gold[0]['lineage']['code_sha256']))
    return dict(contract_version=CONTRACT, status='offline_software_proposal_not_protocol_acceptance',
                corpus_version=CORPUS, plan=deepcopy(plan), by_arm=by_arm, by_family=families,
                pairs=pairs, planned_pairs=9 * plan['repetitions'], rows=rows, revisions=revisions,
                validation_only_excluded=[g['case_id'] for g in gold if g['certification'] == 'oracle_only'])
