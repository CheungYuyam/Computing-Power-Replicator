"""Replot the two frozen controlled trajectories, retaining every saved sample."""
from pathlib import Path
import hashlib, json, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from audit_panel_alignment import require_matplotlib_panel_alignment

R=Path(__file__).resolve().parents[1]
SOURCE=R/'source_data/controlled'
OUT=R/'figures/redesigned'
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman'],'font.size':8.5,
    'axes.titlesize':9,'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,
    'legend.fontsize':8,'mathtext.fontset':'custom','mathtext.rm':'Times New Roman',
    'mathtext.it':'Times New Roman:italic','mathtext.bf':'Times New Roman:bold',
    'pdf.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,
    'axes.spines.right':False,'axes.linewidth':.65,'legend.frameon':False})
fig=plt.figure(figsize=(7.1,3.25))
gs=fig.add_gridspec(2,3,height_ratios=[1.15,1],left=.09,right=.98,bottom=.12,
                      top=.78,wspace=.42,hspace=.85)
hero=fig.add_subplot(gs[0,:]);lower=[fig.add_subplot(gs[1,j]) for j in range(3)]
provenance=[]
source_rows=[]
series={}
for cid,style,method in [('evolution_019','-','Accumulated cost'),
    ('evolution_033','--','Completion-time approximation')]:
    path=SOURCE/(cid+'_trajectory_server_only.npz')
    with np.load(path,allow_pickle=False) as z:
        t=z['time']
        assert len(t)==1601 and t[0]==0 and t[-1]==80
        assert np.all(np.diff(t)>0)
        for group,color,name in [(0,'#6B98C4','Short tasks'),(1,'#F5867F','Long tasks')]:
            x=z['strategy'][:,group];f=z['completion'][:,group];c=z['visible_cost'][:,group]
            flow=(f[:,1]*x[:,0]*np.clip(.2*(c[:,1]-c[:,0]),0,1)
                 -f[:,0]*x[:,1]*np.clip(.2*(c[:,0]-c[:,1]),0,1))/.5
            assert np.max(abs(.5*(x[:,0]-x[0,0])-(z['transfers'][:,group,1]-z['transfers'][:,group,0])))<1e-7
            values=np.column_stack([x[:,0],f.sum(axis=1),c[:,0]-c[:,1],flow])
            assert np.isfinite(values).all()
            series[(method,name)]=values
            hero.plot(t,values[:,0],color=color,ls=style,lw=1.4)
            for ax,v in zip(lower,values[:,1:].T):
                ax.plot(t,v,color=color,ls=style,lw=1.2)
            source_rows.extend([method,name,float(tt),*map(float,v)] for tt,v in zip(t,values))
    provenance.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'samples':1601})
hero.set(ylim=(.45,1),ylabel='Site-0 share',xticks=[0,20,40,60,80])
for ax,letter,title in zip([hero]+lower,'abcd',
    ['Strategy evolution','Completion opportunities','Visible cost ranking','Strategy transfer']):
    ax.set_title(f'({letter}) {title}',loc='left',pad=8)
    ax.set_xlim(0,80);ax.tick_params(length=3,width=.65)
    ax.grid(axis='y',color='#E8E8E8',lw=.45);ax.set_axisbelow(True)
for ax,ylabel in zip(lower,['Completion flow',r'$\hat c_0-\hat c_1$',r'$\dot x_0$']):
    ax.set(ylabel=ylabel,xlabel='Time',xticks=[0,40,80])
for ax in lower[1:]:ax.axhline(0,color='#777777',lw=.65,zorder=0)
legend_handles=[Line2D([],[],color='#6B98C4',lw=1.4,label='Short tasks'),
    Line2D([],[],color='#F5867F',lw=1.4,label='Long tasks'),
    Line2D([],[],color='#444444',lw=1.4,label='Accumulated cost'),
    Line2D([],[],color='#444444',ls='--',lw=1.4,label='Completion-time approximation')]
fig.legend(handles=legend_handles,loc='upper center',bbox_to_anchor=(.54,1),ncol=4,columnspacing=1.2,handlelength=2.4,fontsize=8)
fig.text(.09,.91,r'$\alpha=2,\ \tau=0,\ p=0.5,\ K=2$',ha='left',va='top',fontsize=8.5)
fig.canvas.draw()
require_matplotlib_panel_alignment(fig,json_out=str(R/'qa/figures/fig02_cost_formation.alignment.json'),strict=True)
fig.savefig(OUT/'fig02_cost_formation.pdf',facecolor='white')
fig.savefig(OUT/'fig02_cost_formation.svg',facecolor='white')
fig.savefig(OUT/'fig02_cost_formation.png',dpi=600,facecolor='white')
(R/'qa/figures/controlled_cost_sources.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
with (OUT/'fig02_cost_formation_data.csv').open('w',newline='',encoding='utf-8') as fp:
    writer=csv.writer(fp)
    writer.writerow(['method','task_group','time','site0_share','completion_flow_total_population','received_cost_difference','site0_share_derivative'])
    writer.writerows(source_rows)
comparison={}
for name in ['Short tasks','Long tasks']:
    a=series[('Accumulated cost',name)];b=series[('Completion-time approximation',name)]
    opposite=(a[:,2]*b[:,2]<0)&(np.abs(a[:,2])>1e-6)&(np.abs(b[:,2])>1e-6)
    comparison[name]={'maximum_share_gap_pp':float(100*np.max(abs(a[:,0]-b[:,0]))),
        'final_share_accumulated':float(a[-1,0]),'final_share_approximation':float(b[-1,0]),
        'maximum_completion_gap':float(np.max(abs(a[:,1]-b[:,1]))),
        'opposite_cost_ranking_time_range':[float(t[opposite][0]),float(t[opposite][-1])] if opposite.any() else None}
(R/'qa/figures/fig02_group_comparison.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8')
print(json.dumps(comparison,indent=2))
print('Four curves per panel; all 1601 samples per curve retained.')
