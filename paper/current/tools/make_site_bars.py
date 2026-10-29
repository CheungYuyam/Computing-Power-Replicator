"""Author-selected horizontal bars with light blue/red fills.

All absolute site values and three-seed min/max retained. Bar axes start at
zero. The 32% palette tints match the visual strength of candidate C.
Times New Roman is retained for manuscript consistency.
"""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from audit_panel_alignment import require_matplotlib_panel_alignment
ROOT=Path(__file__).resolve().parents[1]

def render(root=ROOT):
    root=Path(root);out=root/'figures/systems'
    qa=root/'qa/fig04_light_bars_20261027';qa.mkdir(parents=True,exist_ok=True)
    with (root/'source_data/site_metrics.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    lookup={(r['date'],int(r['seed']),r['arm'],int(r['site'])):r for r in rows}
    assert len(rows)==len(lookup)==108
    dates=['2020-07-27','2020-08-05','2020-08-21'];labels=['Jul 27','Aug 5','Aug 21']
    colors=['#B1C6DF','#EDB8BA']
    data=np.zeros((2,3,2,3,6))
    for m,(metric,factor) in enumerate([('node_utilization_snapshot_mean',100),('queue_snapshot_peak',.001)]):
        for d,date in enumerate(dates):
            for a,arm in enumerate(['fixed','reported']):
                for j,seed in enumerate([17,29,43]):
                    data[m,d,a,j]=[float(lookup[(date,seed,arm,s)][metric])*factor for s in range(6)]
    means=data.mean(axis=3);low=data.min(axis=3);high=data.max(axis=3)
    plt.rcParams.update({'font.family':'Times New Roman','font.size':8,
        'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':8,
        'legend.fontsize':8,'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6})
    fig,axes=plt.subplots(2,3,figsize=(7.1,4.65))
    fig.subplots_adjust(left=.075,right=.985,bottom=.13,top=.86,hspace=.55,wspace=.34)
    fig.legend(handles=[Patch(facecolor=c,label=l) for c,l in zip(colors,['Fixed allocation','Proposed model'])],
        loc='upper center',bbox_to_anchor=(.52,.995),ncol=2,columnspacing=2)
    for m in range(2):
        for d in range(3):
            ax=axes[m,d];ax.set_title(f'({"abcdef"[m*3+d]}) {labels[d]}',loc='left',pad=7)
            ax.set_yticks(range(6),[f'Site {s}' for s in range(6)]);ax.set_ylim(5.6,-.6)
            ax.set_xlabel(['Node occupancy (%)','Peak queue (10³ tasks)'][m],labelpad=4)
            ax.tick_params(axis='y',length=0,pad=4);ax.spines['left'].set_visible(False)
            ax.grid(axis='x',color='#E8E8E8',lw=.5,zorder=0)
            for a,c in enumerate(colors):
                vals=means[m,d,a];ys=np.arange(6)+(a-.5)*.31
                ax.barh(ys,vals,height=.27,color=c,zorder=2)
                ax.errorbar(vals,ys,xerr=[vals-low[m,d,a],high[m,d,a]-vals],fmt='none',
                    ecolor='#555555',elinewidth=.6,capsize=1.6,zorder=3)
            ax.set_xlim(0,105 if m==0 else float(high[m,d].max())*1.08)
            if m==0:ax.set_xticks([0,25,50,75,100])
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig,json_out=str(qa/'alignment.json'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(out/'fig_site_constraints.pdf',facecolor='white')
    fig.savefig(out/'fig_site_constraints.svg',facecolor='white')
    fig.savefig(out/'fig_site_constraints.png',dpi=600,facecolor='white')
    plt.close(fig)
    (qa/'contract.json').write_text(json.dumps({'source_rows':108,'displayed_means':int(means.size),'exclusions':0,'values':'absolute operating values','interval':'three-seed min/max','palette':colors,'bar_origin':0,'font_exception':'Times New Roman manuscript consistency'},indent=2),encoding='utf-8')

if __name__=='__main__':render()
