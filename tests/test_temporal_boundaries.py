import copy, unittest
import temporal_validation_v2 as check
from temporal_validation_v2 import render, parse
from temporal_validation_v2 import solve
from surgerybench.temporal_oracle import enumerate_schedules
from temporal_validation_v2 import score


def instance(days=1):
    def resource(name):
        return dict(id=name, gap=0, budgets=[10]*days, calendar=[[[0,10]] for _ in range(days)])
    return dict(schema_version='1.1', days=days, day_minutes=1440,
                surgeons=[resource('s')], rooms=[resource('r')], patients=[
                dict(id='A', mandatory=True, surgeon='s', duration=2, release=0,
                     due=10, eligible_rooms=['r'], priority=0, emergency=False)])


def row(patient='A', day=0, start=0, room='r'):
    return dict(patient=patient, day=day, start=start, room=room)


class StructuralTests(unittest.TestCase):
    def test_array_containers_cannot_be_empty_mappings(self):
        for kind in ['patients','surgeons','rooms']:
            for bad in [{}, (), '', None]:
                i=instance();i['patients']=[];i[kind]=bad
                with self.subTest(kind=kind,bad=bad):
                    self.assertTrue(check.schema_errors(i))
                    with self.assertRaises(ValueError):render(i)

    def test_nested_resource_arrays_and_window_shape(self):
        mutations=[('budgets',{0:10}),('budgets',(10,)),('calendar',{0:[[0,10]]}),
                   ('calendar',[[ (0,10) ]]),('calendar',[{}]),('calendar',[()]),
                   ('calendar',[[[0,5,10]]]),('calendar',[[[0,True]]])]
        for kind in ['surgeons','rooms']:
            for field,value in mutations:
                i=instance();i[kind][0][field]=value
                with self.subTest(kind=kind,field=field,value=value):
                    self.assertTrue(check.schema_errors(i))

    def test_unknown_keys_rejected_at_each_object_level(self):
        for location in ['root','patient','surgeon','room']:
            i=instance();obj={'root':i,'patient':i['patients'][0],
                'surgeon':i['surgeons'][0],'room':i['rooms'][0]}[location]
            obj['misspelled_constraint']=1
            with self.subTest(location=location):
                self.assertTrue(check.schema_errors(i))
                with self.assertRaises(ValueError):solve(i)

    def test_empty_arrays_and_empty_day_windows_stay_valid(self):
        i=instance();i['patients']=[];i['surgeons']=[];i['rooms']=[]
        self.assertEqual(check.schema_errors(i),[])
        self.assertEqual(parse(render(i)),i)
        self.assertEqual(check.check_schedule(i,[]),[])
        i=instance();i['patients']=[];i['rooms'][0]['calendar']=[[]]
        self.assertEqual(check.schema_errors(i),[])
        self.assertEqual(parse(render(i)),i)

    def test_optional_emergency_has_explicit_nonmutating_normalization(self):
        i=instance();del i['patients'][0]['emergency'];before=copy.deepcopy(i)
        self.assertEqual(check.schema_errors(i),[])
        self.assertTrue(hasattr(check,'normalize_instance'))
        canonical=check.normalize_instance(i)
        self.assertEqual(i,before)
        self.assertIs(canonical['patients'][0]['emergency'],False)
        self.assertEqual(parse(render(i)),canonical)
        self.assertEqual(render(i),render(canonical))
        self.assertEqual(check.normalize_instance(canonical),canonical)
        self.assertEqual(check.check_schedule(i,[row()]),[])


