from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import development_registration as consumer
from development_suites_v2 import DEFAULT,build,VERSION as CORPUS
from tier_a_input_view import VERSION as INPUT_VERSION,SHARED
from tier_a_inputs import ARM
from tier_a_contract import model_inputs as old_inputs
import test_tier_a_contract as old_tests


def fixture(root):
    p=root/'package';c=deepcopy(DEFAULT);c.update(candidates_per_suite=4,suites=['scarcity_contention'])
    build(c,p)
    gold=[json.loads(s) for s in (p/'gold.jsonl').read_text().splitlines()]
    plan=dict(registration_version=consumer.VERSION,corpus_version=CORPUS,
              input_view_version=INPUT_VERSION,manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),
              consumer_sha256=hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest(),
              instruction_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in dict(shared=SHARED,**ARM).items()},
              planned_case_ids=[g['case_id'] for g in gold[:2]],arms=['no_tools','csp'],repetitions=1)
    return p,plan,gold


def receipt(case,output,**changes):
    r=dict(case_id=case['case_id'],repetition=0,arm='no_tools',raw_output=json.dumps(output),
           normalized_output=output,normalization_errors=[],provider_error=False,tool_error=False,termination='final')
    r.update(changes);return r


class RegistrationTests(unittest.TestCase):
    def test_bound_readers_precede_old_audit(self):
        for kind in ['oversized','symlink','rows','depth']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                p,plan,gold=fixture(Path(tmp))
                if kind=='oversized':
                    with (p/'coverage.json').open('wb') as f:f.truncate(consumer.MAX_FILE+1)
                if kind=='symlink':
                    (p/'coverage.json').unlink();target=Path(tmp)/'target';target.write_text('{}')
                    (p/'coverage.json').symlink_to(target)
                if kind=='rows':(p/'receipts.jsonl').write_text('{}\n'*129)
                if kind=='depth':(p/'manifest.json').write_text('['*65+']'*65)
                with patch('development_registration.audit') as old_audit:
                    if kind=='oversized':
                        with patch('development_registration.os.read',side_effect=AssertionError('must not read oversized file')):
                            with self.assertRaises(ValueError):consumer.verified_package(p)
                    else:
                        with self.assertRaises((ValueError,OSError)):consumer.verified_package(p)
                    old_audit.assert_not_called()

    def test_explicit_registration_and_matched_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold=fixture(Path(tmp))
            a=consumer.model_inputs(p,plan,'no_tools');b=consumer.model_inputs(p,plan,'csp')
            self.assertEqual(len(a),2)
            self.assertEqual(len(consumer.planned_slots(p,plan)),4)
            for x,y in zip(a,b):
                self.assertEqual(set(x),{'shared_instruction','arm_instruction','instance_text'})
                self.assertEqual(x['instance_text'],y['instance_text'])
                self.assertEqual(x['shared_instruction'],y['shared_instruction'])
                self.assertNotIn('"patients":["A","E"]',x['instance_text'])
                self.assertNotIn(gold[0]['case_id'],json.dumps(x))
            for key,value in [('corpus_version','unsupported'),('manifest_sha256','0'*64),
                              ('consumer_sha256','0'*64),('planned_case_ids',['excluded']),('input_view_version','old')]:
                with self.assertRaises(ValueError):consumer.preflight(p,dict(plan,**{key:value}))
            mixed=Path(tmp)/'extra';mixed.write_text('extra')
            (p/'extra').write_text('extra')
            with self.assertRaises(ValueError):consumer.preflight(p,plan)

    def test_planned_denominators_unknown_error_missing_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold=fixture(Path(tmp))
            rows=[receipt(gold[0],{'status':'UNKNOWN'}),receipt(gold[1],{'status':'UNKNOWN'},
                    provider_error=True,termination='provider_error',normalization_errors=['timeout'])]
            result=consumer.assess(p,plan,rows)
            self.assertEqual(result['by_arm']['no_tools']['planned'],2)
            self.assertEqual(result['by_arm']['no_tools']['success'],0)
            self.assertEqual(result['by_arm']['no_tools']['unknown'],1)  # normalization error suppresses inferred status
            self.assertEqual(result['by_arm']['csp']['missing'],2)
            self.assertEqual(result['by_arm']['csp']['planned'],2)
            good=({'status':'FEASIBLE','schedule':gold[0]['witness']} if gold[0]['gold_label']=='FEASIBLE'
                  else {'status':'INFEASIBLE','certificate':gold[0]['certificate']})
            scored=consumer.assess(p,plan,[receipt(gold[0],good)])
            self.assertEqual(scored['by_arm']['no_tools']['success'],1)
            self.assertEqual(scored['by_arm']['no_tools']['planned'],2)
            with self.assertRaises(ValueError):consumer.assess(p,plan,[rows[0],rows[0]])

    def test_old_package_behavior_unchanged_new_cross_feed_rejected(self):
        old=Path(__file__).resolve().parents[1]/'fixtures/tier-a-original-synthetic-v1'
        self.assertEqual(len(old_inputs(old,old_tests.plan())),9)
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold=fixture(Path(tmp))
            with self.assertRaises(ValueError):consumer.preflight(old,plan)
