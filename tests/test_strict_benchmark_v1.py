import importlib, importlib.util, unittest
from copy import deepcopy
from pathlib import Path
import json,tempfile
from unittest.mock import patch
import temporal_validation_v2 as strict
from surgerybench.temporal_check import schema_errors as old_schema_errors

class RegistrationTests(unittest.TestCase):
    def test_registration_uses_strict_boundary_and_keeps_rejected_slots(self):
        self.assertIsNotNone(importlib.util.find_spec('strict_benchmark_v1'))
        c=importlib.import_module('strict_benchmark_v1')
        plan,cases=c.register()
        self.assertEqual(plan['strict_revision'],strict.REVISION)
        self.assertEqual(len(plan['slots']),8)
        self.assertEqual(len(cases),4)
        invalid=cases['schema-invalid-empty-mappings']
        self.assertEqual(old_schema_errors(invalid['instance']),[])
        self.assertTrue(invalid['input_errors'])
        self.assertIsNone(invalid['text'])
        self.assertEqual(sum(x['stratum']=='oracle_only' for x in cases.values()),1)
        self.assertEqual(plan['source_counts'],{'FEASIBLE':7,'certified_INFEASIBLE':2,'oracle_only_INFEASIBLE':6})
        self.assertEqual(len(plan['source_case_ids']),15)
        self.assertEqual(len(plan['selected_source_ids']),3)
        self.assertEqual(sum(x['arm']=='csp' for x in plan['slots'][::2]),2)