class BoundaryTests(unittest.TestCase):
    def checked(self,i,w):
        self.assertEqual(check.schema_errors(i),[])
        parsed=parse(render(i))
        self.assertEqual(parsed,check.normalize_instance(i))
        self.assertEqual(check.check_schedule(i,w),[])
        self.assertEqual(check.check_schedule(parsed,w),[])
        oracle=enumerate_schedules(i)
        self.assertTrue(oracle['complete']);self.assertIn(w,oracle['solutions'])
        return parsed

    def test_absolute_1439_and_1440_with_day_local_starts(self):
        i=instance(2)
        for kind in ['surgeons','rooms']:
            i[kind][0].update(calendar=[[[1439,1440]],[[0,1]]],budgets=[1,1],gap=7)
        i['patients'][0].update(duration=1,release=1439,due=1440)
        i['patients'].append(dict(i['patients'][0],id='B',release=1440,due=1441))
        w=[row(start=1439),row('B',day=1,start=0)]
        self.checked(i,w)
        early=copy.deepcopy(w);early[1].update(day=0,start=1439)
        self.assertIn('B: starts before arrival',check.check_schedule(i,early))
        late=copy.deepcopy(w);late[0].update(day=1,start=0)
        self.assertIn('A: completes after deadline',check.check_schedule(i,late))

    def test_exact_horizon_deadline_and_out_of_horizon_day(self):
        i=instance(2);i['patients'][0].update(duration=1,release=2879,due=2880)
        for kind in ['surgeons','rooms']:
            i[kind][0].update(calendar=[[],[[1439,1440]]],budgets=[0,1])
        self.checked(i,[row(day=1,start=1439)])
        self.assertTrue(check.check_schedule(i,[row(day=2,start=0)]))

    def test_whole_surgery_may_not_cross_midnight(self):
        i=instance(2);i['patients'][0].update(release=1439,due=1441)
        for kind in ['surgeons','rooms']:
            i[kind][0].update(calendar=[[[1439,1440]],[[0,1]]],budgets=[2,2])
        parsed=parse(render(i));self.assertEqual(parsed,i)
        self.assertTrue(check.check_schedule(i,[row(start=1439)]))
        self.assertTrue(check.check_schedule(i,[row(day=1,start=0)]))
        self.assertEqual(enumerate_schedules(i)['status'],'INFEASIBLE')
        self.assertEqual(solve(parsed)['status'],'UNKNOWN')

    def test_daily_budgets_do_not_pool_across_days(self):
        i=instance(2);i['patients'][0].update(release=1440,due=1442)
        for kind in ['surgeons','rooms']:
            i[kind][0].update(calendar=[[[0,2]],[[0,2]]],budgets=[0,2])
        w=[row(day=1)];self.checked(i,w)
        for kind in ['surgeons','rooms']:
            bad=copy.deepcopy(i);bad[kind][0]['budgets']=[2,1]
            self.assertTrue(check.check_schedule(bad,w))
            self.assertEqual(enumerate_schedules(bad)['status'],'INFEASIBLE')

    def test_same_day_gap_and_surgery_only_budget(self):
        i=instance(2);i['patients'][0].update(release=1440,due=1445)
        i['patients'].append(dict(i['patients'][0],id='B'))
        for kind in ['surgeons','rooms']:
            i[kind][0].update(calendar=[[],[[0,5]]],budgets=[0,4],gap=1)
        w=[row(day=1),row('B',day=1,start=3)];self.checked(i,w)
        adjacent=[row(day=1),row('B',day=1,start=2)]
        self.assertTrue(any('gap' in x for x in check.check_schedule(i,adjacent)))

    def test_zero_mandatory_all_optional_and_impossible_optional(self):
        for empty in [True,False]:
            i=instance()
            if empty:i['patients']=[]
            else:i['patients'][0].update(mandatory=False,due=1)
            with self.subTest(empty=empty):
                self.checked(i,[]);self.assertEqual(solve(i)['schedule'],[])
        i=instance();i['patients'].append(dict(i['patients'][0],id='B',mandatory=False,due=1))
        self.checked(i,[row()]);self.assertEqual(solve(i)['status'],'FEASIBLE')
        i['patients'][1]['mandatory']=True
        self.assertEqual(enumerate_schedules(i)['status'],'INFEASIBLE')
        self.assertEqual(solve(i)['status'],'INFEASIBLE')

    def test_oracle_infeasible_without_pair_proof_remains_unknown_stratum(self):
        cases=[]
        i=instance();i['patients'][0]['due']=1;cases.append(('deadline',i))
        i=instance();i['rooms'][0]['calendar']=[[[0,1],[3,4]]];cases.append(('calendar',i))
        i=instance();i['rooms'][0]['budgets']=[1];cases.append(('budget',i))
        i=instance();i['patients'][0].update(duration=3,due=6)
        i['patients'].append(dict(i['patients'][0],id='B'));i['rooms'][0].update(calendar=[[[0,6]]],gap=1)
        cases.append(('gap',i));outcomes=[]
        for name,i in cases:
            with self.subTest(stratum=name):
                self.assertEqual(check.schema_errors(i),[]);self.assertEqual(parse(render(i)),i)
                oracle=enumerate_schedules(i);self.assertTrue(oracle['complete']);self.assertEqual(oracle['status'],'INFEASIBLE')
                self.assertFalse(check.check_certificate(i,{'kind':'pair_order_impossible','patients':['A','B']}))
                result=solve(i);self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['reason'],'exhausted_without_supported_certificate')
                verdict=score({'instance':i,'label':'INFEASIBLE'},result)
                self.assertTrue(verdict['unknown']);self.assertFalse(verdict['valid']);outcomes.append(verdict)
        self.assertEqual(len(outcomes),4);self.assertEqual(sum(x['unknown'] for x in outcomes),4)


    def test_identifiers_resource_job_order_and_metadata_invariance(self):
        original=instance();original['patients'][0]['due']=4
        original['patients'].append(dict(original['patients'][0],id='B',surgeon='t'))
        original['surgeons'].append(dict(copy.deepcopy(original['surgeons'][0]),id='t'))
        original['rooms'].append(dict(copy.deepcopy(original['rooms'][0]),id='q'))
        for p in original['patients']:p['eligible_rooms']=['r','q']
        for kind in ['surgeons','rooms']:
            for r in original[kind]:r['calendar']=[[[0,4]]]
        w=[row(),row('B',room='q')];count=len(enumerate_schedules(original)['solutions'])
        variants=[]
        i=copy.deepcopy(original)
        for kind in ['patients','rooms','surgeons']:i[kind].reverse()
        for p in i['patients']:p['eligible_rooms'].reverse()
        variants.append(('permuted',i,list(reversed(w))))
        i=copy.deepcopy(original)
        for p in i['patients']:p['priority']=999;p['emergency']=True
        variants.append(('metadata',i,w))
        i=copy.deepcopy(original);renames={'A':'JobZ','B':'JobY','s':'TeamZ','t':'TeamY','r':'SuiteZ','q':'SuiteY'}
        for kind in ['patients','rooms','surgeons']:
            for item in i[kind]:item['id']=renames[item['id']]
        for p in i['patients']:p['surgeon']=renames[p['surgeon']];p['eligible_rooms']=[renames[r] for r in p['eligible_rooms']]
        renamed=[dict(x,patient=renames[x['patient']],room=renames[x['room']]) for x in w]
        variants.append(('renamed',i,renamed))
        for name,i,schedule in variants:
            with self.subTest(variation=name):
                self.assertEqual(check.schema_errors(i),[])
                self.assertEqual(parse(render(i)),i)
                self.assertEqual(check.check_schedule(i,schedule),[])
                self.assertEqual(len(enumerate_schedules(i)['solutions']),count)
                result=solve(i);self.assertEqual(result['status'],'FEASIBLE')
                self.assertEqual(check.check_schedule(i,result['schedule']),[])

    def test_negative_certificate_order_ids_and_metadata_invariance(self):
        i=instance();i['patients'][0].update(duration=3,due=5)
        i['patients'].append(dict(i['patients'][0],id='B'))
        for changed in [False,True]:
            j=copy.deepcopy(i)
            if changed:
                j['patients'].reverse()
                for n,p in enumerate(j['patients']):p.update(id='Renamed'+str(n),priority=900,emergency=True)
            cert={'kind':'pair_order_impossible','patients':[p['id'] for p in j['patients']]}
            self.assertEqual(parse(render(j)),j)
            self.assertTrue(check.check_certificate(j,cert))
            self.assertTrue(check.check_certificate(j,dict(cert,patients=cert['patients'][::-1])))
            self.assertEqual(enumerate_schedules(j)['status'],'INFEASIBLE')
            self.assertEqual(solve(j)['status'],'INFEASIBLE')

    def test_final_evidence_checked_against_original_after_text_translation(self):
        intended=instance();intended['patients'][0]['release']=3
        translated=parse(render(intended));translated['patients'][0]['release']=0
        answer=solve(translated);self.assertEqual(answer['status'],'FEASIBLE')
        self.assertEqual(check.check_schedule(translated,answer['schedule']),[])
        verdict=score({'instance':intended,'label':'FEASIBLE'},answer)
        self.assertFalse(verdict['valid']);self.assertIn('A: starts before arrival',verdict['violations'])

    def test_missing_fields_and_wrong_object_rows_fail_closed(self):
        for level in ['root','patient','resource']:
            source=instance();obj={'root':source,'patient':source['patients'][0],'resource':source['rooms'][0]}[level]
            for key in list(obj):
                if key=='emergency':continue
                i=copy.deepcopy(source);target={'root':i,'patient':i['patients'][0],'resource':i['rooms'][0]}[level];del target[key]
                with self.subTest(level=level,key=key):self.assertTrue(check.schema_errors(i))
        for kind in ['patients','surgeons','rooms']:
            for bad in [None, [], 'record', True]:
                i=instance();i[kind]=[bad]
                with self.subTest(kind=kind,bad=bad):self.assertTrue(check.schema_errors(i))


    def test_versioned_adapter_rejects_unsupported_translation_and_bad_envelope(self):
        adapter=check.CSPAdapter();self.assertEqual(adapter.revision,check.REVISION)
        i=instance();result=adapter.invoke({'instance':i})
        self.assertEqual(check.check_schedule(i,result['schedule']),[])
        for arguments in [{'instance':dict(i,unsupported_constraint=1)}, {'text':render(i)},
                          {'instance':i,'gold':i}, None]:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):adapter.invoke(arguments)
        self.assertEqual(solve(i,max_nodes=0)['status'],'UNKNOWN')

    def test_invalid_intended_schema_cannot_be_scored_or_normalized(self):
        i=instance();i['patients'][0]['due_typo']=1
        with self.assertRaises(ValueError):check.normalize_instance(i)
        with self.assertRaises(ValueError):score({'instance':i,'label':'FEASIBLE'}, {'status':'FEASIBLE','schedule':[row()]})
