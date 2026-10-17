"""Reproduce the approved pilot using only files in this checkout, offline."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from surgerybench.common import canonical, read_jsonl, revision
from surgerybench.temporal_dataset import build, audit
from surgerybench.temporal_benchmark import run

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures/arrival-deadline-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def semantic_record(record):
    """Only build identity can change when packaging imports or Python changes."""
    result = deepcopy(record)
    result.pop('id')
    result['lineage'].pop('code_revision')
    result['lineage'].pop('python')
    return result


def verify():
    report = {'status': 'PASS', 'python_version': platform.python_version(),
              'package_code_revision': revision(), 'real_llm_runs': 0}
    report['fixture_audit'] = audit(FIXTURES)
    before = hashes(FIXTURES)
    with tempfile.TemporaryDirectory(prefix='cs3263-package-') as tmp:
        tmp = Path(tmp)
        a, b = tmp/'generated', tmp/'replayed'
        build(a); build(b)
        report['generated_audit'] = audit(a)
        report['replay_audit'] = audit(b)
        require(hashes(a) == hashes(b), 'current-build byte reproducibility failed')
        original = read_jsonl(FIXTURES/'gold.jsonl')
        generated = read_jsonl(a/'gold.jsonl')
        require([semantic_record(r) for r in original] == [semantic_record(r) for r in generated],
                'regenerated semantics or provenance differ beyond build identity')
        require([r['text'] for r in read_jsonl(FIXTURES/'model.jsonl')] ==
                [r['text'] for r in read_jsonl(a/'model.jsonl')], 'model texts changed')
        families = defaultdict(list)
        for row in original:
            families[row['family']].append(row)
        for pair in families.values():
            require(len(pair) == 2 and len({r['split'] for r in pair}) == 1, 'family split/count mismatch')
            feasible = next(r for r in pair if r['label'] == 'FEASIBLE')
            infeasible = next(r for r in pair if r['label'] == 'INFEASIBLE')
            expected = deepcopy(feasible['instance']); expected['patients'][1]['due'] -= 1
            require(expected == infeasible['instance'], 'counterfactual not a one-minute deadline change')
        rows = run(FIXTURES/'model.jsonl', FIXTURES/'gold.jsonl', tmp/'smoke.jsonl')
        require(len(rows) == 96, 'wrong smoke count')
        pairs = defaultdict(list)
        for row in rows:
            pairs[row['case_id']].append(row)
        require(len(pairs) == 48, 'wrong pair count')
        for pair in pairs.values():
            require(len(pair)==2 and {r['arm'] for r in pair}=={'no_tools','csp'}, 'missing arm')
            require(len({r['text_sha256'] for r in pair})==1, 'arm inputs differ')
            require(len({r['model_revision'] for r in pair})==1, 'arm models differ')
        assisted = [r for r in rows if r['arm']=='csp']
        baseline = [r for r in rows if r['arm']=='no_tools']
        require(all(r['score']['valid'] and r['tool_call_count']==1 for r in assisted), 'invalid CSP result')
        require(all(r['score']['unknown'] and r['tool_call_count']==0 for r in baseline), 'no-tools contract')
        require(not any(r['errors'] for r in rows), 'provider/tool errors')
        report['smoke'] = {'pairs':48,'arm_runs':96,'csp_valid':48,
                           'csp_feasible_schedules':24,'csp_verified_infeasible':24,
                           'no_tools_unknown':48,'tool_calls':48,
                           'provider_parse_errors':0,'tool_errors':0,
                           'model_revision':rows[0]['model_revision']}
        # Production checks must survive optimized Python.
        corrupt = tmp/'corrupt'; corrupt.mkdir()
        for p in FIXTURES.iterdir(): (corrupt/p.name).write_bytes(p.read_bytes())
        (corrupt/'model.jsonl').write_text((corrupt/'model.jsonl').read_text()+'\n')
        proc = subprocess.run([sys.executable,'-O','-m','surgerybench.temporal_dataset',str(corrupt),'--audit'],cwd=ROOT,capture_output=True,text=True)
        require(proc.returncode != 0, 'optimized audit accepted corrupt data')
    require(before == hashes(FIXTURES), 'fixture bytes modified')
    report.update({'fixture_bytes_preserved':True,'regeneration_semantics_identical':True,
                   'regeneration_text_identical':True,'current_build_replay_byte_identical':True,
                   'minimal_counterfactual_pairs_checked':24,'optimized_corruption_rejected':True,
                   'fixture_manifest_sha256':hashlib.sha256((FIXTURES/'manifest.json').read_bytes()).hexdigest()})
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out'); args=parser.parse_args()
    if args.out and Path(args.out).exists(): raise FileExistsError('preserve existing evidence')
    result=verify()
    if args.out:
        out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(canonical(result))
