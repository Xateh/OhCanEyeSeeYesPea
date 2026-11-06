"""Deterministic review descriptors/links, never independent-split assignments."""
from collections import defaultdict
from copy import deepcopy
from development_suites_v2 import canonical,sha

VERSION='development-lineage-review-v1'
PARENT='related-development-pilot-tier-a-and-derived-suites'


def describe(instance):
    i=deepcopy(instance)
    active=sorted({day for kind in ('rooms','surgeons') for r in i[kind]
                   for day,w in enumerate(r['calendar']) if w})
    anchor=min((p['release'] for p in i['patients']),default=0)
    maps={kind:{r['id']:n for n,r in enumerate(i[kind])} for kind in ('rooms','surgeons')}
    graph=dict(counts=[len(i['patients']),len(i['surgeons']),len(i['rooms'])],
               patients=[dict(surgeon=maps['surgeons'][p['surgeon']],
                              rooms=sorted(maps['rooms'][r] for r in p['eligible_rooms']),
                              mandatory=p['mandatory']) for p in i['patients']])
    mechanisms=dict(graph=graph,
                    resources={kind:[dict(positive_gap=r['gap']>0,
                                          windows=[len(r['calendar'][d]) for d in active])
                                     for r in i[kind]] for kind in ('rooms','surgeons')})
    for kind in ('rooms','surgeons'):
        for n,r in enumerate(i[kind]):
            r['id']=str(n)
            if len(active)==1:
                day=active[0]
                r['calendar']=[[[a+day*1440-anchor,b+day*1440-anchor] for a,b in r['calendar'][day]]]
                r['budgets']=[r['budgets'][day]]
    for n,p in enumerate(i['patients']):
        p['id']=str(n);p['surgeon']=str(maps['surgeons'][p['surgeon']])
        p['eligible_rooms']=sorted(str(maps['rooms'][r]) for r in p['eligible_rooms'])
        p.pop('priority',None);p.pop('emergency',None)
        if len(active)==1:p['release']-=anchor;p['due']-=anchor
    if len(active)==1:i['days']=1
    normalized=dict(scope='ordered-renaming-metadata-and-single-active-day-shift' if len(active)==1
                    else 'ordered-renaming-metadata-only',instance=i)
    return dict(exact_sha256=sha(canonical(instance)),normalized_sha256=sha(canonical(normalized)),
                topology_sha256=sha(canonical(graph)),mechanism_sha256=sha(canonical(mechanisms)),
                graph=graph,mechanisms=mechanisms)


def ledger(records,ancestry=None):
    keys=[r['key'] for r in records]
    if len(keys)!=len(set(keys)):raise ValueError('duplicate namespaced lineage key')
    descriptors=[];groups={name:defaultdict(list) for name in ('exact','normalized','topology','mechanism')}
    for r in records:
        d=describe(r['instance'])
        entry={k:v for k,v in r.items() if k!='instance'}
        entry.update(parent_group=PARENT,**d);descriptors.append(entry)
        for level in groups:groups[level][d[level+'_sha256']].append(r['key'])
    groups={level:{h:sorted(v) for h,v in sorted(items.items())} for level,items in groups.items()}
    populations=sorted({r['population'] for r in records})
    comparisons={}
    for level,items in groups.items():
        counts={}
        for a in populations:
            for b in populations:
                if a>=b:continue
                left={r['key'] for r in records if r['population']==a}
                right={r['key'] for r in records if r['population']==b}
                pairs=sum(len(left&set(v))*len(right&set(v)) for v in items.values())
                matched_left=len({k for v in items.values() if right&set(v) for k in left&set(v)})
                matched_right=len({k for v in items.values() if left&set(v) for k in right&set(v)})
                counts[a+' vs '+b]=dict(related_pairs=pairs,left_cases=matched_left,right_cases=matched_right)
        comparisons[level]=counts
    return dict(version=VERSION,parent_group=PARENT,records=descriptors,groups=groups,
                cross_population_relationships=comparisons,counterfactual_ancestry=ancestry or [],
                limits='ordered descriptors only; not unrestricted graph isomorphism, historical derivation or independence proof')


def validate_refs(records,root):
    import ast
    root=root.resolve();cache={}
    for r in records:
        for ref in r.get('development_refs',[]):
            path=(root/ref['file']).resolve()
            if not path.is_relative_to(root):raise ValueError('source reference outside checkout')
            if path not in cache:cache[path]=ast.parse(path.read_text())
            nodes=cache[path].body
            for name in ref['symbol'].split('.'):
                matches=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name]
                if len(matches)!=1:raise ValueError('missing source symbol')
                nodes=matches[0].body
    return True
