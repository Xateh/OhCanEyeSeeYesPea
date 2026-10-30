"""Independent Cartesian exhaustive oracle for tiny fixtures only.

No imports from generator, CSP, or schedule/certificate checkers. Enumerates all
integer assignments and evaluates complete combinations (not incremental DFS).
A combination limit gives UNKNOWN, never an infeasible label.
"""
from itertools import product

REVISION = 'cartesian-integer-oracle-v1'


def enumerate_schedules(i, limit=100000):
    surgeons = {r['id']:r for r in i['surgeons']}; rooms = {r['id']:r for r in i['rooms']}
    jobs = [p for p in i['patients'] if p['mandatory']]
    domains = []
    for p in jobs:
        choices = []
        for day in range(i['days']):
            for room in p['eligible_rooms']:
                for start in range(1440-p['duration']+1):
                    finish = start+p['duration']; absolute = day*1440+start
                    if absolute < p['release'] or absolute+p['duration'] > p['due']: continue
                    if all(any(a<=start and finish<=b for a,b in r['calendar'][day]) and r['budgets'][day]>=p['duration'] for r in (surgeons[p['surgeon']],rooms[room])):
                        choices.append((day,start,finish,room))
        domains.append(choices)
    solutions = []; examined = 0
    for assignment in product(*domains):
        examined += 1
        if examined > limit: return {'status':'UNKNOWN','examined':examined-1,'reason':'combination_limit'}
        valid = True
        for resources, is_surgeon in ((surgeons,True),(rooms,False)):
            for rid,r in resources.items():
                for day in range(i['days']):
                    intervals = sorted((x[1],x[2]) for p,x in zip(jobs,assignment) if x[0]==day and (p['surgeon'] if is_surgeon else x[3])==rid)
                    if sum(b-a for a,b in intervals)>r['budgets'][day] or any(b+r['gap']>c for (a,b),(c,d) in zip(intervals,intervals[1:])): valid = False
        if valid:
            solutions.append([{'patient':p['id'],'day':x[0],'start':x[1],'room':x[3]} for p,x in zip(jobs,assignment)])
    return {'status':'FEASIBLE' if solutions else 'INFEASIBLE','solutions':solutions,'examined':examined,'complete':True}
