import unittest,json,importlib.util
from unittest.mock import patch
from test_direct_benchmark import settings
import direct_api_providers as p
import anthropic_sdk_client as a
class WireReserveTests(unittest.TestCase):
 @unittest.skipUnless(importlib.util.find_spec("anthropic"),"optional Anthropic SDK")
 def test_anthropic_actual_sdk_cache_read_wire_bound(self):
  import httpx2
  c=dict(settings(),provider='anthropic_api',model='claude-opus-5-5');c['rates'].update(input=1,cache_read=1000,cache_write_short=1,cache_write_long=1,output=1)
  seen=[];body=p.body(c['provider'],'synthetic',c)
  def handler(req):seen.append(len(req.content));return httpx2.Response(200,json={'id':'synthetic','type':'message','role':'assistant','model':c['model'],'content':[{'type':'text','text':'{}'}],'stop_reason':'end_turn','usage':{'input_tokens':1,'output_tokens':1}})
  a._in_process(body,2,'synthetic-key-only',http_transport=httpx2.MockTransport(handler),budget_usd=10,rates=c['rates'])
  size=seen.pop();old=(size+256+c['max_output_tokens'])/1000000;new=((size+256)*1000+c['max_output_tokens'])/1000000;budget=(old+new)/2
  self.assertLess(old,budget);self.assertLess(budget,new)
  with self.assertRaises(Exception):a._in_process(body,2,'synthetic-key-only',http_transport=httpx2.MockTransport(handler),budget_usd=budget,rates=c['rates'])
  self.assertEqual(seen,[])
  result=a._in_process(body,2,'synthetic-key-only',http_transport=httpx2.MockTransport(handler),budget_usd=10,rates=c['rates']);self.assertEqual(seen,[size]);self.assertTrue(result[3])
 @unittest.skipUnless(importlib.util.find_spec("openai"),"optional OpenAI SDK")
 def test_openai_actual_sdk_cache_read_wire_bound(self):
  import httpx2,openai_sdk_client as o
  c=dict(settings(),provider='openai_api',model='gpt-6-astra');c['rates'].update(input=1,cache_read=1000,cache_write_short=1,cache_write_long=1,output=1)
  seen=[];request=p.body(c['provider'],'synthetic',c)
  def handler(req):seen.append(len(req.content));return httpx2.Response(200,json={'id':'synthetic','object':'response','model':c['model'],'status':'completed','output':[]})
  real=o.sdk_once
  def invoke(b,t,k,**kw):return real(b,t,k,http_transport=httpx2.MockTransport(handler),**kw)
  with patch.object(o,'sdk_once',side_effect=invoke):
   provider=p.APIProvider(dict(c,mode='live'),allow_live=True,key_loader=lambda:'synthetic-key-only')
   # Bypass only the already-tested plan reserve to exercise serialized SDK wire guard.
   with patch.object(p,'estimate_reserve',return_value=0):
    provider.call('synthetic',10)
    size=seen.pop();old=(size+256+c['max_output_tokens'])/1000000;new=((size+256)*1000+c['max_output_tokens'])/1000000;budget=(old+new)/2
    self.assertLess(old,budget);self.assertLess(budget,new)
    r=provider.call('synthetic',budget);self.assertIsNotNone(r['error']);self.assertEqual(seen,[])
    r=provider.call('synthetic',10);self.assertEqual(seen,[size]);self.assertEqual(r['http_status'],200)
