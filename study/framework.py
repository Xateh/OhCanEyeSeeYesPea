"""Score recorded runs under docs/evaluation-framework.md. Failures always stay in the denominator."""
from collections import Counter
from statistics import mean, median
import time

from surgerybench.temporal_benchmark import score
from surgerybench.temporal_csp import CSPAdapter

from .hard_metrics import outcome
from .metrics import row_cost, succeeded, translation_status

CLAIMS = ('FEASIBLE', 'INFEASIBLE')
BAD_OUTPUT = 'unreadable_reply'


def status_of(row):
    return row['output'].get('status') if isinstance(row['output'], dict) else None


def require_planned(rows, planned):
    if len(rows) != planned:
        raise ValueError(f'planned {planned}, found {len(rows)}: every planned run must stay in the denominator')
    return rows


def rescore(rows, gold):
    """Score again from gold instead of trusting stored results, returning new rows."""
    fresh = []
    for row in rows:
        target = gold[row['case_id']]
        if score(target, row['output']) != row['score']:
            raise ValueError(f"stored score disagrees with gold for {row['case_id']}")
        fresh.append({**row, 'label': target['label']})
    return fresh


def fraction(rows, test):
    return [sum(map(test, rows)), len(rows)]


def f1_score(successes, claims, planned):
    return 2 * successes / (claims + planned) if claims + planned else 0.0


def token_total(row):
    return row['token_usage']['input_tokens'] + row['token_usage']['output_tokens']


def solver_seconds(row):
    return sum(call.get('latency_seconds', 0) for call in row['tool_calls'])


def quality(rows):
    feasible = [r for r in rows if r['label'] == 'FEASIBLE']
    infeasible = [r for r in rows if r['label'] == 'INFEASIBLE']
    claimed = [r for r in rows if status_of(r) in CLAIMS]
    successes = sum(map(succeeded, rows))
    return {'evidence_backed_success': [successes, len(rows)],
            'feasible_schedule_success': fraction(feasible, succeeded),
            'certified_infeasible_success': fraction(infeasible, succeeded),
            'infeasible_decision': fraction(infeasible, lambda r: status_of(r) == 'INFEASIBLE'),
            'status_agreement': fraction(rows, lambda r: status_of(r) == r['label']),
            'feasible_claim_precision': fraction([r for r in rows if status_of(r) == 'FEASIBLE'], succeeded),
            'evidence_precision': [successes, len(claimed)],
            'f1': f1_score(successes, len(claimed), len(rows))}


def reliability(rows):
    outcomes = Counter(map(outcome, rows))
    total = len(rows)
    return {'unknown': fraction(rows, lambda r: status_of(r) == 'UNKNOWN'),
            'parse_errors': [outcomes[BAD_OUTPUT], total], 'timeouts': [outcomes['timed_out'], total],
            'provider_errors': [outcomes['system_error'], total],
            'tool_errors': fraction(rows, lambda r: r['tool_error'])}


def cost(rows):
    usage = [r for r in rows if r['token_usage'] is not None]
    return {'runs_with_tokens': len(usage),
            'mean_tokens': mean(map(token_total, usage)) if usage else None,
            'mean_input_tokens': mean(r['token_usage']['input_tokens'] for r in usage) if usage else None,
            'mean_output_tokens': mean(r['token_usage']['output_tokens'] for r in usage) if usage else None,
            'mean_seconds': mean(r['latency_seconds'] for r in rows),
            'median_seconds': median(r['latency_seconds'] for r in rows),
            'mean_csp_calls': mean(r['tool_call_count'] for r in rows),
            'mean_solver_seconds': mean(map(solver_seconds, rows)),
            'estimated_cost_usd': sum(map(row_cost, rows))}


def summarize(rows):
    return {**quality(rows), **reliability(rows), **cost(rows), 'outcomes': dict(sorted(Counter(map(outcome, rows)).items()))}


def blame(row, gold):
    if outcome(row) == BAD_OUTPUT:
        return 'bad_output'
    last_result = row['tool_calls'][-1]['result'] if row['tool_calls'] else {}
    faithful = translation_status(row, gold[row['case_id']]['instance']) == 'exact'
    return 'solver_unknown' if faithful and last_result.get('status') == 'UNKNOWN' else 'translation_error'


def failure_split(rows, gold):
    """Split LLM+CSP failures into the three causes the framework asks for."""
    causes = Counter(blame(row, gold) for row in rows if not succeeded(row))
    return {name: causes[name] for name in ('translation_error', 'solver_unknown', 'bad_output')}


def csp_on_gold(gold_rows, adapter=None):
    """Give the solver the intended problem directly: the ceiling if translation were perfect."""
    solver = adapter or CSPAdapter()
    rows = []
    for gold in gold_rows:
        started = time.perf_counter()
        result = solver.invoke({'instance': gold['instance']})
        seconds = time.perf_counter() - started
        output = {key: value for key, value in result.items() if key in ('status', 'schedule', 'certificate')}
        rows.append({'case_id': gold['id'], 'label': gold['label'], 'output': output, 'score': score(gold, output),
                     'errors': [], 'parsing_or_provider_error': False, 'tool_error': False, 'latency_seconds': seconds,
                     'token_usage': {'input_tokens': 0, 'output_tokens': 0}, 'responses': [],
                     'tool_calls': [{'latency_seconds': seconds}], 'tool_call_count': 1})
    return rows
