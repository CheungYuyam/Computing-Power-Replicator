"""Figure 6 layout candidates using all 39 frozen signal pairs; no run filtering.

Question: how does a target-site signal relate to other-site and later demand?
(a) response frequency, (b) spatial response, (c) prespecified temporal response.
User palette only. Single-case panel (c) is not an ensemble uncertainty estimate.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
from matplotlib.lines import Line2D
from matplotlib.colors import to_rgb
from audit_panel_alignment import require_matplotlib_panel_alignment

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figure6_options_20261028'
OUT.mkdir(exist_ok=True)
DATA = ROOT / 'source_data'
PAIRS = json.loads((DATA / 'reported_signal_pairs.json').read_text(encoding='utf-8'))
assert len(PAIRS) == 39
GROUPS = ['primary', 'pressure', 'scale', 'initialization']
NAMES = ['Main', 'Capacity', 'Scale', 'Init.']
BLUE, RED, ORANGE = '#6B98C4', '#F5867F', '#F98F34'
DARK_BLUE, DARK_RED, PALE_ORANGE = '#0C4E9B', '#C72228', '#FFBC80'
GROUP_COLORS = [DARK_BLUE, ORANGE, DARK_RED, BLUE]
MARKERS = ['o', 's', 'D', '^']
STATUS_COLORS = [RED, BLUE, PALE_ORANGE]
THRESHOLD = 1e-8  # MWh; unchanged classification follows the original study.
X = np.array([r['target_window_reduction_mwh'] * 1000 for r in PAIRS])
Y = np.array([r['receiving_sites_window_energy_delta_mwh'] * 1000 for r in PAIRS])
COUNTS = np.array([[sum(r['target_window_reduction_mwh'] > THRESHOLD for r in PAIRS if r['kind'] == g),
                    sum(abs(r['target_window_reduction_mwh']) <= THRESHOLD for r in PAIRS if r['kind'] == g),
                    sum(r['target_window_reduction_mwh'] < -THRESHOLD for r in PAIRS if r['kind'] == g)]
                   for g in GROUPS])
assert COUNTS.sum() == 39 and COUNTS[:, 1].sum() == 27
TRACE = list(csv.DictReader((DATA / 'pulse_reference_trace.csv').open(encoding='utf-8')))
HOURS = np.array([float(r['hours_after_onset']) for r in TRACE])
DT = np.diff(np.r_[0, HOURS])
assert np.allclose(DT, 1 / 12)
CUMULATIVE = {key: np.cumsum([float(r[key]) for r in TRACE]) / 12 for key in
              ['target_delta_mw', 'receiving_delta_mw', 'total_delta_mw']}
assert np.allclose(CUMULATIVE['target_delta_mw'] + CUMULATIVE['receiving_delta_mw'], CUMULATIVE['total_delta_mw'])
plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 8,
    'axes.titlesize': 9, 'axes.labelsize': 8, 'xtick.labelsize': 7.5,
    'ytick.labelsize': 7.5, 'legend.fontsize': 7.3, 'legend.frameon': False,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.linewidth': .65, 'pdf.fonttype': 42, 'svg.fonttype': 'none',
    'lines.linewidth': 1.25})

def new_figure():
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 3.25))
    fig.subplots_adjust(left=.10, right=.985, top=.86, bottom=.24, wspace=.57)
    return fig, axes

def temporal(ax):
    for key, label, color, style in [
        ('target_delta_mw', 'Target', BLUE, '-'),
        ('receiving_delta_mw', 'Other sites', ORANGE, '-'),
        ('total_delta_mw', 'Total', DARK_RED, '--')]:
        ax.plot(HOURS, CUMULATIVE[key], color=color, ls=style, label=label)
    ax.axvspan(0, 2, color='#FFF0DF', zorder=0)
    ax.set_xlim(0, 36)
    ax.set_xticks([0, 12, 24, 36])
    ax.set_xlabel('Time after signal onset (h)')
    ax.set_ylabel('Cumulative energy change (MWh)')
    ax.set_title('(c) Response over time', loc='left', pad=10)
    ax.legend(loc='lower left', handlelength=1.8)

def scatter_axes(ax):
    # Include negative and large positive values omitted by the former [-.3, 8] axes.
    ax.set_xlim(-2.4, 11)
    ax.set_ylim(-4.8, 14.8)
    assert np.all((X > -2.4) & (X < 11) & (Y > -4.8) & (Y < 14.8))
    ax.set_xticks([0, 5, 10])
    ax.set_yticks([-4, 0, 5, 10, 14])
    ax.plot([-2.4, 11], [-2.4, 11], color='#999999', lw=.7, ls='--', zorder=0)
    ax.set_xlabel('Target reduction (kWh)')
    ax.set_ylabel('Other-site change (kWh)')
    ax.set_title('(b) Response across sites', loc='left', pad=10)

def count_matrix(ax):
    ax.set_title('(a) Target-window outcomes', loc='left', pad=10)
    ax.set_xlim(0, 3)
    ax.set_ylim(4, -.55)
    ax.axis('off')
    for col, name in enumerate(['Lower', 'Unchanged', 'Higher']):
        ax.text(col + .5, -.24, name, ha='center', va='center', fontsize=7.1)
    for row, name in enumerate(NAMES):
        ax.text(-.10, row + .5, f'{name} ({COUNTS[row].sum()})', ha='right', va='center', fontsize=7.8)
        for col in range(3):
            n = int(COUNTS[row, col])
            base = np.array(to_rgb(STATUS_COLORS[col]))
            fill = 1 - (.16 + .60 * n / max(1, COUNTS[:, col].max())) * (1 - base)
            if not n:
                fill = np.array([.975, .975, .975])
            ax.add_patch(Rectangle((col, row), 1, 1, facecolor=fill, edgecolor='white', lw=2))
            ax.text(col + .5, row + .5, str(n), ha='center', va='center', fontsize=10)
    ax.text(.5, -.18, 'Counts; group totals in parentheses', transform=ax.transAxes,
            ha='center', va='top', fontsize=7)

def bubble_scatter(ax):
    scatter_axes(ax)
    # Exact coordinate coincidences are counted, never jittered or discarded.
    locations = Counter(zip(X.tolist(), Y.tolist()))
    for (x, y), n in locations.items():
        ax.scatter(x, y, s=19 * n, facecolor=BLUE, edgecolor=DARK_BLUE, lw=.65, alpha=.75, zorder=3)
        if n > 2:
            ax.annotate(str(n), (x, y), xytext=(12, -16), textcoords='offset points',
                        color=DARK_BLUE, fontsize=8)
    ax.text(.5, -.18, 'Bubble area = number of pairs', transform=ax.transAxes,
            ha='center', va='top', fontsize=7)

def stacked_counts(ax):
    ax.set_title('(a) Target-window outcomes', loc='left', pad=10)
    left = np.zeros(4)
    for col, color in enumerate(STATUS_COLORS):
        values = COUNTS[:, col]
        ax.barh(np.arange(4), values, left=left, height=.56, color=color)
        for row, n in enumerate(values):
            if n:
                ax.text(left[row] + n / 2, row, str(n), ha='center', va='center', fontsize=8)
        left += values
    ax.set_yticks(range(4), NAMES)
    ax.set_ylim(3.6, -.6)
    ax.set_xlim(0, 19)
    ax.set_xticks([0, 6, 12, 18])
    ax.set_xlabel('Number of pairs')
    ax.legend(handles=[Patch(facecolor=c, label=n) for c, n in zip(STATUS_COLORS, ['Lower', 'Unchanged', 'Higher'])],
              loc='upper center', bbox_to_anchor=(.5, -.24), ncol=3, borderaxespad=0,
              columnspacing=.7, handlelength=1.0, handletextpad=.35, fontsize=7)

def group_scatter(ax):
    scatter_axes(ax)
    for group, name, color, marker in zip(GROUPS, NAMES, GROUP_COLORS, MARKERS):
        idx = np.array([r['kind'] == group for r in PAIRS])
        ax.scatter(X[idx], Y[idx], s=25, facecolor=color, edgecolor='white', lw=.35,
                   marker=marker, alpha=.85, label=name)
    ax.legend(loc='lower right', fontsize=7, labelspacing=.25, handletextpad=.4)
    ax.text(.5, -.18, 'All pairs; exact overlaps retained', transform=ax.transAxes,
            ha='center', va='top', fontsize=7)

def count_dots(ax):
    ax.set_title('(a) Target-window outcomes', loc='left', pad=10)
    y = np.arange(4)
    for col, (color, offset) in enumerate(zip(STATUS_COLORS, [-.23, 0, .23])):
        ax.scatter(COUNTS[:, col], y + offset, s=30, color=color, edgecolor='white', lw=.4, zorder=3)
        for row, n in enumerate(COUNTS[:, col]):
            ax.annotate(str(n), (n, row + offset), xytext=(5, 0), textcoords='offset points',
                        ha='left', va='center', fontsize=7)
    ax.set_yticks(y, NAMES)
    ax.set_ylim(3.6, -.6)
    ax.set_xlim(-1, 19)
    ax.set_xticks([0, 6, 12, 18])
    ax.set_xlabel('Number of pairs')
    ax.legend(handles=[Line2D([], [], marker='o', ls='', color=c, label=n) for c, n in zip(STATUS_COLORS, ['Lower', 'Unchanged', 'Higher'])],
              loc='upper center', bbox_to_anchor=(.5, -.24), ncol=3, borderaxespad=0,
              columnspacing=.7, handlelength=1.0, handletextpad=.35, fontsize=7)

def group_ranges(ax):
    ax.set_title('(b) Group means and ranges', loc='left', pad=10)
    for values, offset, color, marker in [(X, -.13, BLUE, 'o'), (Y, .13, RED, 's')]:
        for i, g in enumerate(GROUPS):
            v = values[[r['kind'] == g for r in PAIRS]]
            mean = float(v.mean())
            ax.errorbar(mean, i + offset, xerr=[[mean-v.min()], [v.max()-mean]],
                        fmt=marker, markersize=4, color=color, elinewidth=.95, capsize=2)
    ax.set_yticks(range(4), NAMES)
    ax.set_ylim(3.6, -.6)
    ax.set_xlim(-4.8, 14.8)
    ax.set_xticks([-4, 0, 5, 10, 14])
    ax.set_xlabel('Energy response (kWh)')
    ax.legend(handles=[Line2D([], [], marker='o', ls='-', color=BLUE, label='Target reduction'),
                       Line2D([], [], marker='s', ls='-', color=RED, label='Other-site change')],
              loc='upper center', bbox_to_anchor=(.5, -.24), ncol=2, borderaxespad=0,
              columnspacing=.8, handlelength=1.1, handletextpad=.35, fontsize=7)

def vertical_counts(ax):
    ax.set_title('(a) Target-window outcomes', loc='left', pad=10)
    bottom = np.zeros(4)
    for col, color in enumerate(STATUS_COLORS):
        values = COUNTS[:, col]
        ax.bar(np.arange(4), values, bottom=bottom, width=.62, color=color)
        for i, n in enumerate(values):
            if n:
                ax.text(i, bottom[i] + n / 2, str(n), ha='center', va='center', fontsize=6.5 if n == 1 else 8)
        bottom += values
    ax.set_xticks(range(4), ['Main', 'Capacity', 'Scale', 'Init.'])
    ax.set_ylim(0, 20)
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.set_ylabel('Number of pairs')
    ax.legend(handles=[Patch(facecolor=c, label=n) for c, n in zip(STATUS_COLORS, ['Lower', 'Unchanged', 'Higher'])],
              loc='upper center', bbox_to_anchor=(.5, -.24), ncol=3, borderaxespad=0,
              columnspacing=.7, handlelength=1.0, handletextpad=.35, fontsize=7)

def group_bars(ax):
    ax.set_title('(b) Mean energy response', loc='left', pad=10)
    # Keep a readable linear scale for group means. Print full ranges in a
    # separate right-hand column rather than cropping outliers or rescaling bars.
    y = np.arange(4)
    for values, offset, color in [(X, -.18, BLUE), (Y, .18, PALE_ORANGE)]:
        for i, g in enumerate(GROUPS):
            v = values[[r['kind'] == g for r in PAIRS]]
            ax.barh(i + offset, v.mean(), height=.29, color=color)
            def fmt(z):
                if z == 0:
                    return '0'
                if abs(z) < .01:
                    return f'{z:.3f}'.replace('-', '−')
                return f'{z:.2f}'.replace('-', '−')
            ax.text(4.35, i + offset, f'[{fmt(v.min())}, {fmt(v.max())}]',
                    ha='right', va='center', fontsize=6.8)
    ax.text(3.45, -.67, 'Min–max', ha='center', va='center', fontsize=7)
    ax.set_yticks(y, NAMES)
    ax.set_ylim(3.55, -.85)
    ax.set_xlim(-.18, 4.4)
    ax.set_xticks([0, 1, 2])
    ax.spines['bottom'].set_bounds(-.1, 2.35)
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=5)
    ax.set_xlabel('Mean response (kWh)', x=.30)
    ax.legend(handles=[Patch(facecolor=BLUE, label='Target reduction'),
                       Patch(facecolor=PALE_ORANGE, label='Other-site change')],
              loc='upper center', bbox_to_anchor=(.5, -.24), ncol=2, borderaxespad=0,
              columnspacing=.8, handlelength=1.1, handletextpad=.35, fontsize=7)

def export(fig, name):
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(OUT / f'{name}.alignment.json'),
                                       tolerance_pt=1.5, strict=True)
    fig.savefig(OUT / f'{name}.pdf', facecolor='white')
    fig.savefig(OUT / f'{name}.svg', facecolor='white')
    fig.savefig(OUT / f'{name}.png', facecolor='white', dpi=600)
    plt.close(fig)

def render_options():
    for name, panel_a, panel_b in [
        ('A_count_matrix_bubbles', count_matrix, bubble_scatter),
        ('B_horizontal_counts_scatter', stacked_counts, group_scatter),
        ('C_dot_counts_group_ranges', count_dots, group_ranges),
        ('D_bars_with_numeric_ranges', vertical_counts, group_bars)]:
        fig, axes = new_figure()
        panel_a(axes[0])
        panel_b(axes[1])
        temporal(axes[2])
        export(fig, name)

audit = {'input_pairs': len(PAIRS), 'counts': COUNTS.tolist(),
         'count_order': ['reduction', 'no_net_change', 'increase'], 'groups': GROUPS,
         'x_range_kwh': [float(X.min()), float(X.max())],
         'y_range_kwh': [float(Y.min()), float(Y.max())],
         'previous_scatter_outside_limits': int(np.sum((X < -.3) | (X > 8) | (Y < -.3) | (Y > 8))),
         'dropped_pairs': 0, 'jitter': False,
         'A': 'Exact coincident coordinates are represented by proportional bubble area.',
         'B': 'All 39 points plotted; exact coordinate overlaps remain.',
         'C': 'Group means and full min-max ranges across all cases, not confidence intervals; group sizes differ.',
         'panel_c': 'All candidates retain the same 432 trace intervals and cumulative-energy calculation.',
         'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [
             DATA/'reported_signal_pairs.json', DATA/'pulse_reference_trace.csv']},
         'font_exception': 'Times New Roman matches manuscript. Vector PDF/SVG final assets with 600 dpi PNG previews.'}
if __name__ == '__main__':
    render_options()
    (OUT/'data_audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    print(json.dumps(audit, indent=2))
