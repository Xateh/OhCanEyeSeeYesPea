"""Targeted seeded development extension; v2 baseline and solvers stay immutable."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import time
from development_suites_v2 import DEFAULT,validate,canonical,sha
from development_registration import snapshot,require
from development_counterfactuals_v2 import lattice
from surgerybench.temporal_check import schema_errors,check_schedule
from tier_a_contract import strict_json
from tier_a_input_view import VERSION as INPUT_VERSION,SHARED
from tier_a_inputs import ARM

VERSION='targeted-interactions-development-v3'
REGISTRATION='targeted-interactions-registration-draft-v3'
FAMILIES=('eligibility_fragmented','eligibility_room_gap','surgeon_gap_fragmented')
VARIANTS=('original','relaxA','relaxB','relaxBoth')
BASELINE={'seeded-development-v2-96-20261105':'d2c880f50dad90ce0593ce03c44e0650a1b7231d89c2ba71c6a529c4cc13af44',
 'v2-surgeon_scarce-20261105':'f614b0cd85ffb612063585c87468dcdef850f66285480005c41bff9d8f895275',
 'v2-room_scarce-20261105':'bab5e5fb657af90eff9fbfe22b5022a9e12ae143f0d8b7c1e3ce392f1068a4fc',
 'v2-room_flexible-20261105':'e5210fc03d5a423380adfacaa5cad2b480f086150a6bdcf022c2e65c711a2570'}
DECISION='3263e319594ac7620b816dd1f09fd71a37f1092a6be3c4f8acf524c8c4d0e75a'
SOURCES=('development_interactions_v3.py','development_suites_v2.py','development_registration.py',
 'development_counterfactuals_v2.py','tier_a_input_view.py','tier_a_inputs.py','tier_a_contract.py',
 'surgerybench/temporal_csp.py','surgerybench/temporal_oracle.py','surgerybench/temporal_check.py',
 'surgerybench/checker.py','surgerybench/temporal_text.py')


def settings(value):
    require(type(value) is dict and set(value)=={'version','seed','base_variants_per_family','families'},'exact v3 settings')
    require(value['version']==VERSION and type(value['seed']) is int and 0<=value['seed']<2**32,'v3 seed/version')
    require(type(value['base_variants_per_family']) is int and 1<=value['base_variants_per_family']<=6,'bounded base count')
    require(value['families']==list(FAMILIES) and type(value['families']) is list,'explicit fixed family order')
    return deepcopy(value)


def authored(family,d,t,g,variant):
    require(family in FAMILIES and variant in VARIANTS and 2<=d<=4 and 0<=t<=2 and g in (1,2),'construction parameters')
    end=t+2*d
    def resource(name,windows,gap=0):return dict(id=name,gap=gap,budgets=[2*d],calendar=[windows])
    rooms=[resource('r0',[[t,end]]),resource('r1',[[t,end]])]
    surgeons=[resource('s0',[[t,end]]),resource('s1',[[t,end]])]
    jobs=[dict(id='p'+str(n),surgeon='s'+str(n),duration=d,release=t+n*d,due=t+(n+1)*d,
               eligible_rooms=['r0'],mandatory=True,priority=1,emergency=False) for n in (0,1)]
    a=variant in ('relaxA','relaxBoth');b=variant in ('relaxB','relaxBoth')
    if family=='eligibility_fragmented':
        rooms[0]['calendar']=[[[t,t+d-1],[t+d,end]]]
        jobs[1]['eligible_rooms']=['r0','r1']
        if a:jobs[0]['eligible_rooms']=['r0','r1']
        if b:rooms[0]['calendar']=[[[t,end]]]
        expected='INFEASIBLE' if variant=='original' else 'FEASIBLE'
        assignment=[('r1' if a else 'r0'), 'r0']
        lemma='A needs d minutes before t+d; r0 first window has d-1. Expanding eligibility or merging r0 windows independently supplies a fit.'
    elif family=='eligibility_room_gap':
        rooms[0]['gap']=0 if a else g
        rooms[1]['calendar']=[[[t,t+d-1]]]
        rooms.append(resource('r2',[[t,end]]))
        for p in jobs:p['eligible_rooms']=['r0','r1','r2'] if b else ['r0','r1']
        expected='INFEASIBLE' if variant=='original' else 'FEASIBLE'
        assignment=['r0','r2' if b else 'r0']
        lemma='Both fixed-start jobs must use r0 because r1 has d-1 minutes; their adjacency violates positive gap. Zero gap or newly eligible r2 independently restores feasibility.'
    else:
        surgeons=[resource('s0',[[t,end]] if b else [[t,t+d-1],[t+d,end]],0 if a else g)]
        for n,p in enumerate(jobs):p.update(surgeon='s0',release=t,due=end,eligible_rooms=['r'+str(n)])
        expected='FEASIBLE' if variant=='relaxBoth' else 'INFEASIBLE'
        assignment=['r0','r1']
        lemma='Only one d-minute job fits fragmented surgeon windows. Merging alone still needs 2d+g in span 2d; zero gap plus merged windows fits both.'
    i=dict(schema_version='1.1',days=1,day_minutes=1440,patients=jobs,rooms=rooms,surgeons=surgeons)
    witness=[dict(patient='p'+str(n),day=0,start=t+n*d,room=assignment[n]) for n in (0,1)] if expected=='FEASIBLE' else None
    require(not schema_errors(i),'authored schema')
    require(witness is None or not check_schedule(i,witness),'authored witness')
    return i,expected,witness,lemma

def construct(config):
    config=settings(config)
    for family in FAMILIES:
        seed=int(sha(canonical([VERSION,config['seed'],family])),16)
        rng=random.Random(seed)
        pairs=rng.sample([(d,t) for d in (2,3,4) for t in (0,1,2)],config['base_variants_per_family'])
        for base,(d,t) in enumerate(pairs):
            g=rng.choice((1,2))
            for variant in VARIANTS:
                i,label,witness,lemma=authored(family,d,t,g,variant)
                identity=[VERSION,config['seed'],family,base,variant,d,t,g]
                yield dict(case_id=sha(canonical(identity))[:24],family=family,base=base,variant=variant,
                           parameters=dict(duration=d,offset=t,gap=g),instance=i,expected_label=label,
                           authored_witness=witness,arithmetic=lemma)

def check_record(record):
    i=record['instance'];p=record['parameters']
    c=deepcopy(DEFAULT)
    c.update(patient_count=2,surgeon_count=len(i['surgeons']),room_count=len(i['rooms']),
             horizon_minutes=p['offset']+2*p['duration'],duration_min=p['duration'],
             duration_max=p['duration'],slack_max=p['duration'],gap_max=p['gap'])
    evidence=validate(i,c)
    require(evidence['gold_label']==record['expected_label'],'authored/oracle disagreement')
    require(evidence['oracle']['complete'],'incomplete oracle')
    return evidence

def build(config):
    config=settings(config);start=time.monotonic();records=[]
    expected=list(construct(config))
    for ordinal,r in enumerate(expected):
        if time.monotonic()-start>40:
            return dict(version=VERSION,status='incomplete',settings=config,records=records,
                        unexamined_ordinals=list(range(ordinal,len(expected))))
        r['ordinal']=ordinal;r['evidence']=check_record(r);records.append(r)
    matrices=[]
    for family in FAMILIES:
        for base in range(config['base_variants_per_family']):
            group=[r for r in records if r['family']==family and r['base']==base]
            labels={r['variant']:r['evidence']['gold_label'] for r in group}
            require(not lattice(labels),'nonmonotone contrast')
            matrices.append(dict(family=family,base=base,labels=labels,case_ids=[r['case_id'] for r in group]))
    counts=Counter(r['evidence']['admission'] for r in records)
    return dict(version=VERSION,status='complete',settings=config,records=records,matrices=matrices,
                counts=dict(counts),baseline_manifests=BASELINE,baseline_decision_sha256=DECISION,
                source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
                related_parent='related-development-pilot-tier-a-and-derived-suites')

def audit(bundle):
    require(type(bundle) is dict and bundle.get('version')==VERSION and bundle.get('status')=='complete','complete v3 required')
    require(bundle==build(bundle['settings']),'v3 replay/evidence/source mismatch')
    return True

def model_inputs(bundle,arm):
    require(arm in ARM,'unsupported arm');audit(bundle)
    return [dict(shared_instruction=SHARED,arm_instruction=ARM[arm],text=r['evidence']['text'])
            for r in bundle['records'] if r['evidence']['admission']=='accepted']
