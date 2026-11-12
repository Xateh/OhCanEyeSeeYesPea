"""Score Claude alone, Claude + OR-Tools and OR-Tools on gold under docs/evaluation-framework.md.

Makes no model calls. Needs ortools for the solver-on-gold columns and matplotlib for the charts.
"""
import json

from surgerybench.common import read_jsonl

from .framework import csp_on_gold, expected_slots, failure_split, require_planned, rescore, summarize
from .framework_report import HARD_GOLD, HARD_PRIMARY, HARD_RERUNS, PILOT_GOLD, by_arm, counts, load_hard_cohort, load_pilot, number
from .hard_dataset import SIZES
from .metrics import paired_buckets
from .report import FIGURES, INK, MUTED, RESULTS, SURFACE, tune
from .run_ortools import COHORTS

PILOT_SPLITS = ('train', 'validation', 'test')
COLORS = {'Claude alone': '#2a78d6', 'Claude alone (with reruns)': '#2a78d6', 'Claude + OR-Tools': '#eb6834'}
ROWS = (('Evidence-backed success', 'evidence_backed_success'), ('Feasible-schedule success', 'feasible_schedule_success'),
        ('Certified-infeasible success', 'certified_infeasible_success'), ('Status agreement', 'status_agreement'),
        ('UNKNOWN', 'unknown'), ('Parse errors', 'parse_errors'), ('Timeouts', 'timeouts'),
        ('Provider errors', 'provider_errors'), ('Tool or solver errors', 'tool_errors'))


def paired(alone, with_solver):
    """Pair two arms on (case, repetition) without changing either list. Older single-run receipts are repetition 0."""
    tag = lambda rows, arm: [{**r, 'repetition': r.get('repetition', 0), 'arm': arm} for r in rows]
    return paired_buckets(tag(alone, 'no_tools') + tag(with_solver, 'csp'))


def cohort_rows(folder, cohort, gold, arm='csp'):
    """Re-scored rows of one runner folder, refusing to report until every planned slot is present."""
    _, field, value, repetitions = COHORTS[cohort]
    rows = rescore(read_jsonl(RESULTS / folder / 'runs.jsonl'), gold)
    ids = sorted(g['id'] for g in gold.values() if str(g[field]) == str(value))
    return require_planned(rows, len(ids) * repetitions, expected_slots(ids, (arm,), repetitions))


def ortools_rows(cohort, gold):
    return cohort_rows(f'ortools-{cohort}', cohort, gold)


def hard_claude_alone(gold):
    """First attempts are the framework's primary view; the rerun view swaps in the later complete 40/80 runs."""
    first = load_hard_cohort(gold, HARD_PRIMARY)
    return first, {**first, **load_hard_cohort(gold, HARD_RERUNS)}


def method_table(columns):
    names = list(columns)
    lines = ['| Measure | ' + ' | '.join(names) + ' |', '|---|' + '--:|' * len(names)]
    lines += [f'| {title} | ' + ' | '.join(counts(columns[n][field]) for n in names) + ' |' for title, field in ROWS]
    lines.append('| Seconds per case (mean) | ' + ' | '.join(number(columns[n]['mean_seconds'], 2) for n in names) + ' |')
    lines.append('| Tokens per case (mean) | ' + ' | '.join(number(columns[n]['mean_tokens']) for n in names) + ' |')
    lines.append('| Estimated cost (USD, known) | ' + ' | '.join(number(columns[n]['known_cost_usd'], 2) for n in names) + ' |')
    return '\n'.join(lines)


def size_table(alone_first, alone_rerun, with_solver, solver_gold):
    lines = ['| Surgeries | Claude alone, first attempt | Claude alone, with reruns | Claude + OR-Tools | OR-Tools on gold | '
             'Seconds: alone / + OR-Tools | Tokens: alone / + OR-Tools |', '|--:|--:|--:|--:|--:|--:|--:|']
    for size in SIZES:
        a, r, o, g = (summarize(x[size]) for x in (alone_first, alone_rerun, with_solver, solver_gold))
        lines.append(f"| {size} | {counts(a['evidence_backed_success'])} | {counts(r['evidence_backed_success'])} "
                     f"| {counts(o['evidence_backed_success'])} | {counts(g['evidence_backed_success'])} "
                     f"| {r['mean_seconds']:.0f} / {o['mean_seconds']:.0f} | {number(r['mean_tokens'])} / {number(o['mean_tokens'])} |")
    return '\n'.join(lines)


def chart_success(plt, alone, with_solver):
    figure, axis = plt.subplots(figsize=(8, 3.6))
    for offset, (name, data) in zip((-0.18, 0.18), (('Claude alone (with reruns)', alone), ('Claude + OR-Tools', with_solver))):
        values = [100 * summarize(data[size])['evidence_backed_success'][0] / len(data[size]) for size in SIZES]
        bars = axis.bar([x + offset for x in range(len(SIZES))], values, width=0.34, color=COLORS[name], label=name,
                        edgecolor=SURFACE, linewidth=2)
        axis.bar_label(bars, fmt='%.0f', color=INK, fontsize=9, padding=2)
    tune(axis)
    axis.set_ylim(0, 112)
    labels = [f'{size} surgeries' for size in SIZES[:-1]] + [f'{SIZES[-1]} surgeries\n(4 + OR-Tools runs hit usage limit)']
    axis.set_xticks(range(len(SIZES)), labels)
    axis.set_ylabel('Correct with valid evidence (%)', color=MUTED, fontsize=9)
    axis.set_title('Harder problems: correct answers with checked evidence', loc='left', color=INK, fontsize=12, pad=28)
    axis.legend(frameon=False, loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, labelcolor=INK, fontsize=9)

    return figure


