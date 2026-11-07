import json,tempfile,unittest,re
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import responses_calibration_runner as r
import responses_calibration_transport as api
from responses_final_schema import SCHEMA,FORMAT
from tier_a_contract import output_verdict,canonical
from surgerybench.temporal_text import parse
from tier_a_input_view import RAW_FRAGMENT,VIEW_FRAGMENT
from responses_fixture import configure
SPEC_PATH=configure()
def config():
 c=json.loads((SPEC_PATH/'settings.json').read_text());b=c['provider_binding'];c['execution_mode']='responses_mock';c['provider_binding']=api.binding('mock-model','mock-model','mock-responses-v1','high',2000,20,.2,b['rates']);return c
def specs():return json.loads((SPEC_PATH/'datasets.json').read_text())
def schema_ok(s,v):
 if 'anyOf' in s:return any(schema_ok(x,v) for x in s['anyOf'])
 types={'object':dict,'array':list,'integer':int,'string':str}
 if 'type' in s and type(v) is not types[s['type']]:return False
 if 'enum' in s and v not in s['enum']:return False
 if s.get('type')=='object':return set(s['required'])<=set(v) and set(v)<=set(s['properties']) and all(schema_ok(s['properties'][k],x) for k,x in v.items())
 if s.get('type')=='array':return all(schema_ok(s['items'],x) for x in v)
 return True
class CalibrationTests(unittest.TestCase):
 def test_genuine_evidence_for_every_case_fits_schema_and_semantics(self):
  _,cases=r.make_plan(specs(),config())
  for case in cases.values():
   o={'status':case['label']};o.update({'schedule':case['evidence']['witness']} if case['label']=='FEASIBLE' else {'certificate':case['evidence']['certificate']})
   self.assertTrue(schema_ok(SCHEMA,{'type':'final','output':o}));self.assertTrue(output_verdict(case['instance'],canonical(o),o,[])['evidence_valid'])
   wrong=deepcopy(o)
   if case['label']=='FEASIBLE':wrong['schedule'][0]['start']=1000000
   else:wrong['certificate']['patients']=['unknown1','unknown2']
   self.assertTrue(schema_ok(SCHEMA,{'type':'final','output':wrong}));self.assertFalse(output_verdict(case['instance'],canonical(wrong),wrong,[])['evidence_valid'])
   unknown={'status':'UNKNOWN'};self.assertTrue(schema_ok(SCHEMA,{'type':'final','output':unknown}));self.assertFalse(output_verdict(case['instance'],canonical(unknown),unknown,[])['evidence_valid'])
 def factory(self,c,seen,mode='valid'):
  _,cases=r.make_plan(specs(),c)
  def send(b,t):
   seen.append(b);case=next(x for x in cases.values() if b['input'].startswith(x['text']))
   if 'Phase TRANSLATE:' in b['instructions']:
    instance=parse(case['text'].replace(VIEW_FRAGMENT,RAW_FRAGMENT));out={'type':'tool_call','name':'csp','arguments':{'instance':instance}}
   else:
    o={'status':case['label']};o.update({'schedule':case['evidence']['witness']} if case['label']=='FEASIBLE' else {'certificate':case['evidence']['certificate']});out={'type':'final','output':o}
   if mode=='timeout':raise TimeoutError()
   content=[{'type':'refusal','refusal':'synthetic'}] if mode=='refusal' else [{'type':'output_text','text':'{' if mode=='invalid' else json.dumps(out)}]
   usage=None if mode=='missing_usage' else dict(input_tokens=100,output_tokens=30,total_tokens=130,input_tokens_details={'cached_tokens':0,'cache_write_tokens':0},output_tokens_details={'reasoning_tokens':0})
   envelope=dict(model='mock-model',service_tier='default',status='incomplete' if mode=='incomplete' else 'completed',output=[dict(type='message',role='assistant',content=content)],usage=usage)
   return 200,{},json.dumps(envelope).encode(),True
  return lambda:api.ResponsesAdapter(c['provider_binding'],transport=send)
 def test_actual_requests_and_12_turn_4_solver_flow(self):
  c=config();seen=[]
  with patch('socket.create_connection',side_effect=AssertionError('blocked')),tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run';s=r.run(specs(),c,out,self.factory(c,seen));self.assertEqual(len(seen),12);self.assertEqual(s['by_arm']['no_tools']['success'],4);self.assertEqual(s['by_arm']['csp']['success'],4);self.assertEqual(s['by_arm']['csp']['tool_calls'],4);self.assertEqual(r.assess_saved(specs(),out)['pairs'],s['pairs'])
   for b in seen:
    self.assertEqual(b['tools'],[]);self.assertLessEqual(len(canonical(b).encode()),7500)
    if 'Phase TRANSLATE:' in b['instructions']:self.assertNotIn('text',b)
    else:self.assertEqual(b['text'],FORMAT);self.assertIn('schedule',b['input']);self.assertIn('certificate',b['input'])
    if 'Phase ' not in b['instructions']:self.assertIsNone(re.search(r'\b(tool|tools|csp)\b',b['instructions']+' '+b['input'],re.I))
 def test_exact_selection_package_and_bounds(self):
  c=config();p,_=r.make_plan(specs(),c);self.assertEqual(len(p['slots']),8);self.assertEqual([x['arm'] for x in p['slots'][::2]].count('csp'),2)
  for ids in [c['case_ids'][:-1],list(reversed(c['case_ids'])),c['case_ids']+['unknown']]:
   with self.assertRaises(ValueError):r.config(dict(c,case_ids=ids))
  bad=specs();bad[0]['plan']['manifest_sha256']='changed'
  with self.assertRaises(ValueError):r.make_plan(bad,c)
 def test_failures_and_unknown_usage_preserve_eight_slots(self):
  for mode in ['invalid','refusal','incomplete','timeout','missing_usage']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
    c=config();seen=[];s=r.run(specs(),c,Path(tmp)/'run',self.factory(c,seen,mode));self.assertEqual(sum(x['planned'] for x in s['by_arm'].values()),8);self.assertEqual(sum(x['success'] for x in s['by_arm'].values()),0);self.assertLessEqual(len(seen),12)
 def test_interruption_and_schema_identity(self):
  c=config()
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'run'
   def stop(*a):raise KeyboardInterrupt()
   with self.assertRaises(KeyboardInterrupt):r.run(specs(),c,out,lambda:api.ResponsesAdapter(c['provider_binding'],transport=stop))
   s=r.assess_saved(specs(),out);self.assertEqual(sum(x['missing'] for x in s['by_arm'].values()),8)
