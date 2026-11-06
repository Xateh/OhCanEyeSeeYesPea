"""Version-specific read-only preflight; incomplete packages fail closed."""
from collections import Counter
import hashlib
import re
from itertools import combinations
from pathlib import Path
from development_suites_v2 import VERSION, settings, candidate, factors, canonical, sha
from surgerybench.temporal_check import schema_errors, check_schedule, check_certificate
from surgerybench.temporal_oracle import enumerate_schedules, REVISION as ORACLE
from surgerybench.temporal_csp import CSPAdapter
from surgerybench.temporal_text import render, parse
from tier_a_input_view import derive
from tier_a_contract import strict_json

FILES={'model.jsonl','gold.jsonl','diagnostics.jsonl','receipts.jsonl','coverage.json'}
SOURCES={'development_suites_v2.py','development_suites_audit.py','tier_a_input_view.py',
         'surgerybench/temporal_csp.py','surgerybench/temporal_check.py','surgerybench/checker.py',
         'surgerybench/temporal_oracle.py','surgerybench/temporal_text.py'}
BASELINE='3f20017148b3290c518483b60afc7c4a75971a9e'
AUDIT_REVISION='seeded-v2-audit-portability-v2'
LEGACY_AUDIT_SHA256='1bd5d3753131cd377ab572449dcb499810f29f292485a37b086c2d9dc6a243fe'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def equal(a,b,message):
    require(canonical(a)==canonical(b),message)


