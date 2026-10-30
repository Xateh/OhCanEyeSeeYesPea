"""Build the study's tables and charts from recorded runs. Needs matplotlib; nothing else in the study does."""
from collections import Counter
import json
from pathlib import Path

from surgerybench.common import read_jsonl

from .metrics import ARMS, summarize, wilson

RESULTS = Path('study/results')
FIGURES = Path('study/figures')
GOLD = Path('fixtures/arrival-deadline-v1/gold.jsonl')
LABELS = {'01-train-baseline-v1': '1. Train, v1', '02-train-required-tool-v2': '2. Train, v2',
          '03-train-format-example-v3': '3. Train, v3', '04-validation-v3': '4. Validation, v3',
          '05-test-v3': '5. Test, v3'}
ARM_NAMES = {'no_tools': 'No tools', 'csp': 'With solver'}
ARM_STYLE = {'no_tools': ('#2a78d6', 'o'), 'csp': ('#eb6834', 's')}
CALL_COLORS = {0: '#c3c2b7', 1: '#7dafea', 2: '#2a78d6', 3: '#123f7a'}
INK, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'


def percent(values):
    return f'{values[0]}/{values[1]} ({values[0] / values[1]:.0%})'


def per_run(arm, value):
    return value / arm['runs']


def load_iterations():
    gold = {g['id']: g for g in read_jsonl(GOLD)}
    loaded = {}
    for name in LABELS:
        rows = read_jsonl(RESULTS / name / 'runs.jsonl')
        loaded[name] = {'rows': rows, 'summary': summarize(rows, gold)}
    return loaded


def overview_table(iterations):
    lines = ['| Iteration | Arm | Runs | Correct | Solver calls per run | Solver errors | Exact translations | Median time (s) | Tokens per run |',
             '|---|---|--:|---|--:|--:|---|--:|--:|']
    for name, data in iterations.items():
        for arm in ARMS:
            stats = data['summary']['arms'][arm]
            arm_rows = [r for r in data['rows'] if r['arm'] == arm]
            calls = sum(r['tool_call_count'] for r in arm_rows) / len(arm_rows)
            errors = sum(1 for r in arm_rows for e in r['errors'] if e['stage'] == 'tool')
            exact = data['summary']['translation'].get('exact', 0) if arm == 'csp' else None
            lines.append(f"| {LABELS[name]} | {ARM_NAMES[arm]} | {stats['runs']} | {percent(stats['overall_success'])} "
                         f"| {calls:.2f} | {errors} | {'n/a' if exact is None else f'{exact}/{stats['runs']}'} "
                         f"| {stats['median_latency_seconds']:.1f} | {per_run(stats, stats['tokens_total']):,.0f} |")
    return '\n'.join(lines)


def theme_table(iterations):
    lines = ['| Problem theme | No tools | With solver |', '|---|---|---|']
    for theme, arms in iterations['05-test-v3']['summary']['by_theme'].items():
        lines.append(f"| {theme.replace('_', ' ')} | {percent(arms['no_tools'])} | {percent(arms['csp'])} |")
    return '\n'.join(lines)


def tune(axis):
    axis.set_facecolor(SURFACE)
    axis.spines[['top', 'right', 'left']].set_visible(False)
    axis.spines['bottom'].set_color(GRID)
    axis.tick_params(colors=MUTED, length=0, labelsize=9)
    axis.yaxis.grid(True, color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)


def short_labels():
    return [label.replace(', ', '\n') for label in LABELS.values()]


def distinct_cases(data):
    return len({r['case_id'] for r in data['rows']})


def case_level_rate(data, arm):
    """Count a problem as solved only if every repetition was, since repeats are not new evidence."""
    outcomes = {}
    for row in (r for r in data['rows'] if r['arm'] == arm):
        outcomes[row['case_id']] = outcomes.get(row['case_id'], True) and row['score']['valid']
    solved = sum(outcomes.values())
    low, high = wilson(solved, len(outcomes))
    return 100 * solved / len(outcomes), 100 * low, 100 * high


