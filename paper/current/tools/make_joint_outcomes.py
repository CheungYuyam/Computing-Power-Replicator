"""Paired joint-system effects with visible near-zero estimates and seed ranges.

Contract: a quantitative grid links completion, waiting, energy and generation
cost under the same reassignment comparison. All 27 paired runs are retained.
Means and min/max ranges refer to three controller seeds, not confidence limits.
Linear scales preserve between-date magnitudes. Numeric labels resolve small
effects without stretching axes or replacing differences by absolute values.
Times New Roman preserves the manuscript's existing figure typography.
"""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from audit_panel_alignment import require_matplotlib_panel_alignment

ROOT = Path(__file__).resolve().parents[1]
DATES = ['2020-07-27', '2020-08-05', '2020-08-21']
SETTINGS = [
    ('Uniform, synchronous', 'Uniform / Synchronous', '#C72228', 'o'),
    ('Uniform, staggered', 'Uniform / Staggered', '#F98F34', 's'),
    ('Capacity-proportional, staggered', 'Proportional / Staggered', '#0C4E9B', '^'),
]
METRICS = [
    ('completion_eval_fraction', 100, 'Completion at 48 h', 'Change (percentage points)', [-7.4, 6.5], [-6, -3, 0, 3, 6]),
    ('restricted_wait_s', 1 / 60, 'Mean Waiting through 72 h', 'Change (min)', [-195, 25], [-180, -120, -60, 0]),
    ('evaluation_it_mwh', 1, 'Task IT Energy, 24–48 h', 'Change (MWh)', [-2.1, 18.3], [0, 5, 10, 15]),
    ('evaluation_generation_cost', 1, 'Generation Cost, 24–48 h', 'Change (currency)', [-135, 305], [-100, 0, 100, 200, 300]),
]


def signed(value):
    if value == 0:
        return '0'
    if abs(value) < .005:
        return f'{value:+.4f}'.replace('-', '−')
    return f'{value:+.2f}'.replace('-', '−')


