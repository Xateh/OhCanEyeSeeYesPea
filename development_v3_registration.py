"""Pinned v3 offline registration and intended-instance evidence scoring. No live runner."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import development_interactions_v3 as corpus
import development_settings_v1 as settings
from development_registration import require,check_depth
from tier_a_contract import strict_json,output_verdict
from tier_a_input_view import SHARED,VERSION as INPUT_VERSION
from tier_a_inputs import ARM
VERSION='targeted-interactions-offline-registration-v1'
BUNDLE_SHA256='8c42915dd4adbdf7394c1e666b40323d16ad12be24d175677e24ff9d8e44aa30'
MAX_BYTES=1024*1024
PIN_FILES=tuple(dict.fromkeys((__file__.split('/')[-1],)+settings.PIN_FILES+corpus.SOURCES))

def digest(data):return hashlib.sha256(data).hexdigest()

def source_pins():
    root=Path(__file__).resolve().parent
    return {p:digest((root/p).read_bytes()) for p in PIN_FILES}

def read_package(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        names=[]
        with os.scandir(fd) as entries:
            for entry in entries:
                require(len(names)<2,'package entry cap');names.append(entry.name)
        require(set(names)=={'bundle.json','manifest.json'},'exact v3 package files')
        blobs={}
        for name in names:
            f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
            try:
                info=os.fstat(f)
                require(stat.S_ISREG(info.st_mode) and info.st_size<=MAX_BYTES,'regular bounded file before read')
                chunks=[];total=0
                while True:
                    chunk=os.read(f,min(65536,MAX_BYTES+1-total))
                    if not chunk:break
                    total+=len(chunk);require(total<=MAX_BYTES,'file growth cap');chunks.append(chunk)
                blobs[name]=b''.join(chunks)
            finally:os.close(f)
        require(digest(blobs['bundle.json'])==BUNDLE_SHA256,'unsupported/tampered bundle identity')
        for data in blobs.values():check_depth(data.decode('utf-8'))
        manifest=strict_json(blobs['manifest.json'].decode('utf-8'))
        require(type(manifest) is dict and set(manifest)=={'registration_version','corpus_version','bundle_sha256','source_sha256','input_view_version','instruction_sha256'},'manifest fields')
        require(manifest==expected_manifest(),'manifest source/version mismatch')
        bundle=strict_json(blobs['bundle.json'].decode('utf-8'))
        require(type(bundle) is dict and bundle.get('status')=='complete' and bundle.get('version')==corpus.VERSION,'complete supported corpus')
        require(type(bundle.get('records')) is list and len(bundle['records'])==48,'exact bounded record count')
        corpus.audit(bundle)
        return bundle,manifest,digest(blobs['manifest.json'])
    finally:os.close(fd)

def expected_manifest():
    return dict(registration_version=VERSION,corpus_version=corpus.VERSION,bundle_sha256=BUNDLE_SHA256,
                source_sha256=source_pins(),input_view_version=INPUT_VERSION,
                instruction_sha256={k:digest(v.encode()) for k,v in dict(shared=SHARED,**ARM).items()})

def preflight(directory,plan):
    require(type(plan) is dict and set(plan)=={'registration_version','corpus_version','manifest_sha256','source_sha256','planned_case_ids','arms','repetitions'},'exact explicit v3 plan fields')
    require(plan['registration_version']==VERSION and plan['corpus_version']==corpus.VERSION,'unsupported plan version')
    require(plan['source_sha256']==source_pins(),'plan source identity')
    require(type(plan['arms']) is list and plan['arms']==['no_tools','csp'],'matched arms')
    require(type(plan['repetitions']) is int and 1<=plan['repetitions']<=10,'repetitions 1..10')
    ids=plan['planned_case_ids']
    require(type(ids) is list and 1<=len(ids)<=28 and all(type(x) is str for x in ids),'bounded selected IDs')
    require(len(set(ids))==len(ids),'duplicate selected ID')
    b,m,h=read_package(directory)
    require(type(plan['manifest_sha256']) is str and plan['manifest_sha256']==h,'planned package identity')
    rows={r['case_id']:r for r in b['records']}
    require(all(x in rows and rows[x]['evidence']['admission']=='accepted' and rows[x]['evidence']['proposed_use']=='evidence_eligible' for x in ids),'unknown/quarantined selected ID')
    return [deepcopy(rows[x]) for x in ids]

def bind(config,directory,plan):
    c=settings.validate(config)
    require(type(plan) is dict,'explicit v3 plan required')
    for ck,pk in [('corpus_version','corpus_version'),('manifest_sha256','manifest_sha256'),('case_ids','planned_case_ids'),('repetitions','repetitions')]:
        require(pk in plan and c[ck]==plan[pk],'settings/plan mismatch: '+ck)
    rows=preflight(directory,plan)
    return dict(status='offline_bound_not_execution_authorization',config=c,plan=deepcopy(plan),selected_count=len(rows))

def prepare(config,directory,plan,arm):
    binding=bind(config,directory,plan)
    require(type(arm) is str and arm in ARM,'unsupported arm')
    rows=preflight(directory,plan)
    payloads=tuple(dict(version='provider-neutral-messages-v2',messages=[dict(role='system',content=SHARED+'\n'+ARM[arm]),dict(role='user',content=r['evidence']['text'])],tool_policy='none' if arm=='no_tools' else 'pinned-merged-schema-1.1-model-translated-CSP-only') for r in rows)
    return binding,payloads

def assess(directory,plan,receipts):
    gold=preflight(directory,plan)
    slots={(g['case_id'],rep,a) for g in gold for rep in range(plan['repetitions']) for a in plan['arms']}
    require(type(receipts) is list and len(receipts)<=len(slots),'bounded receipt list')
    fields={'case_id','repetition','arm','raw_output','normalized_output','normalization_errors','provider_error','tool_error','termination'}
    indexed={}
    for item in receipts:
        require(type(item) is dict and set(item)==fields,'receipt fields')
        require(type(item['case_id']) is str and type(item['arm']) is str and type(item['repetition']) is int,'receipt routing types')
        key=(item['case_id'],item['repetition'],item['arm'])
        require(key in slots and key not in indexed,'duplicate/unplanned receipt')
        require(type(item['provider_error']) is bool and type(item['tool_error']) is bool,'error flag types')
        require(type(item['normalization_errors']) is list and all(type(e) is str and e for e in item['normalization_errors']),'normalization errors')
        require(type(item['termination']) is str and item['termination'] in ('final','abstained','timeout','provider_error','tool_error'),'termination')
        require(item['termination']!='provider_error' or item['provider_error'],'provider error mapping')
        require(item['termination']!='tool_error' or item['tool_error'],'tool error mapping')
        if item['termination']=='abstained':
            require(item['raw_output'] is None and item['normalized_output'] is None and not item['normalization_errors'] and not item['provider_error'] and not item['tool_error'],'abstention shape')
        indexed[key]=item
    rows=[]
    for g in gold:
        for rep in range(plan['repetitions']):
            for a in plan['arms']:
                item=indexed.get((g['case_id'],rep,a))
                row=dict(case_id=g['case_id'],family=g['family'],base=g['base'],repetition=rep,arm=a,missing=item is None,success=False,unknown=False,error=False,timeout=False)
                if item is not None:
                    if item['termination']=='abstained':row['unknown']=True
                    else:
                        verdict=output_verdict(g['instance'],item['raw_output'],item['normalized_output'],item['normalization_errors'])
                        operational=item['termination']!='final' or item['provider_error'] or item['tool_error']
                        row.update(success=verdict['evidence_valid'] and verdict['status']==g['evidence']['gold_label'] and not operational,
                                   unknown=verdict['status']=='UNKNOWN',error=verdict['output_error'] or operational,timeout=item['termination']=='timeout')
                rows.append(row)
    def summary(group):
        return dict(planned=len(group),**{k:sum(bool(r[k]) for r in group) for k in ('missing','success','unknown','error','timeout')})
    return dict(status='offline_synthetic_receipt_assessment_not_model_results',by_arm={a:summary([r for r in rows if r['arm']==a]) for a in plan['arms']},
                by_construction={f'{g[0]}/{g[1]}':{a:summary([r for r in rows if (r['family'],r['base'])==g and r['arm']==a]) for a in plan['arms']} for g in sorted({(r['family'],r['base']) for r in rows})},rows=rows)
