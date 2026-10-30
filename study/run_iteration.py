"""Run one study iteration: each case once per arm and repetition, stopping at a spend limit."""
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
from functools import partial
import json
from pathlib import Path
import subprocess
import tempfile

from surgerybench.common import canonical, read_jsonl
from surgerybench.temporal_benchmark import run

from .claude_provider import EFFORT, MODEL, ClaudeCodeProvider
from .metrics import row_cost
from .prompts import PROMPTS, prompt_sha256

DATA = Path('fixtures/arrival-deadline-v1')


def run_one(case, gold_row, repetition, factory, scratch):
    """Run the unmodified harness on a one-case dataset so cases can run side by side."""
    folder = Path(tempfile.mkdtemp(dir=scratch))
    model_path, gold_path = folder / 'model.jsonl', folder / 'gold.jsonl'
    model_path.write_text(canonical(case) + '\n')
    gold_path.write_text(canonical(gold_row) + '\n')
    rows = run(model_path, gold_path, folder / 'out.jsonl', factory)
    return [{**row, 'repetition': repetition} for row in rows]


def select_cases(split, limit):
    gold = {g['id']: g for g in read_jsonl(DATA / 'gold.jsonl')}
    chosen = [m for m in read_jsonl(DATA / 'model.jsonl') if gold[m['id']]['split'] == split]
    return (chosen[:limit] if limit else chosen), gold


def execute(work, gold, factory, scratch, workers, budget_usd):
    """Return finished rows plus the planned runs skipped because the budget ran out."""
    rows, pending, queue, spent = [], set(), list(work), 0.0
    with ThreadPoolExecutor(workers) as pool:
        while queue or pending:
            while queue and len(pending) < workers and spent < budget_usd:
                case, repetition = queue.pop(0)
                pending.add(pool.submit(run_one, case, gold[case['id']], repetition, factory, scratch))
            if not pending:
                break
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                new_rows = future.result()
                rows += new_rows
                spent += sum(map(row_cost, new_rows))
                print(f'{len(rows)} arm runs done, ${spent:.2f} spent', flush=True)
    return rows, len(queue), spent


def metadata(args, skipped, spent):
    command = lambda *argv: subprocess.run(argv, capture_output=True, text=True).stdout.strip()
    return {'iteration': args.iteration, 'split': args.split, 'prompt': args.prompt,
            'prompt_sha256': prompt_sha256(args.prompt), 'model': MODEL, 'effort': EFFORT,
            'repetitions': args.repetitions, 'skipped_for_budget': skipped, 'cost_usd': spent,
            'budget_usd': args.budget, 'git_commit': command('git', 'rev-parse', 'HEAD'),
            'claude_cli': command('claude', '--version'), 'date': date.today().isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iteration', required=True)
    parser.add_argument('--split', required=True, choices=('train', 'validation', 'test'))
    parser.add_argument('--prompt', required=True, choices=sorted(PROMPTS))
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--limit', type=int, help='use only the first N cases, for a smoke test')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--budget', type=float, required=True, help='stop starting runs past this many USD')
    args = parser.parse_args()
    out = Path('study/results') / args.iteration
    if out.exists():
        raise SystemExit(f'{out} already exists; results are never overwritten')
    cases, gold = select_cases(args.split, args.limit)
    work = [(case, rep) for rep in range(args.repetitions) for case in cases]
    factory = partial(ClaudeCodeProvider, args.prompt)
    with tempfile.TemporaryDirectory() as scratch:
        rows, skipped, spent = execute(work, gold, factory, scratch, args.workers, args.budget)
    out.mkdir(parents=True)
    ordered = sorted(rows, key=lambda r: (r['case_id'], r['repetition'], r['arm']))
    (out / 'runs.jsonl').write_text(''.join(canonical(r) + '\n' for r in ordered))
    (out / 'meta.json').write_text(json.dumps(metadata(args, skipped, spent), indent=2, sort_keys=True) + '\n')
    print(f'wrote {out}: {len(rows)} arm runs, {skipped} skipped, ${spent:.2f}')


if __name__ == '__main__':
    main()
