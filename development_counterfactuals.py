"""Bounded development-only relaxations; oracle labels are not model certificates."""
from copy import deepcopy
from math import prod
from surgerybench.temporal_check import schema_errors,check_schedule
from surgerybench.temporal_oracle import enumerate_schedules
from development_suites_v2 import canonical,sha

VERSION='development-counterfactuals-v1'
CELLS=('room_gap+fragmented','low_budget_proxy+flexible')


def relax(instance,cell,which):
    if cell not in CELLS or which not in {'original','relaxA','relaxB','relaxBoth'}:
        raise ValueError('unsupported counterfactual')
    i=deepcopy(instance)
    a=which in {'relaxA','relaxBoth'}
    b=which in {'relaxB','relaxBoth'}
    if cell=='room_gap+fragmented':
        if a:
            for r in i['rooms']:r['gap']=0
        if b:
            for r in i['rooms']+i['surgeons']:
                r['calendar']=[[[windows[0][0],windows[-1][1]]] if windows else [] for windows in r['calendar']]
    else:
        if a:
            for r in i['rooms']:
                r['budgets']=[max(r['budgets'][day],max((end for start,end in windows),default=0)) for day,windows in enumerate(r['calendar'])]
        if b:
            for p in i['patients']:p['eligible_rooms']=[r['id'] for r in i['rooms']]
    if schema_errors(i):raise ValueError('relaxation broke canonical schema')
    return i


def check(instance,cell):
    result={}
    for name in ('original','relaxA','relaxB','relaxBoth'):
        i=relax(instance,cell,name)
        bound=prod(max(0,p['due']-p['release']-p['duration']+1)*len(p['eligible_rooms']) for p in i['patients'] if p['mandatory'])
        if bound>100:
            receipt=dict(status='UNKNOWN',reason='product_bound',complete=False)
        else:
            oracle=enumerate_schedules(i,limit=10000)
            if not oracle.get('complete'):
                receipt=dict(status='UNKNOWN',reason='oracle_limit',complete=False)
            else:
                for witness in oracle['solutions']:
                    if check_schedule(i,witness):raise ValueError('counterfactual witness invalid')
                receipt=dict(status=oracle['status'],complete=True,examined=oracle['examined'],
                             solution_count=len(oracle['solutions']),
                             witness=oracle['solutions'][0] if oracle['solutions'] else None)
        result[name]=dict(instance=i,instance_sha256=sha(canonical(i)),product_upper_bound=bound,**receipt)
    statuses=[result[n]['status'] for n in ('original','relaxA','relaxB','relaxBoth')]
    if 'UNKNOWN' in statuses:meaning='unresolved'
    elif statuses==['INFEASIBLE','INFEASIBLE','INFEASIBLE','FEASIBLE']:meaning='joint_relaxation_only_restores_feasibility'
    elif statuses[0]=='INFEASIBLE' and statuses[-1]=='FEASIBLE':meaning='at_least_one_selected_relaxation_restores_feasibility'
    else:meaning='no_label_change_for_selected_relaxations'
    if statuses[0]=='FEASIBLE' and 'INFEASIBLE' in statuses[1:]:raise ValueError('nonmonotone relaxation')
    return dict(version=VERSION,cell=cell,meaning=meaning,variants=result,
                use='development_validation_only_not_model_evidence')
