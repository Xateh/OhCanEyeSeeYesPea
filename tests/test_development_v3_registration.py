from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import development_v3_registration as m
import test_development_settings_v1 as settings_tests

BUNDLE=Path(__file__).resolve().parents[1]/'fixtures/development-v3-qa/bundle.json'

def fixture(root):
    p=root/'package';p.mkdir();(p/'bundle.json').write_bytes(BUNDLE.read_bytes())
    (p/'manifest.json').write_text(json.dumps(m.expected_manifest(),sort_keys=True)+'\n')
    b=json.loads(BUNDLE.read_text());ids=[r['case_id'] for r in b['records'] if r['evidence']['admission']=='accepted']
    plan=dict(registration_version=m.VERSION,corpus_version=m.corpus.VERSION,manifest_sha256=m.digest((p/'manifest.json').read_bytes()),source_sha256=m.source_pins(),planned_case_ids=ids,arms=['no_tools','csp'],repetitions=1)
    c=settings_tests.Settings().good();c.update(corpus_version=plan['corpus_version'],manifest_sha256=plan['manifest_sha256'],case_ids=ids)
    return p,plan,c,b

def receipt(case,output,arm='no_tools',**changes):
    r=dict(case_id=case['case_id'],arm=arm,repetition=0,raw_output=json.dumps(output),normalized_output=deepcopy(output),normalization_errors=[],provider_error=False,tool_error=False,termination='final')
    r.update(changes);return r

