"""Official SDK boundary; no imports of SDK, environment or credentials at module import."""
from pathlib import Path
import importlib.metadata as metadata,hashlib,json,logging,re
from tier_a_contract import canonical
from solver_interface import require
import paired_receipts as retention
import subprocess,sys,base64
SDK_VERSIONS={'openai': '3.46.0', 'anyio': '4.16.0', 'httpx2': '2.16.0', 'httpcore2': '2.16.0', 'jiter': '0.19.0', 'pydantic': '2.14.3', 'pydantic-core': '2.50.4', 'typing-extensions': '4.16.0', 'sniffio': '1.3.1', 'annotated-types': '0.8.0', 'idna': '3.20', 'truststore': '0.10.5', 'typing-inspection': '0.4.5', 'h11': '0.16.0'}
ENDPOINT='https://api.openai.com/v1/responses'
def sdk_runtime():
 versions={k:metadata.version(k) for k in SDK_VERSIONS}
 require(versions==SDK_VERSIONS,'pinned optional SDK dependencies required')
 dist=metadata.distribution('openai');names=['openai/_client.py','openai/_base_client.py','openai/_response.py','openai/lib/_client_auth.py','openai/_utils/_transform.py','openai/resources/responses/responses.py']
 return dict(versions=versions,source_sha256={n:hashlib.sha256(Path(dist.locate_file(n)).read_bytes()).hexdigest() for n in names})
def _sdk_in_process(body,timeout,key,*,http_transport=None,budget_usd=.2,rates=None):
 require(type(body) is dict and body.get('stream') is False and body.get('tools')==[],'nonstreaming text protocol required')
 require(type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key),'invalid credential representation')
 identity=sdk_runtime();prior_logging=logging.root.manager.disable;logging.disable(logging.CRITICAL)
 try:
  import openai,httpx2
  read_state={'error':None}
  class LimitedStream(httpx2.SyncByteStream):
   def __init__(self,inner):self.inner=inner
   def __iter__(self):
    remaining=retention.ENVELOPE_BYTES+1
    try:
     for part in self.inner:
      piece=part[:remaining];remaining-=len(piece)
      if piece:yield piece
      if not remaining:break
    except (httpx2.TimeoutException,TimeoutError):read_state['error']='timeout'
    except Exception:read_state['error']='read_failure'
   def close(self):self.inner.close()
  wire={}
  rates=rates or {'input_per_million':10,'cache_write_30m_per_million':12.5,'output_per_million':50}
  class BoundTransport(httpx2.BaseTransport):
   def __init__(self,inner):self.inner=inner
   def handle_request(self,request):
    require(request.method=='POST' and str(request.url)==ENDPOINT,'fixed SDK endpoint only')
    require(json.loads(request.content)==body,'SDK request serialization drift')
    wire.update(request_bytes=len(request.content),request_sha256=hashlib.sha256(request.content).hexdigest())
    require(wire['request_bytes']<=7500,'SDK wire request bound')
    reserve=((wire['request_bytes']+256)*max(rates['input_per_million'],rates['cache_write_30m_per_million'])+body['max_output_tokens']*rates['output_per_million'])/1000000
    require(reserve<=budget_usd,'SDK wire reserve insufficient')
    response=self.inner.handle_request(request)
    wire['response_encoding_supported']=response.headers.get('content-encoding','identity') in ['identity','']
    headers=dict(response.headers)
    # Keep unsupported encoded bytes bounded and intact; never auto-decompress a bomb.
    if not wire['response_encoding_supported']:headers.pop('content-encoding',None)
    return httpx2.Response(response.status_code,headers=headers,stream=LimitedStream(response.stream),extensions=response.extensions,request=request)
   def close(self):self.inner.close()
  inner=http_transport if http_transport is not None else httpx2.HTTPTransport(retries=0,trust_env=False)
  http=httpx2.Client(transport=BoundTransport(inner),trust_env=False,follow_redirects=False,timeout=httpx2.Timeout(timeout),headers={'Accept-Encoding':'identity'})
  client=openai.OpenAI(api_key=key,admin_api_key='',organization='',project='',webhook_secret='',websocket_base_url='wss://api.openai.com/v1',base_url='https://api.openai.com/v1',http_client=http,max_retries=0,timeout=httpx2.Timeout(timeout))
  # Explicit empty constructor values prevent environment lookup; omit these optional headers.
  client.organization=None;client.project=None
  typed=None;typed_error=None
  try:
   try:
    with client.responses.with_streaming_response.create(**body) as response:
     raw=response.read();code=response.status_code;headers=response.headers
     if len(raw)<=retention.ENVELOPE_BYTES and wire.get('response_encoding_supported') and read_state['error'] is None:
      try:typed=response.parse().model_dump(mode='json',exclude_unset=True)
      except Exception:typed_error='typed_parse_error'
   except openai.APIStatusError as error:
    raw=error.response.content;code=error.status_code;headers=error.response.headers;typed_error='http_status_error'
   except openai.APITimeoutError:raise TimeoutError('SDK transport timeout') from None
   except Exception:raise ValueError('SDK transport failure') from None
  finally:client.close()
  complete=len(raw)<=retention.ENVELOPE_BYTES and read_state['error'] is None;secret=key.encode();redacted=secret in raw;raw=raw.replace(secret,b'[CREDENTIAL_REDACTED]')
  if not complete:
   for size in range(len(secret)-1,0,-1):
    if raw.endswith(secret[:size]):raw=raw[:-size]+b'[CREDENTIAL_REDACTED]';redacted=True;break
  safe_headers={k:str(headers[k]).replace(key,'[CREDENTIAL_REDACTED]') for k in ['x-request-id','openai-processing-ms','retry-after'] if k in headers}
  # Typed objects are diagnostic only: preserve the original bytes for parsing/scoring.
  try:matches=typed==json.loads(raw) if typed is not None and not redacted else None
  except (ValueError,UnicodeError):matches=False
  return code,safe_headers,raw,complete,redacted,dict(version='official-openai-sdk-transport-v2',read_error=read_state['error'],runtime=identity,typed_matches_raw=matches,typed_error=typed_error,max_retries=0,redirects=False,environment_routing=False,wire=wire)
 finally:logging.disable(prior_logging)

