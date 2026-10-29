"""Figure 7 candidates from frozen paired event records; no event selection changes."""
from pathlib import Path
import json, sys, hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'figure7_options_20261028'
OUT.mkdir(exist_ok=True)
from audit_panel_alignment import require_matplotlib_panel_alignment
SOURCE = ROOT/'source_data/same_stream_events.json'
EVENTS = json.loads(SOURCE.read_text(encoding='utf-8'))
BLUE, RED, ORANGE = '#6B98C4', '#F5867F', '#FFBC80'
plt.rcParams.update({'font.family':'Times New Roman','font.size':8,
 'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':8,
 'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
 'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,
 'axes.linewidth':.6,'legend.frameon':False,'savefig.dpi':300})
DATES=['Jul 27','Aug 5','Aug 21']

def values(e,status):
    dec=e['first_assignment_change'][status]['time']
    task=e['same_stream_next_task_'+status]
    ready=max(dec,task['release_s'])
    start=task['start_s']
    assert dec<=ready<=start
    return [(v-129600)/3600 for v in (dec,ready,start)]

def export(fig,name,multi=False):
    fig.canvas.draw()
    if multi:
        require_matplotlib_panel_alignment(fig,json_out=str(OUT/(name+'.alignment.json')),
            tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    for ext in ['pdf','svg','png']:
        fig.savefig(OUT/(name+'.'+ext),facecolor='white')
    plt.close(fig)

def base(ax,limit):
    ax.axvspan(0,2,color='#FFF0E1',zorder=0)
    ax.set_xlim(-.15,limit)
    ax.tick_params(axis='y',length=0,pad=5)
    ax.set_xlabel('Hours after signal onset')

def path(ax,e,status,y,stages=False):
    d,r,s=values(e,status)
    col=BLUE if status=='off' else RED
    if stages:
        ax.barh(y,r-d,left=d,height=.24,color=ORANGE,zorder=2)
        ax.barh(y,s-r,left=r,height=.24,color=BLUE,zorder=2)
        ax.plot(d,y,marker='D',ms=3.2,color='#555555',zorder=4)
        ax.plot(s,y,marker='>',ms=4.3,color='#555555',zorder=5)
    else:
        ax.plot([d,r],[y,y],ls=(0,(1.3,1.5)),lw=1.7,color=col)
        ax.plot([r,s],[y,y],lw=2.2,color=col)
        ax.plot(d,y,marker='D',ms=4,color=col,zorder=4)
        ax.plot(s,y,marker='>',ms=4.8,color=col,zorder=5)

def grouped(stages=False):
    fig,ax=plt.subplots(figsize=(3.42,3.65))
    fig.subplots_adjust(left=.23,right=.97,bottom=.15,top=.79)
    base(ax,11.7)
    ys=[6.1,5.35,3.65,2.9,1.2,.45]
    for i,e in enumerate(EVENTS):
        for j,status in enumerate(['off','on']):path(ax,e,status,ys[2*i+j],stages)
        ax.text(-.24,ys[2*i]+.53,DATES[i],fontsize=8.4,fontweight='bold',ha='left',va='center',transform=ax.get_yaxis_transform())
    ax.set_ylim(-.25,6.85)
    ax.set_yticks(ys,['Off','On']*3)
    ax.set_xticks([0,2,4,6,8,10])
    ax.text(1,6.78,'Signal',ha='center',va='top',fontsize=7,color='#875E39')
    if stages:
        handles=[Patch(facecolor=ORANGE,label='Release wait'),Patch(facecolor=BLUE,label='Resource wait')]
    else:
        handles=[Line2D([],[],color='#777777',ls=':',lw=1.5,label='Release wait'),Line2D([],[],color='#777777',lw=2,label='Resource wait')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.53,.995),ncol=2,fontsize=7.5,columnspacing=1,handlelength=1.4)
    fig.legend(handles=[Line2D([],[],color='#555555',marker='D',ls='',ms=3.3,label='Assignment'),Line2D([],[],color='#555555',marker='>',ls='',ms=4,label='Task start')],loc='upper center',bbox_to_anchor=(.53,.925),ncol=2,fontsize=7.5,columnspacing=1.5,handlelength=1)
    export(fig,'B_waiting_stages' if stages else 'A_paired_timeline')

def zoomed(name='C_local_time_scales'):
    fig,axes=plt.subplots(3,1,figsize=(3.42,4.0))
    fig.subplots_adjust(left=.19,right=.96,bottom=.12,top=.84,hspace=.95)
    for i,(ax,e,limit) in enumerate(zip(axes,EVENTS,[3,12,5.5])):
        base(ax,limit)
        for status,y in [('off',1),('on',0)]:path(ax,e,status,y)
        ax.set_ylim(-.55,1.55)
        ax.set_yticks([1,0],['Off','On'])
        ax.set_title(f'({chr(97+i)}) {DATES[i]}',loc='left',pad=6,fontsize=8.5)
        ax.set_xlabel('')
        ax.set_xticks([0,1,2,3] if i==0 else ([0,2,4,6,8,10,12] if i==1 else [0,1,2,3,4,5]))
    axes[-1].set_xlabel('Hours after signal onset')
    fig.legend(handles=[Line2D([],[],color='#777777',ls=':',lw=1.5,label='Release wait'),Line2D([],[],color='#777777',lw=2,label='Resource wait')],loc='upper center',bbox_to_anchor=(.54,1),ncol=2,fontsize=7.5)
    fig.legend(handles=[Line2D([],[],color='#555555',marker='D',ls='',ms=3.3,label='Assignment'),Line2D([],[],color='#555555',marker='>',ls='',ms=4,label='Task start')],loc='upper center',bbox_to_anchor=(.54,.94),ncol=2,fontsize=7.5)
    export(fig,name,True)

if __name__=='__main__':
    grouped();grouped(True);zoomed()
    (OUT/'provenance.json').write_text(json.dumps({'source':str(SOURCE),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'events':[{ 'date':e['date'],'off':values(e,'off'),'on':values(e,'on')} for e in EVENTS],'axis_note':'A/B common 0–11.7 h; C explicitly uses different per-panel ranges. All six paths retained. Bars start at assignment, never at signal onset. Zero-length stages retained as zero.'},indent=2),encoding='utf-8')
