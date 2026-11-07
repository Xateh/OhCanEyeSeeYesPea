"""Direct public Responses transport. No credential/environment reads at import or preflight."""
from copy import deepcopy
from pathlib import Path
import base64,hashlib,http.client,json,math,os,re,stat,sys,time,urllib.request,urllib.error
from tier_a_contract import strict_json,canonical
from study.accounting import known_cost
import paired_receipts as retention
VERSION='openai-responses-phase-text-json-v2'
ENDPOINT='https://api.openai.com/v1/responses'
SERIALIZATION='responses-phase-specific-text-json-v1'

def require(ok,message):
 if not ok:raise ValueError(message)
def binding(model,expected_model,profile,effort,max_output_tokens,call_wall_seconds,call_budget_usd,rates):
 for name in (model,expected_model):require(type(name) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',name),'explicit model identifiers required')
 require(expected_model==model or expected_model.startswith(model+'-'),'explicit returned-model family required')
 require(profile in ('mock-responses-v1','gpt-6.1-sol-text-json-v1'),'unsupported settings profile')
 require(profile=='mock-responses-v1' or model=='gpt-6.1-sol','profile/model mismatch')
 require(effort in ('low','medium','high','xhigh','max'),'explicit supported reasoning effort required')
 require(type(max_output_tokens) is int and 1<=max_output_tokens<=128000,'output-token software bound')
 require(type(call_wall_seconds) is int and 1<=call_wall_seconds<=3600,'explicit call timeout bound')
 require(known_cost(call_budget_usd) and call_budget_usd>0,'explicit call estimate allocation')
 require(type(rates) is dict and set(rates)=={'input_per_million','cached_input_per_million','output_per_million','source'},'explicit pricing identity/rates')
 require(type(rates['source']) is str and 0<len(rates['source'])<=512,'pricing source required')
 for k in ('input_per_million','cached_input_per_million','output_per_million'):require(known_cost(rates[k]),'finite nonnegative pinned rates required')
 root=Path(__file__).resolve().parent
 return dict(version=VERSION,endpoint=ENDPOINT,model=model,expected_model=expected_model,profile=profile,reasoning_effort=effort,max_output_tokens=max_output_tokens,call_wall_seconds=call_wall_seconds,call_budget_usd=call_budget_usd,rates=deepcopy(rates),serialization=SERIALIZATION,transport_retries=0,model_fallback=False,runtime=dict(implementation=sys.implementation.name,version=sys.version),retention_policy=retention.policy(),source_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('responses_phase_transport.py','responses_transport.py','responses_credentials.py','study/prompts.py','tier_a_contract.py','study/accounting.py','paired_receipts.py','responses_http_v2.py')})
def validate(value):
 require(type(value) is dict,'explicit Responses binding required')
 expected=binding(*(value.get(k) for k in ('model','expected_model','profile','reasoning_effort','max_output_tokens','call_wall_seconds','call_budget_usd','rates')))
 require(value==expected,'Responses binding/source/settings drift');return deepcopy(value)
def observed_usage(value,rates,model_matched=True):
 if type(value) is not dict:return None
 def integer(x):return x if type(x) is int and x>=0 else None
 incoming=integer(value.get('input_tokens'));outgoing=integer(value.get('output_tokens'))
 total=value.get('total_tokens')
 if total is not None and (type(total) is not int or incoming is None or outgoing is None or total!=incoming+outgoing):incoming=outgoing=None
 reasoning=value.get('output_tokens_details')
 if type(reasoning) is dict and 'reasoning_tokens' in reasoning and (integer(reasoning['reasoning_tokens']) is None or outgoing is None or reasoning['reasoning_tokens']>outgoing):outgoing=None
 detail=value.get('input_tokens_details');cached=integer(detail.get('cached_tokens')) if type(detail) is dict else None
 if incoming is not None and cached is not None and cached>incoming:cached=None
 amount=None
 if model_matched and None not in (incoming,outgoing,cached):amount=((incoming-cached)*rates['input_per_million']+cached*rates['cached_input_per_million']+outgoing*rates['output_per_million'])/1000000
 return dict(input_tokens=incoming,output_tokens=outgoing,cached_input_tokens=cached,cost_estimate_usd=amount)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def http_once(body,timeout,key):
 require(type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key),'invalid credential representation')
 from responses_http_v2 import once
 return once(ENDPOINT,canonical(body).encode(),timeout,key,NoRedirect(),retention.ENVELOPE_BYTES)

# Separate loader is re-exported for explicit use, never invoked implicitly.
from responses_credentials import load_key_file

