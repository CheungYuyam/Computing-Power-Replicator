"""Author-selected signed matrix. Frozen paired outcomes; no data exclusions."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch,Rectangle
from matplotlib.lines import Line2D
from matplotlib.colors import to_rgb
from audit_panel_alignment import require_matplotlib_panel_alignment
from make_joint_outcomes import ROOT,DATES,SETTINGS,METRICS,signed


def render(root=ROOT):
    ROOT=Path(root)
    OUT=ROOT/'figures/systems'
    QA=ROOT/'qa/user_palette_20261027'
    source=json.loads((ROOT/'source_data/joint_outcome_pairs.json').read_text(encoding='utf-8'))
    assert len(source)==27
    COLORS=['#C72228','#F98F34','#0C4E9B']
    LABELS=['Uniform / Synchronous','Uniform / Staggered','Proportional / Staggered']
    means=np.zeros((3,3,4));low=means.copy();high=means.copy()
    for d,date in enumerate(DATES):
        for s,(setting,*_) in enumerate(SETTINGS):
            rows=[r for r in source if r['date']==date and r['initialization']==setting]
            assert sorted(r['seed'] for r in rows)==[17,29,43]
            for m,(key,factor,*_) in enumerate(METRICS):
                values=np.array([r[key+'_delta']*factor for r in rows])
                means[d,s,m]=values.mean();low[d,s,m]=values.min();high[d,s,m]=values.max()
    assert np.isfinite(means).all()
    plt.rcParams.update({'font.family':'Times New Roman','font.size':8,
        'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,
        'legend.fontsize':8,'legend.frameon':False,'pdf.fonttype':42,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65})
    # B: exact signed results in an orderly matrix. Color is scaled per metric.
    fig,ax=plt.subplots(figsize=(7.1,3.9))
    fig.subplots_adjust(left=.29,right=.985,bottom=.13,top=.88)
    date_gap=.38
    ax.set_xlim(0,4);ax.set_ylim(9+2*date_gap,0);ax.set_axis_off()
    vmax=np.max(np.abs(means),axis=(0,1))
    def brief(v):
        if v==0:return '0'
        if abs(v)<.005:return f'{v:.4f}'.replace('-','−')
        if abs(v)<.1:return f'{v:.3f}'.replace('-','−')
        if abs(v)<1:return f'{v:.2f}'.replace('-','−')
        return f'{v:.1f}'.replace('-','−')
    for d in range(3):
        for s in range(3):
            y=d*(3+date_gap)+s
            ax.text(-.10,y+.5,['Synchronous','Staggered','Proportional'][s],ha='right',va='center',fontsize=8,color=COLORS[s])
            for m in range(4):
                v=means[d,s,m]
                base=np.array(to_rgb('#C72228' if v>0 else '#0C4E9B'))
                strength=.08+.60*abs(v)/vmax[m] if v else 0
                fill=tuple(1-strength*(1-base))
                ax.add_patch(Rectangle((m,y),1,1,facecolor=fill,edgecolor='white',lw=1.6))
                ax.text(m+.5,y+.35,signed(v),ha='center',va='center',fontsize=9,color='#111111')
                ax.text(m+.5,y+.73,f'[{brief(low[d,s,m])}, {brief(high[d,s,m])}]',ha='center',va='center',fontsize=6.5,color='#333333')
        ax.text(-.91,d*(3+date_gap)+1.5,['Jul 27','Aug 5','Aug 21'][d],ha='center',va='center',fontsize=9,fontweight='bold')
    for m,(title,unit) in enumerate(zip(['Completion','Mean Waiting','IT Energy','Generation Cost'],['48 h · pp','72-h cutoff · min','24–48 h · MWh','24–48 h · currency'])):
        ax.text(m+.5,-.55,title,ha='center',va='bottom',fontsize=9)
        ax.text(m+.5,-.17,unit,ha='center',va='bottom',fontsize=7,color='#555555')
    fig.text(.5,.072,'Cell: Mean [Min, Max] across Three Seeds   ·   Blue: Decrease   ·   Red: Increase',ha='center',fontsize=7.3)
    fig.text(.5,.028,'Color intensity is scaled separately within each metric.',ha='center',fontsize=7,color='#555555')
    fig.canvas.draw()
    require_matplotlib_panel_alignment(fig, json_out=str(QA/'matrix_alignment.json'), tolerance_pt=1.5, strict=True)
    fig.savefig(OUT/'fig_joint_outcomes.pdf',facecolor='white')
    fig.savefig(OUT/'fig_joint_outcomes.svg',facecolor='white')
    fig.savefig(OUT/'fig_joint_outcomes.png',facecolor='white',dpi=600)
    plt.close(fig)
    (QA/'matrix_data_contract.json').write_text(json.dumps({'paired_runs':len(source),'aggregates':int(means.size),'excluded':0,'interval':'seed minimum-maximum','color_scale':'independent within metric','font_exception':'Times New Roman matches manuscript'},indent=2),encoding='utf-8')


if __name__=='__main__':
    render()
