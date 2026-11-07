"""Explicit paired plan execution. Defaults cannot call a provider; no credentials read here."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tier_a_contract import strict_json
import paired_runner as runner
from offline_provider_example import OfflineTranslator

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--datasets',required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
 p.add_argument('--allow-live',action='store_true',help='separate opt-in; not research authorization')
 args=p.parse_args()
 def read(name):
  path=Path(name)
  if path.stat().st_size>4*1024*1024:raise ValueError('configuration byte bound')
  return strict_json(path.read_text())
 settings=read(args.config);specs=read(args.datasets)
 factory=OfflineTranslator if settings.get('execution_mode','fixture')=='fixture' else None
 result=runner.run(specs,settings,args.out,factory,allow_live=args.allow_live)
 print(result['status'])
if __name__=='__main__':main()