class V3Registration(unittest.TestCase):
    def test_all28_prepared_and_empty_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));_,a=m.prepare(c,p,plan,'no_tools');_,z=m.prepare(c,p,plan,'csp')
            self.assertEqual(len(a),28);self.assertEqual(len(z),28)
            ids=plan['planned_case_ids']
            for x,y in zip(a,z):
                self.assertEqual(x['messages'][1],y['messages'][1]);self.assertEqual(x['tool_policy'],'none')
                self.assertEqual(set(x),{'version','messages','tool_policy'})
                self.assertEqual([i['role'] for i in x['messages']],['system','user'])
                self.assertTrue(all(i not in json.dumps(x) for i in ids))
            result=m.assess(p,plan,[])
            for a in plan['arms']:
                self.assertEqual(result['by_arm'][a]['planned'],28);self.assertEqual(result['by_arm'][a]['missing'],28)
                self.assertEqual(result['by_arm'][a]['success'],0)
    def test_mixed_receipts_and_group_conservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));g=m.preflight(p,plan)
            good=dict(status='FEASIBLE',schedule=g[0]['evidence']['witness'])
            rows=[receipt(g[0],good),receipt(g[1],{'status':'UNKNOWN'}),receipt(g[2],{'status':'UNKNOWN'},raw_output='{bad'),receipt(g[3],{'status':'FEASIBLE','schedule':[]}),receipt(g[4],good,termination='timeout'),receipt(g[5],{'status':'UNKNOWN'},provider_error=True,termination='provider_error'),receipt(g[6],{'status':'UNKNOWN'},tool_error=True,termination='tool_error'),receipt(g[7],None,raw_output=None,normalized_output=None,termination='abstained')]
            result=m.assess(p,plan,rows)
            a=result['by_arm']['no_tools'];self.assertEqual(a['planned'],28);self.assertEqual(a['success'],1);self.assertEqual(a['missing'],20);self.assertEqual(a['timeout'],1)
            self.assertEqual(result['by_arm']['csp']['missing'],28)
            for arm in plan['arms']:
                for k,v in result['by_arm'][arm].items():self.assertEqual(sum(x[arm][k] for x in result['by_construction'].values()),v)
            with self.assertRaises(ValueError):m.assess(p,plan,[rows[0],rows[0]])
    def test_valid_witnesses_both_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));g=m.preflight(p,plan)
            rows=[receipt(x,dict(status='FEASIBLE',schedule=x['evidence']['witness']),a) for x in g for a in plan['arms']]
            result=m.assess(p,plan,rows)
            for a in plan['arms']:self.assertEqual(result['by_arm'][a]['success'],28)
    def test_intended_instance_and_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));g=m.preflight(p,plan)
            output=dict(status='FEASIBLE',schedule=g[0]['evidence']['witness'])
            wrong=deepcopy(output);wrong['schedule'][0]['room']='not-an-intended-room'
            rows=[receipt(g[0],wrong),receipt(g[1],{'status':'UNKNOWN'},normalized_output=output)]
            result=m.assess(p,plan,rows)
            self.assertEqual(result['by_arm']['no_tools']['success'],0)
            self.assertTrue(all(x['error'] for x in result['rows'] if not x['missing']))
    def test_selection_settings_and_version_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));q=next(x['case_id'] for x in b['records'] if x['evidence']['admission']=='quarantined')
            for ids in ([q],['unknown'],plan['planned_case_ids'][:1]*2):
                bad=deepcopy(plan);bad['planned_case_ids']=ids
                with self.assertRaises(ValueError):m.preflight(p,bad)
            for key,value in [('registration_version','old'),('corpus_version','unsupported'),('manifest_sha256','0'*64),('source_sha256',{}),('repetitions',None)]:
                bad=deepcopy(plan);bad[key]=value
                with self.assertRaises(ValueError):m.preflight(p,bad)
            bad=deepcopy(plan);bad.pop('arms')
            with self.assertRaises(ValueError):m.preflight(p,bad)
            for key in c:
                bad=dict(c);bad[key]=None
                with self.assertRaises(ValueError):m.bind(bad,p,plan)
            bad=dict(c);bad['case_ids']=c['case_ids'][:-1]
            with self.assertRaises(ValueError):m.bind(bad,p,plan)
    def test_tampered_incomplete_and_rehashed_package(self):
        for change in ('label','incomplete','tool','version','metadata'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                p,plan,c,b=fixture(Path(tmp))
                if change=='label':b['records'][0]['expected_label']='FEASIBLE'
                elif change=='incomplete':b['status']='incomplete'
                elif change=='tool':b['records'][0]['evidence']['tool']['status']='INFEASIBLE'
                elif change=='version':b['version']='other'
                else:b['extra']='metadata'
                data=json.dumps(b).encode();(p/'bundle.json').write_bytes(data)
                manifest=m.expected_manifest();manifest['bundle_sha256']=m.digest(data)
                (p/'manifest.json').write_text(json.dumps(manifest))
                plan['manifest_sha256']=m.digest((p/'manifest.json').read_bytes())
                with self.assertRaisesRegex(ValueError,'bundle identity'):m.preflight(p,plan)
    def test_bounded_files_before_parsing(self):
        for kind in ('oversized','symlink','fifo','extra','depth','duplicate'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                p,plan,c,b=fixture(Path(tmp));target=p/'manifest.json'
                if kind=='oversized':
                    with target.open('wb') as f:f.truncate(m.MAX_BYTES+1)
                elif kind=='symlink':
                    target.unlink();target.symlink_to(BUNDLE)
                elif kind=='fifo':target.unlink();os.mkfifo(target)
                elif kind=='extra':(p/'extra').write_text('')
                elif kind=='depth':target.write_text('['*65+']'*65)
                else:target.write_text('{"version":1,"version":2}')
                with patch('development_v3_registration.strict_json',side_effect=AssertionError('must reject before parse')) if kind in ('oversized','symlink','fifo','extra','depth') else patch('development_v3_registration.corpus.audit',side_effect=AssertionError('must reject before audit')):
                    with self.assertRaises((ValueError,OSError)):m.read_package(p)
    def test_repetitions_and_timeout_with_valid_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));plan['repetitions']=2;c['repetitions']=2
            m.bind(c,p,plan);g=m.preflight(p,plan)
            good=dict(status='FEASIBLE',schedule=g[0]['evidence']['witness'])
            item=receipt(g[0],good,termination='timeout')
            result=m.assess(p,plan,[item])
            for arm in plan['arms']:
                self.assertEqual(result['by_arm'][arm]['planned'],56)
                self.assertEqual(result['by_arm'][arm]['success'],0)
            self.assertEqual(result['by_arm']['no_tools']['timeout'],1)
            self.assertEqual(result['by_arm']['no_tools']['missing'],55)
            self.assertEqual(result['by_arm']['csp']['missing'],56)
    def test_false_certificate_and_oversized_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,plan,c,b=fixture(Path(tmp));g=m.preflight(p,plan)
            bad=dict(status='INFEASIBLE',certificate=dict(kind='pair_order_impossible',patients=['p0','p1']))
            rows=[receipt(g[0],bad),receipt(g[1],{'status':'UNKNOWN'},raw_output=' '*65537)]
            result=m.assess(p,plan,rows)
            self.assertEqual(result['by_arm']['no_tools']['success'],0)
            self.assertEqual(result['by_arm']['no_tools']['planned'],28)
            self.assertTrue(all(r['error'] for r in result['rows'] if not r['missing']))
