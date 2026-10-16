"""Plot observed assignment fractions for all nine stage-count settings."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def plot_stage_count():
    root=Path(__file__).resolve().parent
    for font in ('times.ttf','timesi.ttf','timesbd.ttf','timesbi.ttf'):
        if Path(str(Path('C:/Windows/Fonts')/font)).exists(): font_manager.fontManager.addfont(str(Path('C:/Windows/Fonts')/font))
    plt.rcParams.update({'font.family':'Times New Roman','font.size':9,
        'mathtext.fontset':'custom','mathtext.rm':'Times New Roman',
        'mathtext.it':'Times New Roman:italic','mathtext.bf':'Times New Roman:bold',
        'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,
        'axes.spines.right':False,'axes.linewidth':.6})
    from portable_fonts import configure; configure()
    s=pd.read_csv(root/'source_data/case_summary.csv')
    d=s[(s.execution_scale==1)&(s.initial_strategy0_fraction==.5)
        &s.accumulated_payoff&(s.initial_history=='fresh')
        &s.group.isin(['E1_time_and_initial_share','E4_duration_shape'])].copy()
    assert len(d)==9 and not d.duplicated(['execution_stages','feedback_mean']).any()
    assert set(zip(d.execution_stages,d.feedback_mean))=={(k,t) for k in [1,2,4] for t in [0,.5,2]}
    cols=['case_id','execution_scale','initial_strategy0_fraction','execution_stages',
          'feedback_mean','x0_type0_final','x0_type1_final']
    d[cols].sort_values(['execution_stages','feedback_mean']).to_csv(root/'source_data/fig_stage_count.csv',index=False)
    fig=plt.figure(figsize=(7.16,2.45))
    palette=['#04579B','#3492B2','#519D78']
    axes=[]
    for typ,left in enumerate([.085,.585]):
        ax=fig.add_axes([left,.315,.385,.425])
        base=fig.add_axes([left,.205,.385,.065],sharex=ax)
        axes.append(ax)
        title='Short tasks' if typ==0 else 'Long tasks'
        fig.text(.015 if typ==0 else .515,.785,
                 f'({chr(97+typ)}) {title}',ha='left',va='bottom',fontsize=9)
        for offset,(tau,color) in enumerate(zip([0,.5,2],palette)):
            a=d[d.feedback_mean==tau].sort_values('execution_stages')
            vals=a[f'x0_type{typ}_final'].to_numpy()*100
            assert np.all((vals>=0)&(vals<=100))
            for part in (ax,base):
                part.bar(np.arange(3)+(offset-1)*.245,vals,width=.215,
                         color=color,edgecolor='white',linewidth=.45,
                         label=rf'$\tau={tau:g}$',zorder=3)
        ax.set_ylim((86,89) if typ==0 else (69,72))
        ax.set_yticks([86,87,88,89] if typ==0 else [69,70,71,72])
        ax.set_ylabel('Site-0 assignment (%)',labelpad=7)
        ax.yaxis.set_label_coords(-.135,.34)
        ax.set_axisbelow(True)
        ax.grid(axis='y',color='#E2E7EA',lw=.5)
        ax.spines['bottom'].set_visible(False)
        ax.tick_params(axis='x',which='both',bottom=False,labelbottom=False)
        ax.tick_params(axis='y',length=2.5,width=.6,pad=3)
        base.set_ylim(0,1)
        base.set_yticks([0])
        base.set_xticks(np.arange(3),['1','2','4'])
        base.set_xlim(-.55,2.55)
        base.set_xlabel(r'Stage count $K$',labelpad=4)
        base.tick_params(length=2.5,width=.6,pad=3)
        # Explicit breaks separate the zero baseline from the enlarged upper range.
        for part,y in ((ax,0),(base,1)):
            part.plot([-.013,.013],[y-.025,y+.025],transform=part.transAxes,
                      color='#233544',lw=.75,clip_on=False)
    fig.legend(*axes[0].get_legend_handles_labels(),
               loc='upper center',bbox_to_anchor=(.55,1.005),
               title=r'Mean report delay $\tau$',ncol=3,frameon=False,
               handlelength=1.35,handleheight=.8,columnspacing=2.0)
    for ext in ('pdf','svg','png'):
        fig.savefig(root/f'figures/redesigned/fig_stage_count.{ext}',dpi=300,facecolor='white')
    plt.close(fig)
    print('Verified and plotted grouped bars of absolute assignment fractions: 9 settings, 2 task groups.')

if __name__=='__main__':
    plot_stage_count()
