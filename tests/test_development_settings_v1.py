import unittest
import json
import tempfile
from pathlib import Path
from copy import deepcopy
import development_settings_v1 as m
import development_registration as registration
from test_development_registration import fixture

class Settings(unittest.TestCase):
    def good(self):
        return dict(version=m.VERSION,provider='synthetic',model_revision='offline-test',corpus_version=registration.CORPUS,manifest_sha256='a'*64,case_ids=['test'],repetitions=1,spending_ceiling=0,currency='USD',spending_scope='entire_explicit_plan_all_arms_repetitions',token_limit=20,wall_seconds=120,tool_call_limit=4,retry_limit=0,order='case_then_arm',seed=1)
    def test_valid(self):self.assertEqual(m.load(json.dumps(self.good())),self.good())
    def test_missing_uniform(self):
        for k in m.KEYS:
            x=self.good();x[k]=None
            with self.subTest(k=k),self.assertRaises(ValueError):m.validate(x)
    def test_malformed_types(self):
        for k in m.KEYS:
            for v in ([],{},True):
                x=self.good();x[k]=v
                with self.subTest(k=k,v=v),self.assertRaises(ValueError):m.validate(x)
        for v in (None,[],{},True):
            with self.assertRaises(ValueError):m.load(v)
    def test_secret_unknown_duplicate_nonfinite(self):
        for k in ('api_key','password','other'):
            x=self.good();x[k]='synthetic'
            with self.assertRaises(ValueError):m.validate(x)
        for text in ('{"version":1,"version":2}','{"amount":NaN}','{"amount":Infinity}'):
            with self.assertRaises(ValueError):m.load(text)
        for v in (float('nan'),float('inf'),float('-inf'),-1,True,10**400):
            x=self.good();x['spending_ceiling']=v
            with self.assertRaises(ValueError):m.validate(x)
    def test_bounds_and_accounting(self):
        for k,v in [('repetitions',11),('case_ids',['x']*129),('wall_seconds',0),('tool_call_limit',5),('retry_limit',1),('seed',True),('currency',''),('spending_scope','per_attempt')]:
            x=self.good();x[k]=v
            with self.assertRaises(ValueError):m.validate(x)
        self.assertEqual(m.validate(self.good())['wall_seconds'],120)
    def setup_binding(self,tmp):
        p,plan,gold=fixture(Path(tmp));c=self.good()
        c.update(manifest_sha256=plan['manifest_sha256'],case_ids=plan['planned_case_ids'],repetitions=plan['repetitions'])
        return p,plan,gold,c,m.source_pins()
    def test_binding_and_prepared_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold,c,pins=self.setup_binding(tmp)
            a,ma=m.prepare(c,p,plan,pins,'no_tools');b,mb=m.prepare(c,p,plan,pins,'csp')
            self.assertEqual(a['selected_count'],2)
            self.assertEqual(a['status'],'offline_bound_not_execution_authorization')
            for x,y in zip(ma,mb):
                self.assertEqual(x['messages'][1],y['messages'][1]);self.assertEqual(x['tool_policy'],'none')
                self.assertEqual([z['role'] for z in x['messages']],['system','user'])
                self.assertNotIn(gold[0]['case_id'],json.dumps(x))
                self.assertEqual(set(x['messages'][1]),{'role','content'})
            with self.assertRaises(ValueError):m.assemble('arbitrary text','no_tools')
    def test_binding_drift_unaccepted_incomplete_and_v3(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold,c,pins=self.setup_binding(tmp)
            for field in pins:
                changed=dict(pins);changed[field]='0'*64
                with self.subTest(field=field),self.assertRaises(ValueError):m.bind(c,p,plan,changed)
            for key,v in [('manifest_sha256','0'*64),('case_ids',['unknown']),('repetitions',2),('corpus_version','targeted-interactions-development-v3')]:
                bad=dict(c);bad[key]=v
                with self.subTest(key=key),self.assertRaises(ValueError):m.bind(bad,p,plan,pins)
            bad=deepcopy(plan);bad.pop('arms')
            with self.assertRaises(ValueError):m.bind(c,p,bad,pins)
            bad=deepcopy(plan);bad['planned_case_ids']=['quarantined-id'];bc=dict(c,case_ids=['quarantined-id'])
            with self.assertRaises(ValueError):m.bind(bc,p,bad,pins)
    def test_registration_denominators_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,gold,c,pins=self.setup_binding(tmp);m.bind(c,p,plan,pins)
            result=registration.assess(p,plan,[])
            for a in ('no_tools','csp'):
                self.assertEqual(result['by_arm'][a]['planned'],2)
                self.assertEqual(result['by_arm'][a]['missing'],2)
                self.assertEqual(result['by_arm'][a]['success'],0)
    def test_actual_quarantined_membership(self):
        from development_suites_v2 import build,DEFAULT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,plan,gold,c,pins=self.setup_binding(tmp)
            other=root/'quarantine-package';cfg=deepcopy(DEFAULT);cfg['candidates_per_suite']=4
            build(cfg,other)
            diagnostics=[json.loads(s) for s in (other/'diagnostics.jsonl').read_text().splitlines()]
            q=[x['case_id'] for x in diagnostics if x['admission']=='quarantined']
            self.assertTrue(q,'synthetic fixture must include actual quarantined candidate')
            import hashlib
            bad=deepcopy(plan);bad.update(manifest_sha256=hashlib.sha256((other/'manifest.json').read_bytes()).hexdigest(),planned_case_ids=q[:1])
            bc=dict(c,manifest_sha256=bad['manifest_sha256'],case_ids=q[:1])
            with self.assertRaisesRegex(ValueError,'unaccepted/excluded'):m.bind(bc,other,bad,pins)
