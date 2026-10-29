"""Approved Figure 6 layout with explicit paired-energy axes and balance line."""
import numpy as np
import matplotlib.pyplot as plt
import design_signal_options as d

def render():
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.65))
    fig.subplots_adjust(left=.065, right=.985, bottom=.24, top=.84, wspace=.52)
    bottom = np.zeros(4)
    for i, (label, color) in enumerate(zip(['Lower', 'Unchanged', 'Higher'], d.STATUS_COLORS)):
        axes[0].bar(np.arange(4), d.COUNTS[:, i], bottom=bottom, color=color, width=.65, label=label)
        bottom += d.COUNTS[:, i]
    axes[0].set_xticks(range(4), ['Main', 'Pressure', 'Scale', 'Init.'])
    axes[0].set_ylabel('Signal pairs')
    axes[0].set_ylim(0, 20)
    axes[0].set_title('(a) Target-window outcomes', loc='left', pad=8)
    axes[0].legend(loc='upper right', fontsize=6.8, handlelength=1)
    d.scatter_axes(axes[1])
    for group, name, color, marker in zip(d.GROUPS, d.NAMES, d.GROUP_COLORS, d.MARKERS):
        idx = np.array([r['kind'] == group for r in d.PAIRS])
        axes[1].scatter(d.X[idx], d.Y[idx], s=20, marker=marker, color=color, alpha=.8, label=name)
    axes[1].legend(loc='lower right', fontsize=6.7, handletextpad=.3, labelspacing=.2)
    axes[1].set_xlabel('Target-site reduction (kWh)\n(off − on)', fontsize=7.5)
    axes[1].set_ylabel('Other-site increase (kWh)\n(on − off)', fontsize=7.5)
    axes[1].annotate('Unchanged system energy', xy=(9.0, 9.0),
                     xytext=(7.1, 13.35), ha='center', va='center',
                     fontsize=6.2, color='#666666',
                     arrowprops={'arrowstyle':'-', 'color':'#999999',
                                 'lw':.55, 'shrinkA':4, 'shrinkB':0})
    d.temporal(axes[2])
    axes[2].set_xlabel('Hours after signal onset')
    axes[2].set_ylabel('Cumulative change (MWh)')
    axes[2].legend(loc='lower left', fontsize=7)
    # Preserve the user-selected three-panel layout; alternate candidates stay separate.
    previous_out = d.OUT
    d.OUT = d.ROOT / 'figures/systems'
    try:
        d.export(fig, 'fig_signal_consequences')
    finally:
        d.OUT = previous_out

if __name__ == '__main__':
    render()
