"""Apply the shared evaluation framework to recorded Claude runs. Makes no model calls. Charts need matplotlib."""
import json
from pathlib import Path

from surgerybench.common import read_jsonl

from .framework import csp_on_gold, failure_split, require_planned, rescore, summarize, expected_slots
from .hard_dataset import SIZES
from .metrics import paired_buckets, theme_of
from .report import FIGURES, INK, MUTED, RESULTS, SURFACE, tune

PILOT_GOLD = Path('fixtures/arrival-deadline-v1/gold.jsonl')
HARD_GOLD = Path('fixtures/hard-synthetic-v1/gold.jsonl')
SPLITS = {'train': ('03-train-format-example-v3', 32), 'validation': ('04-validation-v3', 8), 'test': ('05-test-v3', 24)}
PROMPT_RUNS = {'v1': ('01-train-baseline-v1', 32), 'v2': ('02-train-required-tool-v2', 32), 'v3': ('03-train-format-example-v3', 32)}
HARD_RUNS_PER_SIZE = 20
HARD_PRIMARY = {5:'hard-n05',10:'hard-n10',20:'hard-n20',40:'hard-n40-partial-usage-limit',80:'hard-n80-all-usage-limit-failures'}
HARD_RERUNS = {40:'hard-n40',80:'hard-n80'}
LABELS = {'no_tools': 'LLM-only', 'csp': 'LLM+CSP'}
COLORS = {'no_tools': '#2a78d6', 'csp': '#eb6834'}
ROWS = (('Evidence-backed success', 'evidence_backed_success'), ('Feasible-schedule success', 'feasible_schedule_success'),
        ('Certified-infeasible success', 'certified_infeasible_success'), ('Infeasible decision (diagnostic)', 'infeasible_decision'),
        ('Status agreement', 'status_agreement'), ('UNKNOWN', 'unknown'), ('Parse errors', 'parse_errors'),
        ('Timeouts', 'timeouts'), ('Provider errors', 'provider_errors'), ('Tool or solver errors', 'tool_errors'))


def counts(values):
    return f'{values[0]}/{values[1]}'


def number(value, digits=0):
    return 'not reported' if value is None else f'{value:,.{digits}f}'


def pilot_rows(gold, folder, planned):
    meta=json.loads((RESULTS / folder / 'meta.json').read_text())
    ids=[g['id'] for g in gold.values() if g['split']==meta['split']]
    expected=expected_slots(ids,('no_tools','csp'),meta['repetitions'])
    return require_planned(rescore(read_jsonl(RESULTS / folder / 'runs.jsonl'), gold), planned * 2,expected)


def by_arm(rows, arm):
    return [r for r in rows if r['arm'] == arm]


def load_pilot(gold):
    return {split: pilot_rows(gold, folder, planned) for split, (folder, planned) in SPLITS.items()}


def load_hard_cohort(gold, folders):
    result={}
    for size,folder in folders.items():
        ids=[g['id'] for g in gold.values() if g['size']==size]
        expected=expected_slots(ids,('no_tools',),1)
        result[size]=require_planned(rescore(read_jsonl(RESULTS/folder/'runs.jsonl'),gold),HARD_RUNS_PER_SIZE,expected)
    return result


def load_hard(gold):
    """First recorded full planned cohorts; provider failures remain primary rows."""
    return load_hard_cohort(gold,HARD_PRIMARY)


def load_hard_reruns(gold):
    """Explicit separate rerun cohorts, never replacements or best-of selection."""
    return load_hard_cohort(gold,HARD_RERUNS)


def method_table(columns):
    names = list(columns)
    lines = ['| Measure | ' + ' | '.join(names) + ' |', '|---|' + '--:|' * len(names)]
    lines += [f'| {title} | ' + ' | '.join(counts(columns[name][field]) for name in names) + ' |' for title, field in ROWS]
    lines.append('| Seconds per case (mean) | ' + ' | '.join(number(columns[name]['mean_seconds'], 4 if name == 'CSP-on-gold' else 1) for name in names) + ' |')
    lines.append('| Tokens per case (mean) | ' + ' | '.join(number(columns[name]['mean_tokens']) for name in names) + ' |')
    return '\n'.join(lines)


def split_table(pilot):
    lines = ['| Split | Runs per approach | LLM-only success | LLM+CSP success | Both | LLM-only only | LLM+CSP only | Neither | Incomplete |',
             '|---|--:|--:|--:|--:|--:|--:|--:|--:|']
    for split, rows in pilot.items():
        buckets = paired_buckets(rows)
        lines.append(f"| {split} | {len(by_arm(rows, 'csp'))} | {counts(summarize(by_arm(rows, 'no_tools'))['evidence_backed_success'])} "
                     f"| {counts(summarize(by_arm(rows, 'csp'))['evidence_backed_success'])} | {buckets['both']} | {buckets['no_tools_only']} "
                     f"| {buckets['csp_only']} | {buckets['neither']} | {buckets['incomplete']} |")
    return '\n'.join(lines)


