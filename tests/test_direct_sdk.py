import json,unittest,io,tempfile,os,subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import anthropic_sdk_client as sdk
import direct_api_providers as providers
import test_direct_benchmark as helper
settings=helper.settings
try:
 import httpx2
 HAVE_HTTPX=True
except ImportError:HAVE_HTTPX=False
KEY='synthetic-direct-key-only'
class FakeStatus(Exception):pass
class FakeTimeout(Exception):pass
class FakeSDK:
 APIStatusError=FakeStatus;APITimeoutError=FakeTimeout;constructed=[]
 class Anthropic:
  def __init__(self,**kwargs):
   FakeSDK.constructed.append(kwargs);self.http=kwargs['http_client'];self.key=kwargs['api_key'];self.messages=SimpleNamespace(with_streaming_response=SimpleNamespace(create=self.create))
  def create(self,**body):return self.http.stream('POST',sdk.ENDPOINT,json=body,headers={'x-api-key':self.key})
  def close(self):self.http.close()

class KeyFileTests(unittest.TestCase):
 def test_synthetic_anthropic_key_file_and_no_fallback(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'key';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'w') as f:f.write('ANTHROPIC_API_KEY='+KEY+'\n')
   self.assertEqual(sdk.load_key_file(path),KEY)
   path.write_text('OPENAI_API_KEY='+KEY+'\n')
   with self.assertRaises(ValueError):sdk.load_key_file(path)
   link=Path(td)/'link';link.symlink_to(path)
   with self.assertRaises(OSError):sdk.load_key_file(link)
   with patch.dict(os.environ,{'ANTHROPIC_API_KEY':KEY}):
    with self.assertRaises(OSError):sdk.load_key_file(Path(td)/'missing')
 def test_worker_uses_clean_environment_stdin_and_no_retry(self):
  packed=json.dumps(dict(code=200,headers={},raw='e30=',complete=True,redacted=False,meta={})).encode()
  with patch.object(sdk,'runtime',return_value={'test_only':True}),patch.object(sdk.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=packed)) as run:
   self.assertEqual(sdk.once({},2,KEY)[2],b'{}');a,k=run.call_args;self.assertNotIn(KEY,str(a));self.assertIn(KEY.encode(),k['input']);self.assertEqual(k['env'],{'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C.UTF-8'});self.assertEqual(run.call_count,1)
  with patch.object(sdk,'runtime',return_value={}),patch.object(sdk.subprocess,'run',side_effect=subprocess.TimeoutExpired('synthetic',2)) as run:
   with self.assertRaises(TimeoutError):sdk.once({},2,KEY)
   self.assertEqual(run.call_count,1)

@unittest.skipUnless(HAVE_HTTPX,'optional pinned HTTP/SDK environment required')
class AnthropicBoundaryTests(unittest.TestCase):
 def body(self):return providers.body('anthropic_api','exact user prompt',dict(settings(),model='mock-model'))
 def invoke(self,handler):return sdk._in_process(self.body(),2,KEY,http_transport=httpx2.MockTransport(handler),sdk_module=FakeSDK)
 def test_one_message_serialization_and_constructor_security(self):
  seen=[]
  def handler(request):seen.append(json.loads(request.content));self.assertEqual(str(request.url),sdk.ENDPOINT);return httpx2.Response(200,json=helper.ProviderTests().envelope('anthropic_api'))
  r=self.invoke(handler);self.assertEqual(seen,[self.body()]);self.assertTrue(r[3]);self.assertEqual(r[5]['runtime'],{'test_only':'injected SDK boundary; not installed SDK validation'});kw=FakeSDK.constructed[-1];self.assertEqual(kw['max_retries'],0);self.assertIs(kw['open_telemetry'],False);self.assertEqual(kw['base_url'],'https://api.anthropic.com');self.assertEqual(kw['api_key'],KEY)
 def test_status_redirect_and_credential_echo_do_not_retry(self):
  for code in [200,302,429,500]:
   seen=[]
   def handler(request):seen.append(1);return httpx2.Response(code,content=('echo:'+KEY).encode(),headers={'request-id':KEY,'location':'https://invalid.example/never-follow'})
   r=self.invoke(handler);self.assertEqual(len(seen),1);self.assertEqual(r[0],code);self.assertNotIn(KEY,str(r));self.assertTrue(r[4])
 def test_partial_timeout_non_timeout_and_unsupported_encoding(self):
  for failure in ['timeout','read_failure']:
   class Stream(httpx2.SyncByteStream):
    def __iter__(self):
     yield b'echo:'+KEY[:12].encode()
     if failure=='timeout':raise httpx2.ReadTimeout('synthetic')
     raise RuntimeError('synthetic')
   r=self.invoke(lambda req:httpx2.Response(200,stream=Stream()));self.assertFalse(r[3]);self.assertEqual(r[5]['read_error'],failure);self.assertNotIn(KEY[:12].encode(),r[2])
  r=self.invoke(lambda req:httpx2.Response(200,stream=httpx2.ByteStream(b'{}'),headers={'content-encoding':'gzip'}));self.assertFalse(r[5]['wire']['encoding_supported']);self.assertEqual(r[2],b'{}')
 @unittest.skipUnless(__import__('importlib').util.find_spec('openai'),'optional OpenAI SDK required')
 def test_openai_official_sdk_accepts_same_single_user_body(self):
  from openai_sdk_client import sdk_once
  body=providers.body('openai_api','exact user prompt',dict(settings(),model='mock-model'));seen=[]
  def handler(request):seen.append(json.loads(request.content));return httpx2.Response(200,json=helper.ProviderTests().envelope('openai_api'))
  r=sdk_once(body,2,KEY,http_transport=httpx2.MockTransport(handler));self.assertEqual(seen,[body]);self.assertTrue(r[3]);self.assertNotIn('instructions',seen[0])