def chart_time(plt, alone, with_solver):
    figure, axis = plt.subplots(figsize=(8, 3.6))
    for name, data, marker in (('Claude alone (with reruns)', alone, 'o'), ('Claude + OR-Tools', with_solver, 's')):
        values = [summarize(data[size])['mean_seconds'] for size in SIZES]
        axis.plot(range(len(SIZES)), values, color=COLORS[name], marker=marker, markersize=8, linewidth=2,
                  markeredgecolor='white', label=name)
        axis.text(len(SIZES) - 0.9, values[-1], f'{values[-1]:.0f}s', color=INK, fontsize=9, va='center')
    tune(axis)
    axis.set_xlim(-0.2, len(SIZES) - 0.5)
    axis.set_xticks(range(len(SIZES)), [f'{size} surgeries' for size in SIZES])
    axis.set_ylabel('Mean seconds per problem', color=MUTED, fontsize=9)
    axis.set_title('Time per problem as problems grow', loc='left', color=INK, fontsize=12)
    axis.legend(frameon=False, loc='upper left', labelcolor=INK, fontsize=9)
    return figure


def pilot_section(pilot_gold_rows):
    from .ortools_solver import ORToolsAdapter
    gold = {g['id']: g for g in pilot_gold_rows}
    recorded = load_pilot(gold)
    solver = {split: ortools_rows(f'pilot-{split}', gold) for split in PILOT_SPLITS}
    test_gold = [g for g in pilot_gold_rows if g['split'] == 'test']
    columns = {'Claude alone': summarize(by_arm(recorded['test'], 'no_tools')),
               'Claude + simple solver': summarize(by_arm(recorded['test'], 'csp')),
               'Claude + OR-Tools': summarize(solver['test']),
               'OR-Tools on gold': summarize(csp_on_gold(test_gold, ORToolsAdapter()))}
    splits = {split: {'Claude alone': summarize(by_arm(recorded[split], 'no_tools'))['evidence_backed_success'],
                      'Claude + OR-Tools': summarize(solver[split])['evidence_backed_success'],
                      'pairs': paired(by_arm(recorded[split], 'no_tools'), solver[split])} for split in PILOT_SPLITS}
    every = [r for rows in solver.values() for r in rows]
    return columns, splits, failure_split(every, gold)


def hard_section(hard_gold_rows):
    from .ortools_solver import ORToolsAdapter
    gold = {g['id']: g for g in hard_gold_rows}
    alone_first, alone_rerun = hard_claude_alone(gold)
    with_solver = {size: ortools_rows(f'hard-n{size:02d}', gold) for size in SIZES}
    solver_gold = {size: csp_on_gold([g for g in hard_gold_rows if int(g['size']) == size], ORToolsAdapter()) for size in SIZES}
    flat = lambda data: [r for rows in data.values() for r in rows]
    columns = {'Claude alone, first attempt': summarize(flat(alone_first)), 'Claude alone, with reruns': summarize(flat(alone_rerun)),
               'Claude + OR-Tools': summarize(flat(with_solver)), 'OR-Tools on gold': summarize(flat(solver_gold)),
               'Simple solver on gold': summarize(csp_on_gold(hard_gold_rows))}
    extras = {'pairs_vs_rerun_view': paired(flat(alone_rerun), flat(with_solver)),
              'failure_split': failure_split(flat(with_solver), gold),
              'by_size_table': size_table(alone_first, alone_rerun, with_solver, solver_gold)}
    return columns, extras, alone_rerun, with_solver


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pilot_columns, pilot_splits, pilot_failures = pilot_section(read_jsonl(PILOT_GOLD))
    hard_columns, hard_extras, alone, with_solver = hard_section(read_jsonl(HARD_GOLD))
    summary = {'pilot_test': pilot_columns, 'pilot_splits': pilot_splits, 'pilot_ortools_failure_split': pilot_failures,
               'hard': hard_columns, **{k: v for k, v in hard_extras.items() if k != 'by_size_table'}}
    (RESULTS / 'ortools-summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    for name, chart in (('ortools-hard-success', chart_success), ('ortools-hard-time', chart_time)):
        chart(plt, alone, with_solver).savefig(FIGURES / f'{name}.png', dpi=200, bbox_inches='tight', facecolor=SURFACE)
    print(method_table(pilot_columns), json.dumps(pilot_splits), json.dumps(pilot_failures), method_table(hard_columns),
          hard_extras['by_size_table'], json.dumps({k: v for k, v in hard_extras.items() if k != 'by_size_table'}), sep='\n\n')


if __name__ == '__main__':
    main()
