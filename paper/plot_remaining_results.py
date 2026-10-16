"""Reproduce complete remaining-results panels from saved experiment summaries."""
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'figures/redesigned'; DATA=ROOT/'source_data'
for name in ('times.ttf','timesi.ttf','timesbd.ttf','timesbi.ttf'):
    if Path(str(Path('C:/Windows/Fonts')/name)).exists(): font_manager.fontManager.addfont(str(Path('C:/Windows/Fonts')/name))
plt.rcParams.update({'font.family':'Times New Roman','font.size':9,'mathtext.fontset':'custom','mathtext.rm':'Times New Roman','mathtext.it':'Times New Roman:italic','mathtext.bf':'Times New Roman:bold','pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6})
from portable_fonts import configure; configure()
COLORS=['#306998','#BB5735']
def save(fig,name):
    for ext in ['pdf','svg','png']:
        fig.savefig(OUT/f'{name}.{ext}',dpi=250,facecolor='white')
    plt.close(fig)
s=pd.read_csv(DATA/'case_summary.csv').set_index('case_id')
c=pd.read_csv(DATA/'contrasts.csv')
# Verify recorded terminal contrasts against independently stored case endpoints.
for _,r in c.iterrows():
    col=f'x0_type{r["type"]}_final'
    assert np.isclose(s.loc[r.case_id,col]-s.loc[r.reference_case,col],r.terminal_difference,atol=1e-10)
z=c.merge(s[['execution_scale','feedback_mean','execution_stages']],left_on='case_id',right_index=True)
for group,name,param,values,expected in [('E2_completion_payoff_approximation','fig_cost_comparisons','execution_scale',[.5,1,2],18)]:
    d=z[z.group==group].copy();assert len(d)==expected
    d.to_csv(DATA/f'{name}.csv',index=False)
    keys=[(v,t) for v in values for t in [0,.5,2]]
    labels=[rf'${"K" if param=="execution_stages" else "α"}={v:g},\quad\tau={t:g}$' for v,t in keys]
    fig,axes=plt.subplots(1,2,figsize=(7.16,2.45 if len(keys)==6 else 2.65),sharey=True)
    fig.subplots_adjust(left=.18,right=.985,bottom=.20,top=.74,wspace=.25)
    for ax,metric,title in zip(axes,['max_abs_path_difference','terminal_difference'],['(a) Largest gap over 0–80','(b) Difference at t = 80']):
        title_x = .015 if ax is axes[0] else ax.get_position().x0
        fig.text(title_x, ax.get_position().y1 + .045, title, ha='left', va='bottom', fontsize=9)
        for typ,label,col,offset in [(0,'Short tasks',COLORS[0],-.12),(1,'Long tasks',COLORS[1],.12)]:
            vals=[float(d[(d[param]==v)&(d.feedback_mean==t)&(d.type==typ)][metric].iloc[0])*100 for v,t in keys]
            ax.scatter(vals,np.arange(len(keys))+offset,s=30,color=col,marker='o' if typ==0 else 's',label=label,zorder=3)
        ax.axvline(0,color='#555555',lw=.7);ax.grid(axis='x',color='#dddddd',lw=.5)
        ax.set_yticks(range(len(keys)),labels);ax.set_ylim(len(keys)-.5,-.5);ax.tick_params(axis='y',length=0)
        for y in np.arange(2.5,len(keys)-1,3): ax.axhline(y,color='#cccccc',lw=.6)
        ax.set_xlabel('Assignment difference (percentage points)')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.55,.982),ncol=2,frameon=False,handlelength=1.6,columnspacing=1.5)
    save(fig,name)
