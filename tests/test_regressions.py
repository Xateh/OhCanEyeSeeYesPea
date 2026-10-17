"""Focused original-synthetic checker/harness regressions; no external data."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from surgerybench.common import canonical, digest, read_jsonl, revision
from surgerybench.temporal_check import schema_errors, check_schedule, check_certificate
from surgerybench.temporal_benchmark import run, run_arm, score
from surgerybench.temporal_csp import CSPAdapter
from surgerybench.temporal_text import render

ROOT = Path(__file__).resolve().parents[1]


def tiny():
    def resource(name):
        return {'id':name,'gap':0,'budgets':[10],'calendar':[[[0,10]]]}
    def patient(name,surgeon,release,due):
        return {'id':name,'mandatory':True,'surgeon':surgeon,'duration':4,
                'release':release,'due':due,'eligible_rooms':['r0'],
                'priority':1,'emergency':False}
    return {'schema_version':'1.1','days':1,'day_minutes':1440,
            'surgeons':[resource('s0'),resource('s1')],'rooms':[resource('r0')],
            'patients':[patient('A','s0',0,10),patient('E','s1',3,8)]}


def witness():
    return [{'patient':'A','day':0,'start':0,'room':'r0'},
            {'patient':'E','day':0,'start':4,'room':'r0'}]


def final(usage=None, output=None):
    return {'type':'final','output':output or {'status':'UNKNOWN'},'usage':usage}


def call(usage=None):
    return {'type':'tool_call','name':'csp','arguments':{'instance':tiny()},'usage':usage}


class ScriptedProvider:
    model_revision = 'scripted-test-v1'
    def __init__(self, messages):
        self.messages = copy.deepcopy(messages)
        self.seen = []
    def next(self, text, history, tools):
        self.seen.append((text,copy.deepcopy(history),copy.deepcopy(tools)))
        return self.messages.pop(0)


class StubAdapter:
    revision = 'test-stub-v1'
    tool_definition = CSPAdapter.tool_definition
    def __init__(self):
        self.calls = []
    def invoke(self, arguments):
        self.calls.append(copy.deepcopy(arguments))
        return {'status':'UNKNOWN','reason':'test stub; no search'}


class CheckerInputTests(unittest.TestCase):
    def setUp(self):
        self.i=tiny(); self.w=witness()
        self.bad=tiny(); self.bad['patients'][1]['due']=7
        self.cert={'kind':'pair_order_impossible','patients':['A','E']}
    def test_malformed_schedule_container(self):
        for value in (None,{},'schedule',True,4):
            with self.subTest(value=value): self.assertTrue(check_schedule(self.i,value))
    def test_malformed_schedule_rows(self):
        for row in (None,[],{},'A',dict(self.w[0],surgeon='s1'),{'patient':'A'}):
            with self.subTest(row=row): self.assertTrue(check_schedule(self.i,[row,self.w[1]]))
    def test_noninteger_day_and_start(self):
        for key in ('day','start'):
            for value in (True,False,0.0,'0',None,[],{}):
                with self.subTest(key=key,value=value):
                    row=dict(self.w[0]); row[key]=value
                    self.assertTrue(check_schedule(self.i,[row,self.w[1]]))
    def test_out_of_bounds_day_and_start(self):
        for key,values in (('day',(-1,1,1440)),('start',(-1,1440,1441))):
            for value in values:
                with self.subTest(key=key,value=value):
                    row=dict(self.w[0]); row[key]=value
                    self.assertTrue(check_schedule(self.i,[row,self.w[1]]))
    def test_unknown_or_unhashable_schedule_ids(self):
        for key in ('patient','room'):
            for value in ('missing',[],{},None,True):
                with self.subTest(key=key,value=value):
                    row=dict(self.w[0]); row[key]=value
                    self.assertTrue(check_schedule(self.i,[row,self.w[1]]))
    def test_malformed_instances_fail_closed(self):
        for value in (None,[],{},'instance',True):
            with self.subTest(value=value):
                self.assertTrue(schema_errors(value))
                self.assertTrue(check_schedule(value,self.w))
                self.assertFalse(check_certificate(value,self.cert))
    def test_invalid_identifiers_and_duration(self):
        for value in ('bad id','bad,id','bad\nid','-',[],None):
            with self.subTest(value=value):
                i=copy.deepcopy(self.i); i['patients'][0]['id']=value
                self.assertTrue(schema_errors(i))
        for value in (-1,0,True,4.0):
            with self.subTest(duration=value):
                i=copy.deepcopy(self.i); i['patients'][0]['duration']=value
                self.assertTrue(schema_errors(i))
    def test_malformed_certificate_shapes(self):
        for value in (None,[],{},'proof',True,
                      {'kind':'unknown','patients':['A','E']},
                      dict(self.cert,extra=1),{'kind':'pair_order_impossible'}):
            with self.subTest(value=value): self.assertFalse(check_certificate(self.bad,value))
    def test_malformed_certificate_patient_ids(self):
        for value in (None,{},'A',[],['A'],['A','E','X'],['A','A'],
                      ['A','missing'],['A',[]],['A',{}],['A',True]):
            with self.subTest(value=value):
                self.assertFalse(check_certificate(self.bad,{'kind':'pair_order_impossible','patients':value}))
    def test_optional_patient_cannot_support_contradiction(self):
        self.assertTrue(check_certificate(self.bad,self.cert))
        self.bad['patients'][1]['mandatory']=False
        self.assertFalse(check_certificate(self.bad,self.cert))
    def test_optional_present_still_once_and_constrained(self):
        self.i['patients'][1]['mandatory']=False
        self.assertEqual(check_schedule(self.i,self.w),[])
        self.assertTrue(check_schedule(self.i,self.w+[self.w[1]]))
        bad=copy.deepcopy(self.w); bad[1]['start']=5
        self.assertTrue(check_schedule(self.i,bad))
    def test_positive_gap_exact_boundary(self):
        self.i['rooms'][0]['gap']=1; self.i['patients'][1]['due']=9
        self.w[1]['start']=5
        self.assertEqual(check_schedule(self.i,self.w),[])
        self.w[1]['start']=4
        self.assertTrue(check_schedule(self.i,self.w))
    def test_score_rejects_missing_or_malformed_feasible_witness(self):
        gold={'instance':self.i,'label':'FEASIBLE'}
        for schedule in (None,{},[],[None],self.w+[self.w[0]]):
            with self.subTest(schedule=schedule):
                result=score(gold,{'status':'FEASIBLE','schedule':schedule})
                self.assertFalse(result['valid']); self.assertFalse(result['feasible_schedule_success'])
    def test_infeasible_decision_is_not_certified_without_valid_proof(self):
        result=score({'instance':self.bad,'label':'INFEASIBLE'},{'status':'INFEASIBLE','certificate':{}})
        self.assertTrue(result['infeasible_decision_correct'])
        self.assertFalse(result['infeasible_certified_success']); self.assertFalse(result['valid'])
    def test_output_errors_distinct_from_unknown(self):
        gold={'instance':self.i,'label':'FEASIBLE'}
        for output in (None,[],{},'FEASIBLE',{'status':[]},{'status':'invalid'}):
            with self.subTest(output=output):
                result=score(gold,output)
                self.assertTrue(result['output_error']); self.assertFalse(result['unknown'])
        result=score(gold,{'status':'UNKNOWN'})
        self.assertFalse(result['output_error']); self.assertTrue(result['unknown'])
        self.assertFalse(result['feasible_schedule_success'])


class HarnessControlTests(unittest.TestCase):
    def setUp(self): self.text=render(tiny()); self.adapter=StubAdapter()
    def execute(self,messages,arm='csp',limit=4):
        return run_arm(ScriptedProvider(messages),self.text,arm,self.adapter,max_calls=limit)
    def test_usage_sums_all_provider_turns(self):
        result=self.execute([call({'input_tokens':10,'output_tokens':2}),final({'input_tokens':20,'output_tokens':3})])
        self.assertEqual(result['token_usage'],{'input_tokens':30,'output_tokens':5})
        self.assertIsNone(result['token_usage_reason']); self.assertEqual(result['tool_call_count'],1)
    def test_zero_usage_is_known(self):
        result=self.execute([final({'input_tokens':0,'output_tokens':0})])
        self.assertEqual(result['token_usage'],{'input_tokens':0,'output_tokens':0})
    def test_partial_usage_is_not_silently_underreported(self):
        for usage in (None,{}, {'input_tokens':3}):
            with self.subTest(usage=usage):
                result=self.execute([call({'input_tokens':10,'output_tokens':2}),final(usage)])
                self.assertIsNone(result['token_usage']); self.assertTrue(result['token_usage_reason'])
    def test_invalid_usage_counts_are_unknown(self):
        for value in (True,-1,1.5,'2',None,[],{}):
            for key in ('input_tokens','output_tokens'):
                with self.subTest(value=value,key=key):
                    usage={'input_tokens':1,'output_tokens':2}; usage[key]=value
                    self.assertIsNone(self.execute([final(usage)])['token_usage'])
    def test_call_limit_blocks_extra_invocation(self):
        result=self.execute([call(),call(),call()],limit=2)
        self.assertEqual(result['tool_call_count'],2); self.assertEqual(len(self.adapter.calls),2)
        self.assertEqual(len(result['responses']),3)
        self.assertTrue(result['parsing_or_provider_error'])
        self.assertIn('tool call limit',result['errors'][0]['error'])
        self.assertFalse(result['tool_error']); self.assertEqual(result['output']['status'],'UNKNOWN')
    def test_final_after_exact_call_limit_is_allowed(self):
        result=self.execute([call(),call(),final()],limit=2)
        self.assertEqual(result['tool_call_count'],2); self.assertEqual(result['errors'],[])
    def test_zero_call_limit_allows_final_but_blocks_tool(self):
        self.assertEqual(self.execute([final()],limit=0)['errors'],[])
        result=self.execute([call()],limit=0)
        self.assertEqual(result['tool_call_count'],0); self.assertEqual(self.adapter.calls,[])
        self.assertTrue(result['parsing_or_provider_error'])
    def test_call_limit_attempt_usage_is_still_counted(self):
        usage={'input_tokens':2,'output_tokens':1}
        result=self.execute([call(usage),call(usage)],limit=1)
        self.assertEqual(result['token_usage'],{'input_tokens':4,'output_tokens':2})
    def test_no_tools_never_invokes_adapter(self):
        result=self.execute([call()],arm='no_tools')
        self.assertEqual(self.adapter.calls,[]); self.assertEqual(result['tool_call_count'],0)
        self.assertTrue(result['parsing_or_provider_error'])
    def test_only_csp_is_exposed_and_repair_is_rejected(self):
        message=call(); message['name']='repair'
        provider=ScriptedProvider([message])
        result=run_arm(provider,self.text,'csp',self.adapter)
        self.assertEqual([t['name'] for t in provider.seen[0][2]],['csp'])
        self.assertEqual(self.adapter.calls,[]); self.assertTrue(result['parsing_or_provider_error'])
    def test_malformed_provider_message(self):
        for message in (None,[],True,'text',{}, {'type':'invalid'}):
            with self.subTest(message=message):
                result=self.execute([message])
                self.assertTrue(result['parsing_or_provider_error']); self.assertFalse(result['tool_error'])
    def test_provider_exception_classified_separately(self):
        class Broken:
            def next(self,*args): raise ValueError('translation failed')
        result=run_arm(Broken(),self.text,'csp',self.adapter)
        self.assertTrue(result['parsing_or_provider_error']); self.assertFalse(result['tool_error'])
        self.assertEqual(result['tool_call_count'],0)
    def test_adapter_exception_classified_separately(self):
        class Broken(StubAdapter):
            def invoke(self,arguments): raise ValueError('invalid translated constraints')
        result=run_arm(ScriptedProvider([call(),final()]),self.text,'csp',Broken())
        self.assertTrue(result['tool_error']); self.assertFalse(result['parsing_or_provider_error'])
        self.assertEqual(result['tool_calls'][0]['result']['status'],'UNKNOWN')
    def test_malformed_later_response_invalidates_usage_total(self):
        for malformed in (None,[],True,'not an object'):
            with self.subTest(malformed=malformed):
                result=self.execute([call({'input_tokens':10,'output_tokens':2}),malformed])
                self.assertEqual(result['tool_call_count'],1)
                self.assertTrue(result['parsing_or_provider_error'])
                self.assertIsNone(result['token_usage'])
                self.assertTrue(result['token_usage_reason'])
    def test_later_provider_exception_invalidates_usage_total(self):
        class Broken(ScriptedProvider):
            def next(self,*args):
                if self.messages: return super().next(*args)
                raise RuntimeError('provider failed without reporting usage')
        provider=Broken([call({'input_tokens':10,'output_tokens':2})])
        result=run_arm(provider,self.text,'csp',self.adapter)
        self.assertEqual(result['tool_call_count'],1)
        self.assertTrue(result['parsing_or_provider_error'])
        self.assertIsNone(result['token_usage'])
        self.assertTrue(result['token_usage_reason'])
    def test_latency_and_structured_calls_recorded(self):
        result=self.execute([call(),final()])
        self.assertGreaterEqual(result['latency_seconds'],0)
        self.assertGreaterEqual(result['tool_calls'][0]['latency_seconds'],0)
        self.assertEqual(result['tool_calls'][0]['arguments'],{'instance':tiny()})
        self.assertEqual(result['tool_calls'][0]['result']['status'],'UNKNOWN')


class HarnessDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.model=self.root/'model.jsonl'; self.gold=self.root/'gold.jsonl'; self.out=self.root/'run.jsonl'
        self.models=read_jsonl(ROOT/'fixtures/arrival-deadline-v1/model.jsonl')[:2]
        self.golds=read_jsonl(ROOT/'fixtures/arrival-deadline-v1/gold.jsonl')[:2]
        self.write_inputs()
    def write_inputs(self):
        self.model.write_text(''.join(canonical(r)+'\n' for r in self.models))
        self.gold.write_text(''.join(canonical(r)+'\n' for r in self.golds))
    def factory(self): return ScriptedProvider([final()])
    def invoke(self,factory=None):
        return run(self.model,self.gold,self.out,factory=factory or self.factory,adapter=StubAdapter())
    def test_revision_mismatch_between_arms_rejected(self):
        revisions=iter(['model-a','model-b'])
        def factory():
            p=self.factory(); p.model_revision=next(revisions); return p
        with self.assertRaisesRegex(ValueError,'same model'): self.invoke(factory)
        self.assertFalse(self.out.exists())
    def test_revision_mismatch_between_cases_rejected(self):
        revisions=iter(['model-a','model-a','model-b'])
        def factory():
            p=self.factory(); p.model_revision=next(revisions); return p
        with self.assertRaisesRegex(ValueError,'same model'): self.invoke(factory)
        self.assertFalse(self.out.exists())
    def test_missing_or_malformed_revision_rejected(self):
        for index,value in enumerate((None,'','   ',True,5,['model'],{})):
            self.out=self.root/f'revision-{index}.jsonl'
            with self.subTest(value=value):
                def factory():
                    p=self.factory(); p.model_revision=value; return p
                with self.assertRaisesRegex(ValueError,'exact model revision'): self.invoke(factory)
                self.assertFalse(self.out.exists())
    def test_exact_revision_and_dataset_hashes_recorded(self):
        rows=self.invoke()
        self.assertEqual(len(rows),4)
        expected_model=hashlib.sha256(self.model.read_bytes()).hexdigest()
        expected_gold=hashlib.sha256(self.gold.read_bytes()).hexdigest()
        for row in rows:
            self.assertEqual(row['model_revision'],'scripted-test-v1')
            self.assertEqual(row['code_revision'],revision())
            self.assertEqual(row['dataset_revision'],expected_model)
            self.assertEqual(row['gold_revision'],expected_gold)
            self.assertEqual(row['tool_revision'],'test-stub-v1' if row['arm']=='csp' else None)
    def test_pair_input_identity_and_no_gold_in_provider(self):
        providers=[]
        def factory():
            p=self.factory(); providers.append(p); return p
        self.invoke(factory)
        self.assertEqual(len(providers),4)
        for index,p in enumerate(providers):
            text,history,tools=p.seen[0]
            self.assertEqual(text,self.models[index//2]['text'])
            self.assertEqual(history,[])
            self.assertEqual([t['name'] for t in tools],[] if index%2==0 else ['csp'])
    def test_refuses_to_overwrite_prior_run(self):
        self.out.write_text('preserve')
        with self.assertRaises(FileExistsError): self.invoke()
        self.assertEqual(self.out.read_text(),'preserve')
    def test_duplicate_and_mismatched_ids_rejected(self):
        original_models=copy.deepcopy(self.models); original_gold=copy.deepcopy(self.golds)
        for kind in ('model_duplicate','gold_duplicate','mismatch'):
            with self.subTest(kind=kind):
                self.models=copy.deepcopy(original_models); self.golds=copy.deepcopy(original_gold)
                if kind=='model_duplicate': self.models.append(self.models[0])
                elif kind=='gold_duplicate': self.golds.append(self.golds[0])
                else: self.models[0]['id']='different'
                self.write_inputs()
                with self.assertRaises(ValueError): self.invoke()
                self.assertFalse(self.out.exists())
    def test_model_extra_gold_field_rejected(self):
        self.models[0]['label']='FEASIBLE'; self.write_inputs()
        with self.assertRaisesRegex(ValueError,'only id and text'): self.invoke()
        self.assertFalse(self.out.exists())
    def test_text_and_instance_hash_corruption_rejected(self):
        original_models=copy.deepcopy(self.models); original_gold=copy.deepcopy(self.golds)
        for kind in ('text','instance'):
            with self.subTest(kind=kind):
                self.models=copy.deepcopy(original_models); self.golds=copy.deepcopy(original_gold)
                if kind=='text': self.models[0]['text']+='changed'
                else: self.golds[0]['instance']['patients'][0]['duration']+=1
                self.write_inputs()
                with self.assertRaisesRegex(ValueError,'integrity mismatch'): self.invoke()
                self.assertFalse(self.out.exists())

if __name__=='__main__': unittest.main()
