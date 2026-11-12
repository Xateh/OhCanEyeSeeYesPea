"""Explicit direct API/fixture execution; no implicit credential or network access."""
from pathlib import Path
import sys,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import direct_benchmark as direct

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--config');p.add_argument('--datasets');p.add_argument('--demo',action='store_true');p.add_argument('--out');p.add_argument('--assess')
 p.add_argument('--prepare-datasets');p.add_argument('--write-spec')
 p.add_argument('--allow-live',action='store_true');p.add_argument('--allow-key-file',action='store_true');p.add_argument('--key-file')
 a=p.parse_args()
 if a.prepare_datasets or a.write_spec:
  if not (a.prepare_datasets and a.write_spec) or any([a.config,a.datasets,a.demo,a.out,a.assess,a.allow_live,a.allow_key_file,a.key_file]):p.error('prepare takes only --prepare-datasets DIRECTORY --write-spec NEW.json')
  specs=direct.dataset_specs(a.prepare_datasets);direct.catalog.load(specs)
  with Path(a.write_spec).open('x') as stream:json.dump(specs,stream,sort_keys=True);stream.write('\n')
  print('Wrote fixed four-case dataset registration');return
 if a.assess:
  if any([a.config,a.datasets,a.demo,a.out,a.allow_live,a.allow_key_file,a.key_file]):p.error('assessment takes only --assess')
  result=direct.assess(a.assess)
 else:
  if not a.config or not a.out or bool(a.datasets)==bool(a.demo):p.error('require --config, --out and exactly one of --datasets/--demo')
  c=direct.config(json.loads(Path(a.config).read_text()))
  if a.demo and c['mode']!='mock':p.error('--demo is offline only')
  if c['mode']=='live' and not (a.allow_live and a.allow_key_file and a.key_file):p.error('live mode requires both explicit opt-ins and a key file')
  if c['mode']=='mock' and any([a.allow_live,a.allow_key_file,a.key_file]):p.error('mock mode never reads a key')
  specs=direct.demo_specs() if a.demo else json.loads(Path(a.datasets).read_text())
  result=direct.run(specs,c,a.out,allow_live=a.allow_live and a.allow_key_file,key_file=a.key_file)
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
