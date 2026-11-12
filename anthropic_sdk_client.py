"""Optional official Anthropic SDK. Explicit key, fixed host, bounded isolated call."""
from pathlib import Path
import base64,hashlib,importlib.metadata as metadata,json,logging,os,re,stat,subprocess,sys
from solver_interface import require
from tier_a_contract import canonical
from paired_receipts import ENVELOPE_BYTES
ENDPOINT='https://api.anthropic.com/v1/messages'
SDK_VERSION='2.8.0'
VERSION='anthropic-explicit-sdk-v1'

def runtime():
 require(metadata.version('anthropic')==SDK_VERSION,'anthropic==2.8.0 required')
 names=['anthropic','httpx2','anyio','docstring-parser','jiter','opentelemetry-api','pydantic','sniffio','typing-extensions']
 versions={n:metadata.version(n) for n in names}
 require(versions['httpx2']=='2.16.0','reviewed httpx2==2.16.0 required')
 dist=metadata.distribution('anthropic')
 return {'versions':versions,'source_sha256':{n:hashlib.sha256(Path(dist.locate_file(n)).read_bytes()).hexdigest() for n in ['anthropic/_client.py','anthropic/_base_client.py','anthropic/_response.py']}}

def load_key_file(path):
 fd=os.open(Path(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as f:
  s=os.fstat(f.fileno());require(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and not s.st_mode&0o077 and s.st_size<=8192,'owner-only bounded regular key file required');raw=f.read(8193)
 require(len(raw)<=8192,'key file bound')
 try:
  lines=[x.strip() for x in raw.decode().splitlines() if x.strip() and not x.lstrip().startswith('#')]
  require(len(lines)==1 and lines[0].startswith('ANTHROPIC_API_KEY='),'one ANTHROPIC_API_KEY assignment required')
  key=lines[0].split('=',1)[1];require(re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key) is not None,'key representation')
 except (UnicodeError,ValueError):raise ValueError('one nonempty ANTHROPIC_API_KEY assignment; no expansion or extra keys') from None
 return key

def _in_process(body,timeout,key,*,http_transport=None,sdk_module=None,budget_usd=None,rates=None):
 require(body.get('stream') is False and len(body.get('messages',[]))==1 and body['messages'][0]['role']=='user' and 'system' not in body and 'tools' not in body,'single user message only')
 require(type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{16,512}',key),'credential representation')
 identity=runtime() if sdk_module is None else {'test_only':'injected SDK boundary; not installed SDK validation'}
 if sdk_module is None:import anthropic as sdk_module
 import httpx2
 previous=logging.root.manager.disable;logging.disable(logging.CRITICAL)
 state={'read_error':None};wire={};raw=b'';headers={};code=None
 class BoundedStream(httpx2.SyncByteStream):
  def __init__(self,inner):self.inner=inner
  def __iter__(self):
   remaining=ENVELOPE_BYTES+1
   try:
    for part in self.inner:
     piece=part[:remaining];remaining-=len(piece)
     if piece:yield piece
     if not remaining:break
   except (httpx2.TimeoutException,TimeoutError):state['read_error']='timeout'
   except Exception:state['read_error']='read_failure'
  def close(self):self.inner.close()
 class FixedTransport(httpx2.BaseTransport):
  def handle_request(self,request):
   require(request.method=='POST' and str(request.url)==ENDPOINT,'fixed Anthropic endpoint only')
   require(json.loads(request.content)==body and len(request.content)<=7500,'SDK request identity/byte cap')
   if budget_usd is not None:
    require(type(rates) is dict and ((len(request.content)+256)*max(rates[k] for k in ('input','cache_read','cache_write_short','cache_write_long'))+body['max_tokens']*rates['output'])/1000000<=budget_usd,'wire reserve insufficient')
   wire.update(request_bytes=len(request.content),request_sha256=hashlib.sha256(request.content).hexdigest())
   response=inner.handle_request(request);wire['encoding_supported']=response.headers.get('content-encoding','identity') in ('','identity')
   h=dict(response.headers);h.pop('content-encoding',None)
   return httpx2.Response(response.status_code,headers=h,stream=BoundedStream(response.stream),request=request,extensions=response.extensions)
  def close(self):inner.close()
 inner=http_transport if http_transport is not None else httpx2.HTTPTransport(retries=0,trust_env=False)
 client=None
 try:
  http=httpx2.Client(transport=FixedTransport(),trust_env=False,follow_redirects=False,timeout=httpx2.Timeout(timeout),headers={'Accept-Encoding':'identity'})
  client=sdk_module.Anthropic(api_key=key,webhook_key='',base_url='https://api.anthropic.com',max_retries=0,timeout=httpx2.Timeout(timeout),http_client=http,open_telemetry=False,middleware=[])
  try:
   with client.messages.with_streaming_response.create(**body) as response:
    code=response.status_code;headers=response.headers;raw=response.read()
  except sdk_module.APIStatusError as error:code=error.status_code;headers=error.response.headers;raw=error.response.content
  except sdk_module.APITimeoutError:raise TimeoutError('Anthropic timeout; remote outcome unknown') from None
  except Exception:raise ValueError('Anthropic SDK failure') from None
 finally:
  if client is not None:client.close()
  elif 'http' in locals():http.close()
  logging.disable(previous)
 complete=len(raw)<=ENVELOPE_BYTES and state['read_error'] is None
 from responses_http_v2 import redact
 raw,redacted=redact(raw,key,complete)
 safe={k:str(headers[k]).replace(key,'[CREDENTIAL_REDACTED]') for k in ['request-id','retry-after'] if k in headers}
 return code,safe,raw,complete,redacted,dict(version=VERSION,runtime=identity,wire=wire,**state)

def once(body,timeout,key,*,budget_usd=None,rates=None):
 runtime()
 payload=canonical({'body':body,'timeout':timeout,'key':key,'budget_usd':budget_usd,'rates':rates}).encode();require(len(payload)<=65536,'SDK worker input bound')
 program='import sys;sys.path.insert(0,'+repr(str(Path(__file__).resolve().parent))+');from anthropic_sdk_client import child;child()'
 try:r=subprocess.run([sys.executable,'-I','-c',program],input=payload,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,cwd=str(Path(__file__).resolve().parent),env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C.UTF-8'},timeout=timeout)
 except subprocess.TimeoutExpired:raise TimeoutError('local Anthropic worker deadline; remote outcome unknown') from None
 require(r.returncode==0 and len(r.stdout)<=2*1024*1024,'SDK worker bounded result')
 data=json.loads(r.stdout)
 if 'error' in data:
  if data['error']=='TimeoutError':raise TimeoutError('Anthropic timeout; remote outcome unknown') from None
  raise ValueError('Anthropic worker failure') from None
 return data['code'],data['headers'],base64.b64decode(data['raw'],validate=True),data['complete'],data['redacted'],data['meta']

def child():
 try:
  p=json.loads(sys.stdin.buffer.read(65537));require(set(p)=={'body','timeout','key','budget_usd','rates'},'worker fields')
  code,headers,raw,complete,redacted,meta=_in_process(**p)
  result=dict(code=code,headers=headers,raw=base64.b64encode(raw).decode(),complete=complete,redacted=redacted,meta=meta)
 except Exception as e:result={'error':'TimeoutError' if isinstance(e,TimeoutError) else 'ValueError'}
 sys.stdout.write(canonical(result))
