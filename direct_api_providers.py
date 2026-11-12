"""Explicit single-user-message API providers; network construction is opt-in."""
from copy import deepcopy
import base64,json,time,math
from tier_a_contract import canonical,strict_json
from solver_interface import require
VERSION='direct-single-message-providers-v1'
RATE_KEYS={'input','output','cache_read','cache_write_short','cache_write_long','source'}

def body(provider,prompt,c):
 common={'model':c['model'],'stream':False}
 if provider=='openai_api':return dict(common,input=[{'role':'user','content':prompt}],reasoning={'effort':c['effort']},service_tier='default',max_output_tokens=c['max_output_tokens'],tools=[],store=False)
 if provider=='anthropic_api':return dict(common,messages=[{'role':'user','content':prompt}],max_tokens=c['max_output_tokens'],service_tier='standard_only',thinking={'type':'adaptive'},output_config={'effort':c['effort']})
 raise ValueError('explicit supported API provider required')

def estimate_reserve(request,c):
 rates=c['rates'];return ((len(canonical(request).encode())+256)*max(rates[k] for k in ('input','cache_read','cache_write_short','cache_write_long'))+c['max_output_tokens']*rates['output'])/1000000

def usage(provider,envelope,rates):
 u=envelope.get('usage');out={'input_tokens':None,'output_tokens':None,'cost_estimate_usd':None,'reported':deepcopy(u),'returned_tier':None}
 if type(u) is not dict:return out
 def integer(x):return type(x) is int and x>=0
 if provider=='openai_api':
  I=u.get('input_tokens');O=u.get('output_tokens');d=u.get('input_tokens_details') or {};R=d.get('cached_tokens');W=d.get('cache_write_tokens');Q=(u.get('output_tokens_details') or {}).get('reasoning_tokens');tier=envelope.get('service_tier');out['returned_tier']=tier
  if not all(integer(x) for x in (I,O,R,W,Q)) or R+W>I or Q>O or u.get('total_tokens')!=I+O:return out
  out.update(input_tokens=I,output_tokens=O)
  if tier!='default' or set(d)-{'cached_tokens','cache_write_tokens','cache_write_tokens_details'}:return out
  details=d.get('cache_write_tokens_details');short=W;long=0
  if details is not None:
   short=details.get('ttl_30m_tokens');long=details.get('ttl_12h_tokens')
   if not all(integer(x) for x in (short,long)) or short+long!=W:return out
  ordinary=I-R-W
 elif provider=='anthropic_api':
  I=u.get('input_tokens');O=u.get('output_tokens');R=u.get('cache_read_input_tokens');W=u.get('cache_creation_input_tokens');tier=u.get('service_tier');out['returned_tier']=tier
  if not all(integer(x) for x in (I,O,R,W)):return out
  out.update(input_tokens=I+R+W,output_tokens=O)
  if tier!='standard' or u.get('speed','standard')!='standard' or u.get('inference_geo','global')!='global':return out
  if any(v for v in (u.get('server_tool_use') or {}).values()):return out
  details=u.get('cache_creation');short=0;long=0
  if W:
   if type(details) is not dict:return out
   short=details.get('ephemeral_5m_input_tokens');long=details.get('ephemeral_1h_input_tokens')
   if not all(integer(x) for x in (short,long)) or short+long!=W:return out
  ordinary=I
 else:return out
 out['cost_estimate_usd']=(ordinary*rates['input']+R*rates['cache_read']+short*rates['cache_write_short']+long*rates['cache_write_long']+O*rates['output'])/1000000
 return out

def extract(provider,envelope):
 if provider=='openai_api':
  require(envelope.get('status')=='completed' and not envelope.get('error') and not envelope.get('incomplete_details'),'incomplete/error response')
  require(type(envelope.get('output')) is list and all(type(i) is dict and i.get('type') in ('reasoning','message') for i in envelope['output']),'unsupported native output item')
  blocks=[b for item in envelope.get('output',[]) if item.get('type')=='message' and item.get('role')=='assistant' for b in item.get('content',[])]
  require(len(blocks)==1 and blocks[0].get('type')=='output_text' and type(blocks[0].get('text')) is str,'one text answer; no refusal/native tool')
 else:
  require(envelope.get('stop_reason')=='end_turn' and not envelope.get('stop_details'),'incomplete/refused/nonfinal response')
  content=envelope.get('content');require(type(content) is list and all(x.get('type') in ('text','thinking','redacted_thinking') for x in content),'no native tool or unsupported content')
  blocks=[x for x in content if x.get('type')=='text'];require(len(blocks)==1 and type(blocks[0].get('text')) is str,'one text answer')
 return blocks[0]['text']

class APIProvider:
 def __init__(self,c,*,transport=None,allow_live=False,key_loader=None):
  self.c=deepcopy(c);self.transport=transport;self.key_loader=key_loader;self.calls=[]
  require(c['provider'] in ('openai_api','anthropic_api'),'API selection')
  require((c['mode']=='mock' and callable(transport)) or (c['mode']=='live' and allow_live is True and transport is None and callable(key_loader)),'network disabled without live opt-in; mock transport required')
 def call(self,prompt,budget):
  c=self.c;request=body(c['provider'],prompt,c);require(len(canonical(request).encode())<=7500,'request byte bound');require(estimate_reserve(request,c)<=budget,'conservative per-call reserve')
  record=dict(request=request,raw_response_base64=None,raw_model_text=None,http_status=None,response_complete=False,redacted=False,usage=None,error=None,elapsed_seconds=None)
  self.calls.append(record);start=time.monotonic()
  try:
   if self.transport is not None:result=self.transport(request,c['call_seconds'])
   else:
    key=self.key_loader()
    if c['provider']=='openai_api':
     from openai_sdk_client import sdk_once
     result=sdk_once(request,c['call_seconds'],key,budget_usd=budget,rates={'input_per_million':c['rates']['input'],'cache_write_30m_per_million':max(c['rates']['cache_read'],c['rates']['cache_write_short'],c['rates']['cache_write_long']),'output_per_million':c['rates']['output']})
    else:
     from anthropic_sdk_client import once
     result=once(request,c['call_seconds'],key,budget_usd=budget,rates=c['rates'])
   if len(result)==4:result=(*result,False,{})
   code,headers,raw,complete,redacted,*meta=result;require(type(raw) is bytes and len(raw)<=1024*1024+1,'bounded response bytes')
   record.update(http_status=code,safe_headers=headers,raw_response_base64=base64.b64encode(raw).decode(),response_complete=complete,redacted=redacted,transport_metadata=meta[0] if meta else {})
   if record['transport_metadata'].get('read_error')=='timeout':raise TimeoutError('response stream timeout')
   require(complete and not redacted,'incomplete/redacted response')
   require(not record['transport_metadata'].get('read_error'),'partial transport response')
   wire=record['transport_metadata'].get('wire',{});require(wire.get('encoding_supported',wire.get('response_encoding_supported',True)),'unsupported encoding')
   envelope=strict_json(raw.decode());require(type(envelope) is dict,'provider envelope')
   record['usage']=usage(c['provider'],envelope,c['rates'])
   require(code==200 and envelope.get('model')==c['model'],'HTTP/model identity')
   record['raw_model_text']=extract(c['provider'],envelope)
  except Exception as e:record['error']='timeout' if isinstance(e,TimeoutError) else 'provider_or_response_error'
  record['elapsed_seconds']=time.monotonic()-start
  return deepcopy(record)
