from copy import deepcopy
from pathlib import Path
import hashlib,json,tempfile,unittest
import benchmark_datasets as catalog
import development_registration as registration
import development_suites_audit as audit
import test_development_registration as v2
import test_development_v3_registration as v3
import test_tier_a_contract as tier
ROOT=Path(__file__).resolve().parents[1]
class CatalogTests(unittest.TestCase):
 def test_tier_a_excludes_oracle_only_without_changing_frozen_contract(self):
  cases,identities=catalog.load([dict(kind='tier-a-v1',directory=str(ROOT/'fixtures/tier-a-original-synthetic-v1'),plan=tier.plan())]);self.assertEqual(len(cases),9);self.assertEqual(sum(g['label']=='FEASIBLE' for g in cases),7)
 def test_seeded_v2_and_legacy_auditor_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,plan,gold=v2.fixture(Path(tmp));cases,_=catalog.load([dict(kind='seeded-v2',directory=str(p),plan=plan)]);self.assertEqual(len(cases),2)
   m=json.loads((p/'manifest.json').read_text());m['source_sha256']['development_suites_audit.py']=audit.LEGACY_AUDIT_SHA256;m['baseline_revision']=audit.BASELINE;(p/'manifest.json').write_text(json.dumps(m))
   self.assertEqual(audit.audit(p)['audit'],'PASS')
   m['source_sha256']['development_suites_audit.py']='0'*64;(p/'manifest.json').write_text(json.dumps(m))
   with self.assertRaises(ValueError):audit.audit(p)
 def test_v3_preserved_bundle_with_explicit_current_source_binding(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,plan,c,b=v3.fixture(Path(tmp));cases,_=catalog.load([dict(kind='interactions-v3',directory=str(p),plan=plan)]);self.assertEqual(len(cases),28)
   bad=dict(plan,planned_case_ids=[next(r['case_id'] for r in b['records'] if r['evidence']['admission']!='accepted')])
   with self.assertRaises(ValueError):catalog.load([dict(kind='interactions-v3',directory=str(p),plan=bad)])
 def test_allan_source100_is_distinct_from_supported51(self):
  import hard_corpus_registration as hard
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   for n in ('model.jsonl','gold.jsonl'):(p/n).write_bytes((ROOT/'fixtures/hard-synthetic-v1'/n).read_bytes())
   for n in ('manifest.json','tool-receipts.jsonl'):(p/n).write_bytes((ROOT/'fixtures/hard-registration-qa'/n).read_bytes())
   identity=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest();g,m,eligible=hard.preflight(p,identity)
   plan=dict(version=hard.VERSION,manifest_sha256=identity,selected_ids=list(eligible),arms=['no_tools','csp'],repetitions=1)
   cases,identities=catalog.load([dict(kind='allan-hard-v1',directory=str(p),plan=plan)]);i=identities[0]
   self.assertEqual((len(g),len(cases),i['authored_gold_valid_count'],i['tool_unknown_count']),(100,51,100,49))
   plan['selected_ids']=[next(r['id'] for r in g if r['id'] not in eligible)]
   with self.assertRaises(ValueError):catalog.load([dict(kind='allan-hard-v1',directory=str(p),plan=plan)])
 def test_unknown_kind_and_duplicate_case_across_specs_fail(self):
  s=dict(kind='tier-a-v1',directory=str(ROOT/'fixtures/tier-a-original-synthetic-v1'),plan=tier.plan())
  with self.assertRaises(ValueError):catalog.load([dict(s,kind='unsupported')])
  with self.assertRaises(ValueError):catalog.load([s,s])