def render(messages,tools):
 from study.prompts import SYSTEM_V1,FINAL_SHAPE,TOOL_SHAPE,format_history
 require(type(messages) is list and len(messages)>=2,'paired messages required')
 history=[]
 for i in range(2,len(messages),2):
  a,b=messages[i:i+2];require(a['role']=='assistant' and b['role']=='tool' and b.get('name')=='csp','local result routing')
  call=strict_json(a['content'])['tool_call'];require(call['name']=='csp','checked CSP only')
  history.append(dict(arguments=call['arguments'],result=strict_json(b['content'])))
 require(len(history)<=1 and type(tools) is list and len(tools)<=1,'phase bounds')
 text=messages[1]['content']
 if not tools:
  require(not history,'baseline history forbidden');body=text+'\n\n'+FINAL_SHAPE
 elif not history:
  body=text+'\n\n'+TOOL_SHAPE+json.dumps(tools[0],sort_keys=True)
 else:
  body=text+'\n\n'+format_history(history)+'\n\n'+FINAL_SHAPE
 return messages[0]['content']+'\n'+SYSTEM_V1,body

def output_span(raw):
 # The whole outer object has already passed strict_json, including duplicate-key checks.
 decoder=json.JSONDecoder();i=raw.index('{')+1
 while True:
  while raw[i].isspace():i+=1
  key,i=decoder.raw_decode(raw,i)
  while raw[i].isspace():i+=1
  require(raw[i]==':','JSON member separator');i+=1
  while raw[i].isspace():i+=1
  start=i;_,i=decoder.raw_decode(raw,i)
  if key=='output':return raw[start:i]
  while raw[i].isspace():i+=1
  require(raw[i]==',','missing final output');i+=1

def extract_text(response):
 output=response.get('output',[]);require(type(output) is list,'Responses output list required')
 pieces=[]
 for item in output:
  require(type(item) is dict and item.get('type') in ('message','reasoning'),'unexpected/native tool output')
  if item['type']=='message':
   require(item.get('role')=='assistant' and type(item.get('content')) is list,'assistant content list required')
   for part in item['content']:
    require(type(part) is dict and part.get('type')=='output_text' and type(part.get('text')) is str,'refusal/unsupported content retained as failure')
    pieces.append(part['text'])
 return ''.join(pieces)

class ResponsesAdapter:
 revision=VERSION
 def __init__(self,configuration,transport=None,key_loader=None,*,allow_live=False):
  self.binding=validate(configuration);self.calls=[];self.is_mock=transport is not None
  require(self.is_mock or allow_live is True and callable(key_loader),'live transport/key-file access requires explicit opt-in')
  require(self.is_mock or self.binding['profile']!='mock-responses-v1','mock profile cannot run live')
  self.transport=transport;self.key_loader=key_loader
 def respond(self,messages,tools,limits):
  instructions,text=render(messages,tools);b=self.binding
  cap=min(b['max_output_tokens'],limits['token_limit']);require(type(cap) is int and cap>0,'positive remaining output allocation')
  budget=min(b['call_budget_usd'],limits['spending_remaining_usd']);timeout=min(b['call_wall_seconds'],limits['wall_seconds'])
  require(budget>0 and timeout>0,'remaining allocation required')
  body=dict(model=b['model'],instructions=instructions,input=text,tools=[],store=False,stream=False,max_output_tokens=cap,reasoning=dict(effort=b['reasoning_effort']))
  record=dict(request=body,endpoint=ENDPOINT,timeout_seconds=timeout,budget_usd=budget,cost_basis='estimate_from_pinned_rates_not_billing',billed_cost_usd=None,transport_started=False,raw_response=None,raw_model_text=None,observed_usage=None,cost_violation=False,resource_error=None,error=None,elapsed_seconds=None,response_complete=None)
  observed=None;started=time.perf_counter()
  try:
   if len(canonical(body).encode())>retention.REQUEST_BYTES:record['resource_error']='request_bound';raise ValueError('request bound before credential access')
   if self.is_mock:
    record['transport_started']=True;result=self.transport(deepcopy(body),timeout)
   else:
    key=self.key_loader();require(type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key),'invalid credential representation')
    record['transport_started']=True;result=http_once(body,timeout,key)
   require(type(result) is tuple and len(result) in (4,5,6),'HTTP transport contract')
   code,headers,raw,complete=result[:4]
   require(type(headers) is dict and type(complete) is bool,'HTTP metadata types')
   headers={k:v for k,v in headers.items() if k in ('x-request-id','openai-processing-ms','retry-after')}
   record.update(http_status=code,response_headers=headers,response_complete=complete,credential_echo_redacted=bool(result[4]) if len(result)>=5 else False)
   meta=result[5] if len(result)==6 else {'version':'bounded-raw-http-v2','read_error':None}
   require(type(meta) is dict and set(meta)=={'version','read_error'} and meta['version']=='bounded-raw-http-v2' and meta['read_error'] in (None,'timeout','read_failure'),'bounded HTTP metadata')
   record['http_read_error']=meta['read_error']
   require(type(raw) is bytes,'HTTP body bytes required')
   try:record['raw_response']=raw.decode('utf-8')
   except UnicodeError:record['raw_response_base64']=base64.b64encode(raw).decode()
   if meta['read_error']=='timeout':raise TimeoutError('HTTP read timeout; partial body retained')
   if meta['read_error']=='read_failure':raise ValueError('HTTP read failure; partial body retained')
   require(record['raw_response'] is not None,'non-UTF8 provider response retained')
   if not complete or len(raw)>retention.ENVELOPE_BYTES:record['resource_error']='envelope_bound';raise ValueError('incomplete/oversized HTTP body retained')
   response=strict_json(raw.decode());require(type(response) is dict,'Responses envelope object')
   matched=response.get('model')==b['expected_model'];observed=observed_usage(response.get('usage'),b['rates'],matched)
   record.update(response_id=response.get('id'),returned_model=response.get('model'),response_status=response.get('status'),incomplete_details=response.get('incomplete_details'))
   text=extract_text(response);record['raw_model_text']=text
   require(code==200 and response.get('status')=='completed' and not response.get('error'),'HTTP/provider/incomplete failure')
   require(matched,'returned model differs from explicit identity')
   parsed=strict_json(text);require(type(parsed) is dict,'strict text JSON object')
   if set(parsed)=={'type','output'} and parsed['type']=='final':return dict(type='final',raw=output_span(text),usage=observed)
   require(set(parsed)=={'type','name','arguments'} and parsed['type']=='tool_call' and parsed['name']=='csp','unsupported text-tool protocol')
   return dict(**parsed,usage=observed)
  except Exception as error:
   record['error']=type(error).__name__
   if not record['transport_started']:observed=dict(input_tokens=0,output_tokens=0,cached_input_tokens=0,cost_estimate_usd=0)
   replacement=TimeoutError('Responses transport timeout') if isinstance(error,TimeoutError) or isinstance(error,urllib.error.URLError) and isinstance(error.reason,TimeoutError) else ValueError('Responses transport/protocol failure: '+type(error).__name__)
   replacement.observed_usage=observed;raise replacement from None
  finally:
   record['observed_usage']=deepcopy(observed);amount=observed.get('cost_estimate_usd') if observed else None
   record['cost_violation']=known_cost(amount) and amount>budget
   record['elapsed_seconds']=time.perf_counter()-started;self.calls.append(record)

