from test_direct_benchmark import settings,Reply
from copy import deepcopy
import unittest,json,base64,tempfile
from pathlib import Path
import direct_benchmark as d
import direct_api_providers as api
class IntegrityTests(unittest.TestCase):
 def setUp(self):
  self.c=settings();self.plan,self.cases=d.make_plan(d.demo_specs(),self.c)
 def slot(self,arm,case):return next(s for s in self.plan["slots"] if s["arm"]==arm and s["case_id"]==case)
 def test_provenance_required(self):
  g=next(v for v in self.cases.values() if v['label']=='FEASIBLE');r=d.attempt(self.slot('no_tools',g['case_id']),g,self.c,Reply({'type':'final','output':{'status':'FEASIBLE','schedule':g['evidence']['witness']}}))
  r['provider_calls'][0].pop('fixture_not_model')
  with self.assertRaises(ValueError):d.summarize(self.plan,self.cases,[r])
 def test_native_rejected_and_reasoning_allowed(self):
  e={'status':'completed','output':[{'type':'reasoning'},{'type':'message','role':'assistant','content':[{'type':'output_text','text':'{}'}]}]}
  self.assertEqual(api.extract('openai_api',e),'{}')
  e['output'].append({'type':'function_call'})
  with self.assertRaises(ValueError):api.extract('openai_api',e)
 def test_cache_read_reserve(self):
  c=deepcopy(self.c);c['rates'].update(input=1,cache_read=1000,cache_write_short=1,cache_write_long=1,output=1)
  self.assertGreater(api.estimate_reserve({'x':'y'},c),.2)

 def test_corrupt_identity_and_live_fixture_spoof(self):
  g=next(v for v in self.cases.values() if v['label']=='FEASIBLE')
  answer={'type':'final','output':{'status':'FEASIBLE','schedule':g['evidence']['witness']}}
  row=d.attempt(self.slot('no_tools',g['case_id']),g,self.c,Reply(answer))
  c=deepcopy(self.c);c['provider']='openai_api';c['model']='gpt-6-astra'
  p=deepcopy(self.plan);p['config']=c
  env={'model':c['model'],'status':'completed','service_tier':'default','usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},'output_tokens_details':{'reasoning_tokens':0}},'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':d.canonical(answer)}]}]}
  call=row['provider_calls'][0];call.pop('fixture_not_model');call.update(request=api.body('openai_api',d.prompt(g['text'],'no_tools'),c),raw_response_base64=base64.b64encode(d.canonical(env).encode()).decode(),http_status=200,redacted=False)
  call['usage']=api.usage('openai_api',env,c['rates']);row['cost_estimate_usd']=call['usage']['cost_estimate_usd']
  d.summarize(p,self.cases,[row])
  bad=deepcopy(row);bad['provider_calls'][0]['http_status']=403
  with self.assertRaises(ValueError):d.summarize(p,self.cases,[bad])
  bad=deepcopy(row);env['model']='other';bad['provider_calls'][0]['raw_response_base64']=base64.b64encode(d.canonical(env).encode()).decode()
  with self.assertRaises(ValueError):d.summarize(p,self.cases,[bad])
  p['config']['mode']='live';bad=deepcopy(row);bad['provider_calls'][0].update(fixture_not_model=True,raw_response_base64=None)
  with self.assertRaises(ValueError):d.summarize(p,self.cases,[bad])
 def test_recursion_boundary_real_run_probe(self):
  outcomes=[]
  for depth in (970,980,985,990,995,1000):
   raw='{"type":"final","output":'+'['*depth+'0'+']'*depth+'}'
   with tempfile.TemporaryDirectory() as tmp:
    try:
     result=d.run(d.demo_specs(),self.c,Path(tmp)/'run',provider=Reply(raw))
     outcomes.append((depth,'summary',result['planned_slots']))
    except RecursionError:self.fail('receipt serialization lost failure')
  print('NESTING_PROBE',outcomes,flush=True)
