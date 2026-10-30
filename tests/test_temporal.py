import copy, unittest
from surgerybench.temporal_check import check_schedule, check_certificate, schema_errors
from surgerybench.temporal_csp import solve, CSPAdapter
from surgerybench.temporal_oracle import enumerate_schedules
from surgerybench.temporal_text import render, parse
from surgerybench.temporal_benchmark import score, run_arm, MockProvider
from surgerybench.temporal_dataset import fixture


def tiny():
    def r(name): return {'id':name,'gap':0,'budgets':[10],'calendar':[[[0,10]]]}
    def p(name,s,release,due): return {'id':name,'mandatory':True,'surgeon':s,'duration':4,'release':release,'due':due,'eligible_rooms':['r0'],'priority':1,'emergency':name=='E'}
    return {'schema_version':'1.1','days':1,'day_minutes':1440,'surgeons':[r('s0'),r('s1')],'rooms':[r('r0')],'patients':[p('A','s0',0,10),p('E','s1',3,8)]}


def witness(): return [{'patient':'A','day':0,'start':0,'room':'r0'},{'patient':'E','day':0,'start':4,'room':'r0'}]


class TemporalTests(unittest.TestCase):
    def setUp(self): self.i=tiny(); self.w=witness()
    def test_unique_oracle(self):
        result=enumerate_schedules(self.i); self.assertTrue(result['complete']); self.assertEqual(result['solutions'],[self.w])
    def test_deadline_seven_unsat_below_horizon(self):
        self.i['patients'][1]['due']=7
        self.assertEqual(enumerate_schedules(self.i)['status'],'INFEASIBLE')
        self.assertTrue(check_certificate(self.i,{'kind':'pair_order_impossible','patients':['A','E']}))
        self.assertLess(sum(p['duration'] for p in self.i['patients']),10)
    def test_boundaries_and_adjacency(self): self.assertEqual(check_schedule(self.i,self.w),[])
    def test_arrival_boundary(self):
        self.i['patients'][1]['release']=4; self.assertEqual(check_schedule(self.i,self.w),[])
        self.i['patients'][1]['release']=5; self.assertIn('E: starts before arrival',check_schedule(self.i,self.w))
    def test_deadline_boundary(self):
        self.i['patients'][1]['due']=7; self.assertIn('E: completes after deadline',check_schedule(self.i,self.w))
    def test_room_overlap(self):
        self.w[1]['start']=3; self.assertTrue(any('clash' in e for e in check_schedule(self.i,self.w)))
    def test_surgeon_overlap(self):
        self.i['rooms'].append(copy.deepcopy(self.i['rooms'][0])); self.i['rooms'][1]['id']='r1'
        self.i['patients'][1]['surgeon']='s0'; self.i['patients'][1]['eligible_rooms']=['r1']; self.w[1].update(start=3,room='r1')
        self.assertTrue(any('surgeons/s0' in e for e in check_schedule(self.i,self.w)))
    def test_ineligible_room(self):
        self.w[1]['room']='r1'; self.assertTrue(any('incompatible' in e for e in check_schedule(self.i,self.w)))
    def test_missing(self): self.assertTrue(check_schedule(self.i,self.w[:1]))
    def test_duplicate(self): self.assertTrue(check_schedule(self.i,self.w+[self.w[0]]))
    def test_split_preemption_rejected(self):
        self.assertTrue(check_schedule(self.i,[{'patient':'A','day':0,'start':0,'end':3,'room':'r0'},self.w[1],{'patient':'A','day':0,'start':7,'end':8,'room':'r0'}]))
        self.assertTrue(check_schedule(self.i,[self.w[0],self.w[1],dict(self.w[0],start=7)]))
    def test_break_whole_interval(self):
        self.i['rooms'][0]['calendar']=[[[0,3],[3,10]]]; self.assertTrue(check_schedule(self.i,self.w))
    def test_gap(self):
        self.i['rooms'][0]['gap']=1; self.assertTrue(check_schedule(self.i,self.w))
    def test_daily_budget(self):
        self.i['rooms'][0]['budgets']=[7]; self.assertTrue(check_schedule(self.i,self.w))
    def test_emergency_no_hidden_constraint(self):
        self.i['patients'][0]['emergency']=True; self.i['patients'][1]['emergency']=False; self.assertEqual(check_schedule(self.i,self.w),[])
    def test_roundtrip(self): self.assertEqual(parse(render(self.i)),self.i)
    def test_room_named_none_roundtrip(self):
        self.i['rooms'][0]['id']='none'
        for p in self.i['patients']: p['eligible_rooms']=['none']
        self.assertEqual(parse(render(self.i)),self.i)
    def test_schema_version_and_integer(self):
        self.i['patients'][1]['due']=True; self.assertTrue(schema_errors(self.i))
        self.i=tiny(); self.i['schema_version']='1.0'; self.assertTrue(schema_errors(self.i))
    def test_absolute_next_day(self):
        i,_=fixture('room_contention',1); r=solve(i); self.assertEqual(r['status'],'FEASIBLE'); self.assertEqual(check_schedule(i,r['schedule']),[]); self.assertTrue(all(x['day']==1 for x in r['schedule']))
    def test_limits_unknown(self):
        self.assertEqual(solve(self.i,max_nodes=0)['status'],'UNKNOWN'); self.assertEqual(enumerate_schedules(self.i,limit=0)['status'],'UNKNOWN')
    def test_certificate_rejected_for_feasible(self): self.assertFalse(check_certificate(self.i,{'kind':'pair_order_impossible','patients':['A','E']}))
    def test_unforced_pair_certificate(self):
        self.i['patients'][1]['due']=7; self.i['rooms'].append(dict(self.i['rooms'][0],id='r1')); self.i['patients'][1]['eligible_rooms']=['r1']
        self.assertFalse(check_certificate(self.i,{'kind':'pair_order_impossible','patients':['A','E']}))
    def test_optional_not_required(self):
        self.i['patients'][1]['mandatory']=False; self.assertEqual(check_schedule(self.i,self.w[:1]),[])
    def test_translation_mistake_external_scoring(self):
        intended=tiny(); intended['patients'][1]['due']=7
        translated=tiny(); result=solve(translated)
        self.assertEqual(check_schedule(translated,result['schedule']),[])
        verdict=score({'instance':intended,'label':'INFEASIBLE'},result)
        self.assertFalse(verdict['valid']); self.assertIn('E: completes after deadline',verdict['violations'])
    def test_tool_only_structured_model_args(self):
        with self.assertRaises(ValueError): CSPAdapter().invoke({'text':render(self.i)})
    def test_paired_provider_sees_same_text(self):
        seen=[]
        class Spy(MockProvider):
            def next(self,text,history,tools): seen.append(text); return super().next(text,history,tools)
        text=render(self.i)
        a=run_arm(Spy(),text,'no_tools',CSPAdapter()); b=run_arm(Spy(),text,'csp',CSPAdapter())
        self.assertTrue(all(s==text for s in seen)); self.assertEqual(a['tool_call_count'],0); self.assertEqual(b['tool_call_count'],1); self.assertEqual(b['output']['status'],'FEASIBLE')
        self.assertEqual(b['tool_calls'][0]['arguments']['instance'],self.i)
    def test_tool_error_separate_from_unknown(self):
        class Bad(MockProvider):
            def next(self,text,history,tools):
                if not history: return {'type':'tool_call','name':'csp','arguments':{'text':text}}
                return super().next(text,history,tools)
        r=run_arm(Bad(),render(self.i),'csp',CSPAdapter()); self.assertTrue(r['tool_error']); self.assertEqual(r['output']['status'],'UNKNOWN')
    def test_no_tools_rejects_tool_call(self):
        class Bad(MockProvider):
            def next(self,*args): return {'type':'tool_call','name':'csp','arguments':{'instance':tiny()}}
        r=run_arm(Bad(),render(self.i),'no_tools',CSPAdapter()); self.assertTrue(r['parsing_or_provider_error']); self.assertEqual(r['tool_call_count'],0)

if __name__=='__main__': unittest.main()