def validate_record(record,binding):
 """Recompute observable usage/estimates from retained HTTP data, not claimed dollars."""
 request=record.get('request')
 require(type(request) is dict and set(request)=={'model','instructions','input','tools','store','stream','max_output_tokens','reasoning'},'exact credential-free API request receipt')
 require(record.get('endpoint')==ENDPOINT and request['model']==binding['model'] and request['tools']==[] and request['store'] is False and request['stream'] is False,'API request identity/tool isolation')
 require(request['reasoning']=={'effort':binding['reasoning_effort']} and type(request['max_output_tokens']) is int and 1<=request['max_output_tokens']<=binding['max_output_tokens'],'API setting receipt mismatch')
 require(type(record.get('response_headers',{})) is dict and set(record.get('response_headers',{}))<={'x-request-id','openai-processing-ms','retry-after'},'unapproved response-header receipt')
 require(record.get('http_read_error') in (None,'timeout','read_failure'),'HTTP read outcome')
 if record.get('http_read_error') is not None:
  require(record.get('response_complete') is False and record.get('observed_usage') is None and record.get('error')==('TimeoutError' if record['http_read_error']=='timeout' else 'ValueError'),'partial HTTP outcome mismatch')
 expected=None
 if record.get('transport_started') is False:expected=dict(input_tokens=0,output_tokens=0,cached_input_tokens=0,cost_estimate_usd=0)
 elif record.get('response_complete') is True and type(record.get('raw_response')) is str:
  raw=record['raw_response'];require(len(raw.encode())<=retention.ENVELOPE_BYTES,'raw API receipt bound')
  try:parsed=strict_json(raw)
  except (ValueError,RecursionError):parsed=None
  if type(parsed) is dict:
   expected=observed_usage(parsed.get('usage'),binding['rates'],parsed.get('model')==binding['expected_model'])
   try:expected_text=extract_text(parsed)
   except ValueError:expected_text=None
   require(record.get('raw_model_text')==expected_text,'HTTP body/model text disagreement')
 require(record.get('observed_usage')==expected,'raw API usage/estimate disagreement')
 require(record.get('billed_cost_usd') is None and record.get('cost_basis')=='estimate_from_pinned_rates_not_billing','estimates cannot assert billing')
