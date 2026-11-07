"""Explicit version-specific catalog; no automatic corpus mixing or gold in payloads."""
from copy import deepcopy
from pathlib import Path
import hashlib,stat
import tier_a_contract as tier
from tier_a_input_view import derive
from solver_interface import require
VERSION='paired-dataset-catalog-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(specs):
 require(type(specs) is list and 1<=len(specs)<=8,'explicit bounded dataset list')
 cases=[];identities=[]
 for spec in specs:
  require(type(spec) is dict and set(spec)=={'kind','directory','plan'},'dataset spec fields')
  kind=spec['kind'];directory=spec['directory'];plan=spec['plan'];require(type(directory) is str,'dataset directory path')
  if kind=='tier-a-v1':
   d=Path(directory);require(not d.is_symlink() and {x.name for x in d.iterdir()}==set(tier.HASHES),'Tier A exact file set')
   for n in tier.HASHES:
    p=d/n;s=p.lstat();require(stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_size<=2*1024*1024,'Tier A bounded regular files')
   gold,model=tier.preflight(directory,plan);source=[(g,m['text'],g['label']) for g,m in zip(gold,model) if g['certification']!='oracle_only']
   selected=[dict(case_id=g['case_id'],family=g['family'],label=label,instance=g['instance'],text=derive(t),evidence=g['evidence']) for g,t,label in source]
   identity=dict(kind=kind,version=tier.CORPUS,manifest_sha256=sha(d/'manifest.json'),selected_ids=[g['case_id'] for g in selected],repetitions=plan['repetitions'])
  elif kind=='seeded-v2':
   import development_registration as r
   gold,texts,report=r.preflight(directory,plan)
   selected=[dict(case_id=g['case_id'],family=g.get('suite',g.get('construction_group','related-development')),label=g['gold_label'],instance=g['instance'],text=t,evidence={'witness':g.get('witness'),'certificate':g.get('certificate')}) for g,t in zip(gold,texts)]
   identity=dict(kind=kind,version=plan['corpus_version'],manifest_sha256=plan['manifest_sha256'],selected_ids=plan['planned_case_ids'],repetitions=plan['repetitions'])
  elif kind=='interactions-v3':
   import development_v3_registration as r
   gold=r.preflight(directory,plan)
   selected=[dict(case_id=g['case_id'],family=g['family']+'/'+str(g['base']),label=g['evidence']['gold_label'],instance=g['instance'],text=g['evidence']['text'],evidence=g['evidence']) for g in gold]
   identity=dict(kind=kind,version=plan['corpus_version'],manifest_sha256=plan['manifest_sha256'],selected_ids=plan['planned_case_ids'],repetitions=plan['repetitions'])
  elif kind=='allan-hard-v1':
   import hard_corpus_registration as r
   require(type(plan) is dict and set(plan)=={'version','manifest_sha256','selected_ids','arms','repetitions'},'hard plan fields')
   gold,model,eligible=r.preflight(directory,plan['manifest_sha256']);r.prepare(directory,plan['manifest_sha256'],plan)
   lookup={g['id']:(g,m) for g,m in zip(gold,model)}
   selected=[dict(case_id=i,family=lookup[i][0]['family'],label=lookup[i][0]['label'],instance=lookup[i][0]['instance'],text=r.view(lookup[i][0]['instance'],lookup[i][1]['text']),evidence=lookup[i][0]['evidence']) for i in plan['selected_ids']]
   identity=dict(kind=kind,version=r.VERSION,manifest_sha256=plan['manifest_sha256'],selected_ids=plan['selected_ids'],repetitions=plan['repetitions'],source_case_count=100,authored_gold_valid_count=100,tool_supported_count=len(eligible),tool_unknown_count=100-len(eligible),selection_policy='checked-authored-proof-and-actual-tool-supported-evidence-v1')
  else:raise ValueError('unsupported explicit dataset registration')
  for g in selected:
   require(type(g['text']) is str and len(g['text'].encode())<=500000,'bounded case text')
   g['dataset_identity']=deepcopy(identity);g['family']=kind+'/'+g['family'];cases.append(deepcopy(g))
  identities.append(deepcopy(identity))
 require(0<len(cases)<=512 and len({g['case_id'] for g in cases})==len(cases),'bounded globally unique selected IDs')
 return cases,identities
