"""Plot all initial-progress contrasts from verified saved results."""
from pathlib import Path
import csv, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures/redesigned'
def read(name):
    with (ROOT/'source_data'/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))
summary={r['case_id']:r for r in read('case_summary.csv')}
rows=[r for r in read('contrasts.csv') if r['group']=='E3_execution_inventory']
assert len(rows)==6
export=[]
for r in rows:
    case,ref=summary[r['case_id']],summary[r['reference_case']]
    for key in ('execution_scale','feedback_mean','initial_strategy0_fraction','execution_stages'):
        assert case[key]==ref[key]
    assert float(case['execution_scale'])==1 and float(case['initial_strategy0_fraction'])==.5
    key='x0_type'+r['type']+'_final'
    assert abs(float(case[key])-float(ref[key])-float(r['terminal_difference']))<1e-12
    export.append(dict(case_id=r['case_id'],reference_case=r['reference_case'],tau=float(case['feedback_mean']),task_group='Short tasks' if r['type']=='0' else 'Long tasks',maximum_gap_pp=100*float(r['max_abs_path_difference']),endpoint_difference_pp=100*float(r['terminal_difference'])))
with (ROOT/'source_data/initial_progress_changes.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=export[0]);w.writeheader();w.writerows(export)
for name in ('times.ttf','timesi.ttf','timesbd.ttf','timesbi.ttf'):
    if Path(str(Path('C:/Windows/Fonts')/name)).exists(): font_manager.fontManager.addfont(str(Path('C:/Windows/Fonts')/name))
plt.rcParams.update({'font.family':'Times New Roman','font.size':8.5,'mathtext.fontset':'custom','mathtext.rm':'Times New Roman','mathtext.it':'Times New Roman:italic','mathtext.bf':'Times New Roman:bold','pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65})
from portable_fonts import configure; configure()
fig,axes=plt.subplots(2,1,figsize=(3.48,3.65),sharex=True)
fig.subplots_adjust(left=.17,right=.985,bottom=.125,top=.81,hspace=.65)
x=np.arange(3);width=.32
colors=['#306998','#BB5735']
for ax,metric,title in zip(axes,('maximum_gap_pp','endpoint_difference_pp'),('(a) Largest separation over 0–80','(b) Difference at t = 80')):
    ax.set_axisbelow(True);ax.grid(axis='y',color='#e8e8e8',linewidth=.5)
    ax.axhline(0,color='#555555',linewidth=.65)
    for k,group in enumerate(('Short tasks','Long tasks')):
        values=[next(r[metric] for r in export if r['task_group']==group and r['tau']==tau) for tau in (0,.5,2)]
        bars=ax.bar(x+(k-.5)*width,values,width,color=colors[k],label=group,edgecolor='white',linewidth=.5,hatch=None if k==0 else '///')
        for bar,v in zip(bars,values):
            ax.text(bar.get_x()+width/2,v+(.12 if metric=='maximum_gap_pp' else .055)*(1 if v>=0 else -1),f'{v:.2f}' if metric=='maximum_gap_pp' else f'{v:+.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=8)
    fig.text(.015, ax.get_position().y1 + .035, title,
             ha='left', va='bottom', fontsize=9)
    ax.set_ylabel('Percentage points',fontsize=8.5)
    ax.tick_params(length=3,width=.65,pad=3)
axes[0].set_ylim(0,7);axes[0].set_yticks([0,2,4,6])
axes[1].set_ylim(-1.85,1.85);axes[1].set_yticks([-1.5,0,1.5])
axes[1].set_xticks(x,['0','0.5','2']);axes[1].set_xlabel(r'Mean report delay $\tau$',labelpad=4)
fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.982),ncol=2,frameon=False,handlelength=1.6,columnspacing=1.5)
for ext in ('pdf','svg','png'):
    fig.savefig(OUT/f'fig_initial_progress.{ext}',dpi=320,facecolor='white')
print(json.dumps(export,indent=2))
