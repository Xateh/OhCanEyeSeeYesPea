"""Official SDK Responses runner; actual key-file access requires separate explicit flags and approval."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tier_a_contract import strict_json
import responses_sdk_runner as runner
from responses_credentials import load_key_file

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('datasets','config','out'):p.add_argument('--'+name,required=True)
 p.add_argument('--allow-live',action='store_true');p.add_argument('--allow-key-file',action='store_true');p.add_argument('--key-file',default='.env')
 args=p.parse_args()
 def read(path):
  path=Path(path)
  if path.stat().st_size>4*1024*1024:raise ValueError('configuration byte bound')
  return strict_json(path.read_text())
 if not args.allow_live or not args.allow_key_file:raise ValueError('live execution and credential-file access require explicit opt-in and separate authority')
 result=runner.run(read(args.datasets),read(args.config),args.out,allow_live=True,key_loader=lambda:load_key_file(args.key_file))
 print(result['status'])
if __name__=='__main__':main()
