"""Independent validation for temporal schema 1.1; v1 modules stay unchanged."""
from copy import deepcopy
from . import checker as legacy

VERSION = '1.1'

def relaxed(i):
    j = deepcopy(i)
    j['schema_version'] = '1.0'
    for p in j['patients']:
        p['release'], p['due'] = 0, j['days'] - 1
    return j


def schema_errors(i):
    try:
        if not isinstance(i, dict) or i.get('schema_version') != VERSION:
            return ['expected temporal schema 1.1']
        errors = legacy.schema_errors(relaxed(i))
        for p in i['patients']:
            if not all(legacy.integer(p[k]) for k in ('release', 'due')) or not 0 <= p['release'] <= p['due'] <= i['days'] * 1440:
                errors.append('invalid absolute-minute release/completion deadline')
            if 'emergency' in p and type(p['emergency']) is not bool:
                errors.append('emergency metadata must be boolean')
        return errors
    except (KeyError, TypeError, ValueError, AttributeError):
        return ['malformed temporal instance']


def check_schedule(i, schedule):
    errors = schema_errors(i)
    if errors:
        return errors
    errors = legacy.check_schedule(relaxed(i), schedule)
    if not isinstance(schedule, list):
        return errors
    patients = {p['id']: p for p in i['patients']}
    for row in schedule:
        if not isinstance(row, dict) or not isinstance(row.get('patient'), str):
            continue
        p = patients.get(row['patient'])
        if p is None or not all(legacy.integer(row.get(k)) for k in ('day', 'start')):
            continue
        start = 1440 * row['day'] + row['start']
        if start < p['release']:
            errors.append(p['id'] + ': starts before arrival')
        if start + p['duration'] > p['due']:
            errors.append(p['id'] + ': completes after deadline')
    return errors


def check_certificate(i, certificate):
    """Check a two-job necessary-condition contradiction, ignoring calendars/budgets.

    If mandatory jobs must share a resource, one must precede the other.
    Failure even in this relaxed problem proves the full instance infeasible.
    """
    if schema_errors(i) or not isinstance(certificate, dict):
        return False
    if set(certificate) != {'kind', 'patients'} or certificate['kind'] != 'pair_order_impossible':
        return False
    ids = certificate['patients']
    if not isinstance(ids, list) or len(ids) != 2 or not all(isinstance(x, str) for x in ids) or ids[0] == ids[1]:
        return False
    patients = {p['id']: p for p in i['patients']}
    if any(x not in patients or not patients[x]['mandatory'] for x in ids):
        return False
    a, b = (patients[x] for x in ids)
    forced = a['surgeon'] == b['surgeon'] or (len(a['eligible_rooms']) == len(b['eligible_rooms']) == 1 and a['eligible_rooms'] == b['eligible_rooms'])
    if not forced:
        return False
    def possible(first, second):
        end = first['release'] + first['duration']
        return end <= first['due'] and max(end, second['release']) + second['duration'] <= second['due']
    return not possible(a, b) and not possible(b, a)
