"""Build the tables and charts for the Claude-only study. Needs matplotlib."""
import json
from pathlib import Path
from statistics import median

from surgerybench.common import read_jsonl

from .hard_dataset import SIZES
from .hard_metrics import summarize_size
from .report import FIGURES, GRID, INK, MUTED, RESULTS, SURFACE, tune

TIME_LIMIT_SECONDS = 300
SERIES = {'schedule_success': ('Solvable: valid schedule', '#2a78d6', 'o', -0.06),
          'proof_success': ('Impossible: valid proof', '#eb6834', 's', 0.06)}


def load():
    return {size: read_jsonl(RESULTS / f'hard-n{size:02d}' / 'runs.jsonl') for size in SIZES}


def counts(values):
    return f'{values[0]}/{values[1]}'


def seconds_for(rows, label):
    return median(r['latency_seconds'] for r in rows if r['label'] == label)


def results_table(data):
    lines = ['| Surgeries | Fully correct | Solvable: valid schedule | Impossible: valid proof | Right yes/no decision | Median output tokens |',
             '|--:|---|---|---|---|--:|']
    for size, rows in data.items():
        s = summarize_size(rows)
        lines.append(f"| {size} | {counts(s['fully_correct'])} | {counts(s['schedule_success'])} | {counts(s['proof_success'])} "
                     f"| {counts(s['decision_correct'])} | {s['median_output_tokens']:,.0f} |")
    return '\n'.join(lines)


def timing_table(data):
    lines = ['| Surgeries | Median time, solvable (s) | Median time, impossible (s) | Slowest run (s) |', '|--:|--:|--:|--:|']
    for size, rows in data.items():
        lines.append(f"| {size} | {seconds_for(rows, 'FEASIBLE'):.0f} | {seconds_for(rows, 'INFEASIBLE'):.0f} "
                     f"| {max(r['latency_seconds'] for r in rows):.0f} |")
    return '\n'.join(lines)


def chart_success(plt, data):
    figure, axis = plt.subplots(figsize=(8, 4))
    for field, (name, color, marker, offset) in SERIES.items():
        for x, rows in enumerate(data.values()):
            done, total, low, high = summarize_size(rows)[field]
            middle = 100 * done / total
            axis.errorbar(x + offset, middle, yerr=[[middle - 100 * low], [100 * high - middle]], color=color, marker=marker,
                          markersize=8, linewidth=2, capsize=4, markeredgecolor='white', label=name if x == 0 else None)
    tune(axis)
    axis.set_ylim(0, 108)
    axis.set_xticks(range(len(data)), [f'{size} surgeries' for size in data])
    axis.set_ylabel('Correct answers (%)', color=MUTED, fontsize=9)
    axis.set_title('Claude stayed near 100%, with first failures at 40 and 80 surgeries', loc='left', color=INK, fontsize=12)
    axis.legend(frameon=False, loc='lower left', labelcolor=INK, fontsize=9)
    return figure


def chart_time(plt, data):
    figure, axis = plt.subplots(figsize=(8, 4))
    for label, name, color, marker in (('FEASIBLE', 'Solvable problems', '#2a78d6', 'o'),
                                       ('INFEASIBLE', 'Impossible problems', '#eb6834', 's')):
        values = [seconds_for(rows, label) for rows in data.values()]
        axis.plot(range(len(values)), values, color=color, marker=marker, markersize=8, linewidth=2,
                  markeredgecolor='white', label=name)
        axis.text(len(values) - 0.92, values[-1], f'{values[-1]:.0f}s', color=INK, fontsize=9, va='center')
    axis.axhline(TIME_LIMIT_SECONDS, color=MUTED, linewidth=1, linestyle='--')
    axis.text(0, TIME_LIMIT_SECONDS - 8, '5-minute limit per problem', color=MUTED, fontsize=9, va='top')
    tune(axis)
    axis.set_ylim(0, 320)
    axis.set_xlim(-0.2, len(data) - 0.6)
    axis.set_xticks(range(len(data)), [f'{size} surgeries' for size in data])
    axis.set_ylabel('Median seconds per problem', color=MUTED, fontsize=9)
    axis.set_title('Building a schedule slows fast, while finding a conflict stays quick', loc='left', color=INK, fontsize=12)
    axis.legend(frameon=False, loc='center left', labelcolor=INK, fontsize=9)
    return figure


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = load()
    for name, chart in (('hard-success', chart_success), ('hard-time', chart_time)):
        chart(plt, data).savefig(FIGURES / f'{name}.png', dpi=200, bbox_inches='tight', facecolor=SURFACE)
    summaries = {str(size): summarize_size(rows) for size, rows in data.items()}
    (RESULTS / 'hard-summary.json').write_text(json.dumps(summaries, indent=2, sort_keys=True) + '\n')
    print(results_table(data), '', timing_table(data), sep='\n')


if __name__ == '__main__':
    main()