def chart_success(plt, iterations):
    figure, axis = plt.subplots(figsize=(8, 4))
    for offset, arm in zip((-0.09, 0.09), ARMS):
        color, marker = ARM_STYLE[arm]
        for x, data in enumerate(iterations.values()):
            middle, low, high = case_level_rate(data, arm)
            axis.errorbar(x + offset, middle, yerr=[[middle - low], [high - middle]], color=color,
                          marker=marker, markersize=8, linewidth=2, capsize=4, markeredgecolor='white',
                          label=ARM_NAMES[arm] if x == 0 else None)
    for x, data in enumerate(iterations.values()):
        axis.text(x, 4, f"{distinct_cases(data)} problems", ha='center', color=MUTED, fontsize=8)
    tune(axis)
    axis.set_ylim(0, 108)
    axis.set_xticks(range(len(LABELS)), short_labels())
    axis.set_ylabel('Correct answers (%)', color=MUTED, fontsize=9)
    axis.set_title('Both arms scored 100%, but small samples leave real uncertainty', loc='left', color=INK, fontsize=12)
    axis.legend(frameon=False, loc='lower left', bbox_to_anchor=(0, 0.12), labelcolor=INK, fontsize=9)
    return figure


def chart_calls(plt, iterations):
    figure, axis = plt.subplots(figsize=(8, 4))
    shares = []
    for data in iterations.values():
        arm_rows = [r for r in data['rows'] if r['arm'] == 'csp']
        counts = Counter(r['tool_call_count'] for r in arm_rows)
        shares.append({calls: 100 * counts[calls] / len(arm_rows) for calls in CALL_COLORS})
    bottoms = [0.0] * len(shares)
    for calls, color in CALL_COLORS.items():
        heights = [share[calls] for share in shares]
        axis.bar(range(len(shares)), heights, 0.55, bottom=bottoms, color=color, edgecolor='white', linewidth=2,
                 label=f"{calls} solver call{'' if calls == 1 else 's'}")
        for x, (height, bottom) in enumerate(zip(heights, bottoms)):
            if height >= 10:
                axis.text(x, bottom + height / 2, f'{height:.0f}%', ha='center', va='center', fontsize=9,
                          color='white' if calls >= 2 else INK)
        bottoms = [b + h for b, h in zip(bottoms, heights)]
    tune(axis)
    axis.set_ylim(0, 100)
    axis.set_xticks(range(len(LABELS)), short_labels())
    axis.set_ylabel('Share of solver-arm runs (%)', color=MUTED, fontsize=9)
    axis.set_title('Requiring the solver worked, and the format example removed retries', loc='left', color=INK, fontsize=12)
    axis.legend(frameon=False, ncols=4, loc='upper center', bbox_to_anchor=(0.5, -0.17), labelcolor=INK, fontsize=9)
    return figure


def chart_effort(plt, iterations):
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    readers = (('Tokens per run', lambda s: per_run(s, s['tokens_total'])),
               ('Median seconds per run', lambda s: s['median_latency_seconds']))
    for axis, (title, read) in zip(axes, readers):
        for offset, arm in zip((-0.19, 0.19), ARMS):
            values = [read(d['summary']['arms'][arm]) for d in iterations.values()]
            axis.bar([x + offset for x in range(len(values))], values, 0.36, color=ARM_STYLE[arm][0],
                     edgecolor='white', linewidth=2, label=ARM_NAMES[arm])
        tune(axis)
        axis.set_xticks(range(len(LABELS)), short_labels(), fontsize=8)
        axis.set_title(title, loc='left', color=INK, fontsize=11)
    axes[0].legend(frameon=False, labelcolor=INK, fontsize=9, loc='upper left')
    axes[0].set_ylim(top=axes[0].get_ylim()[1] * 1.15)
    figure.suptitle('The solver route uses about 3 times the tokens and twice the time', x=0.01, ha='left', color=INK, fontsize=12)
    figure.tight_layout()
    return figure


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    iterations = load_iterations()
    FIGURES.mkdir(exist_ok=True)
    for name, chart in (('success', chart_success), ('solver-calls', chart_calls), ('effort', chart_effort)):
        chart(plt, iterations).savefig(FIGURES / f'{name}.png', dpi=200, bbox_inches='tight', facecolor=SURFACE)
    summaries = {name: data['summary'] for name, data in iterations.items()}
    (RESULTS / 'summary.json').write_text(json.dumps(summaries, indent=2, sort_keys=True) + '\n')
    print(overview_table(iterations), '', theme_table(iterations), sep='\n')


if __name__ == '__main__':
    main()
