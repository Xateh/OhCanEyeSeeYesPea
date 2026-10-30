"""Score Claude alone on the harder problems. Only model decisions count as right or wrong."""
from collections import Counter
import re
from statistics import median

from .metrics import rate

MODEL_OUTCOMES = ('correct', 'broken_schedule', 'bad_proof', 'false_alarm', 'missed_conflict', 'gave_up', 'unreadable_reply', 'timed_out')
SYSTEM_OUTCOME = 'system_error'


def outcome(row):
    if row['parsing_or_provider_error']:
        error = row['errors'][0]['error']
        if 'Timeout' in error:
            return 'timed_out'
        return 'unreadable_reply' if error.startswith(('JSONDecodeError', 'ValueError')) else SYSTEM_OUTCOME
    if row['score']['valid']:
        return 'correct'
    status = row['output'].get('status') if isinstance(row['output'], dict) else None
    if row['score']['unknown']:
        return 'gave_up'
    if status == row['label']:
        return 'broken_schedule' if status == 'FEASIBLE' else 'bad_proof'
    if status == 'FEASIBLE':
        return 'missed_conflict'
    return 'false_alarm' if status == 'INFEASIBLE' else 'unreadable_reply'


def violation_kind(text):
    return re.sub(r'^\w+: |\s+P\d+$', '', text)


def summarize_size(rows):
    """System failures, such as hitting a usage limit, say nothing about the model, so they are set aside."""
    outcomes = Counter(map(outcome, rows))
    counted = [r for r in rows if outcome(r) != SYSTEM_OUTCOME]
    solved = lambda items: sum(outcome(r) == 'correct' for r in items)
    feasible = [r for r in counted if r['label'] == 'FEASIBLE']
    infeasible = [r for r in counted if r['label'] == 'INFEASIBLE']
    decided = sum(isinstance(r['output'], dict) and r['output'].get('status') == r['label'] for r in counted)
    usage = [r['token_usage'] for r in counted if r['token_usage']]
    return {'problems': len(counted), 'system_failures': outcomes[SYSTEM_OUTCOME],
            'fully_correct': rate(solved(counted), len(counted)),
            'schedule_success': rate(solved(feasible), len(feasible)),
            'proof_success': rate(solved(infeasible), len(infeasible)),
            'decision_correct': rate(decided, len(counted)),
            'outcomes': {k: outcomes[k] for k in MODEL_OUTCOMES if outcomes[k]},
            'violations': dict(Counter(violation_kind(v) for r in counted for v in r['score']['violations']).most_common()),
            'median_seconds': median(r['latency_seconds'] for r in counted) if counted else None,
            'median_output_tokens': median(u['output_tokens'] for u in usage) if usage else None}