def render_forest(root=ROOT):
    data = root / 'source_data'
    out = root / 'figures/systems'
    qa = root / 'qa/fig03_readability_20261027'
    qa.mkdir(parents=True, exist_ok=True)
    source = data / 'joint_outcome_pairs.json'
    pairs = json.loads(source.read_text(encoding='utf-8'))
    assert len(pairs) == 27
    raw = {}
    for tag, filename in [('uniform', 'main_case_metrics.csv'), ('proportional', 'capacity_case_metrics.csv')]:
        with (data / filename).open(encoding='utf-8-sig', newline='') as stream:
            raw[tag] = {r['case']: r for r in csv.DictReader(stream)}
    residuals = []
    for row in pairs:
        pool = raw['proportional' if row['initialization'].startswith('Capacity') else 'uniform']
        a, b = pool[row['candidate']], pool[row['reference']]
        assert a['date'] == b['date'] == row['date']
        assert int(a['seed']) == int(b['seed']) == row['seed']
        assert a['cohort_jobs'] == b['cohort_jobs']
        assert float(a['restricted_wait_s']) >= 0 and float(b['restricted_wait_s']) >= 0
        for metric, *_ in METRICS:
            residual = abs(float(a[metric]) - float(b[metric]) - row[metric + '_delta'])
            residuals.append(residual)
            assert residual < 1e-8, (metric, residual)

    plt.rcParams.update({
        'font.family': 'Times New Roman', 'font.size': 8,
        'axes.titlesize': 8.7, 'axes.labelsize': 8,
        'xtick.labelsize': 7.5, 'ytick.labelsize': 8,
        'legend.fontsize': 8, 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'svg.fonttype': 'none', 'legend.frameon': False,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.spines.left': False, 'axes.linewidth': .65,
    })
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.55))
    fig.subplots_adjust(left=.085, right=.925, bottom=.10, top=.81, hspace=.65, wspace=.62)
    y_centers = [8, 4, 0]
    summary = []
    for ax, (metric, scale, title, xlabel, limits, ticks), letter in zip(axes.flat, METRICS, 'abcd'):
        ax.set_title(f'({letter}) {title}', loc='left', pad=14)
        ax.set_ylim(-1.9, 9.9)
        ax.set_xlim(limits)
        ax.set_xticks(ticks)
        ax.set_xlabel(xlabel, labelpad=3)
        ax.set_yticks(y_centers, ['Jul 27', 'Aug 5', 'Aug 21'])
        ax.tick_params(axis='y', length=0, pad=5)
        ax.tick_params(axis='x', length=3)
        ax.axvline(0, color='#9B9B9B', lw=.7, zorder=0)
        for boundary in [6, 2]:
            ax.axhline(boundary, color='#E6E6E6', lw=.55, zorder=0)
        ax.text(1.03, 1.025, 'Mean', transform=ax.transAxes, fontsize=7.5, ha='left', va='bottom', color='#555555')
        for date, y_center in zip(DATES, y_centers):
            for j, (key, label, color, marker) in enumerate(SETTINGS):
                group = [r for r in pairs if r['date'] == date and r['initialization'] == key]
                assert sorted(r['seed'] for r in group) == [17, 29, 43]
                values = np.array([r[metric + '_delta'] * scale for r in group])
                assert np.isfinite(values).all()
                m, lo, hi = float(values.mean()), float(values.min()), float(values.max())
                assert limits[0] < lo <= m <= hi < limits[1]
                y = y_center + 1.05 * (1 - j)
                ax.errorbar(m, y, xerr=[[m-lo], [hi-m]], fmt=marker,
                    color=color, ms=4, markeredgecolor='white', markeredgewidth=.4,
                    elinewidth=1, capsize=2, capthick=.7, zorder=3)
                ax.text(1.03, y, signed(m), transform=ax.get_yaxis_transform(),
                    fontsize=7.5, ha='left', va='center', color=color)
                summary.append({'date': date, 'setting': key, 'metric': metric,
                    'scale': scale, 'mean': m, 'minimum': lo, 'maximum': hi,
                    'seed_count': len(group), 'mean_label': signed(m)})
    fig.text(.5, .978, 'Change = Accumulated-Cost Feedback − Fixed Allocation',
             ha='center', va='top', fontsize=8.5)
    handles = [Line2D([], [], color=c, marker=m, ls='none', markersize=4.5, label=l)
               for _, l, c, m in SETTINGS]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .936),
               ncol=3, columnspacing=1.8, handletextpad=.5)
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(qa/'alignment.json'),
        overlay_svg=str(qa/'alignment.svg'), tolerance_pt=1.5,
        gutter_tolerance_pt=1.5, strict=True)
    fig.savefig(out/'fig_joint_outcomes.pdf', facecolor='white')
    fig.savefig(out/'fig_joint_outcomes.svg', facecolor='white')
    fig.savefig(out/'fig_joint_outcomes.png', dpi=600, facecolor='white')
    plt.close(fig)
    with (data/'joint_outcome_display.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    checks = {
        'claim': 'Reassignment links task-service changes to energy and generation-cost changes, with effects depending on workload and initialization.',
        'archetype': 'quantitative grid', 'backend': 'Python/matplotlib',
        'input_pairs': len(pairs), 'excluded_pairs': 0, 'aggregates': len(summary),
        'paired_metric_reconciliations': len(residuals), 'maximum_residual': max(residuals),
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'zero_aggregate_means': [r for r in summary if r['mean'] == 0],
        'interval': 'minimum to maximum of three paired controller seeds',
        'scale': 'linear in each metric, shared across all dates and settings',
        'typography_exception': 'Times New Roman retained for consistency with the manuscript and existing figures.',
        'caption_update': 'Bars replaced by points, with horizontal min-max ranges and printed signed means.',
    }
    (qa/'data_checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps(checks, indent=2))


def render(root=ROOT):
    from make_joint_outcome_matrix import render as render_matrix
    render_matrix(root)


if __name__ == '__main__':
    render()
