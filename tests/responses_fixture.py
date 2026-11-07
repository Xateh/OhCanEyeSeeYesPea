"""Test-only path binding. Production registration/protocol guards are unchanged."""
from pathlib import Path
import json,tempfile,atexit,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]/'fixtures/responses-offline-v1'
_STATE=None
def configure():
 global _STATE
 if _STATE is not None:return _STATE
 for n,h in json.loads((ROOT/'fixture-hashes.json').read_text()).items():
  if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h:raise ValueError('offline fixture hash drift')
 import responses_calibration_runner as r,responses_handoff_runner as h,responses_sdk_runner as sdk
 import responses_calibration_transport as api,development_registration as registration
 import handoff_comparison as comparison,schema_final_replay as replay
 directory=ROOT/'seeded-v2'
 for module in [r,h,sdk]:module.DIRECTORY=str(directory)
 temp=Path(tempfile.mkdtemp(prefix='responses-offline-'));atexit.register(shutil.rmtree,temp,ignore_errors=True)
 specs=json.loads((ROOT/'datasets.json').read_text());specs[0]['directory']=str(directory);specs[0]['plan']['consumer_sha256']=hashlib.sha256(Path(registration.__file__).read_bytes()).hexdigest()
 (temp/'datasets.json').write_text(json.dumps(specs))
 for name in ['settings.json','settings-final.json']:
  c=json.loads((ROOT/name).read_text());b=c['provider_binding'];c['provider_binding']=api.binding(*(b[k] for k in ['model','expected_model','profile','reasoning_effort','max_output_tokens','call_wall_seconds','call_budget_usd','rates']));(temp/name).write_text(json.dumps(c))
 (temp/'run').mkdir();(temp/'run/attempts.jsonl').write_bytes((ROOT/'abstention-projection.jsonl').read_bytes())
 comparison.PRIOR=temp
 replay.PRIOR=ROOT;replay.RECEIPT_SHA=hashlib.sha256((ROOT/'handoff-request-projection.jsonl').read_bytes()).hexdigest()
 # Match replay's existing relative filename, without changing its frozen source.
 holder=temp/'replay';(holder/'run').mkdir(parents=True);(holder/'run/attempts.jsonl').write_bytes((ROOT/'handoff-request-projection.jsonl').read_bytes());replay.PRIOR=holder
 _STATE=temp;return temp
