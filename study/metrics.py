"""Turn harness rows into counts. Failures are kept in every denominator."""
from collections import Counter
import json
from math import comb, sqrt
from statistics import median
from .accounting import row_cost, cost_summary

ARMS = ('no_tools', 'csp')
Z_95 = 1.96


def wilson(successes, total):
    """95% Wilson interval: stays sensible for tiny samples and for 0% or 100%."""
    if total == 0:
        return (0.0, 1.0)
    rate = successes / total
    denominator = 1 + Z_95 ** 2 / total
    centre = (rate + Z_95 ** 2 / (2 * total)) / denominator
    spread = Z_95 * sqrt(rate * (1 - rate) / total + Z_95 ** 2 / (4 * total ** 2)) / denominator
    return (max(0.0, centre - spread), 1.0 if successes == total else min(1.0, centre + spread))


def mcnemar_exact(only_first, only_second):
    """Two-sided exact test using only the pairs where the two arms disagreed."""
    disagreements = only_first + only_second
    if disagreements == 0:
        return 1.0
    tail = sum(comb(disagreements, k) for k in range(min(only_first, only_second) + 1))
    return min(1.0, 2 * tail / 2 ** disagreements)


def succeeded(row):
    score = row['score']
    return bool(score['feasible_schedule_success'] or score['infeasible_certified_success'])


def failure_kind(row):
    score = row['score']
    status = row['output'].get('status') if isinstance(row['output'], dict) else None
    if succeeded(row):
        return 'success'
    if row['parsing_or_provider_error']:
        return 'provider_error'
    if score['output_error']:
        return 'output_error'
    if score['unknown']:
        return 'unknown'
    if score['feasible_schedule_success'] is False:
        return 'invalid_schedule' if status == 'FEASIBLE' else 'wrong_decision'
    return 'invalid_certificate' if score['infeasible_decision_correct'] else 'wrong_decision'


def normalize_instance(instance):
    """Ignore the order items are listed in, because that changes nothing about the problem."""
    if not isinstance(instance, dict):
        return instance
    sort_ids = lambda items: sorted(items, key=lambda item: str(item.get('id')))
    patients = [{**p, 'eligible_rooms': sorted(p.get('eligible_rooms', []))} for p in sort_ids(instance.get('patients', []))]
    return {**instance, 'patients': patients, 'rooms': sort_ids(instance.get('rooms', [])),
            'surgeons': sort_ids(instance.get('surgeons', []))}


def translation_status(row, gold_instance):
    if not row['tool_calls']:
        return 'no_tool_call'
    arguments = row['tool_calls'][-1]['arguments']
    submitted = arguments.get('instance') if isinstance(arguments, dict) else None
    try:
        return 'exact' if normalize_instance(submitted) == normalize_instance(gold_instance) else 'mismatch'
    except (AttributeError, TypeError):
        return 'mismatch'


def rate(successes, total):
    return [successes, total, *wilson(successes, total)]


def count(rows, field):
    scored = [r['score'][field] for r in rows if r['score'][field] is not None]
    return rate(sum(map(bool, scored)), len(scored))


def summarize_arm(rows):
    usage = [r['token_usage'] for r in rows]
    known = bool(usage) and all(u is not None for u in usage)
    return {'runs': len(rows), 'overall_success': rate(sum(map(succeeded, rows)), len(rows)),
            'feasible_success': count(rows, 'feasible_schedule_success'),
            'decision_correct': count(rows, 'infeasible_decision_correct'),
            'certified_success': count(rows, 'infeasible_certified_success'),
            'failure_kinds': dict(sorted(Counter(map(failure_kind, rows)).items())),
            'tool_errors': sum(r['tool_error'] for r in rows),
            'median_latency_seconds': median(r['latency_seconds'] for r in rows) if rows else None,
            'tokens_total': sum(u['input_tokens'] + u['output_tokens'] for u in usage) if known else None,
            **cost_summary(rows)}


def paired_buckets(rows, expected_pairs=None):
    if any(type(r.get('case_id')) is not str or type(r.get('repetition')) is not int or r['repetition']<0 or type(r.get('arm')) is not str or r['arm'] not in ARMS for r in rows):
        raise ValueError('invalid paired receipt routing')
    slots=[(r['case_id'],r['repetition'],r['arm']) for r in rows]
    if len(set(slots))!=len(slots):raise ValueError('duplicate paired receipt slot')
    pairs = {}
    for r in rows:
        key = (r['case_id'], r['repetition'])
        pairs[key] = {**pairs.get(key, {}), r['arm']: succeeded(r)}
    if expected_pairs is not None:
        if not set(pairs)<=set(expected_pairs):raise ValueError('unplanned pair')
        for key in expected_pairs:pairs.setdefault(key,{})
    buckets = Counter(both=0, no_tools_only=0, csp_only=0, neither=0, incomplete=0)
    for pair in pairs.values():
        if set(pair) != set(ARMS):
            buckets['incomplete'] += 1
        elif pair['no_tools'] and pair['csp']:
            buckets['both'] += 1
        elif pair['no_tools']:
            buckets['no_tools_only'] += 1
        elif pair['csp']:
            buckets['csp_only'] += 1
        else:
            buckets['neither'] += 1
    return dict(buckets)


def theme_of(row):
    return row['family'].rsplit('-', 1)[0].split('v1-')[-1]


def summarize(rows, gold):
    by_arm = {arm: [r for r in rows if r['arm'] == arm] for arm in ARMS}
    translations = Counter(translation_status(r, gold[r['case_id']]['instance']) for r in by_arm['csp'])
    themes = sorted({theme_of(r) for r in rows})
    buckets = paired_buckets(rows)
    return {'arms': {arm: summarize_arm(arm_rows) for arm, arm_rows in by_arm.items()},
            'by_theme': {t: {arm: rate(sum(succeeded(r) for r in arm_rows if theme_of(r) == t),
                                       sum(theme_of(r) == t for r in arm_rows))
                             for arm, arm_rows in by_arm.items()} for t in themes},
            'translation': dict(sorted(translations.items())), 'pairs': buckets,
            'mcnemar_p': mcnemar_exact(buckets['no_tools_only'], buckets['csp_only'])}


def to_json(summary):
    return json.dumps(summary, indent=2, sort_keys=True) + '\n'
