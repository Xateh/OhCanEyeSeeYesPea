import json,unittest,sys,tempfile,io,logging
from pathlib import Path
from copy import deepcopy
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
from types import SimpleNamespace
try:
 import openai,httpx2
 AVAILABLE=True
except ImportError:AVAILABLE=False
import responses_sdk_transport as api
from responses_fixture import configure
configure()
@unittest.skipUnless(AVAILABLE,'pinned optional SDK environment required')
class SDKTests(unittest.TestCase):
 def body(self):
  from schema_final_replay import register,body
  p,_=register();return body(p,p['case_ids'][0],'on')
 def envelope(self):return dict(id='resp_synthetic',model='gpt-6-astra',object='response',created_at=1,service_tier='default',status='completed',incomplete_details=None,error=None,output=[dict(id='msg_synthetic',type='message',role='assistant',status='completed',content=[dict(type='output_text',text='{"type":"final","output":{"status":"UNKNOWN"}}',annotations=[])])],usage=dict(input_tokens=100,output_tokens=30,total_tokens=130,input_tokens_details={'cached_tokens':0,'cache_write_tokens':0},output_tokens_details={'reasoning_tokens':0}))
 def test_real_sdk_serialization_and_typed_raw_parity(self):
  b=self.body();seen=[];env=self.envelope()
  def handler(req):
   seen.append(json.loads(req.content));self.assertEqual(str(req.url),api.ENDPOINT);self.assertNotIn('openai-organization',req.headers);return httpx2.Response(200,json=env)
  result=api.sdk_once(b,20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  self.assertEqual(seen,[b]);self.assertEqual(json.loads(result[2]),env);self.assertTrue(result[3]);self.assertEqual(result[5]['typed_matches_raw'],True)
 def test_no_retries_on_status_timeout_or_redirect(self):
  for code in [429,500,302,'timeout']:
   with self.subTest(code=code):
    seen=[]
    def handler(req):
     seen.append(req)
     if code=='timeout':raise httpx2.ReadTimeout('synthetic-sdk-key must not leak',request=req)
     return httpx2.Response(code,json=self.envelope(),headers={'location':'https://invalid.example/credential-sink'})
    if code=='timeout':
     with self.assertRaises(TimeoutError):api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
    else:
     r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler));self.assertEqual(r[0],code)
    self.assertEqual(len(seen),1)
 def test_bounds_and_credential_echo_redaction(self):
  env=self.envelope();env['synthetic']='synthetic-sdk-key';seen=[]
  def handler(req):return httpx2.Response(200,json=env)
  out=io.StringIO()
  with redirect_stdout(out),redirect_stderr(out):r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  self.assertNotIn('synthetic-sdk-key',r[2].decode()+out.getvalue());self.assertTrue(r[4])
  def large(req):return httpx2.Response(500,content=b'x'*(api.retention.ENVELOPE_BYTES+10000))
  r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(large));self.assertEqual(len(r[2]),api.retention.ENVELOPE_BYTES+1);self.assertFalse(r[3])
 def test_paired_mock_sdk_boundary_preserves_protocol(self):
  import test_responses_calibration as f
  import responses_sdk_runner as runner
  c=f.config();c['version']=runner.VERSION;b=c['provider_binding'];c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','high',2000,20,.2,b['rates']);c['provider_revision']=api.VERSION
  _,cases=runner.make_plan(f.specs(),c);seen=[]
  from surgerybench.temporal_text import parse
  from tier_a_input_view import VIEW_FRAGMENT,RAW_FRAGMENT
  def handler(req):
   body=json.loads(req.content);seen.append(body);case=next(x for x in cases.values() if body['input'].startswith(x['text']))
   if 'Phase TRANSLATE:' in body['instructions']:output={'type':'tool_call','name':'csp','arguments':{'instance':parse(case['text'].replace(VIEW_FRAGMENT,RAW_FRAGMENT))}}
   else:
    result={'status':case['label']};result.update({'schedule':case['evidence']['witness']} if case['label']=='FEASIBLE' else {'certificate':case['evidence']['certificate']});output={'type':'final','output':result}
   e=self.envelope();e['model']='mock-model';e['output'][0]['content'][0]['text']=json.dumps(output);return httpx2.Response(200,json=e)
  def send(b,t):return api.sdk_once(b,t,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  with tempfile.TemporaryDirectory() as t:
   s=runner.run(f.specs(),c,Path(t)/'run',lambda:api.ResponsesAdapter(c['provider_binding'],transport=send));self.assertEqual(s['by_arm']['no_tools']['success'],4);self.assertEqual(s['by_arm']['csp']['success'],4);self.assertEqual(len(seen),12)
   self.assertEqual(runner.assess_saved(f.specs(),Path(t)/'run')['pairs'],s['pairs'])
   import responses_handoff_runner as old
   oc=f.config();oc['version']=old.VERSION;oldseen=[]
   fixture_config=dict(oc,version=f.r.VERSION)
   old.run(f.specs(),oc,Path(t)/'old',f.CalibrationTests().factory(fixture_config,oldseen))
   self.assertEqual(seen,oldseen)
   bad=json.loads((Path(t)/'run/attempts.jsonl').read_text().splitlines()[0])['provider_calls'][0];bad['sdk']['runtime']['versions']['openai']='changed'
   with self.assertRaises(ValueError):api.validate_record(bad,c['provider_binding'])

 def test_clean_child_and_hard_local_timeout(self):
  b=self.body()
  meta={'test':'synthetic'};packed=json.dumps(dict(code=200,headers={},raw_base64='e30=',complete=True,redacted=False,sdk=meta)).encode()
  with patch('openai_sdk_client.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=packed)) as call:
   r=api.sdk_once(b,20,'synthetic-sdk-key');self.assertEqual(r[2],b'{}')
   args,kw=call.call_args;self.assertNotIn('synthetic-sdk-key',str(args));self.assertEqual(kw['env'],{'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C.UTF-8'});self.assertEqual(kw['timeout'],20);self.assertIn(b'synthetic-sdk-key',kw['input'])
  import subprocess
  with patch('openai_sdk_client.subprocess.run',side_effect=subprocess.TimeoutExpired('synthetic',20)):
   with self.assertRaises(TimeoutError):api.sdk_once(b,20,'synthetic-sdk-key')
 def test_refusal_incomplete_invalid_and_missing_usage_retain_ledger(self):
  from test_responses_calibration import config
  c=config();rates=c['provider_binding']['rates'];binding=api.binding('gpt-6-astra','gpt-6-astra','gpt-6-astra-high-standard-v1','high',2000,20,.2,rates)
  for mode in ['refusal','incomplete','invalid','fence','usage']:
   with self.subTest(mode=mode):
    seen=[]
    def handler(req):
     seen.append(req);e=self.envelope()
     if mode=='refusal':e['output'][0]['content']=[{'type':'refusal','refusal':'synthetic'}]
     if mode=='incomplete':e['status']='incomplete';e['incomplete_details']={'reason':'max_output_tokens'}
     if mode=='invalid':e['output'][0]['content'][0]['text']='{'
     if mode=='fence':e['output'][0]['content'][0]['text']='```json\n{}\n```'
     if mode=='usage':e['usage']=None
     return httpx2.Response(200,json=e)
    def send(b,t):return api.sdk_once(b,t,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
    a=api.ResponsesAdapter(binding,transport=send)
    with self.assertRaises(ValueError):a.respond([{'role':'system','content':'Final JSON only.'},{'role':'user','content':'Synthetic problem.'}],[],{'token_limit':2000,'wall_seconds':20,'spending_remaining_usd':.2})
    self.assertEqual(len(seen),1);self.assertEqual(len(a.calls),1);self.assertIsNotNone(a.calls[0]['raw_response'])
    if mode!='usage':self.assertEqual(a.calls[0]['observed_usage']['output_tokens'],30)
 def test_child_error_has_no_raw_diagnostics(self):
  import openai_sdk_client as child
  source=io.BytesIO(json.dumps({'body':self.body(),'timeout':20,'key':'synthetic-sdk-key','budget_usd':.2,'rates':None}).encode());out=io.StringIO()
  with patch.object(child.sys,'stdin',SimpleNamespace(buffer=source)),redirect_stdout(out),patch.object(child,'_sdk_in_process',side_effect=ValueError('synthetic-sdk-key PRIVATE ERROR')):
   child._child_main()
  self.assertEqual(json.loads(out.getvalue()),{'error':'ValueError'})

 def test_actual_isolated_child_with_mock_sdk_no_network(self):
  import subprocess,base64
  program="import sys,json,socket;sys.path.insert(0,"+repr(str(Path.cwd()))+");import httpx2;from openai_sdk_client import _child_main;socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden'));e="+repr(self.envelope())+";httpx2.HTTPTransport=lambda **k:httpx2.MockTransport(lambda r:httpx2.Response(200,json=e));_child_main()"
  payload=json.dumps({'body':self.body(),'timeout':20,'key':'synthetic-sdk-key','budget_usd':.2,'rates':None}).encode()
  r=subprocess.run([sys.executable,'-I','-c',program],input=payload,capture_output=True,env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'},timeout=20)
  self.assertEqual(r.returncode,0);o=json.loads(r.stdout);self.assertNotIn('error',o);self.assertTrue(o['sdk']['typed_matches_raw']);self.assertNotIn(b'synthetic-sdk-key',r.stdout+r.stderr)

 def test_encoded_response_retained_without_unbounded_decompression(self):
  import gzip
  encoded=gzip.compress(b'x'*(2*api.retention.ENVELOPE_BYTES))
  def handler(req):return httpx2.Response(200,stream=httpx2.ByteStream(encoded),headers={'content-encoding':'gzip'})
  r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  self.assertEqual(r[2],encoded);self.assertFalse(r[5]['wire']['response_encoding_supported'])

 def test_partial_body_timeout_and_protocol_failure_keep_bytes(self):
  for error,status in [(e,s) for e in [httpx2.ReadTimeout,httpx2.RemoteProtocolError] for s in [200,500]]:
   with self.subTest(error=error,status=status):
    seen=[]
    class Broken(httpx2.SyncByteStream):
     def __iter__(self):
      yield b'{"partial":"synthetic-'
      yield b'sdk-key"'
      raise error('synthetic-sdk-key must not leak')
    def handler(req):seen.append(req);return httpx2.Response(status,headers={'x-request-id':'synthetic-id','private':'discard'},stream=Broken())
    r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
    self.assertEqual(len(seen),1);self.assertEqual(r[0],status);self.assertFalse(r[3]);self.assertEqual(r[2],b'{"partial":"[CREDENTIAL_REDACTED]"');self.assertEqual(r[1],{'x-request-id':'synthetic-id'})
    self.assertEqual(r[5]['read_error'],'timeout' if error is httpx2.ReadTimeout else 'read_failure')
 def test_valid_json_with_unsupported_encoding_fails_closed(self):
  from test_responses_calibration import config
  b=config()['provider_binding'];binding=api.binding('gpt-6-astra','gpt-6-astra','gpt-6-astra-high-standard-v1','high',2000,20,.2,b['rates'])
  def handler(req):return httpx2.Response(200,content=json.dumps(self.envelope()).encode(),headers={'content-encoding':'unsupported'})
  def send(b,t):return api.sdk_once(b,t,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  a=api.ResponsesAdapter(binding,transport=send)
  with self.assertRaises(ValueError):a.respond([{'role':'system','content':'Final JSON only.'},{'role':'user','content':'Synthetic.'}],[],{'token_limit':2000,'wall_seconds':20,'spending_remaining_usd':.2})
  self.assertIsNone(a.calls[0]['observed_usage']);self.assertEqual(a.calls[0]['resource_error'],'unsupported_encoding')
  api.validate_record(a.calls[0],binding)
  bad=deepcopy(a.calls[0]);bad['resource_error']=None;bad['error']=None
  with self.assertRaises(ValueError):api.validate_record(bad,binding)

 def test_partial_adapter_and_saved_plan_keep_failure_denominators(self):
  import test_responses_calibration as f
  import responses_sdk_runner as runner
  c=f.config();c['version']=runner.VERSION;b=c['provider_binding'];c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','high',2000,20,.2,b['rates']);c['provider_revision']=api.VERSION
  e=self.envelope();e['model']='mock-model'
  for failure,chunk in [(httpx2.ReadTimeout,b'{"partial":'),(httpx2.RemoteProtocolError,b'{"partial":'),(httpx2.ReadTimeout,json.dumps(e).encode())]:
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
    seen=[]
    class Broken(httpx2.SyncByteStream):
     def __iter__(self):yield chunk;raise failure('synthetic private diagnostic')
    def handler(req):seen.append(req);return httpx2.Response(200,stream=Broken(),headers={'x-request-id':'synthetic'})
    def send(body,t):return api.sdk_once(body,t,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
    out=Path(tmp)/'run';summary=runner.run(f.specs(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=send))
    self.assertEqual(len(seen),1);self.assertEqual(sum(x['planned'] for x in summary['by_arm'].values()),8);self.assertEqual(sum(x['missing'] for x in summary['by_arm'].values()),7);self.assertEqual(sum(x['success'] for x in summary['by_arm'].values()),0)
    row=json.loads((out/'attempts.jsonl').read_text().splitlines()[0]);call=row['provider_calls'][0];self.assertEqual(call['raw_response'],chunk.decode());self.assertIsNone(call['observed_usage']);self.assertFalse(call['response_complete']);self.assertEqual(row['termination'],'timeout' if failure is httpx2.ReadTimeout else 'provider_error')
    self.assertEqual(runner.assess_saved(f.specs(),out)['pairs'],summary['pairs'])

 def test_incomplete_echo_prefix_is_redacted(self):
  class Broken(httpx2.SyncByteStream):
   def __iter__(self):yield b'{"echo":"synthetic-sdk-';raise httpx2.ReadTimeout('private')
  def handler(req):return httpx2.Response(200,stream=Broken())
  r=api.sdk_once(self.body(),20,'synthetic-sdk-key',http_transport=httpx2.MockTransport(handler))
  self.assertEqual(r[2],b'{"echo":"[CREDENTIAL_REDACTED]');self.assertTrue(r[4]);self.assertFalse(r[3])


 def test_missing_planned_sdk_cost_is_unknown(self):
  import responses_sdk_runner as runner
  import test_responses_calibration as fixture
  c=fixture.config();c.update(version=runner.VERSION,provider_revision=api.VERSION)
  b=c['provider_binding'];c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','low',100,2,1,b['rates'])
  plan,cases=runner.make_plan(fixture.specs(),c);summary=runner.summarize(plan,cases,[])
  for arm in ['no_tools','csp']:
   self.assertIsNone(summary['by_arm'][arm]['cost_estimate_usd']);self.assertEqual(summary['by_arm'][arm]['cost_estimate_coverage'],[0,4])