from plot_stage_count import plot_stage_count
plot_stage_count()
source=DATA/'repeats_fdd26d2c7684'
p=pd.read_csv(source/'matrix_pairs.csv');r=pd.read_csv(source/'matrix_results.csv')
keys=['date','seed','feedback_delay_s','admission_period_s']
assert len(p)==135 and not p.duplicated(keys).any() and len(r)==270
assert p.pre_intervention_identical.all() and p.common_event_draws_equal.all()
assert np.allclose(p.post_observation_hours,24)
# Verify completion deltas from the individual runs.
a=r[r.incentive].set_index(keys);b=r[~r.incentive].set_index(keys)
for _,row in p.iterrows():
    key=tuple(row[k] for k in keys)
    assert a.loc[key,'completed_all']-b.loc[key,'completed_all']==row.completed_all_on_minus_off
p.to_csv(DATA/'engineering_all_135_pairs.csv',index=False)
r.to_csv(DATA/'engineering_all_270_runs.csv',index=False)
dates=sorted(p.date.unique());seeds=sorted(p.seed.unique());settings=[(tc,ta) for tc in [0,900,3600] for ta in [0,150,300]]
index=p.set_index(keys)
rows=[(date,seed) for date in dates for seed in seeds]
def matrix(col):
    return np.array([[index.loc[(date,seed,tc,ta),col] for tc,ta in settings] for date,seed in rows],dtype=float)
def heat_axes(ax,full=True):
    ax.set_xticks(range(9),[str(ta) for tc,ta in settings],fontsize=8)
    ax.set_xlabel(r'Admission period $T_a$ (s)',labelpad=5)
    ax.set_yticks(range(15),[str(seed) for date,seed in rows],fontsize=8)
    ax.set_ylabel('Seed',labelpad=3)
    ax.set_xticks(np.arange(-.5,9,1),minor=True);ax.set_yticks(np.arange(-.5,15,1),minor=True)
    ax.grid(which='minor',color='white',linewidth=.5);ax.tick_params(which='both',length=0)
    for x in [2.5,5.5]: ax.axvline(x,color='#777777',lw=1)
    for y in [4.5,9.5]: ax.axhline(y,color='#777777',lw=1)
    for x,tc in [(1,0),(4,900),(7,3600)]: ax.text(x,1.025,rf'$T_c={tc}$ s',transform=ax.get_xaxis_transform(),ha='center',va='bottom',fontsize=8)
    if full:
        for y,date in zip([2,7,12],['Aug. 1','Aug. 18','Aug. 31']):
            ax.text(.015,y,date,transform=blended_transform_factory(ax.figure.transFigure, ax.transData),ha='left',va='center',fontsize=9)
lag=matrix('site0_first_interval_start_hour')-12
observed=matrix('site0_observed_difference').astype(bool)
assert observed.sum()==37 and ((lag<2)&observed).sum()==3
fig,ax=plt.subplots(figsize=(7.16,3.50));fig.subplots_adjust(left=.20,right=.87,bottom=.16,top=.88)
cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#eeeeee')
im=ax.imshow(np.ma.masked_where(~observed,lag),aspect='auto',cmap=cmap,vmin=0,vmax=24)
heat_axes(ax)
for y in range(15):
    for x in range(9):
        if observed[y,x]:
            val=lag[y,x];ax.text(x,y,f'{val:.2f}',ha='center',va='center',fontsize=8,color='white' if val>12 else '#222222')
            if val<2:ax.add_patch(Rectangle((x-.46,y-.46),.92,.92,fill=False,ec='#BB5735',lw=1.5))
        else:ax.text(x,y,'—',ha='center',va='center',color='#999999',fontsize=8)
cax=fig.add_axes([.90,.19,.018,.65]);cb=fig.colorbar(im,cax=cax);cb.set_label('Hours after incentive onset')
save(fig,'fig_response_all_seeds')
# Keep Figure 10 on the dedicated capped-color-scale renderer.
import runpy
runpy.run_path(str(ROOT/'plot_energy_all_seeds.py'), run_name='__main__')
print('Verified and exported four figures; 9 stage settings, 9 cost, 135 engineering comparisons.')