def hard_table(hard):
    lines = ['| Surgeries | Evidence-backed success | Feasible-schedule | Certified-infeasible | Status agreement | UNKNOWN | Parse errors | Timeouts | Seconds per case (mean) | Tokens per case (mean) |',
             '|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|']
    for size, rows in {**hard, 'All': [r for rows in hard.values() for r in rows]}.items():
        s = summarize(rows)
        lines.append(f"| {size} | {counts(s['evidence_backed_success'])} | {counts(s['feasible_schedule_success'])} "
                     f"| {counts(s['certified_infeasible_success'])} | {counts(s['status_agreement'])} | {counts(s['unknown'])} "
                     f"| {counts(s['parse_errors'])} | {counts(s['timeouts'])} | {s['mean_seconds']:.1f} | {number(s['mean_tokens'])} |")
    return '\n'.join(lines)


def prompt_table(gold):
    lines = ['| Prompt | LLM+CSP success | Solver actually called | Parse or format failures | Tool errors |', '|---|--:|--:|--:|--:|']
    for prompt, (folder, planned) in PROMPT_RUNS.items():
        rows = by_arm(pilot_rows(gold, folder, planned), 'csp')
        s = summarize(rows)
        used = sum(r['tool_call_count'] > 0 for r in rows)
        lines.append(f"| {prompt} | {counts(s['evidence_backed_success'])} | {used}/{planned} | {counts(s['parse_errors'])} | {counts(s['tool_errors'])} |")
    return '\n'.join(lines)


def extra_lines(pilot, pilot_gold):
    themes = {}
    for arm in LABELS:
        for row in by_arm(pilot['test'], arm):
            themes.setdefault(theme_of(row), {}).setdefault(arm, []).append(row)
    return {'test_csp_failure_split': failure_split(by_arm(pilot['test'], 'csp'), pilot_gold),
            'test_by_theme': {theme: {LABELS[arm]: summarize(rows)['evidence_backed_success'] for arm, rows in arms.items()}
                              for theme, arms in sorted(themes.items())}}


def chart_cost(plt, columns):
    figure, axes = plt.subplots(1, 2, figsize=(8, 3.4))
    panels = (('mean_seconds', 'Seconds per case', '{:.1f}s'), ('mean_tokens', 'Tokens per case', '{:,.0f}'))
    for axis, (field, title, shape) in zip(axes, panels):
        for x, (arm, name) in enumerate(LABELS.items()):
            value = columns[name][field]
            if value is None:
                axis.text(x, 0, 'not reported', ha='center', va='bottom', color=INK, fontsize=9)
                continue
            axis.bar(x, value, width=0.5, color=COLORS[arm], edgecolor=SURFACE, linewidth=2)
            axis.text(x, value, shape.format(value), ha='center', va='bottom', color=INK, fontsize=9)
        tune(axis)
        axis.set_xticks(range(len(LABELS)), LABELS.values())
        axis.set_title(title, loc='left', color=MUTED, fontsize=10)
    figure.suptitle('Time and token usage per case (not monetary spending)', x=0.01, ha='left', color=INK, fontsize=12)
    figure.tight_layout()
    return figure


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pilot_gold_rows = read_jsonl(PILOT_GOLD)
    pilot_gold = {g['id']: g for g in pilot_gold_rows}
    hard_gold = {g['id']: g for g in read_jsonl(HARD_GOLD)}
    pilot, hard = load_pilot(pilot_gold), load_hard(hard_gold)
    test_gold = [g for g in pilot_gold_rows if g['split'] == 'test']
    test_columns = {'LLM-only': summarize(by_arm(pilot['test'], 'no_tools')), 'LLM+CSP': summarize(by_arm(pilot['test'], 'csp')),
                    'CSP-on-gold': summarize(csp_on_gold(test_gold))}
    all_hard = [r for rows in hard.values() for r in rows]
    extras = extra_lines(pilot, pilot_gold)
    summary = {'pilot_test': test_columns, 'pilot_all_gold_csp': summarize(csp_on_gold(pilot_gold_rows)),
               'pilot_splits': {split: {LABELS[arm]: summarize(by_arm(rows, arm)) for arm in LABELS} for split, rows in pilot.items()},
               'hard': {**{str(size): summarize(rows) for size, rows in hard.items()}, 'all': summarize(all_hard)}, **extras}
    summary['hard_reruns_separate']={str(size):summarize(rows) for size,rows in load_hard_reruns(hard_gold).items()}
    destination=RESULTS/'framework-summary-v2.json'
    if destination.exists():raise FileExistsError('preserve prior report revision')
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True,allow_nan=False) + '\n')
    chart_cost(plt, test_columns).savefig(FIGURES / 'framework-cost-v2.png', dpi=200, bbox_inches='tight', facecolor=SURFACE)
    print(method_table(test_columns), split_table(pilot), 'First recorded planned cohorts:', hard_table(hard), 'Separate reruns (not replacement primary rows):', hard_table(load_hard_reruns(hard_gold)), prompt_table(pilot_gold), sep='\n\n')
    print(json.dumps({'hard': {k: summary['hard']['all'][k] for k in ('f1', 'evidence_precision', 'feasible_claim_precision', 'runs_with_tokens', 'estimated_cost_usd', 'outcomes')},
                      'test_llm_only': {k: test_columns['LLM-only'][k] for k in ('f1', 'median_seconds', 'estimated_cost_usd')},
                      'test_llm_csp': {k: test_columns['LLM+CSP'][k] for k in ('f1', 'mean_csp_calls', 'mean_solver_seconds', 'median_seconds', 'estimated_cost_usd')},
                      'all_48_csp_on_gold': summary['pilot_all_gold_csp']['evidence_backed_success'], **extras}, indent=1))


if __name__ == '__main__':
    main()
