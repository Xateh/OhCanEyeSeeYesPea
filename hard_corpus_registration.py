"""Offline PR21 snapshot proposal; no runner/provider. Trust root is an explicit manifest hash."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,stat,sys
SOURCE=Path(__file__).resolve().parent
IMPLEMENTATION_VERSION='portable-hard-registration-v1'
ORIGIN_IMPLEMENTATION_SHA256='bb103303daebff0f6970c5656113d25860304687665b74e76d1abb20fd7bd210'
sys.path.insert(0,str(SOURCE))
from surgerybench.common import digest
from surgerybench.temporal_check import schema_errors,check_schedule,check_certificate
from surgerybench.temporal_text import RULES,render
from surgerybench.temporal_csp import CSPAdapter
from tier_a_contract import strict_json,output_verdict
VERSION='allan-hard-offline-registration-proposal-v1'
VIEW='hard-actual-id-view-v1'
HEAD='a9217a0cd8ee24ad6614dab9b2dba4aafc951431'
ARMS=['no_tools','csp']
INSTRUCTION='Solve the supplied instance. Return only the requested final JSON. Use actual instance IDs. Optional jobs may be omitted; no optimization objective is scored.'
EXAMPLE='{"kind":"pair_order_impossible","patients":["FIRST_ID","SECOND_ID"]}'
DESCRIPTION='an object with exactly kind="pair_order_impossible" and patients containing two distinct actual mandatory surgery IDs from this instance'
FILES={'gold.jsonl','model.jsonl','manifest.json','tool-receipts.jsonl'}
def require(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def bounded(path,cap):
 path=Path(path);s=path.lstat();require(stat.S_ISREG(s.st_mode) and not path.is_symlink(),'regular nonsymlink file required');require(s.st_size<=cap,'file size bound')
 with path.open('rb') as f:b=f.read(cap+1)
 require(len(b)<=cap,'file grew beyond bound');return b
def parse(b):
 depth=0;quoted=False;escape=False
 for c in b.decode('utf-8'):
  if quoted:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quoted=False
  elif c=='"':quoted=True
  elif c in '[{':
   depth+=1;require(depth<=24,'JSON depth bound')
  elif c in ']}':depth-=1;require(depth>=0,'JSON nesting')
 require(depth==0 and not quoted,'JSON nesting');return strict_json(b.decode('utf-8'))
def rows(b):
 lines=b.splitlines();require(len(lines)==100 and all(0<len(x)<=500000 for x in lines),'100 bounded records required');return [parse(x) for x in lines]
def view(instance,original):
 expected=render(instance).replace(RULES,RULES.replace('["A","E"]','["FIRST_ID","SECOND_ID"]'))
 require(original==expected and original.count(EXAMPLE)==1,'exact original renderer identity')
 return original.replace(EXAMPLE,DESCRIPTION)
def evidence(instance,status,output):
 if status=='FEASIBLE':return type(output) is dict and output.get('status')==status and not check_schedule(instance,output.get('schedule'))
 return type(output) is dict and output.get('status')==status and check_certificate(instance,output.get('certificate'))
def source_hashes():
 names=['study/hard_dataset.py','tier_a_contract.py']+['fixtures/hard-synthetic-v1/'+n for n in ('model.jsonl','gold.jsonl','manifest.json')]+[str(p.relative_to(SOURCE)) for p in sorted((SOURCE/'surgerybench').glob('*.py'))]
 return {n:sha(bounded(SOURCE/n,1000000)) for n in names}
def inspect_original(gold,model):
 require(len(gold)==len(model)==100,'count');require(len({g['id'] for g in gold})==100,'unique IDs');families={}
 for g,m in zip(gold,model):
  require(set(m)=={'id','text'} and m['id']==g['id'],'model schema/join')
  require(set(g)=={'id','family','size','label','variant','instance','evidence','instance_sha256','text_sha256','split','source'},'gold schema')
  i=g['instance'];require(not schema_errors(i),'canonical schema')
  require(g['size'] in (5,10,20,40,80) and len(i['patients'])==g['size'],'size');require(g['label'] in ('FEASIBLE','INFEASIBLE'),'label')
  require(digest(i)==g['instance_sha256'] and sha(m['text'].encode())==g['text_sha256'],'instance/text digest')
  require(g['source']=={'kind':'original_synthetic','durations_doi':'10.5281/zenodo.7147921'} and g['split']=='evaluation','source metadata')
  require(g['variant']==g['label'].lower(),'variant')
  require(g['id'].startswith(g['family'].replace('hard-synthetic-v1-','hard-')+'-') and g['id'].endswith(digest(i)[:10]),'case identity')
  e=g['evidence'];key='witness' if g['label']=='FEASIBLE' else 'certificate';require(set(e)=={key},'evidence shape')
  require(evidence(i,g['label'],dict(status=g['label'],**({'schedule':e[key]} if key=='witness' else {'certificate':e[key]}))),'authored evidence invalid')
  view(i,m['text']);families.setdefault(g['family'],[]).append(g)
 require(len(families)==50 and all(sorted(g['label'] for g in gs)==['FEASIBLE','INFEASIBLE'] for gs in families.values()),'50 paired families')
 require(all(sum(g['size']==s for g in gold)==20 for s in (5,10,20,40,80)),'size coverage');return families
def preflight(directory,identity):
 d=Path(directory);require(d.is_dir() and not d.is_symlink(),'package directory');require({p.name for p in d.iterdir()}==FILES,'exact package files')
 blob={n:bounded(d/n,20000000 if n.endswith('.jsonl') else 1000000) for n in FILES}
 require(type(identity) is str and sha(blob['manifest.json'])==identity,'explicit manifest identity');manifest=parse(blob['manifest.json'])
 require(set(manifest)=={'version','source_head','sources','input_view','instruction_sha256','files','admission','count'},'manifest schema')
 require(manifest['version']==VERSION and manifest['source_head']==HEAD and manifest['input_view']==VIEW,'unsupported version/source')
 require(manifest['sources']==source_hashes() and manifest['instruction_sha256']==sha(INSTRUCTION.encode()),'source/input drift')
 require(manifest['count']==100 and manifest['admission']=='checked-authored-proof-and-actual-tool-supported-evidence-v1','admission contract')
 require(manifest['files']=={n:sha(blob[n]) for n in FILES-{'manifest.json'}},'file hashes')
 require(all(sha(blob[n])==manifest['sources']['fixtures/hard-synthetic-v1/'+n] for n in ('gold.jsonl','model.jsonl')),'original export bytes required')
 gold=rows(blob['gold.jsonl']);model=rows(blob['model.jsonl']);receipts=rows(blob['tool-receipts.jsonl']);inspect_original(gold,model)
 require([r.get('id') for r in receipts]==[g['id'] for g in gold],'receipt join/ordering');eligible=[]
 for g,r in zip(gold,receipts):
  require(set(r)=={'id','tool_revision','result','accepted','elapsed_seconds','oracle'},'receipt schema')
  require(r['tool_revision']==CSPAdapter.revision and type(r['accepted']) is bool,'tool identity')
  require(type(r['elapsed_seconds']) in (int,float) and 0<=r['elapsed_seconds']<60,'receipt elapsed')
  require(r['oracle']=={'executed':False,'reason':'large Cartesian domains; no complete enumeration claimed'},'oracle semantics')
  result=r['result'];require(type(result) is dict and result.get('status') in ('FEASIBLE','INFEASIBLE','UNKNOWN'),'tool status')
  accepted=evidence(g['instance'],g['label'],result);require(r['accepted']==accepted,'false admission/tool evidence')
  if accepted:eligible.append(g['id'])
 return deepcopy(gold),deepcopy(model),tuple(eligible)
def prepare(directory,identity,plan):
 gold,model,eligible=preflight(directory,identity)
 require(type(plan) is dict and set(plan)=={'version','manifest_sha256','selected_ids','arms','repetitions'},'plan schema')
 require(plan['version']==VERSION and plan['manifest_sha256']==identity,'plan identities')
 ids=plan['selected_ids'];require(type(ids) is list and ids and all(type(x) is str for x in ids) and len(set(ids))==len(ids) and set(ids)<=set(eligible),'explicit unique eligible selection')
 require(plan['arms']==ARMS and type(plan['repetitions']) is int and 1<=plan['repetitions']<=10,'matched arms/repetition bounds')
 lookup={g['id']:(g,m) for g,m in zip(gold,model)}
 slots=[(cid,rep,arm) for cid in ids for rep in range(plan['repetitions']) for arm in ARMS]
 payloads={arm:[{'messages':[{'role':'system','content':INSTRUCTION},{'role':'user','content':view(lookup[cid][0]['instance'],lookup[cid][1]['text'])}], 'tools':[] if arm=='no_tools' else [deepcopy(CSPAdapter.tool_definition)]} for cid in ids for rep in range(plan['repetitions'])] for arm in ARMS}
 return slots,payloads,lookup
def assess(directory,identity,plan,receipts):
 slots,payloads,lookup=prepare(directory,identity,plan);require(type(receipts) is list and len(receipts)<=len(slots),'receipt bound');observed={}
 for r in receipts:
  require(type(r) is dict and set(r)=={'case_id','repetition','arm','raw','normalized','normalization_errors','termination'},'attempt schema')
  require(type(r['case_id']) is str and type(r['arm']) is str and type(r['repetition']) is int,'receipt routing types')
  key=(r['case_id'],r['repetition'],r['arm']);require(key in slots and key not in observed,'duplicate/unplanned receipt')
  require(r['termination'] in ('final','timeout','error','abstention') and type(r['normalization_errors']) is list and all(type(x) is str for x in r['normalization_errors']),'attempt metadata')
  verdict=output_verdict(lookup[key[0]][0]['instance'],r['raw'],r['normalized'],r['normalization_errors'])
  observed[key]=dict(verdict,success=r['termination']=='final' and verdict['evidence_valid'] and verdict['status']==lookup[key[0]][0]['label'])
 arms={a:dict(planned=sum(k[2]==a for k in slots),received=sum(k[2]==a for k in observed),missing=sum(k[2]==a and k not in observed for k in slots),success=sum(v['success'] for k,v in observed.items() if k[2]==a)) for a in ARMS}
 pairs=dict(both=0,no_tools_only=0,csp_only=0,neither=0,incomplete=0)
 for cid,rep in dict.fromkeys((k[0],k[1]) for k in slots):
  ks=[(cid,rep,a) for a in ARMS]
  if any(k not in observed for k in ks):pairs['incomplete']+=1;continue
  a,b=(observed[k]['success'] for k in ks);pairs['both' if a and b else 'no_tools_only' if a else 'csp_only' if b else 'neither']+=1
 return dict(arms=arms,pairs=pairs,verdicts=observed)
