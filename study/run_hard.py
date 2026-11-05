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
from .accounting import attach, validate_budget, cost_summary
from .prompts import prompt_sha256

PROMPT = 'v3'
RESULTS = Path('study/results')
USAGE_LIMIT_WORDS = ('usage limit', 'rate limit', 'limit reached', 'hit your')


def evaluate(case, gold):
    """No tools are offered: the unused adapter only satisfies the harness signature."""
    provider=ClaudeCodeProvider(PROMPT)
    row = attach(run_arm(provider, case['text'], 'no_tools', CSPAdapter()),provider)
    return {**row, 'case_id': case['id'], 'family': gold['family'], 'size': gold['size'], 'label': gold['label'],
            'score': score(gold, row['output'])}


def hit_usage_limit(row):
    return any(word in error['error'].lower() for error in row['errors'] for word in USAGE_LIMIT_WORDS)


def execute(cases, gold, workers, budget_usd, evaluator=evaluate):
    """Run in small groups so the spend limit and any usage limit stop further work quickly."""
    validate_budget(budget_usd,workers)
    rows, spent, position, uncertain = [], 0.0, 0, False
    while position < len(cases) and spent < budget_usd and not uncertain and not any(map(hit_usage_limit, rows)):
        batch = cases[position:position + workers]
        with ThreadPoolExecutor(workers) as pool:
            finished = list(pool.map(lambda c: evaluator(c, gold[c['id']]), batch))
        rows, position = rows + finished, position + len(batch)
        costs=[row_cost(r) for r in finished]
        uncertain=uncertain or any(c is None for c in costs)
        spent += sum(c for c in costs if c is not None)
        print(f'{len(rows)}/{len(cases)} done; cost complete={not uncertain}', flush=True)
    return rows, len(cases) - position, None if uncertain else spent


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
            'skipped': skipped, **cost_summary(rows), 'cost_complete': spent is not None, 'budget_usd': args.budget, 'date': date.today().isoformat(),
            'git_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()}
    (out / 'meta.json').write_text(json.dumps(meta, indent=2, sort_keys=True,allow_nan=False) + '\n')
    cost_label = 'UNKNOWN; scheduling stopped' if spent is None else f'${spent:.2f}'
    print(f"wrote {out}: {len(rows)} done, {skipped} skipped, cost={cost_label}")


if __name__ == '__main__':
    main()
