"""Draft offline registration/input preparation; never a live runner or old-contract bypass."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from development_suites_audit import audit,FILES
from development_suites_v2 import VERSION as CORPUS
from tier_a_contract import strict_json,output_verdict
from tier_a_input_view import VERSION as INPUT_VERSION,SHARED
from tier_a_inputs import ARM

VERSION='development-registration-draft-v1'
MAX_FILE=2*1024*1024


def require(ok,message):
    if not ok:raise ValueError(message)


def check_depth(text):
    depth=0;quoted=False;escape=False
    for c in text:
        if quoted:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':
            depth+=1
            require(depth<=64,'JSON nesting cap')
        elif c in ']}':depth-=1


def snapshot(directory):
    """Bounded no-follow reads; returns detached bytes, no untrusted path reopens."""
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    fd=os.open(directory,flags)
    try:
        names=[]
        with os.scandir(fd) as entries:
            for entry in entries:
                require(len(names)<6,'directory entry cap')
                names.append(entry.name)
        require(len(names)==6 and set(names)==FILES|{'manifest.json'},'exact file set')
        blobs={}
        for name in sorted(names):
            f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            try:
                info=os.fstat(f)
                require(stat.S_ISREG(info.st_mode) and info.st_size<=MAX_FILE,'regular file/size cap before read')
                chunks=[];total=0
                while True:
                    chunk=os.read(f,min(65536,MAX_FILE+1-total))
                    if not chunk:break
                    total+=len(chunk);require(total<=MAX_FILE,'file grew beyond cap')
                    chunks.append(chunk)
                data=b''.join(chunks)
            finally:os.close(f)
            text=data.decode('utf-8');check_depth(text)
            if name.endswith('.jsonl'):
                require(len(text.splitlines())<=128,'record count cap before JSON parse')
            blobs[name]=data
        return blobs
    finally:os.close(fd)


def verified_package(directory):
    blobs=snapshot(directory)
    with tempfile.TemporaryDirectory(prefix='cs3263-audit-') as tmp:
        for n,b in blobs.items():(Path(tmp)/n).write_bytes(b)
        report=audit(tmp)
    return blobs,report


def preflight(directory,plan):
    fields={'registration_version','corpus_version','manifest_sha256','consumer_sha256',
            'input_view_version','instruction_sha256','planned_case_ids','arms','repetitions'}
    require(type(plan) is dict and set(plan)==fields,'explicit registration plan keys')
    require(plan['registration_version']==VERSION and plan['corpus_version']==CORPUS
            and plan['input_view_version']==INPUT_VERSION,'unsupported registration/corpus/input version')
    require(plan['consumer_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'consumer identity')
    require(plan['arms']==['no_tools','csp'] and type(plan['arms']) is list,'matched arms')
    require(type(plan['repetitions']) is int and 1<=plan['repetitions']<=10,'explicit repetitions 1..10')
    expected_instructions={k:hashlib.sha256(v.encode()).hexdigest() for k,v in dict(shared=SHARED,**ARM).items()}
    require(plan['instruction_sha256']==expected_instructions,'explicit instruction identities')
    ids=plan['planned_case_ids']
    require(type(ids) is list and 1<=len(ids)<=128 and all(type(i) is str for i in ids)
            and len(ids)==len(set(ids)),'explicit unique planned case IDs')
    blobs,report=verified_package(directory)
    require(type(plan['manifest_sha256']) is str and
            hashlib.sha256(blobs['manifest.json']).hexdigest()==plan['manifest_sha256'],'explicit package manifest identity')
    gold={r['case_id']:r for r in (strict_json(s) for s in blobs['gold.jsonl'].decode().splitlines())}
    model={r['case_id']:r for r in (strict_json(s) for s in blobs['model.jsonl'].decode().splitlines())}
    require(all(i in gold and i in model and gold[i]['admission']=='accepted'
                and gold[i]['proposed_use']=='evidence_eligible' for i in ids),'unaccepted/excluded planned case')
    return [gold[i] for i in ids],[model[i]['text'] for i in ids],report


def model_inputs(directory,plan,arm):
    require(type(arm) is str and arm in ARM,'unsupported arm')
    _,texts,_=preflight(directory,plan)
    return tuple(dict(shared_instruction=SHARED,arm_instruction=ARM[arm],instance_text=t) for t in texts)


def planned_slots(directory,plan):
    gold,_,_=preflight(directory,plan)
    return tuple(dict(case_id=g['case_id'],repetition=r,arm=a) for g in gold
                 for r in range(plan['repetitions']) for a in plan['arms'])


def assess(directory,plan,receipts):
    """Synthetic recorded-attempt evidence only; all explicit planned slots remain.

    No new completion, cost, budget or research protocol definition is introduced.
    """
    gold,_,_=preflight(directory,plan)
    keys={(g['case_id'],r,a) for g in gold for r in range(plan['repetitions']) for a in plan['arms']}
    require(type(receipts) is list and len(receipts)<=len(keys),'bounded receipt list')
    fields={'case_id','repetition','arm','raw_output','normalized_output','normalization_errors',
            'provider_error','tool_error','termination'}
    indexed={}
    for item in receipts:
        require(type(item) is dict and set(item)==fields,'frozen receipt fields')
        require(type(item['case_id']) is str and type(item['arm']) is str
                and type(item['repetition']) is int,'routing types')
        key=(item['case_id'],item['repetition'],item['arm'])
        require(key in keys and key not in indexed,'duplicate/unplanned attempt')
        require(type(item['provider_error']) is bool and type(item['tool_error']) is bool,'error flags')
        require(type(item['normalization_errors']) is list and all(type(e) is str and e for e in item['normalization_errors']),'normalization diagnostics')
        require(item['termination'] in ('final','abstained','provider_error','tool_error'),'frozen termination enum')
        require(item['termination']!='provider_error' or item['provider_error'],'provider error mapping')
        require(item['termination']!='tool_error' or item['tool_error'],'tool error mapping')
        if item['termination']=='abstained':
            require(item['raw_output'] is None and item['normalized_output'] is None
                    and not item['normalization_errors'] and not item['provider_error']
                    and not item['tool_error'],'explicit abstention shape')
        indexed[key]=item
    rows=[]
    for g in gold:
        for rep in range(plan['repetitions']):
            for arm in plan['arms']:
                item=indexed.get((g['case_id'],rep,arm))
                row=dict(case_id=g['case_id'],repetition=rep,arm=arm,gold_label=g['gold_label'],
                         missing=item is None,success=False,unknown=False,error=False)
                if item is not None:
                    if item['termination']=='abstained':
                        row['unknown']=True
                    else:
                        verdict=output_verdict(g['instance'],item['raw_output'],item['normalized_output'],item['normalization_errors'])
                        operational=item['provider_error'] or item['tool_error'] or item['termination']!='final'
                        row['success']=verdict['evidence_valid'] and not operational and verdict['status']==g['gold_label']
                        row['unknown']=verdict['status']=='UNKNOWN'
                        row['error']=verdict['output_error'] or operational
                rows.append(row)
    arms={}
    for arm in plan['arms']:
        group=[r for r in rows if r['arm']==arm]
        arms[arm]=dict(planned=len(group),success=sum(r['success'] for r in group),
                       missing=sum(r['missing'] for r in group),unknown=sum(r['unknown'] for r in group),
                       errors=sum(r['error'] for r in group),
                       feasible_planned=sum(r['gold_label']=='FEASIBLE' for r in group),
                       negative_planned=sum(r['gold_label']=='INFEASIBLE' for r in group))
    return dict(status='offline_registration_draft_not_execution_approval',by_arm=arms,rows=rows,
                plan=deepcopy(plan))
