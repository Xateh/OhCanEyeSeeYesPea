"""Fixed strict-v2 offline regression consumer; no credentials or live option."""
from pathlib import Path
import sys,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import strict_benchmark_v1 as consumer
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--out');group.add_argument('--assess')
    args=parser.parse_args()
    result=consumer.assess(args.assess) if args.assess else consumer.run(args.out)
    print(json.dumps({k:result[k] for k in ['version','status','by_arm','validation_strata','stop_reason']},sort_keys=True))
