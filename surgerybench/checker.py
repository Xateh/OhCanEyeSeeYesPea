"""Independent schedule checker. Does not import the generator or solver."""
from collections import defaultdict
import re


def identifier(x):
    return isinstance(x,str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',x) is not None


def integer(x):
    return type(x) is int


def schema_errors(i):
    errors = []
    try:
        if i['schema_version'] != '1.0' or not integer(i['days']) or not 1 <= i['days'] <= 56:
            return ['invalid schema version or horizon']
        days = i['days']
        if not integer(i['day_minutes']) or i['day_minutes'] != 1440:
            errors.append('day_minutes must be 1440')
        for kind in ('surgeons', 'rooms'):
            ids = [r['id'] for r in i[kind]]
            if len(ids) != len(set(ids)) or not all(identifier(x) for x in ids):
                errors.append(f'invalid {kind} IDs')
            for r in i[kind]:
                if not integer(r['gap']) or r['gap'] < 0:
                    errors.append('invalid gap')
                if len(r['budgets']) != days or any(not integer(b) or not 0 <= b <= 1440 for b in r['budgets']):
                    errors.append('invalid budgets')
                if len(r['calendar']) != days:
                    errors.append('invalid calendar length')
                for intervals in r['calendar']:
                    last = -1
                    for a,b in intervals:
                        if not integer(a) or not integer(b) or not 0 <= a < b <= 1440 or a < last:
                            errors.append('invalid calendar intervals')
                        last = b
        surgeons = {r['id'] for r in i['surgeons']}
        rooms = {r['id'] for r in i['rooms']}
        ids = [p['id'] for p in i['patients']]
        if len(ids) != len(set(ids)) or not all(identifier(x) for x in ids):
            errors.append('invalid patient IDs')
        for p in i['patients']:
            if type(p['mandatory']) is not bool or p['surgeon'] not in surgeons:
                errors.append('invalid patient assignment')
            if not integer(p['duration']) or not 1 <= p['duration'] <= 1440:
                errors.append('invalid duration')
            if not integer(p['release']) or not integer(p['due']) or not 0 <= p['release'] <= p['due'] < days:
                errors.append('invalid day window')
            if len(p['eligible_rooms']) != len(set(p['eligible_rooms'])) or not set(p['eligible_rooms']) <= rooms:
                errors.append('invalid room eligibility')
            if not integer(p['priority']) or p['priority'] < 0:
                errors.append('invalid priority')
    except (KeyError, TypeError, ValueError):
        errors.append('malformed instance')
    return errors


def check_schedule(i, schedule):
    errors = schema_errors(i)
    if errors:
        return errors
    if not isinstance(schedule, list):
        return ['schedule must be a list']
    patients = {p['id']: p for p in i['patients']}
    resources = {k: {r['id']: r for r in i[k]} for k in ('surgeons','rooms')}
    seen = set()
    occupied = defaultdict(list)
    minutes = defaultdict(int)
    for row in schedule:
        if not isinstance(row,dict) or set(row) != {'patient','day','start','room'}:
            errors.append('invalid schedule row'); continue
        pid,d,t,rid = (row[k] for k in ('patient','day','start','room'))
        if not isinstance(pid,str) or pid not in patients or pid in seen:
            errors.append('unknown or duplicate patient'); continue
        seen.add(pid)
        p = patients[pid]
        if not integer(d) or not integer(t) or not 0 <= d < i['days'] or not 0 <= t < 1440:
            errors.append(f'{pid}: invalid day/start'); continue
        if not isinstance(rid,str) or rid not in p['eligible_rooms']:
            errors.append(f'{pid}: incompatible room'); continue
        end = t + p['duration']
        if not p['release'] <= d <= p['due']:
            errors.append(f'{pid}: outside release/due window')
        for kind,r in [('surgeons',p['surgeon']),('rooms',rid)]:
            resource = resources[kind][r]
            if not any(a <= t and end <= b for a,b in resource['calendar'][d]):
                errors.append(f'{pid}: {kind} calendar/break violation')
            key = (kind,r,d)
            occupied[key].append((t,end,pid))
            minutes[key] += p['duration']
    for p in i['patients']:
        if p['mandatory'] and p['id'] not in seen:
            errors.append(f"{p['id']}: missing mandatory patient")
    for (kind,r,d),rows in occupied.items():
        gap = resources[kind][r]['gap']
        rows.sort()
        for left,right in zip(rows,rows[1:]):
            if left[1] + gap > right[0]:
                errors.append(f'{kind}/{r}/day{d}: clash or required gap')
        if minutes[kind,r,d] > resources[kind][r]['budgets'][d]:
            errors.append(f'{kind}/{r}/day{d}: daily minute budget exceeded')
    return errors


def check_certificate(i, cert):
    """Verify necessary-condition contradictions, without trusting totals supplied."""
    if schema_errors(i) or not isinstance(cert,dict):
        return False
    patients = {p['id']:p for p in i['patients']}
    surgeons = {r['id']:r for r in i['surgeons']}
    rooms = {r['id']:r for r in i['rooms']}
    if cert.get('kind') == 'patient_no_slot':
        if not identifier(cert.get('patient')): return False
        p = patients.get(cert.get('patient'))
        if p is None or not p['mandatory']:
            return False
        s = surgeons[p['surgeon']]
        for d in range(p['release'],p['due']+1):
            if s['budgets'][d] < p['duration']:
                continue
            for rid in p['eligible_rooms']:
                r = rooms[rid]
                if r['budgets'][d] < p['duration']:
                    continue
                for a,b in s['calendar'][d]:
                    for c,e in r['calendar'][d]:
                        if min(b,e)-max(a,c) >= p['duration']:
                            return False
        return True
    if cert.get('kind') == 'surgeon_overload':
        sid = cert.get('surgeon')
        if not identifier(sid): return False
        if sid not in surgeons:
            return False
        return sum(p['duration'] for p in i['patients'] if p['mandatory'] and p['surgeon']==sid) > sum(surgeons[sid]['budgets'])
    return False
