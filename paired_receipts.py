"""Shared bounded JSON receipt storage; large evidence is retained without truncation."""
from pathlib import Path
import hashlib,stat
from tier_a_contract import canonical,strict_json
VERSION='paired-receipt-retention-v1'
LINE_BYTES=8*1024*1024
EVIDENCE_BYTES=64*1024*1024
REQUEST_BYTES=1024*1024
ENVELOPE_BYTES=1024*1024

def policy():return dict(version=VERSION,line_bytes=LINE_BYTES,evidence_bytes=EVIDENCE_BYTES,request_bytes=REQUEST_BYTES,envelope_bytes=ENVELOPE_BYTES)
def encoded(value):return canonical(value).encode('utf-8')
def checked(condition,message):
 if not condition:raise ValueError(message)
def text_file(path,limit):
 info=path.lstat();checked(stat.S_ISREG(info.st_mode) and info.st_size<=limit,'regular bounded receipt evidence required')
 with path.open('rb') as stream:raw=stream.read(limit+1)
 checked(len(raw)<=limit,'receipt evidence grew past bound')
 return raw

def failure(item,reference,opaque=False):
 result=dict(item,resource_error='evidence_bound' if opaque else 'aggregate_receipt_bound',retained_evidence=reference)
 if opaque:
  result.update(termination='resource_bound',raw_output=None,normalized_output=None,normalization_errors=['full original receipt retained as opaque evidence; parse bound exceeded'])
  result['tool_calls']=[dict(retained_ordinal=i) for i in range(len(item['tool_calls']))]
  result['solver_events']=[{k:e[k] for k in ('error','timeout','elapsed_seconds')} for e in item['solver_events']]
  result['provider_calls']=[{k:v for k,v in call.items() if k in ('budget_usd','observed_usage','cost_violation','resource_error','transport_started','elapsed_seconds','timeout_seconds','error')} for call in item['provider_calls']]
 return result

def retain(directory,item):
 """Preserve the exact original before emitting a bounded failed-attempt representation."""
 raw=encoded(item)
 if len(raw)+1<=LINE_BYTES:return item,raw.decode()+'\n'
 name='evidence-'+item['attempt_id']+'.json';path=Path(directory)/name
 with path.open('xb') as stream:stream.write(raw)
 reference=dict(kind=VERSION,attempt_id=item['attempt_id'],file=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),opaque=len(raw)>EVIDENCE_BYTES)
 result=failure(item,reference,reference['opaque'])
 line=encoded(result).decode()+'\n' if reference['opaque'] else encoded(reference).decode()+'\n'
 checked(len(line.encode())<=LINE_BYTES,'bounded failure representation')
 return result,line

def resolve(directory,value):
 if type(value) is not dict:return value
 if value.get('resource_error')=='evidence_bound':
  reference=value.get('retained_evidence');validate_reference(directory,reference,opaque=True)
  checked(value.get('termination')=='resource_bound' and value.get('raw_output') is None,'opaque evidence is a failed attempt')
  return value
 if value.get('kind')!=VERSION:return value
 validate_reference(directory,value,opaque=False)
 raw=text_file(Path(directory)/value['file'],EVIDENCE_BYTES)
 checked(hashlib.sha256(raw).hexdigest()==value['sha256'],'evidence hash mismatch')
 item=strict_json(raw.decode());checked(type(item) is dict and item.get('attempt_id')==value['attempt_id'] and item.get('retained_evidence') is None,'original archived receipt identity')
 return failure(item,value)

def validate_reference(directory,value,opaque):
 checked(type(value) is dict and set(value)=={'kind','attempt_id','file','bytes','sha256','opaque'} and value['kind']==VERSION,'exact evidence reference')
 identity=value['attempt_id'];checked(type(identity) is str and len(identity)==64 and all(x in '0123456789abcdef' for x in identity),'evidence attempt identity')
 checked(value['file']=='evidence-'+identity+'.json','evidence path identity')
 checked(type(value['bytes']) is int and value['bytes']>=0 and value['opaque'] is opaque and (value['bytes']>EVIDENCE_BYTES if opaque else value['bytes']<=EVIDENCE_BYTES),'evidence declared bound')
 checked(type(value['sha256']) is str and len(value['sha256'])==64 and all(x in '0123456789abcdef' for x in value['sha256']),'evidence digest shape')
 info=(Path(directory)/value['file']).lstat();checked(stat.S_ISREG(info.st_mode) and info.st_size==value['bytes'],'regular retained evidence metadata')
 # Opaque overflow is not parsed/hashed by assessment; it can never yield success.

def read(directory,maximum):
 out=[];path=Path(directory)/'attempts.jsonl';info=path.lstat()
 checked(stat.S_ISREG(info.st_mode) and info.st_size<=maximum*LINE_BYTES,'regular bounded attempt stream required')
 with path.open('rb') as stream:
  while True:
   line=stream.readline(LINE_BYTES+1)
   if not line:break
   checked(len(out)<maximum and len(line)<=LINE_BYTES and line.endswith(b'\n'),'bounded complete attempt line')
   out.append(resolve(directory,strict_json(line.decode())))
 return out
