"""Predeclared relaxations plus separately labeled optional mandatory controls."""
from copy import deepcopy
from math import prod
from surgerybench.temporal_check import schema_errors,check_schedule
from surgerybench.temporal_oracle import enumerate_schedules
from development_suites_v2 import canonical,sha
from development_counterfactuals import relax as old_relax

VERSION='development-counterfactuals-v2'
CELLS=('room_gap+fragmented','low_budget_proxy+flexible','room_gap+surgeon_gap',
       'low_budget_proxy+room_gap','surgeon_gap+flexible')
NAMES=('original','relaxA','relaxB','relaxBoth')


def relax(instance,cell,which):
    if cell not in CELLS or which not in NAMES:raise ValueError('unsupported contrast')
    if cell in CELLS[:2]:return old_relax(instance,cell,which)
    i=deepcopy(instance)
    for flag,enabled in zip(cell.split('+'),(which in ('relaxA','relaxBoth'),which in ('relaxB','relaxBoth'))):
        if not enabled:continue
        if flag in ('room_gap','surgeon_gap'):
            for r in i['rooms' if flag=='room_gap' else 'surgeons']:r['gap']=0
        elif flag=='low_budget_proxy':
            for r in i['rooms']:
                r['budgets']=[max(r['budgets'][day],max((b for a,b in windows),default=0)) for day,windows in enumerate(r['calendar'])]
        elif flag=='flexible':
            for p in i['patients']:p['eligible_rooms']=[r['id'] for r in i['rooms']]
    if schema_errors(i):raise ValueError('invalid relaxed schema')
    return i


def evidence(i):
    if schema_errors(i):raise ValueError('invalid canonical instance')
    bound=prod(max(0,p['due']-p['release']-p['duration']+1)*len(p['eligible_rooms']) for p in i['patients'] if p['mandatory'])
    base=dict(instance=i,instance_sha256=sha(canonical(i)),product_upper_bound=bound)
    if bound>100:return dict(base,status='UNKNOWN',complete=False,reason='product_bound')
    oracle=enumerate_schedules(i,limit=10000)
    if not oracle.get('complete'):return dict(base,status='UNKNOWN',complete=False,reason='oracle_limit')
    for witness in oracle['solutions']:
        if check_schedule(i,witness):raise ValueError('invalid oracle witness')
    return dict(base,status=oracle['status'],complete=True,examined=oracle['examined'],
                solution_count=len(oracle['solutions']),witness=oracle['solutions'][0] if oracle['solutions'] else None)


def lattice(status):
    edges=[('original','relaxA'),('original','relaxB'),('original','relaxBoth'),
           ('relaxA','relaxBoth'),('relaxB','relaxBoth')]
    for a,b in edges:
        if status[a]=='FEASIBLE' and status[b]=='INFEASIBLE':raise ValueError('Boolean-lattice monotonicity violated')
    return [a+'->'+b for a,b in edges if 'UNKNOWN' in (status[a],status[b])]


def check(instance,cell):
    variants={n:evidence(relax(instance,cell,n)) for n in NAMES}
    status={n:v['status'] for n,v in variants.items()};unresolved=lattice(status)
    sequence=[status[n] for n in NAMES]
    meaning=('unresolved' if unresolved else 'joint_only' if sequence==['INFEASIBLE']*3+['FEASIBLE']
             else 'selected_relaxation_effect' if sequence[0]=='INFEASIBLE' and sequence[-1]=='FEASIBLE'
             else 'no_label_change')
    return dict(version=VERSION,cell=cell,variants=variants,meaning=meaning,unresolved_lattice_edges=unresolved,
                use='development_validation_only_not_model_evidence')


def optional_control(instance):
    if not any(not p['mandatory'] for p in instance['patients']):raise ValueError('optional control requires optional jobs')
    forced=deepcopy(instance)
    for p in forced['patients']:p['mandatory']=True
    a,b=evidence(instance),evidence(forced)
    if a['status']=='INFEASIBLE' and b['status']=='FEASIBLE':raise ValueError('mandatory tightening violated')
    return dict(version=VERSION,control='optional_to_mandatory_counterpart_not_original_binding',
                original=a,mandatory_counterpart=b,
                meaning='optional_omission_permits_feasibility' if a['status']=='FEASIBLE' and b['status']=='INFEASIBLE'
                else 'unresolved' if 'UNKNOWN' in (a['status'],b['status']) else 'no_label_change',
                use='development_validation_only_not_model_evidence')
