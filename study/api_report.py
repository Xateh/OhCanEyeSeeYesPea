"""Compare the recorded Claude CLI runs with SDK runs from run_api, under docs/evaluation-framework.md.

Makes no model calls. A comparison is reported only once its SDK cohorts are complete; missing ones are listed.
Usage: python -m study.api_report --provider openai
"""
import argparse
import json

from surgerybench.common import read_jsonl

from .framework import summarize
from .framework_report import HARD_GOLD, PILOT_GOLD, by_arm, counts, load_pilot, number
from .hard_dataset import SIZES
from .ortools_report import PILOT_SPLITS, cohort_rows, hard_claude_alone, ortools_rows, paired
from .report import RESULTS
from .run_api import ARMS, PROVIDERS, folder_for

MEASURES = (('Evidence-backed success', 'evidence_backed_success'), ('Feasible-schedule success', 'feasible_schedule_success'),
            ('Certified-infeasible success', 'certified_infeasible_success'), ('UNKNOWN', 'unknown'),
            ('Parse errors', 'parse_errors'), ('Timeouts', 'timeouts'), ('Provider errors', 'provider_errors'),
            ('Tool or solver errors', 'tool_errors'))
COHORTS = {'pilot': [f'pilot-{s}' for s in PILOT_SPLITS], 'hard': [f'hard-n{size:02d}' for size in SIZES]}
LABELS = {'claude': 'Claude API', 'openai': 'GPT-6 Astra API'}


def api_rows(provider, arm, cohorts, gold):
    """Rows for the cohorts, or why they are not ready yet."""
    missing = [c for c in cohorts if not (folder_for(provider, arm, c) / 'runs.jsonl').exists()]
    if missing:
        return None, missing
    try:
        return [r for c in cohorts for r in cohort_rows(folder_for(provider, arm, c).name, c, gold, ARMS[arm])], []
    except ValueError as error:
        return None, [str(error)]


def cli_rows(pilot_gold, hard_gold):
    """Claude CLI rows: all three pilot splits and the harder set's complete (with reruns) Claude-alone view."""
    recorded = load_pilot(pilot_gold)
    _, alone_hard = hard_claude_alone(hard_gold)
    return {('pilot', 'alone'): [r for s in PILOT_SPLITS for r in by_arm(recorded[s], 'no_tools')],
            ('pilot', 'ortools'): [r for s in PILOT_SPLITS for r in ortools_rows(f'pilot-{s}', pilot_gold)],
            ('hard', 'alone'): [r for size in SIZES for r in alone_hard[size]],
            ('hard', 'ortools'): [r for size in SIZES for r in ortools_rows(f'hard-n{size:02d}', hard_gold)]}


def pairs(first, second, names):
    """paired() tags its first list no_tools and its second csp; rename the buckets for readers."""
    keys = {'both': 'both', 'no_tools_only': f'{names[0]}_only', 'csp_only': f'{names[1]}_only', 'neither': 'neither', 'incomplete': 'incomplete'}
    return {keys[k]: v for k, v in paired(first, second).items()}


def comparison(cli, api, label):
    c, a = summarize(cli), summarize(api)
    lines = [f'| Measure | Claude CLI | {label} |', '|---|--:|--:|']
    lines += [f'| {title} | {counts(c[field])} | {counts(a[field])} |' for title, field in MEASURES]
    lines += [f"| Seconds per case (mean) | {number(c['mean_seconds'], 1)} | {number(a['mean_seconds'], 1)} |",
              f"| Tokens per case (mean) | {number(c['mean_tokens'])} | {number(a['mean_tokens'])} |",
              f"| Estimated cost (USD, known) | {number(c['known_cost_usd'], 2)} | {number(a['known_cost_usd'], 2)} |"]
    return {'claude_cli': c, 'api': a, 'pairs': pairs(cli, api, ('claude_cli', 'api')), 'table': '\n'.join(lines)}


def by_size(rows):
    return {size: summarize([r for r in rows if int(r['size']) == size])['evidence_backed_success'] for size in SIZES}


def report(provider):
    pilot_gold = {g['id']: g for g in read_jsonl(PILOT_GOLD)}
    hard_gold = {g['id']: g for g in read_jsonl(HARD_GOLD)}
    golds = {'pilot': pilot_gold, 'hard': hard_gold}
    compared, api, waiting = {}, {}, {}
    for (dataset, arm), cli in cli_rows(pilot_gold, hard_gold).items():
        rows, missing = api_rows(provider, arm, COHORTS[dataset], golds[dataset])
        if missing:
            waiting[f'{dataset}/{arm}'] = missing
            continue
        api[(dataset, arm)] = rows
        compared[f'{dataset}/{arm}'] = comparison(cli, rows, LABELS[provider])
        if dataset == 'hard':
            compared[f'{dataset}/{arm}']['by_size'] = {'claude_cli': by_size(cli), 'api': by_size(rows)}
    for dataset in COHORTS:
        if (dataset, 'alone') in api and (dataset, 'ortools') in api:
            compared[f'{dataset}/solver_effect'] = pairs(api[(dataset, 'alone')], api[(dataset, 'ortools')], ('alone', 'ortools'))
    return compared, waiting


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=PROVIDERS, default='openai')
    args = parser.parse_args()
    compared, waiting = report(args.provider)
    for name, result in compared.items():
        table = result.pop('table', None)
        print(f'\n### {name}\n\n{table}\n' if table else f'\n### {name}\n')
        print(json.dumps({k: v for k, v in result.items() if k in ('pairs', 'by_size')} if table else result))
    for name, missing in waiting.items():
        print(f'{name}: not ready ({"; ".join(missing)})')
    path = RESULTS / f'api-{args.provider}-vs-claude-cli-summary.json'
    path.write_text(json.dumps({'compared': compared, 'not_ready': waiting}, indent=2, sort_keys=True, default=str) + '\n')
    print(f'\nwrote {path}')


if __name__ == '__main__':
    main()
