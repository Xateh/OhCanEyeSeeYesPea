"""Bounded complete integer-minute DFS; receives ONLY model-supplied constraints."""
from itertools import combinations
from time import monotonic
from .temporal_check import schema_errors, check_certificate

REVISION = 'temporal-minute-dfs-v1'
TOOL = {'name':'csp','description':'Solve the surgery constraints you translate from the text. Submit a schema 1.1 instance, not text. No gold instance, repair, or scoring access.','parameters':{'type':'object','properties':{'instance':{'type':'object','description':'schema_version=1.1; days; day_minutes=1440; surgeons/rooms arrays of {id,gap,budgets:[daily minutes],calendar:[daily [start,end] windows]}; patients array of {id,mandatory,surgeon,duration,release:absolute arrival minute,due:absolute completion deadline,eligible_rooms:[IDs],priority,emergency:boolean}'}},'required':['instance'],'additionalProperties':False}}


def solve(i, max_nodes=100000, seconds=2):
    errors = schema_errors(i)
    if errors: raise ValueError(errors)
    began = monotonic(); nodes = 0
    def tick():
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes or monotonic()-began >= seconds: raise TimeoutError
    try:
        tick()
        mandatory = [p for p in i['patients'] if p['mandatory']]
        for a,b in combinations(mandatory,2):
            tick(); cert = {'kind':'pair_order_impossible','patients':[a['id'],b['id']]}
            if check_certificate(i,cert): return {'status':'INFEASIBLE','certificate':cert,'nodes':nodes}
        resources = {k:{r['id']:r for r in i[k]} for k in ('surgeons','rooms')}
        jobs = sorted(mandatory,key=lambda p:(p['due']-p['release']-p['duration'],p['id']))
        occupied = {}; used = {}; schedule = []
        def dfs(index):
            tick()
            if index == len(jobs): return list(schedule)
            p = jobs[index]
            for day in range(i['days']):
                for rid in p['eligible_rooms']:
                    keys = [('surgeons',p['surgeon'],day),('rooms',rid,day)]
                    if any(used.get(k,0)+p['duration'] > resources[k[0]][k[1]]['budgets'][day] for k in keys): continue
                    s,r = (resources[k[0]][k[1]] for k in keys)
                    for a,b in s['calendar'][day]:
                        for c,d in r['calendar'][day]:
                            lo = max(a,c,p['release']-day*1440)
                            hi = min(b,d,p['due']-day*1440)-p['duration']
                            for start in range(lo,hi+1):
                                tick(); end = start+p['duration']
                                if any(any(not (end+resources[k[0]][k[1]]['gap']<=u or v+resources[k[0]][k[1]]['gap']<=start) for u,v in occupied.get(k,[])) for k in keys): continue
                                for k in keys:
                                    occupied.setdefault(k,[]).append((start,end)); used[k] = used.get(k,0)+p['duration']
                                schedule.append({'patient':p['id'],'day':day,'start':start,'room':rid})
                                result = dfs(index+1)
                                if result is not None: return result
                                schedule.pop()
                                for k in keys: occupied[k].pop(); used[k] -= p['duration']
            return None
        result = dfs(0)
        if result is not None: return {'status':'FEASIBLE','schedule':result,'nodes':nodes}
        # Exhaustion is reproducible but not a supported compact external certificate.
        return {'status':'UNKNOWN','reason':'exhausted_without_supported_certificate','search_exhausted':True,'nodes':nodes}
    except TimeoutError:
        return {'status':'UNKNOWN','reason':'search_limit','nodes':nodes}


class CSPAdapter:
    revision = REVISION
    tool_definition = TOOL
    def invoke(self, arguments):
        if not isinstance(arguments,dict) or set(arguments) != {'instance'}:
            raise ValueError('only a model-translated instance is accepted')
        return solve(arguments['instance'])