class ConsumerTests(unittest.TestCase):
    def test_end_to_end_consumer_adopts_strict_scoring_and_tool_dispatch(self):
        c=importlib.import_module('strict_benchmark_v1')
        self.assertTrue(hasattr(c,'run'))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(strict,'schema_errors',wraps=strict.schema_errors) as schema, patch.object(strict,'score',wraps=strict.score) as scoring, patch.object(strict,'solve',wraps=strict.solve) as solving:
                result=c.run(Path(tmp)/'run')
            self.assertGreater(schema.call_count,0);self.assertEqual(scoring.call_count,6);self.assertEqual(solving.call_count,3)
            self.assertEqual(sum(x['planned'] for x in result['by_arm'].values()),8)
            self.assertEqual(result['by_arm']['csp']['evidence_success'],2)
            self.assertEqual(result['by_arm']['no_tools']['evidence_success'],0)
            self.assertEqual(result['validation_strata']['schema_invalid']['input_invalid'],2)
            self.assertEqual(result['validation_strata']['oracle_only']['planned'],2)
            self.assertEqual(result['validation_strata']['oracle_only']['unknown'],2)
            self.assertEqual(result['valid_missing'],0)
            self.assertEqual(c.assess(Path(tmp)/'run')['rows'],result['rows'])


    def test_payload_isolation_same_case_text_and_no_baseline_dispatch(self):
        c=importlib.import_module('strict_benchmark_v1');seen=[]
        class Spy(c.OfflineTranslator):
            def respond(self,messages,tools,limits):
                seen.append((deepcopy(messages),deepcopy(tools)))
                return super().respond(messages,tools,limits)
        with tempfile.TemporaryDirectory() as tmp:result=c.run(Path(tmp)/'run',Spy)
        self.assertEqual(len(seen),9)
        texts={}
        for messages,tools in seen:
            self.assertTrue(all(set(m)<= {'role','content','name'} for m in messages))
            self.assertNotIn('case_id',json.dumps(messages));self.assertNotIn('lineage',json.dumps(messages))
            self.assertNotIn('certification',json.dumps(messages));self.assertNotIn('witness',json.dumps(messages))
            texts.setdefault(messages[1]['content'],set()).add(bool(tools))
        self.assertEqual(len(texts),3);self.assertTrue(all(arms=={False,True} for arms in texts.values()))
        self.assertTrue(all(not r['translation_invalid'] for r in result['rows']))

    def test_strict_tool_rejection_cannot_become_evidence_success(self):
        c=importlib.import_module('strict_benchmark_v1')
        class Bad(c.OfflineTranslator):
            def respond(self,messages,tools,limits):
                if tools and messages[-1]['role']!='tool':
                    return dict(type='tool_call',name='csp',arguments={'instance':dict(schema_version='1.1',days=1,day_minutes=1440,patients={},rooms={},surgeons={})},usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                return super().respond(messages,tools,limits)
        with tempfile.TemporaryDirectory() as tmp:result=c.run(Path(tmp)/'run',Bad)
        rows=[r for r in result['rows'] if r['arm']=='csp' and not r['input_invalid']]
        self.assertEqual(len(rows),3);self.assertTrue(all(r['translation_invalid'] and not r['evidence_success'] for r in rows))

    def test_mistranslation_final_is_scored_against_original(self):
        c=importlib.import_module('strict_benchmark_v1')
        class Wrong(c.OfflineTranslator):
            def respond(self,messages,tools,limits):
                result=super().respond(messages,tools,limits)
                if result['type']=='tool_call':
                    for job in result['arguments']['instance']['patients']:
                        if job['id']=='B':job['mandatory']=False
                return result
        with tempfile.TemporaryDirectory() as tmp:result=c.run(Path(tmp)/'run',Wrong)
        row=next(r for r in result['rows'] if r['stratum']=='certified_negative' and r['arm']=='csp')
        self.assertTrue(row['format_valid']);self.assertFalse(row['strict_evidence_valid']);self.assertFalse(row['evidence_success'])
        self.assertEqual(row['stage'],'final_evidence_invalid')

    def test_malformed_timeout_missing_usage_and_interruption_denominators(self):
        c=importlib.import_module('strict_benchmark_v1')
        for mode in ['malformed','timeout','missing_usage','interrupted']:
            class Fault(c.OfflineTranslator):
                def respond(self,messages,tools,limits):
                    if mode=='timeout':raise TimeoutError('synthetic offline timeout')
                    if mode=='malformed':return dict(type='final',raw='{',usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                    if mode=='missing_usage':return dict(type='final',raw='{"status":"UNKNOWN"}',usage=None)
                    return super().respond(messages,tools,limits)
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result=c.run(Path(tmp)/'run',Fault,max_attempts=0 if mode=='interrupted' else None)
                self.assertEqual(sum(x['planned'] for x in result['by_arm'].values()),8)
                self.assertEqual(result['validation_strata']['schema_invalid']['input_invalid'],2)
                if mode=='malformed':self.assertEqual(sum(r['stage']=='final_invalid' for r in result['rows']),6)
                if mode=='timeout':self.assertEqual(sum(r['timeout'] for r in result['rows']),1);self.assertEqual(result['valid_missing'],5)
                if mode=='missing_usage':self.assertEqual(result['stop_reason'],'unknown_cost_stopped_new_slots');self.assertEqual(result['valid_missing'],5)
                if mode=='interrupted':self.assertEqual(result['valid_missing'],6)

    def test_valid_fixture_finals_in_both_gold_classes_and_no_tools_arm(self):
        c=importlib.import_module('strict_benchmark_v1')
        class Answers(c.OfflineTranslator):
            def respond(self,messages,tools,limits):
                text=messages[1]['content']
                if not tools:
                    out={'status':'UNKNOWN'} if 'takes 3 minutes' in text else {'status':'INFEASIBLE','certificate':{'kind':'pair_order_impossible','patients':['A','B']}} if 'Surgery B is mandatory' in text else {'status':'FEASIBLE','schedule':[{'patient':'A','day':0,'start':0,'room':'r0'}]}
                    return dict(type='final',raw=json.dumps(out),usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                return super().respond(messages,tools,limits)
        with tempfile.TemporaryDirectory() as tmp:result=c.run(Path(tmp)/'run',Answers)
        self.assertEqual(result['by_arm']['no_tools']['evidence_success'],2)
        self.assertEqual(result['by_arm']['csp']['evidence_success'],2)

    def test_saved_plan_and_duplicate_attempt_tampering_rejected(self):
        c=importlib.import_module('strict_benchmark_v1')
        for mode in ['plan','duplicate']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'run';c.run(out)
                if mode=='plan':
                    plan=json.loads((out/'plan.json').read_text());plan['strict_revision']='wrong';(out/'plan.json').write_text(json.dumps(plan))
                else:
                    lines=(out/'attempts.jsonl').read_text().splitlines();lines[1]=lines[0];(out/'attempts.jsonl').write_text('\n'.join(lines)+'\n')
                with self.assertRaises(ValueError):c.assess(out)
                with self.assertRaises(FileExistsError):c.run(out)

    def test_cli_run_and_readonly_assessment(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            for flag in ['--out','--assess']:
                result=subprocess.run([sys.executable,'tools/run_strict_benchmark.py',flag,str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout)['version'],'strict-temporal-offline-consumer-v1')


    def test_early_final_and_repeated_tool_call_guards(self):
        c=importlib.import_module('strict_benchmark_v1')
        for mode in ['early','repeat']:
            class Bad(c.OfflineTranslator):
                def respond(self,messages,tools,limits):
                    if tools and mode=='early':return dict(type='final',raw='{"status":"UNKNOWN"}',usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                    if tools and mode=='repeat':
                        instance=strict.parse(messages[1]['content'].replace(c.VIEW_FRAGMENT,c.RAW_FRAGMENT))
                        return dict(type='tool_call',name='csp',arguments={'instance':instance},usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                    return super().respond(messages,tools,limits)
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                result=c.run(Path(tmp)/'run',Bad)
                rows=[r for r in result['rows'] if r['arm']=='csp' and not r['input_invalid']]
                self.assertTrue(all(not r['success'] for r in rows))
                if mode=='early':self.assertTrue(all(r.get('required_tool_missing') for r in rows))
                if mode=='repeat':self.assertEqual(result['by_arm']['csp']['tool_calls'],3);self.assertTrue(all(r['operational_error'] for r in rows))


    def test_normalized_input_text_and_source_pins(self):
        c=importlib.import_module('strict_benchmark_v1');plan,cases=c.register()
        source=next(g for g in cases.values() if g['stratum']=='feasible')
        i=deepcopy(source['instance']);del i['patients'][0]['emergency'];before=deepcopy(i)
        prepared=c.prepare_case('local-check','local-family','FEASIBLE','feasible',i)
        self.assertEqual(i,before);self.assertFalse(prepared['input_errors'])
        parsed=strict.parse(prepared['text'].replace(c.VIEW_FRAGMENT,c.RAW_FRAGMENT))
        self.assertEqual(parsed,strict.normalize_instance(i))
        for name in ['strict_benchmark_v1.py','temporal_validation_v2.py','solver_interface.py','paired_runner.py','surgerybench/temporal_check.py','surgerybench/temporal_text.py']:
            self.assertIn(name,plan['source_sha256'])
        for mutation in [dict(source['instance'],unknown_constraint=True),dict(source['instance'],patients={})]:
            rejected=c.prepare_case('bad','probe',None,'schema_invalid',mutation)
            self.assertTrue(rejected['input_errors']);self.assertIsNone(rejected['text'])

    def test_observed_fixture_overrun_stops_and_reassesses_without_replacement(self):
        c=importlib.import_module('strict_benchmark_v1')
        class Over(c.OfflineTranslator):
            def respond(self,*args):
                return dict(type='final',raw='{"status":"UNKNOWN"}',usage=dict(input_tokens=0,output_tokens=0,cost_usd=1.5))
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';result=c.run(out,Over)
            self.assertEqual(result['stop_reason'],'spending_ceiling_stopped_new_slots')
            self.assertEqual(result['valid_missing'],5)
            self.assertEqual(c.assess(out)['stop_reason'],result['stop_reason'])
            self.assertEqual(len((out/'attempts.jsonl').read_text().splitlines()),1)


    def test_claimed_objective_does_not_extend_frozen_output_contract(self):
        c=importlib.import_module('strict_benchmark_v1')
        class Claimed(c.OfflineTranslator):
            def respond(self,messages,tools,limits):
                if not tools:return dict(type='final',raw='{"status":"UNKNOWN","objective":0}',usage=dict(input_tokens=0,output_tokens=0,cost_usd=0))
                return super().respond(messages,tools,limits)
        with tempfile.TemporaryDirectory() as tmp:result=c.run(Path(tmp)/'run',Claimed)
        rows=[r for r in result['rows'] if r['arm']=='no_tools' and not r['input_invalid']]
        self.assertTrue(all(not r['format_valid'] and not r['success'] for r in rows))
        self.assertTrue(all(r['optimality']=='not_applicable' for r in result['rows']))
