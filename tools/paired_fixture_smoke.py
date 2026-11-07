"""Offline software smoke only; no provider credentials, model APIs or research results."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import paired_runner as runner
import tier_a_contract as core
from solver_interface import MergedSolver,LIMITS
from offline_provider_example import OfflineTranslator

def inputs():
 directory=ROOT/'fixtures/tier-a-original-synthetic-v1'
 gold=[core.strict_json(s) for s in (directory/'tier-a-gold.jsonl').read_text().splitlines()]
 plan=dict(contract_version=core.CONTRACT,corpus_version=core.CORPUS,case_use={g['case_id']:'validation_only' if g['certification']=='oracle_only' else 'eligible' for g in gold},repetitions=1,arms=['no_tools','csp'])
 specs=[dict(kind='tier-a-v1',directory=str(directory),plan=plan)]
 settings=dict(version=runner.VERSION,provider_revision=OfflineTranslator.revision,case_ids=[g['case_id'] for g in gold if g['certification']!='oracle_only'],repetitions=1,seed=0,shuffle_cases=False,order='case_then_arm',token_limit=1000,wall_seconds=10,tool_call_limit=4,retry_limit=0,spending_ceiling=1,currency='USD',solver_revision=MergedSolver.revision,solver_limits=LIMITS)
 return specs,settings
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);args=p.parse_args()
 specs,settings=inputs();result=runner.run(specs,settings,args.out,OfflineTranslator)
 print(json.dumps({k:result[k] for k in ('status','by_arm','pairs')},sort_keys=True))
