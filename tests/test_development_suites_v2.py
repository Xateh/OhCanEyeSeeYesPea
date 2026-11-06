from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from development_suites_v2 import DEFAULT,build,read_settings
from development_suites_audit import audit


def config(**changes):
    c=deepcopy(DEFAULT)
    c.update(candidates_per_suite=4,suites=['scarcity_contention','combined_constraints'])
    c.update(changes)
    return c


def rehash(path):
    p=path/'manifest.json';m=json.loads(p.read_text())
    m['files']={n:hashlib.sha256((path/n).read_bytes()).hexdigest() for n in m['files']}
    p.write_text(json.dumps(m))


class DevelopmentV2Tests(unittest.TestCase):
    def test_strict_settings_and_ranges(self):
        for text in ['{"seed":1,"seed":2}','{"seed":NaN}','{"seed":Infinity}']:
            with self.assertRaises(ValueError):read_settings(text)
        for c in [config(duration_min=4,duration_max=2),config(optional_percent=True),config(seed=True)]:
            with self.assertRaises(ValueError):read_settings(json.dumps(c))
        self.assertEqual(read_settings(json.dumps(config(duration_min=2,duration_max=2))),config(duration_min=2,duration_max=2))

    def test_complete_audit_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            build(config(),a);build(config(),b)
            self.assertEqual(audit(a)['candidates'],8)
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},
                             {p.name:p.read_bytes() for p in b.iterdir()})

    def test_corrupt_manifest_sources_version_hash_and_shape(self):
        for kind in ['version','source','hash','extra']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'out';build(config(),p)
                m=json.loads((p/'manifest.json').read_text())
                if kind=='version':m['version']='unsupported'
                if kind=='source':m['source_sha256']['development_suites_v2.py']='0'*64
                if kind=='hash':m['files']['gold.jsonl']='0'*64
                if kind=='extra':m['extra']=True
                (p/'manifest.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):audit(p)

    def test_rehashed_text_join_count_and_tool_corruption(self):
        for kind in ['text','join','count','tool','certificate','quarantine','label','ordinal']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'out';build(config(),p)
                if kind in ['text','join']:
                    rows=[json.loads(s) for s in (p/'model.jsonl').read_text().splitlines()]
                    rows[0]['text' if kind=='text' else 'case_id']='corrupt'
                    (p/'model.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                elif kind=='count':
                    c=json.loads((p/'coverage.json').read_text());c['exported']+=1
                    (p/'coverage.json').write_text(json.dumps(c))
                else:
                    rows=[json.loads(s) for s in (p/'receipts.jsonl').read_text().splitlines()]
                    r=next(x for x in rows if x['admission']=='accepted')
                    if kind=='tool':r['tool']={'status':'FEASIBLE','schedule':[],'nodes':1}
                    if kind=='certificate':r['tool']={'status':'INFEASIBLE','certificate':{'kind':'unsupported','patients':['j0','j1']},'nodes':1}
                    if kind=='quarantine':r['tool']={'status':'UNKNOWN','reason':'search_limit','nodes':1}
                    if kind=='label':r['gold_label']='UNKNOWN'
                    if kind=='ordinal':r['ordinal']=999
                    (p/'receipts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                rehash(p)
                with self.assertRaises(ValueError):audit(p)

    def test_timeout_retains_examined_and_unexamined_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'out'
            with patch('development_suites_v2.time.monotonic',side_effect=[0,0,41,41,41]):
                report=build(config(suites=['scarcity_contention']),p)
            self.assertEqual(report['status'],'incomplete')
            self.assertEqual(report['examined'],1)
            receipts=[json.loads(s) for s in (p/'receipts.jsonl').read_text().splitlines()]
            self.assertEqual([r['ordinal'] for r in receipts],[0,1,2,3])
            self.assertIn('instance',receipts[0])
            self.assertEqual(sum(r['admission']=='unexamined' for r in receipts),3)
            self.assertEqual((p/'model.jsonl').read_text(),'')
            self.assertEqual((p/'gold.jsonl').read_text(),'')
            self.assertEqual((p/'receipts.jsonl').read_text(),(p/'diagnostics.jsonl').read_text())
            with self.assertRaises(ValueError):audit(p)
