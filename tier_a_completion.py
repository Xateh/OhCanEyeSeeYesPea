"""Additive offline completion proposal; leaves legacy results untouched."""
from copy import deepcopy
import tier_a_contract as core


def well_formed(receipt):
    if receipt['normalization_errors']:
        return False
    try:
        raw = receipt['raw_output']
        if type(raw) is not str or len(raw.encode()) > 65536:
            return False
        value = core.strict_json(raw)
        if core.canonical(value) != core.canonical(receipt['normalized_output']):
            return False
        if type(value) is not dict:
            return False
        status = value.get('status')
        if status == 'UNKNOWN':
            return set(value) == {'status'}
        if status == 'FEASIBLE':
            return (set(value) == {'status', 'schedule'} and type(value['schedule']) is list
                    and all(type(r) is dict and set(r) == {'patient', 'room', 'day', 'start'}
                            and type(r['patient']) is str and type(r['room']) is str
                            and type(r['day']) is int and type(r['start']) is int for r in value['schedule']))
        if status == 'INFEASIBLE':
            c = value.get('certificate')
            return (set(value) == {'status', 'certificate'} and type(c) is dict
                    and set(c) == {'kind', 'patients'} and c['kind'] == 'pair_order_impossible'
                    and type(c['patients']) is list and len(c['patients']) == 2
                    and all(type(x) is str for x in c['patients']) and c['patients'][0] != c['patients'][1])
        return False
    except (ValueError, TypeError, RecursionError, OverflowError):
        return False


def reconcile(legacy):
    """Accept validated scorer/preparation results, never raw unvalidated receipts."""
    result = deepcopy(legacy)
    result['completion_contract'] = 'answer-completion-proposal-v1'
    for row in result['rows']:
        receipt = row['receipt']
        row['legacy_completed'] = row['completed']
        row['execution_terminal'] = receipt is not None  # False means no terminal evidence, not proven nontermination.
        row['answer_complete'] = bool(receipt and (receipt['termination'] == 'abstained'
            or receipt['termination'] == 'final' and well_formed(receipt)))
    def summary(rows):
        return dict(planned=len(rows), attempted=sum(not r['missing'] for r in rows),
                    terminal=sum(r['execution_terminal'] for r in rows),
                    answer_complete=sum(r['answer_complete'] for r in rows),
                    missing=sum(r['missing'] for r in rows))
    result['completion_by_arm'] = {a: summary([r for r in result['rows'] if r['arm'] == a]) for a in core.ARMS}
    result['completion_by_family'] = {f: {a: summary([r for r in result['rows'] if r['family'] == f and r['arm'] == a])
        for a in core.ARMS} for f in sorted({r['family'] for r in result['rows']})}
    pairs = dict(both_success=0, no_tools_only=0, csp_only=0, neither_success=0, incomplete=0)
    grouped = {}
    for r in result['rows']:
        grouped.setdefault((r['case_id'], r['repetition']), {})[r['arm']] = r
    for pair in grouped.values():
        a, b = (pair[arm] for arm in core.ARMS)
        key = ('incomplete' if not a['answer_complete'] or not b['answer_complete'] else
               'both_success' if a['success'] and b['success'] else 'no_tools_only' if a['success']
               else 'csp_only' if b['success'] else 'neither_success')
        pairs[key] += 1
    result['completion_pairs'] = pairs
    return result
