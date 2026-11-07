import json,tempfile,unittest,socket
from pathlib import Path
from unittest.mock import patch
import responses_transport as api
class ResponsesTests(unittest.TestCase):
 def setUp(self):self.block=patch('socket.create_connection',side_effect=AssertionError('network forbidden'));self.block.start();self.addCleanup(self.block.stop)
 def binding(self):return api.binding('mock-model','mock-model','mock-responses-v1','low',200,3,.1,dict(input_per_million=2,cached_input_per_million=.2,output_per_million=10,source='synthetic test rates'))
 def reply(self,text='{"type":"final","output":{"status":"UNKNOWN"}}'):
  return dict(id='synthetic-response',model='mock-model',status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=text)])],usage=dict(input_tokens=100,output_tokens=20,input_tokens_details=dict(cached_tokens=10),output_tokens_details=dict(reasoning_tokens=5)))
 def messages(self):return [dict(role='system',content='shared'),dict(role='user',content='same case')]
 def test_request_is_direct_and_tool_free_and_cost_is_estimate(self):
  seen=[]
  def fake(body,timeout):seen.append(body);return 200,{'x-request-id':'request-test'},json.dumps(self.reply()).encode(),True
  p=api.ResponsesAdapter(self.binding(),transport=fake);r=p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
  self.assertEqual(r['raw'],'{"status":"UNKNOWN"}');self.assertEqual(seen[0]['tools'],[]);self.assertFalse(seen[0]['store']);self.assertEqual(seen[0]['max_output_tokens'],200)
  self.assertAlmostEqual(r['usage']['cost_estimate_usd'],.000382);self.assertIsNone(p.calls[0]['billed_cost_usd']);self.assertEqual(p.calls[0]['observed_usage']['output_tokens'],20)
 def test_key_file_parser_is_only_called_explicitly_on_synthetic_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'.env';p.write_text('OPENAI_API_KEY=synthetic-not-a-real-key\n');p.chmod(0o600)
   self.assertEqual(api.load_key_file(p),'synthetic-not-a-real-key')
   p.write_text('OPENAI_API_KEY=synthetic-not-a-real-key\nEXTRA=bad\n')
   with self.assertRaises(ValueError):api.load_key_file(p)
 def test_unresolved_configuration_and_endpoint_override_fail(self):
  with self.assertRaises(ValueError):api.binding(None,None,None,None,None,None,None,None)
  b=self.binding();b['endpoint']='https://untrusted.invalid'
  with self.assertRaises(ValueError):api.validate(b)
 def test_invalid_incomplete_refusal_native_output_keep_usage(self):
  variants=[]
  for text in ('{broken','```json\n{"type":"final","output":{"status":"UNKNOWN"}}\n```','{"type":"final","output":{},"output":{}}'):
   variants.append(self.reply(text))
  incomplete=self.reply();incomplete['status']='incomplete';incomplete['incomplete_details']={'reason':'max_output_tokens'};variants.append(incomplete)
  native=self.reply();native['output']=[dict(type='function_call',name='unapproved')];variants.append(native)
  refusal=self.reply();refusal['output'][0]['content']=[dict(type='refusal',refusal='synthetic refusal')];variants.append(refusal)
  for value in variants:
   calls=[]
   def fake(*a):calls.append(1);return 200,{},json.dumps(value).encode(),True
   p=api.ResponsesAdapter(self.binding(),transport=fake)
   with self.assertRaises(ValueError) as caught:p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
   self.assertEqual(len(calls),1);self.assertEqual(caught.exception.observed_usage['output_tokens'],20);self.assertIsNotNone(p.calls[0]['raw_response'])
 def test_missing_usage_and_mismatched_model_never_get_zero_estimate(self):
  value=self.reply();value.pop('usage')
  p=api.ResponsesAdapter(self.binding(),transport=lambda *a:(200,{},json.dumps(value).encode(),True))
  self.assertIsNone(p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))['usage'])
  value=self.reply();value['model']='wrong-model'
  p=api.ResponsesAdapter(self.binding(),transport=lambda *a:(200,{},json.dumps(value).encode(),True))
  with self.assertRaises(ValueError) as caught:p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
  self.assertIsNone(caught.exception.observed_usage['cost_estimate_usd']);self.assertEqual(p.calls[0]['returned_model'],'wrong-model')
 def test_http_errors_and_timeout_have_no_retry(self):
  for mode in ('rate','timeout'):
   calls=[]
   def fake(*args):
    calls.append(1)
    if mode=='timeout':raise api.urllib.error.URLError(TimeoutError('synthetic timeout'))
    return 429,{'retry-after':'20'},json.dumps({'error':{'message':'rate limit'}}).encode(),True
   p=api.ResponsesAdapter(self.binding(),transport=fake)
   with self.assertRaises((ValueError,TimeoutError)) as caught:p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
   self.assertEqual(len(calls),1);self.assertIsNone(caught.exception.observed_usage)
   if mode=='timeout':self.assertIsInstance(caught.exception,TimeoutError)
 def test_lowlevel_auth_is_private_and_redirects_are_not_followed(self):
  secret='synthetic-not-a-real-key';captured=[]
  class Response:
   status=302;headers={'x-request-id':secret,'Location':'https://unapproved.invalid'}
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return json.dumps({'error':{'message':secret}}).encode()
  class Opener:
   def open(self,request,timeout):captured.append(request);return Response()
  b=api.binding('gpt-6.1-sol','gpt-6.1-sol','gpt-6.1-sol-text-json-v1','low',200,3,.1,self.binding()['rates'])
  p=api.ResponsesAdapter(b,key_loader=lambda:secret,allow_live=True)
  with patch('urllib.request.build_opener',return_value=Opener()) as builder:
   with self.assertRaises(ValueError):p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
  self.assertEqual(len(captured),1);self.assertEqual(captured[0].full_url,api.ENDPOINT);self.assertEqual(captured[0].get_header('Authorization'),'Bearer '+secret)
  self.assertNotIn(secret,json.dumps(p.calls));self.assertTrue(p.calls[0]['credential_echo_redacted']);self.assertNotIn('Location',p.calls[0]['response_headers'])
  self.assertIsNone(api.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://unapproved.invalid'))
  self.assertEqual(builder.call_args.args[0].proxies,{})
 def test_loader_failure_is_sanitized_and_no_http_starts(self):
  secret='synthetic-not-a-real-key';b=api.binding('gpt-6.1-sol','gpt-6.1-sol','gpt-6.1-sol-text-json-v1','low',200,3,.1,self.binding()['rates'])
  def loader():raise RuntimeError(secret)
  p=api.ResponsesAdapter(b,key_loader=loader,allow_live=True)
  with self.assertRaises(ValueError) as caught:p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
  self.assertNotIn(secret,str(caught.exception)+json.dumps(p.calls));self.assertFalse(p.calls[0]['transport_started']);self.assertEqual(p.calls[0]['observed_usage']['cost_estimate_usd'],0)
 def test_key_file_permissions_symlinks_and_ignore_rules(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   file=Path(tmp)/'.env';file.write_text('OPENAI_API_KEY=synthetic-not-a-real-key\n');file.chmod(0o644)
   with self.assertRaises(ValueError):api.load_key_file(file)
   link=Path(tmp)/'link';link.symlink_to(file)
   with self.assertRaises(OSError):api.load_key_file(link)
  for path,expected in (('.env',0),('.env.local',0),('nested/.env.production',0),('.env.example',1)):
   result=subprocess.run(['git','check-ignore','--no-index','--quiet',path],capture_output=True)
   self.assertEqual(result.returncode,expected,path)
 def test_inconsistent_usage_and_missing_cache_stay_unknown(self):
  value=self.reply()['usage'];value['total_tokens']=999
  self.assertIsNone(api.observed_usage(value,self.binding()['rates'])['cost_estimate_usd'])
  value=self.reply()['usage'];value['output_tokens_details']['reasoning_tokens']=21
  self.assertIsNone(api.observed_usage(value,self.binding()['rates'])['output_tokens'])
  value=self.reply()['usage'];value.pop('input_tokens_details')
  self.assertIsNone(api.observed_usage(value,self.binding()['rates'])['cost_estimate_usd'])
 def test_unapproved_headers_dropped_and_partial_response_not_parsed(self):
  p=api.ResponsesAdapter(self.binding(),transport=lambda *a:(200,{'Authorization':'synthetic-sensitive-header','set-cookie':'synthetic'},b'{partial',False))
  with self.assertRaises(ValueError):p.respond(self.messages(),[],dict(token_limit=1000,wall_seconds=3,spending_remaining_usd=1))
  self.assertEqual(p.calls[0]['response_headers'],{});self.assertEqual(p.calls[0]['raw_response'],'{partial');self.assertEqual(p.calls[0]['resource_error'],'envelope_bound');self.assertIsNone(p.calls[0]['observed_usage'])
 def test_visible_system_instruction_is_preserved(self):
  from study.prompts import SYSTEM_V1,user_message
  system,text=api.render(self.messages(),[])
  self.assertEqual(system,'shared\n'+SYSTEM_V1);self.assertEqual(text,user_message('v1','same case',[],[]))
