"""Evaluate Claude alone on one size of the harder dataset, with no solver and a spend limit."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path
import subprocess

from surgerybench.common import canonical, read_jsonl
from surgerybench.temporal_benchmark import run_arm, score
from surgerybench.temporal_csp import CSPAdapter

from .claude_provider import EFFORT, MODEL, ClaudeCodeProvider
from .hard_dataset import OUTPUT
from .metrics import row_cost
from .prompts import prompt_sha256

PROMPT = 'v3'
RESULTS = Path('study/results')
USAGE_LIMIT_WORDS = ('usage limit', 'rate limit', 'limit reached', "hit your limit")


def evaluate(case, gold):
    """No tools are offered: the unused adapter only satisfies the harness signature."""
    row = run_arm(ClaudeCodeProvider(PROMPT), case['text'], 'no_tools', CSPAdapter())
    return {**row, 'case_id': case['id'], 'family': gold['family'], 'size': gold['size'], 'label': gold['label'],
            'score': score(gold, row['output'])}


def hit_usage_limit(row):
    return any(word in error['error'].lower() for error in row['errors'] for word in USAGE_LIMIT_WORDS)


def execute(cases, gold, workers, budget_usd, evaluator=evaluate):
    """Run in small groups so the spend limit and any usage limit stop further work quickly."""
    rows, spent, position = [], 0.0, 0
    while position < len(cases) and spent < budget_usd and not any(map(hit_usage_limit, rows)):
        batch = cases[position:position + workers]
        with ThreadPoolExecutor(workers) as pool:
            finished = list(pool.map(lambda c: evaluator(c, gold[c['id']]), batch))
        rows, position = rows + finished, position + len(batch)
        spent += sum(map(row_cost, finished))
        print(f'{len(rows)}/{len(cases)} done, ~${spent:.2f}', flush=True)
    return rows, len(cases) - position, spent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, required=True)
    parser.add_argument('--budget', type=float, required=True, help='stop past this estimated USD')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    out = RESULTS / f'hard-n{args.size:02d}'
    if out.exists():
        raise SystemExit(f'{out} already exists; results are never overwritten')
    gold = {g['id']: g for g in read_jsonl(OUTPUT / 'gold.jsonl')}
    cases = [m for m in read_jsonl(OUTPUT / 'model.jsonl') if gold[m['id']]['size'] == args.size]
    rows, skipped, spent = execute(cases, gold, args.workers, args.budget)
    out.mkdir(parents=True)
    (out / 'runs.jsonl').write_text(''.join(canonical(r) + '\n' for r in sorted(rows, key=lambda r: r['case_id'])))
    meta = {'size': args.size, 'model': MODEL, 'effort': EFFORT, 'prompt': PROMPT, 'prompt_sha256': prompt_sha256(PROMPT),
            'skipped': skipped, 'cost_usd': spent, 'budget_usd': args.budget, 'date': date.today().isoformat(),
            'git_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}
    (out / 'meta.json').write_text(json.dumps(meta, indent=2, sort_keys=True) + '\n')
    print(f'wrote {out}: {len(rows)} done, {skipped} skipped, ~${spent:.2f}')


if __name__ == '__main__':
    main()