def audit(directory):
    d=Path(directory)
    require(d.is_dir() and {p.name for p in d.iterdir()}==FILES|{'manifest.json'},'exact export file set')
    blobs={p.name:p.read_bytes() for p in d.iterdir() if p.is_file()}
    require(set(blobs)==FILES|{'manifest.json'} and all(len(b)<=2*1024*1024 for b in blobs.values()),'bounded regular files')
    m=strict_json(blobs['manifest.json'].decode())
    require(type(m) is dict and set(m)=={'python_version','baseline_revision','version','status','source','split',
            'old_harness_compatible','oracle_revision','adapter_revision','adapter_entrypoint','adapter_limits',
            'source_sha256','files','sampling','lineage'},'manifest shape')
    require(m['version']==VERSION and m['status']=='complete','unsupported version or incomplete package')
    require(type(m['baseline_revision']) is str and re.fullmatch('[0-9a-f]{40}',m['baseline_revision']) is not None and m['source']=='original_synthetic'
            and m['split']=='development_review' and m['old_harness_compatible'] is False,'manifest provenance')
    require(m['oracle_revision']==ORACLE and m['adapter_revision']==CSPAdapter.revision
            and m['adapter_entrypoint']=='CSPAdapter.invoke','validator identities')
    equal(m['adapter_limits'],dict(max_nodes=100000,seconds=2),'tool limits')
    root=Path(__file__).resolve().parent
    current={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCES}
    legacy=dict(current,**{'development_suites_audit.py':LEGACY_AUDIT_SHA256})
    require(m['source_sha256'] in (current,legacy),'source identity drift')
    if m['source_sha256']==legacy:require(m['baseline_revision']==BASELINE,'legacy snapshot provenance')
    equal(m['files'],{p:hashlib.sha256(blobs[p]).hexdigest() for p in FILES},'file hashes')
    require(type(m['python_version']) is str and bool(m['python_version']),'python identity')
    equal(m['sampling'],'independent per-candidate Python random.Random with SHA256-derived seed','sampling identity')
    equal(m['lineage'],'related to existing pilot/Tier A/tests; not independent holdout','lineage')
    c=strict_json(blobs['coverage.json'].decode())
    require(type(c) is dict and 'settings' in c,'coverage shape')
    config=settings(c['settings'])
    def rows(name):
        return [strict_json(s) for s in blobs[name].decode().splitlines()]
    receipts=rows('receipts.jsonl')
    expected=[(s,n) for s in config['suites'] for n in range(config['candidates_per_suite'])]
    require(len(receipts)==len(expected),'planned candidate accounting')
    seen=set()
    for r,(suite,ordinal) in zip(receipts,expected):
        require(type(r) is dict,'receipt object')
        equal([r.get('suite'),r.get('ordinal')],[suite,ordinal],'ordinal/order')
        i=candidate(config,suite,ordinal)
        equal(r.get('instance'),i,'canonical seeded instance')
        require(not schema_errors(i),'instance schema')
        cid=sha(canonical([VERSION,suite,ordinal,i]))[:24]
        require(r.get('case_id')==cid and cid not in seen,'case ID/uniqueness')
        seen.add(cid)
        equal(r.get('factors'),factors(i),'factor descriptors')
        equal(r.get('construction_group'),'related-development-not-holdout','group identity')
        base={'case_id','suite','ordinal','instance','factors','construction_group'}
        bound=1
        for p in i['patients']:
            if p['mandatory']:
                bound*=max(0,p['due']-p['release']-p['duration']+1)*len(p['eligible_rooms'])
        if bound>config['oracle_product_cap']:
            equal(sorted(r),sorted(base|{'admission','reason','product_upper_bound'}),'rejection shape')
            equal([r['admission'],r['reason'],r['product_upper_bound']],['rejected','product_bound',bound],'rejection evidence')
            continue
        oracle=enumerate_schedules(i,limit=config['oracle_assignment_limit'])
        if not oracle.get('complete'):
            equal(sorted(r),sorted(base|{'admission','reason','gold_label','oracle'}),'oracle UNKNOWN shape')
            equal([r['admission'],r['reason'],r['gold_label']],['quarantined','oracle_UNKNOWN','UNKNOWN'],'oracle UNKNOWN admission')
            equal(r['oracle'],oracle,'oracle UNKNOWN receipt')
            continue
        normal=base|{'admission','reason','gold_label','proposed_use','product_upper_bound','raw_text_sha256',
                     'text_sha256','text','witness','certificate','oracle','tool'}
        equal(sorted(r),sorted(normal),'evidence receipt shape')
        equal(r['gold_label'],oracle['status'],'oracle label')
        equal(r['product_upper_bound'],bound,'domain bound')
        equal(r['oracle'],dict(complete=True,examined=oracle['examined'],solution_count=len(oracle['solutions'])),'oracle receipt')
        raw=render(i)
        require(parse(raw)==i,'raw roundtrip')
        equal([r['text'],r['raw_text_sha256'],r['text_sha256']],[derive(raw),sha(raw),sha(derive(raw))],'derived text identity')
        if oracle['status']=='FEASIBLE':
            require(not check_schedule(i,r['witness']),'gold witness')
        else:
            require(r['witness'] is None,'negative witness null')
        tool=r['tool']
        require(type(tool) is dict and type(tool.get('status')) is str,'tool receipt')
        status=tool['status']
        if status=='FEASIBLE':
            require(set(tool)=={'status','schedule','nodes'},'feasible tool shape')
            require(not check_schedule(i,tool['schedule']),'invalid actual tool witness')
        elif status=='INFEASIBLE':
            require(set(tool)=={'status','certificate','nodes'} and check_certificate(i,tool['certificate']),'invalid tool certificate')
        elif status=='UNKNOWN':
            allowed=[{'status','reason','nodes','search_exhausted'},{'status','reason','nodes'},{'status','reason','diagnostic'}]
            require(set(tool) in allowed and tool.get('reason') in {'search_limit','exhausted_without_supported_certificate','tool_error'},'UNKNOWN tool shape')
            if 'search_exhausted' in tool:
                require(tool['search_exhausted'] is True,'exhaustion receipt')
        else:
            raise ValueError('unsupported tool status')
        if 'nodes' in tool:
            require(type(tool['nodes']) is int and 1<=tool['nodes']<=100001,'tool node receipt')
        certified=status=='INFEASIBLE' and check_certificate(i,tool.get('certificate'))
        equal(r['certificate'],tool['certificate'] if certified else None,'stored certificate')
        valid_tool=(oracle['status']=='FEASIBLE' and status=='FEASIBLE') or (oracle['status']=='INFEASIBLE' and certified)
        equal(r['proposed_use'],'evidence_eligible' if oracle['status']=='FEASIBLE' or certified else 'validation_only','evidence eligibility')
        equal([r['admission'],r['reason']],['accepted','validated'] if valid_tool else
              ['quarantined','required_tool_validation_unresolved_or_contradictory'],'admission')
    accepted=[r for r in receipts if r['admission']=='accepted']
    equal(rows('model.jsonl'),[dict(case_id=r['case_id'],text=r['text']) for r in accepted],'model join/schema/text')
    equal(rows('gold.jsonl'),[{k:v for k,v in r.items() if k!='text'} for r in accepted],'gold join/schema')
    equal(rows('diagnostics.jsonl'),[r for r in receipts if r['admission']!='accepted'],'quarantine separation')
    names=('room_gap','surgeon_gap','fragmented','optional','flexible','low_budget_proxy')
    coverage=dict(version=VERSION,settings=config,candidates=len(receipts),status='complete',
                  examined=len(receipts),exported=len(accepted),
                  admissions=dict(Counter(r['admission'] for r in receipts)),
                  labels=dict(Counter(r.get('gold_label','unlabelled') for r in receipts)),
                  accepted_labels=dict(Counter(r['gold_label'] for r in accepted)),
                  proposed_uses=dict(Counter(r.get('proposed_use','unassigned') for r in receipts)),
                  accepted_factor_counts={k:sum(r['factors'][k] for r in accepted) for k in names},
                  all_factor_counts={k:sum(r['factors'][k] for r in receipts) for k in names})
    coverage['accepted_interactions']={a+'+'+b:sum(r['factors'][a] and r['factors'][b] for r in accepted) for a,b in combinations(sorted(names),2)}
    coverage['missing_accepted_interactions']=[k for k,v in coverage['accepted_interactions'].items() if not v]
    equal(c,coverage,'coverage accounting')
    return dict(audit='PASS',audit_revision=AUDIT_REVISION,version=VERSION,candidates=len(receipts),admissions=coverage['admissions'],
                unique_structures=len({canonical(r['instance']) for r in receipts}),exported=len(accepted))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    print(canonical(audit(parser.parse_args().directory)))
