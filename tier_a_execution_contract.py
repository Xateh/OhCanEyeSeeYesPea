"""Offline execution-contract preparation only: never authorizes or starts a run."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import math
import re
from pathlib import Path

import tier_a_contract as scorer
from surgerybench.temporal_csp import TOOL, REVISION

VERSION = 'tier-a-execution-preparation-proposal-v1'
require = scorer.require


def bindings(shared_prompt, output_prompt):
    def prompt_hash(text):
        require(type(text) is str and 0 < len(text.encode()) <= 65536, 'explicit bounded prompt text required')
        return hashlib.sha256(text.encode()).hexdigest()
    return dict(consumer_sha256=hashlib.sha256(Path(scorer.__file__).read_bytes()).hexdigest(),
                execution_contract_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                shared_prompt_sha256=prompt_hash(shared_prompt), output_prompt_sha256=prompt_hash(output_prompt),
                tool_schema_sha256=hashlib.sha256(scorer.canonical(TOOL).encode()).hexdigest(),
                tool_revision=REVISION)


def identifier(value):
    return (type(value) is str and 1 <= len(value) <= 64 and value.isascii()
            and all(c.isalnum() or c in '_-' for c in value))


def revision(value):
    return (type(value) is str and bool(value.strip()) and len(value) <= 256
            and value.strip().lower() not in ('unknown', 'tbd', 'unresolved'))


def money(value, positive=False):
    require(type(value) is str and re.fullmatch(r'[0-9]{1,12}(?:\.[0-9]{1,8})?', value) is not None,
            'USD amount must be plain decimal text (<=12 whole/8 fractional digits)')
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('invalid decimal USD amount') from exc
    require(amount.is_finite() and (amount > 0 if positive else amount >= 0), 'invalid USD amount')
    return amount


def elapsed(value):
    if type(value) is int:
        return value >= 0  # integers are finite; avoid lossy/overflowing float conversion
    return type(value) is float and math.isfinite(value) and value >= 0


def budget_accounting(scored, receipts, violations, batch_violations):
    """Apply preparation-layer failures without changing evidence or losing slots."""
    recorded = {(r['scoring_receipt']['case_id'], 0, r['scoring_receipt']['arm']): r for r in receipts}
    for row in scored['rows']:
        slot = (row['case_id'], row['repetition'], row['arm'])
        receipt = recorded.get(slot)
        errors = list(violations.get(slot, [])) + (batch_violations if receipt else [])
        row['unadjusted_scorer_success'] = row['success']
        row['budget_violations'] = errors
        row['budget_error'] = bool(errors)
        complete = receipt is not None and receipt['usage'] is not None and receipt['spend_usd'] is not None
        row['budget_compliance'] = 'violated' if errors else 'within_reported_limits' if complete else 'unknown'
        if errors:
            row['success'] = row['feasible_success'] = row['certified_success'] = False
            row['diagnostics'].extend('execution budget violation: ' + e for e in errors)
    def summary(rows):
        result = scorer.summarize(rows)
        result['budget_error_rate'] = dict(numerator=sum(r['budget_error'] for r in rows), denominator=len(rows))
        return result
    scored['by_arm'] = {arm: summary([r for r in scored['rows'] if r['arm'] == arm]) for arm in scorer.ARMS}
    scored['by_family'] = {family: {arm: summary([r for r in scored['rows']
        if r['family'] == family and r['arm'] == arm]) for arm in scorer.ARMS} for family in scored['by_family']}
    pairs = dict(both_success=0, no_tools_only=0, csp_only=0, neither_success=0, incomplete=0)
    matched = {}
    for row in scored['rows']:
        matched.setdefault((row['case_id'], row['repetition']), {})[row['arm']] = row
    for pair in matched.values():
        a, b = (pair[arm] for arm in scorer.ARMS)
        bucket = ('incomplete' if not a['completed'] or not b['completed'] else
                  'both_success' if a['success'] and b['success'] else
                  'no_tools_only' if a['success'] else 'csp_only' if b['success'] else 'neither_success')
        pairs[bucket] += 1
    scored['pairs'] = pairs
    return scored


def validate(directory, manifest, receipts, shared_prompt, output_prompt):
    """Fail closed on missing pins/budgets or receipt violations; no network/writes."""
    pins = bindings(shared_prompt, output_prompt)
    fields = {'version', 'status', 'run_id', 'scoring_plan', 'corpus_hashes',
              'provider_revision', 'model_revision', 'limits'} | set(pins)
    require(type(manifest) is dict and set(manifest) == fields, 'manifest keys')
    require(manifest['version'] == VERSION and manifest['status'] == 'proposal_only', 'proposal version/status')
    require(identifier(manifest['run_id']), 'run_id must be explicit bounded identifier')
    require(manifest['corpus_hashes'] == scorer.HASHES, 'corpus export revision drift')
    for key, value in pins.items():
        require(manifest[key] == value, 'manifest revision drift: ' + key)
    for key in ('provider_revision', 'model_revision'):
        require(revision(manifest[key]), 'explicit provider/model revision required: ' + key)
    limits = manifest['limits']
    require(type(limits) is dict and set(limits) == {'tokens_per_attempt', 'wall_seconds_per_attempt',
            'spending_ceiling_usd', 'max_csp_calls'}, 'explicit limits required')
    require(type(limits['tokens_per_attempt']) is int and limits['tokens_per_attempt'] > 0,
            'positive explicit token limit required')
    require(elapsed(limits['wall_seconds_per_attempt']) and 0 < limits['wall_seconds_per_attempt'] <= 60,
            'positive explicit wall-clock limit <=60s required')
    ceiling = money(limits['spending_ceiling_usd'], positive=True)
    require(type(limits['max_csp_calls']) is int and limits['max_csp_calls'] == 4, 'proposed CSP cap must be four')
    gold, _ = scorer.preflight(directory, manifest['scoring_plan'])
    require(manifest['scoring_plan']['repetitions'] == 1, 'only proposed R=1 smoke envelope supported')
    eligible = {g['case_id'] for g in gold if g['certification'] != 'oracle_only'}
    require(type(receipts) is list and len(receipts) <= 18, 'at most 18 recorded synthetic arm-attempts')
    receipt_fields = {'attempt_id', 'run_id', 'provider_revision', 'model_revision', 'scoring_receipt',
                      'elapsed_seconds', 'usage', 'usage_unknown_reason', 'spend_usd',
                      'spend_unknown_reason', 'termination_cause', 'tool_calls', 'tool_count'} | set(pins)
    seen_ids, seen_slots, scoring_receipts = set(), set(), []
    violations = {}
    known_spend = Decimal('0')
    usage_known = spend_known = 0
    termination_map = {'completed': 'final', 'abstained': 'abstained',
                       'provider_error': 'provider_error', 'provider_timeout': 'provider_error',
                       'tool_error': 'tool_error', 'tool_timeout': 'tool_error'}
    for receipt in receipts:
        require(type(receipt) is dict and set(receipt) == receipt_fields, 'receipt extension keys')
        aid = receipt['attempt_id']
        require(identifier(aid) and aid not in seen_ids, 'missing/duplicate attempt_id')
        seen_ids.add(aid)
        for key in ('run_id', 'provider_revision', 'model_revision', *pins):
            require(receipt[key] == manifest[key], 'receipt revision/run drift: ' + key)
        scoring = receipt['scoring_receipt']
        require(type(scoring) is dict and type(scoring.get('case_id')) is str
                and scoring['case_id'] in eligible and type(scoring.get('repetition')) is int
                and scoring['repetition'] == 0 and type(scoring.get('arm')) is str
                and scoring['arm'] in scorer.ARMS, 'unplanned/excluded scoring slot')
        slot = (scoring['case_id'], scoring['repetition'], scoring['arm'])
        require(slot not in seen_slots, 'duplicate planned scoring slot/retry')
        seen_slots.add(slot)
        violations[slot] = []
        cause = receipt['termination_cause']
        require(type(cause) is str and cause in termination_map and
                termination_map[cause] == scoring.get('termination'), 'termination cause mismatch')
        require(elapsed(receipt['elapsed_seconds']), 'malformed elapsed time')
        if receipt['elapsed_seconds'] > limits['wall_seconds_per_attempt']:
            violations[slot].append('wall_clock_limit')
        usage = receipt['usage']
        if usage is None:
            require(type(receipt['usage_unknown_reason']) is str and bool(receipt['usage_unknown_reason'].strip()),
                    'unknown token counts require reason')
        else:
            require(type(usage) is dict and set(usage) == {'input_tokens', 'output_tokens'} and
                    all(type(v) is int and v >= 0 for v in usage.values()) and
                    receipt['usage_unknown_reason'] is None, 'malformed token usage')
            if sum(usage.values()) > limits['tokens_per_attempt']:
                violations[slot].append('token_limit')
            usage_known += 1
        if receipt['spend_usd'] is None:
            require(type(receipt['spend_unknown_reason']) is str and bool(receipt['spend_unknown_reason'].strip()),
                    'unknown spending requires reason')
        else:
            with localcontext() as context:
                context.prec = 24  # exact for <=18 amounts with <=12 whole/8 fractional digits
                known_spend += money(receipt['spend_usd'])
            require(receipt['spend_unknown_reason'] is None, 'known spending must have null unknown reason')
            spend_known += 1
        calls = receipt['tool_calls']
        require(type(calls) is list and type(receipt['tool_count']) is int
                and receipt['tool_count'] == len(calls), 'tool count/list mismatch')
        require(len(calls) <= (0 if scoring['arm'] == 'no_tools' else 4), 'forbidden tool use/call limit')
        for call in calls:
            require(type(call) is dict and set(call) == {'name', 'schema_sha256'}
                    and call['name'] == 'csp' and call['schema_sha256'] == pins['tool_schema_sha256'],
                    'forbidden tool or schema drift')
        scoring_receipts.append(scoring)
    batch_violations = ['batch_spending_ceiling'] if known_spend > ceiling else []
    scored = scorer.evaluate(directory, manifest['scoring_plan'], scoring_receipts)
    scored = budget_accounting(scored, receipts, violations, batch_violations)
    complete = usage_known == spend_known == len(receipts) == 18
    any_violation = bool(batch_violations) or any(violations.values())
    return dict(version=VERSION, status='proposal_only', execution_authorized=False,
                manifest=deepcopy(manifest), execution_receipts=deepcopy(receipts),
                planned_arm_attempts=18, recorded_attempts=len(receipts),
                known_spend_usd=str(known_spend), usage_known_attempts=usage_known,
                spend_known_attempts=spend_known,
                budget_evidence_complete=complete,
                budget_compliant=False if any_violation else True if complete else None,
                batch_budget_violations=batch_violations,
                scoring=scored)
