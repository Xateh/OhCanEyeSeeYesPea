"""Versioned strict text-protocol bridge to the merged isolated Claude transport.
Construction alone never calls a provider. Live transport requires runner opt-in.
"""
from copy import deepcopy
from pathlib import Path
import hashlib,json,math,re,subprocess,time,sys
from study.claude_provider import ClaudeCodeProvider,run_cli
from study.prompts import SYSTEM_V1
from study.accounting import known_cost
import paired_receipts as retention
from tier_a_contract import strict_json,canonical
VERSION='claude-paired-text-json-v2'
SERIALIZATION='merged-user-message-v1-strict-unfenced-json-exact-output-span-v1'

def binding(model,effort,call_wall_seconds,call_budget_usd):
 if type(model) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',model):raise ValueError('explicit safe model identity required')
 if effort not in ('low','medium','high','max'):raise ValueError('unsupported effort')
 if type(call_wall_seconds) is not int or not 1<=call_wall_seconds<=3600:raise ValueError('call timeout software bound')
 if type(call_budget_usd) not in (int,float) or not 0<call_budget_usd<1_000_000_000 or not math.isfinite(call_budget_usd):raise ValueError('finite positive call USD budget required')
 root=Path(__file__).resolve().parent
 return dict(version=VERSION,model=model,effort=effort,call_wall_seconds=call_wall_seconds,call_budget_usd=call_budget_usd,serialization=SERIALIZATION,runtime=dict(implementation=sys.implementation.name,version=sys.version),retention_policy=retention.policy(),source_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('claude_pair_adapter.py','study/claude_provider.py','study/prompts.py','study/accounting.py','tier_a_contract.py','paired_receipts.py')})

def validate(value):
 if type(value) is not dict:raise ValueError('explicit provider binding required')
 expected=binding(value.get('model'),value.get('effort'),value.get('call_wall_seconds'),value.get('call_budget_usd'))
 if value!=expected:raise ValueError('provider binding/source/serialization mismatch')
 return deepcopy(value)

def output_span(raw):
 """Return the untouched JSON value slice; whole-object strict parsing happens first."""
 decoder=json.JSONDecoder();i=raw.index('{')+1
 while True:
  while raw[i].isspace():i+=1
  key,end=decoder.raw_decode(raw,i);i=end
  while raw[i].isspace():i+=1
  if raw[i]!=':':raise ValueError('JSON member separator')
  i+=1
  while raw[i].isspace():i+=1
  start=i;_,i=decoder.raw_decode(raw,i)
  if key=='output':return raw[start:i]
  while raw[i].isspace():i+=1
  if raw[i]!=',':raise ValueError('missing final output')
  i+=1

class ClaudePairAdapter:
 offline=False
 def __init__(self,configuration,transport=None,*,allow_live=False):
  self.binding=validate(configuration);self.revision=VERSION;self.calls=[]
  if transport is None and allow_live is not True:raise ValueError('default live transport requires explicit opt-in')
  self.transport=transport or run_cli
 def respond(self,messages,tools,limits):
  if len(messages)<2 or messages[0]['role']!='system' or messages[1]['role']!='user':raise ValueError('validated paired message assembly required')
  history=[]
  for i in range(2,len(messages),2):
   a,b=messages[i:i+2]
   if a['role']!='assistant' or b['role']!='tool' or b.get('name')!='csp':raise ValueError('text tool history routing')
   call=strict_json(a['content'])['tool_call'];history.append(dict(arguments=call['arguments'],result=strict_json(b['content'])))
  remaining=limits['wall_seconds'];budget=min(self.binding['call_budget_usd'],limits['spending_remaining_usd'])
  if remaining<=0 or budget<=0:raise ValueError('no remaining call allocation')
  record=dict(raw_envelope=None,raw_model_text=None,elapsed_seconds=None,error=None,resource_error=None,transport_started=False,observed_usage=None,cost_violation=False,timeout_seconds=min(self.binding['call_wall_seconds'],remaining),budget_usd=budget,serialization=SERIALIZATION)
  observed=None;started=time.perf_counter()
  def transport(argv,stdin,cwd):
   argv=list(argv);argv[argv.index('--system-prompt')+1]=messages[0]['content']+'\n'+SYSTEM_V1
   argv[argv.index('--max-budget-usd')+1]=str(budget)
   record['request']=dict(argv=argv,stdin=stdin)
   if len(canonical(record['request']).encode())>retention.REQUEST_BYTES:
    record['resource_error']='request_bound';raise ValueError('serialized request bound before transport')
   record['transport_started']=True
   options=dict(timeout_seconds=record['timeout_seconds'])
   if self.transport is run_cli:options['status_observer']=lambda code:record.update(returncode=code)
   raw=self.transport(argv,stdin,cwd,**options)
   record['raw_envelope']=raw
   if type(raw) is not str:raise ValueError('CLI envelope text required')
   if len(raw.encode('utf-8','surrogatepass'))>retention.ENVELOPE_BYTES:
    record['resource_error']='envelope_bound';raise ValueError('CLI envelope software bound')
   strict_json(raw)
   return raw
  provider=ClaudeCodeProvider('v1',model=self.binding['model'],effort=self.binding['effort'],runner=transport)
  try:
   reply=provider.next(messages[1]['content'],history,tools);observed=reply['usage'];raw=reply['raw_text'];record['raw_model_text']=raw
   if record.get('returncode',0)!=0:raise ValueError('nonzero CLI exit')
   parsed=strict_json(raw)
   if type(parsed) is not dict:raise ValueError('strict JSON object required')
   if parsed.get('type')=='final' and set(parsed)=={'type','output'}:
    return dict(type='final',raw=output_span(raw),usage=observed)
   if set(parsed)=={'type','name','arguments'} and parsed['type']=='tool_call' and parsed['name']=='csp':return dict(**parsed,usage=observed)
   raise ValueError('strict text protocol shape')
  except Exception as error:
   observed=getattr(error,'observed_usage',observed);record['error']=type(error).__name__
   if isinstance(error,subprocess.TimeoutExpired):
    partial=error.stdout
    record['partial_stdout']=partial.decode('utf-8',errors='replace') if isinstance(partial,bytes) else partial
    replacement=TimeoutError('CLI transport timeout')
   else:replacement=ValueError('Claude adapter failure: '+type(error).__name__)
   if not record['transport_started']:observed=dict(input_tokens=0,output_tokens=0,cost_usd=0)
   replacement.observed_usage=observed
   raise replacement from None
  finally:
   if record['raw_model_text'] is None and type(record['raw_envelope']) is str and len(record['raw_envelope'].encode('utf-8','surrogatepass'))<=retention.ENVELOPE_BYTES:
    try:
     envelope=strict_json(record['raw_envelope']);record['raw_model_text']=envelope.get('result') if type(envelope) is dict else None
    except (ValueError,RecursionError):pass
   if not record['transport_started']:observed=dict(input_tokens=0,output_tokens=0,cost_usd=0)
   record['observed_usage']=deepcopy(observed)
   cost=observed.get('cost_usd') if type(observed) is dict else None
   record['cost_violation']=known_cost(cost) and cost>budget
   record['elapsed_seconds']=time.perf_counter()-started;self.calls.append(record)
