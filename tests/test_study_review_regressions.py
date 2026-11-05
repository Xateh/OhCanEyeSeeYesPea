"""Synthetic receipts / existing recorded attempts only; no provider calls."""
from copy import deepcopy
import json
import unittest
from study import framework,framework_report,metrics
from study.claude_provider import parse_cli_reply,MODEL
from study.run_hard import execute
from surgerybench.common import read_jsonl
import test_study_framework as examples

class ReviewRegressions(unittest.TestCase):
    def test_duplicate_repetition_cannot_fill_missing_repetition(self):
        a=examples.row(examples.FEASIBLE_GOLD,examples.GOOD,arm='no_tools',repetition=0)
        b=examples.row(examples.FEASIBLE_GOLD,examples.GOOD,arm='csp',repetition=0)
        with self.assertRaises(ValueError):framework.require_planned([a,b,deepcopy(a),deepcopy(b)],4)
        with self.assertRaises(ValueError):metrics.paired_buckets([a,a,b])
    def test_invalid_final_keeps_valid_envelope_usage(self):
        envelope=dict(is_error=False,result='{broken',modelUsage={MODEL:{}},usage=dict(input_tokens=100,output_tokens=20),total_cost_usd=0.5)
        try:parse_cli_reply(json.dumps(envelope),MODEL)
        except ValueError as error:self.assertEqual(getattr(error,'observed_usage',None),dict(input_tokens=100,output_tokens=20,cost_usd=0.5))
        else:self.fail('invalid JSON accepted')
    def test_unknown_cost_is_not_zero_and_stops_scheduling(self):
        row=dict(responses=[],errors=[{'stage':'provider_or_parse','error':'TimeoutExpired'}],parsing_or_provider_error=True)
        self.assertIsNone(metrics.row_cost(row))
        cases=[{'id':'a'},{'id':'b'}];gold={r['id']:{} for r in cases}
        def fake(case,gold):return dict(case_id=case['id'],responses=[],errors=[])
        rows,skipped,spent=execute(cases,gold,1,5,evaluator=fake)
        self.assertEqual((len(rows),skipped,spent),(1,1,None))
    def test_original_failures_retained_reruns_separate(self):
        gold={g['id']:g for g in read_jsonl('fixtures/hard-synthetic-v1/gold.jsonl')}
        primary=framework_report.load_hard(gold)
        self.assertEqual(sum(r['score']['valid'] for group in primary.values() for r in group),64)
        self.assertEqual(sum(r['parsing_or_provider_error'] for group in primary.values() for r in group),36)
    def test_explicit_plan_rejects_unplanned_slot_and_boolean_repeat(self):
        a=examples.row(examples.FEASIBLE_GOLD,examples.GOOD,arm='no_tools',repetition=0)
        expected=framework.expected_slots([a['case_id']],('no_tools',),1)
        wrong=dict(a,case_id='unplanned')
        with self.assertRaises(ValueError):framework.require_planned([wrong],1,expected)
        with self.assertRaises(ValueError):framework.require_planned([dict(a,repetition=True)],1,expected)
        with self.assertRaises(ValueError):framework.expected_slots([a['case_id']],('no_tools',),True)
        pairs=metrics.paired_buckets([a],expected_pairs={(a['case_id'],0),(a['case_id'],1)})
        self.assertEqual(pairs['incomplete'],2)
    def test_malformed_output_usage_survives_frozen_harness_to_pair_rows(self):
        import tempfile
        from study.claude_provider import ClaudeCodeProvider
        from study.run_iteration import run_one,select_cases
        envelope=dict(is_error=False,result='{broken',modelUsage={MODEL:{}},usage=dict(input_tokens=100,output_tokens=20),total_cost_usd=0.5)
        def factory():return ClaudeCodeProvider('v1',runner=lambda *args:json.dumps(envelope))
        cases,gold=select_cases('test',1)
        with tempfile.TemporaryDirectory() as scratch:rows=run_one(cases[0],gold[cases[0]['id']],0,factory,scratch)
        self.assertEqual(len(rows),2)
        for row in rows:
            self.assertTrue(row['parsing_or_provider_error']);self.assertFalse(row['score']['valid'])
            self.assertEqual(row['token_usage'],dict(input_tokens=100,output_tokens=20))
            self.assertEqual(metrics.row_cost(row),0.5)
        self.assertEqual(metrics.cost_summary(rows)['cost_usd'],1.0)
    def test_known_usage_on_provider_error_and_unknown_costs(self):
        from study.accounting import envelope_usage,cost_summary
        envelope=dict(is_error=True,result='synthetic failure',modelUsage={MODEL:{}},usage=dict(input_tokens=2,output_tokens=3),total_cost_usd=0.25)
        try:parse_cli_reply(json.dumps(envelope),MODEL)
        except RuntimeError as error:self.assertEqual(error.observed_usage['cost_usd'],0.25)
        else:self.fail('provider error accepted')
        for cost in (None,True,-1,float('inf'),float('nan')):
            bad=dict(envelope,total_cost_usd=cost)
            self.assertIsNone(envelope_usage(bad)['cost_usd'])
        row=dict(call_accounting=[dict(usage=dict(cost_usd=0.25)),dict(usage=None)])
        self.assertIsNone(metrics.row_cost(row))
        self.assertEqual(cost_summary([row]),dict(cost_usd=None,known_cost_usd=0.25,unknown_cost_runs=1,cost_coverage=[0,1]))
    def test_missing_tokens_do_not_erase_observed_cost(self):
        from study.accounting import envelope_usage
        observed=envelope_usage(dict(total_cost_usd=0.5))
        self.assertEqual(observed,dict(input_tokens=None,output_tokens=None,cost_usd=0.5))
        self.assertEqual(metrics.row_cost(dict(call_accounting=[dict(usage=observed)])),0.5)
    def test_invalid_budget_never_starts_evaluator(self):
        def forbidden(*args):self.fail('evaluator must not start')
        for budget in (float('nan'),float('inf'),-1,True,None):
            with self.assertRaises(ValueError):execute([{'id':'a'}],{'a':{}},1,budget,evaluator=forbidden)
    def test_reruns_remain_complete_separate_cohorts(self):
        gold={g['id']:g for g in read_jsonl('fixtures/hard-synthetic-v1/gold.jsonl')}
        primary=framework_report.load_hard(gold);reruns=framework_report.load_hard_reruns(gold)
        self.assertEqual(sum(len(r) for r in primary.values()),100)
        self.assertEqual(sum(len(r) for r in reruns.values()),40)
        self.assertEqual(sum(x['score']['valid'] for r in reruns.values() for x in r),38)
        for size in reruns:
            self.assertEqual({r['case_id'] for r in primary[size]},{r['case_id'] for r in reruns[size]})

    def test_harness_cardinality_mismatch_cannot_drop_rows(self):
        import tempfile
        from unittest.mock import patch
        from study.run_iteration import run_one,select_cases
        cases,gold=select_cases('test',1)
        for rows,provider_count in (([{}],0),([],1),([{},{}],1)):
            def fake_run(model,gold,out,factory):
                for _ in range(provider_count):factory()
                return rows
            with tempfile.TemporaryDirectory() as scratch, patch('study.run_iteration.run',side_effect=fake_run):
                with self.assertRaisesRegex(ValueError,'cardinality mismatch'):
                    run_one(cases[0],gold[cases[0]['id']],0,lambda:object(),scratch)
    def test_report_unknown_and_mixed_costs_remain_null(self):
        from study.accounting import cost_summary
        known=dict(call_accounting=[dict(usage=dict(cost_usd=0.5))])
        unknown=dict(call_accounting=[dict(usage=None)])
        for rows,subtotal,coverage in (([unknown],0,[0,1]),([known,unknown],0.5,[1,2])):
            summary=cost_summary(rows)
            self.assertIsNone(summary['cost_usd'])
            self.assertEqual(summary['known_cost_usd'],subtotal)
            self.assertEqual(summary['cost_coverage'],coverage)
            self.assertIsNone(json.loads(json.dumps(summary,allow_nan=False))['cost_usd'])
    def test_chart_unknown_usage_is_not_a_zero_bar(self):
        class Axis:
            def __init__(self):self.bars=[];self.labels=[]
            def bar(self,x,value,**kw):self.bars.append((x,value))
            def text(self,x,value,label,**kw):self.labels.append(label)
            def set_xticks(self,*args):pass
            def set_title(self,*args,**kw):pass
        class Figure:
            def suptitle(self,title,**kw):self.title=title
            def tight_layout(self):pass
        class Plot:
            def subplots(self,*args,**kw):return figure,axes
        from unittest.mock import patch
        axes=[Axis(),Axis()];figure=Figure()
        columns={'LLM-only':dict(mean_seconds=1,mean_tokens=None,cost_usd=None,known_cost_usd=0),
                 'LLM+CSP':dict(mean_seconds=2,mean_tokens=20,cost_usd=None,known_cost_usd=0.5)}
        with patch('study.framework_report.tune'):
            self.assertIs(framework_report.chart_cost(Plot(),columns),figure)
        self.assertEqual(axes[1].bars,[(1,20)])
        self.assertIn('not reported',axes[1].labels)
        self.assertIn('not monetary spending',figure.title)
