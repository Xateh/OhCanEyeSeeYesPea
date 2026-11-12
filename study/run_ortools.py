"""Run Claude with the OR-Tools solver on the same slots as the recorded Claude-alone runs. Needs ortools.

Rows are saved as they finish. Calling again runs only slots never attempted: a failed attempt stays recorded,
so it still counts in the framework's denominator. New work stops at the spend limit, a usage limit or an
unknown cost.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
import subprocess

from surgerybench.common import canonical, read_jsonl
from surgerybench.temporal_benchmark import run_arm, score

from .accounting import attach, row_cost, validate_budget
from .claude_provider import EFFORT, MODEL, ClaudeCodeProvider
from .hard_dataset import OUTPUT as HARD_DATA
from .prompts import prompt_sha256
from .run_hard import RESULTS, hit_usage_limit

PROMPT = 'v3'
PILOT_DATA = Path('fixtures/arrival-deadline-v1')
COHORTS = {'pilot-train': (PILOT_DATA, 'split', 'train', 1), 'pilot-validation': (PILOT_DATA, 'split', 'validation', 1),
           'pilot-test': (PILOT_DATA, 'split', 'test', 3),
           **{f'hard-n{size:02d}': (HARD_DATA, 'size', size, 1) for size in (5, 10, 20, 40, 80)}}


def load(name):
    folder, field, value, repetitions = COHORTS[name]
    gold = {g['id']: g for g in read_jsonl(folder / 'gold.jsonl')}
    cases = [m for m in read_jsonl(folder / 'model.jsonl') if str(gold[m['id']][field]) == str(value)]
    return [(case, rep) for rep in range(repetitions) for case in cases], gold


def planned_slots(name):
    return load(name)[0]


def evaluate(case, gold, repetition):
    from .ortools_solver import REVISION, ORToolsAdapter
    provider = ClaudeCodeProvider(PROMPT)
    row = attach(run_arm(provider, case['text'], 'csp', ORToolsAdapter()), provider)
    return {**row, 'case_id': case['id'], 'repetition': repetition, 'arm': 'csp', 'family': gold['family'], 'label': gold['label'],
            'split': gold.get('split'), 'size': gold.get('size'), 'model_revision': provider.model_revision,
            'tool_revision': REVISION, 'score': score(gold, row['output'])}


def attempted(path):
    return {(r['case_id'], r['repetition']) for r in read_jsonl(path)} if path.exists() else set()


def execute(name, folder, budget_usd, workers, evaluator=evaluate, limit=None):
    """Return how many planned slots remain, the known spend and why work stopped."""
    validate_budget(budget_usd, workers)
    slots, gold = load(name)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'runs.jsonl'
    done = attempted(path)
    todo = [(case, rep) for case, rep in slots if (case['id'], rep) not in done][:limit]
    spent, position, reason = 0.0, 0, 'finished'
    while position < len(todo):
        batch = todo[position:position + workers]
        with ThreadPoolExecutor(workers) as pool:
            rows = list(pool.map(lambda slot: evaluator(slot[0], gold[slot[0]['id']], slot[1]), batch))
        with path.open('a') as handle:
            handle.writelines(canonical(row) + '\n' for row in rows)
        position += len(batch)
        costs = [row_cost(row) for row in rows]
        spent += sum(cost for cost in costs if cost is not None)
        print(f'{name}: {len(done) + position}/{len(slots)} attempted, ~${spent:.2f} this session', flush=True)
        if any(map(hit_usage_limit, rows)):
            reason = 'usage_limit'
        elif any(cost is None for cost in costs):
            reason = 'unknown_cost'
        elif spent >= budget_usd:
            reason = 'spend_limit'
        if reason != 'finished':
            break
    return len(slots) - len(done) - position, spent, reason


def record_session(folder, name, budget_usd, remaining, spent, reason, setup=None):
    """Append one session to meta.json; setup describes the run the first time and defaults to Claude + OR-Tools."""
    if setup is None:
        from .ortools_solver import REVISION
        setup = {'arm': 'csp', 'solver': REVISION}
    meta_path = folder / 'meta.json'
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {
        'cohort': name, 'model': MODEL, 'effort': EFFORT, 'prompt': PROMPT,
        'prompt_sha256': prompt_sha256(PROMPT), **setup, 'sessions': []}
    session = {'finished_at': datetime.now().isoformat(timespec='seconds'), 'budget_usd': budget_usd, 'known_spend_usd': spent,
               'stopped_because': reason, 'remaining_slots': remaining,
               'git_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}
    meta_path.write_text(json.dumps({**meta, 'sessions': [*meta['sessions'], session]}, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=sorted(COHORTS), required=True)
    parser.add_argument('--budget', type=float, required=True, help='stop new work past this estimated USD')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    folder = RESULTS / f'ortools-{args.cohort}'
    remaining, spent, reason = execute(args.cohort, folder, args.budget, args.workers)
    record_session(folder, args.cohort, args.budget, remaining, spent, reason)
    print(f'{folder}: stopped because {reason}; {remaining} slots left; ~${spent:.2f}')


if __name__ == '__main__':
    main()