def sdk_once(body,timeout,key,*,http_transport=None,budget_usd=.2,rates=None):
 # Injected HTTP transports are for offline tests in a clean test environment only.
 if http_transport is not None:return _sdk_in_process(body,timeout,key,http_transport=http_transport,budget_usd=budget_usd,rates=rates)
 sdk_runtime()
 program="import sys;sys.path.insert(0,"+repr(str(Path(__file__).resolve().parent))+");from openai_sdk_client import _child_main;_child_main()"
 payload=canonical(dict(body=body,timeout=timeout,key=key,budget_usd=budget_usd,rates=rates)).encode()
 require(len(payload)<=65536,'SDK child input bound')
 try:
  done=subprocess.run([sys.executable,'-I','-c',program],input=payload,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C.UTF-8'},cwd=str(Path(__file__).resolve().parent),timeout=timeout)
 except subprocess.TimeoutExpired:raise TimeoutError('SDK local wall timeout; remote outcome unknown') from None
 require(done.returncode==0 and len(done.stdout)<=2*1024*1024,'SDK isolated worker failure')
 try:result=json.loads(done.stdout)
 except Exception:raise ValueError('SDK worker receipt failure') from None
 if 'error' in result:
  if result['error']=='TimeoutError':raise TimeoutError('SDK transport timeout') from None
  raise ValueError('SDK transport failure') from None
 require(set(result)=={'code','headers','raw_base64','complete','redacted','sdk'},'SDK worker fields')
 return result['code'],result['headers'],base64.b64decode(result['raw_base64'],validate=True),result['complete'],result['redacted'],result['sdk']
def _child_main():
 try:
  payload=sys.stdin.buffer.read(65537);require(len(payload)<=65536,'SDK worker input bound');p=json.loads(payload)
  require(set(p)=={'body','timeout','key','budget_usd','rates'},'SDK worker input fields')
  code,headers,raw,complete,redacted,meta=_sdk_in_process(p['body'],p['timeout'],p['key'],budget_usd=p['budget_usd'],rates=p['rates'])
  result=dict(code=code,headers=headers,raw_base64=base64.b64encode(raw).decode(),complete=complete,redacted=redacted,sdk=meta)
 except Exception as error:result={'error':'TimeoutError' if isinstance(error,TimeoutError) else 'ValueError'}
 sys.stdout.write(canonical(result))
