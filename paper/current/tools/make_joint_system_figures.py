"""Editable system interfaces and a prespecified joint trajectory; frozen data only."""
from pathlib import Path
import csv, gzip, hashlib, json, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.path import Path as MPath
from audit_panel_alignment import require_matplotlib_panel_alignment

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'source_data/trajectory'
OUT = ROOT / 'figures/systems'
DATA = ROOT / 'source_data'
QA = ROOT / 'qa/figures'
BLUE = '#0C4E9B'
ORANGE = '#F98F34'
GRAY = '#777777'
plt.rcParams.update({'font.family':'Times New Roman','font.size':8.5,'axes.titlesize':9,
 'axes.labelsize':8.5,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
 'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','legend.frameon':False,
 'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,'lines.linewidth':1.1})

def save(fig,name,panels=False):
    fig.canvas.draw()
    if panels:
        require_matplotlib_panel_alignment(fig,json_out=str(QA/f'{name}.alignment.json'),
          overlay_svg=str(QA/f'{name}.alignment.svg'),tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True)
    fig.savefig(OUT/f'{name}.pdf',facecolor='white')
    fig.savefig(OUT/f'{name}.svg',facecolor='white')
    fig.savefig(OUT/f'{name}.png',facecolor='white',dpi=600)
    svg=OUT/f'{name}.svg'
    # Matplotlib's standard SVG 1.1 external DTD is unnecessary for this standalone asset.
    svg_text=re.sub(r'<!DOCTYPE[^>]*>\s*','',svg.read_text(encoding='utf-8'))
    # Equivalent SVG presentation attribute in viewBox units; avoids treating a CSS px
    # inside the point-scaled viewBox as an unscaled physical pixel in downstream audits.
    def explicit_font(match):
        style,tail=match.group(1),match.group(2)
        size=re.search(r'font-size:\s*([\d.]+)px;?\s*',style)
        if not size:return match.group(0)
        return '<text font-size="'+size.group(1)+'" style="'+style[:size.start()]+style[size.end():]+'"'+tail+'>'
    svg_text=re.sub(r'<text style="([^"]*)"([^>]*)>',explicit_font,svg_text)
    svg.write_text(svg_text,encoding='utf-8')
    plt.close(fig)

def render_legacy_architecture():
    # Four interfaces in a closed loop; separate completion and information returns.
    fig=plt.figure(figsize=(7.1,3.35))
    ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,7.1);ax.set_ylim(0,3.35);ax.axis('off')
    def label(x,y,text,gid,size=8.5,color='#222222',weight='normal',ha='center'):
        t=ax.text(x,y,text,ha=ha,va='center',fontsize=size,color=color,fontweight=weight,
                  linespacing=1.25);t.set_gid(gid);return t
    def box(x,y,w,h,name,body,gid,highlight=False):
        p=Rectangle((x,y),w,h,facecolor='#F1F6F9' if highlight else '#F6F6F6',
                    edgecolor=BLUE if highlight else '#999999',lw=1)
        p.set_gid(gid);ax.add_patch(p)
        label(x+w/2,y+h-.19,name,gid+'-title',9,BLUE if highlight else '#222222','bold')
        label(x+w/2,y+.32,body,gid+'-body')
    def arrow(points,gid,color=GRAY):
        path=MPath(points,[MPath.MOVETO]+[MPath.LINETO]*(len(points)-1))
        p=FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=8,lw=.9,color=color)
        p.set_gid(gid);ax.add_patch(p)
    box(.20,2.04,2.27,.86,'Assignment controller',
        'Received costs + current shares\nChoose the next task’s site', 'assignment-controller',True)
    box(4.63,2.04,2.27,.86,'Computing sites',
        'Release + resource admission\nNonpreemptive task execution', 'computing-sites')
    box(.20,.62,2.27,.86,'Accumulated-cost reports',
        'Completed-task charges + waiting\nSettlement and delivery delay', 'accumulated-reports',True)
    box(4.63,.62,2.27,.86,'Electrical operation',
        'Bus loads + background demand\nDispatch and interval settlement', 'electrical-operation')
    arrow([(2.47,2.38),(4.63,2.38)],'next-assignment',BLUE)
    label(3.55,2.62,'Assign next tasks','assignment-label')
    arrow([(5.75,2.90),(5.75,3.08),(1.34,3.08),(1.34,2.90)],'completion-return',BLUE)
    label(3.55,3.25,'Task completion: next assignment opportunity','completion-label',size=8.5)
    arrow([(5.75,2.04),(5.75,1.48)],'physical-load')
    label(5.87,1.76,'Site loads','load-label',ha='left')
    arrow([(4.63,1.02),(2.47,1.02)],'settled-energy-price')
    label(3.55,1.25,'Settled prices','settlement-label')
    arrow([(4.63,2.14),(4.18,2.14),(4.18,1.69),(2.72,1.69),(2.72,1.29),(2.47,1.29)],
          'task-execution-records')
    label(3.45,1.87,'Task energy + waiting','execution-records-label')
    arrow([(1.34,1.48),(1.34,2.04)],'received-reports',BLUE)
    label(1.47,1.76,'Received reports','report-label',ha='left')
    label(3.55,.30,'Joint assessment from the same execution records','assessment-title',9,weight='bold')
    label(3.55,.08,'Task completion and waiting   |   Site occupancy and queues   |   Bus demand and grid dispatch',
          'assessment-outputs',8.5)
    save(fig,'fig_system_architecture')



# First date, first seed, staggered reference case; never select by outcome.
def loadtrace(arm):
    path=STUDY/'001'/arm/'trace.jsonl.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f: rows=[json.loads(s) for s in f]
    return path,[r for r in rows if 24*3600<=r['start_s']<48*3600]
pa,a=loadtrace('reported');pb,b=loadtrace('fixed')
assert len(a)==len(b)==288
assert all((x['start_s'],x['end_s'])==(y['start_s'],y['end_s']) for x,y in zip(a,b))
metrics=json.loads((STUDY/'case_metrics.json').read_text(encoding='utf-8'))
case=next(r for r in metrics if r['case']=='001/reported')
assert case['date']=='2020-07-27' and case['seed']==17 and case['phase']=='stagger'
points=[];cum=0.
for x,y in zip(a,b):
    dt=(x['end_s']-x['start_s'])/3600
    cum+=(x['generation_cost_per_h']-y['generation_cost_per_h'])*dt
    row={'start_h':x['start_s']/3600,'end_h':x['end_s']/3600}
    for k,name in enumerate(['cpu','gpu']):
        row[f'{name}_small_share_delta_pp']=100*sum(x['shares'][k][i]-y['shares'][k][i] for i in [0,3])
    for name,idx in [('small',[0,3]),('other',[1,2,4,5])]:
        row[f'{name}_queue_delta']=sum(x['waiting_by_site'][i]-y['waiting_by_site'][i] for i in idx)
        row[f'{name}_power_delta_mw']=sum(x['power_mw'][i]-y['power_mw'][i] for i in idx)
    row['cumulative_generation_cost_delta']=cum
    points.append(row)
with (DATA/'joint_trajectory.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(points[0]));w.writeheader();w.writerows(points)
source={'selection':{'bundle':'001','date':case['date'],'seed':case['seed'],'phase':case['phase'],
                    'arms':['reported','fixed'],'signal':'off','hours':[24,48]},
        'sources':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [pa,pb]],
        'definitions':{'shares':'sum at sites 0 and 3 within each class; percentage point difference',
                       'queue':'sum of endpoint waiting_by_site within groups',
                       'power':'sum of interval-average site power within groups',
                       'generation_cost':'cumulative difference in generation_cost_per_h * interval hours; excludes tariff transfers'},
        'end_generation_cost_difference':cum,'rows':len(points)}
# Independent reconciliation to the frozen summary, using the matched arm metrics.
ref=next(r for r in metrics if r['case']=='001/fixed')
expected=case['evaluation_generation_cost']-ref['evaluation_generation_cost']
assert abs(cum-expected)<1e-6,(cum,expected)
source['summary_reconciliation']={'from_intervals':cum,'from_frozen_metrics':expected,'tolerance':1e-6}
source['final_endpoint']=points[-1]
source['service_differences']={k:case[k]-ref[k] for k in
    ['completion_eval_fraction','restricted_wait_s','evaluation_it_mwh']}
source['case_metric_keys']=list(case.keys())
(DATA/'joint_trajectory_provenance.json').write_text(json.dumps(source,indent=2),encoding='utf-8')

t=np.array([r['end_h'] for r in points]);get=lambda key:np.array([r[key] for r in points])
# User-approved palette: light blue/red for paired traces, deep red for grid total.
TRACE_BLUE = '#6B98C4'
TRACE_RED = '#F5867F'
TOTAL_RED = '#C72228'
fig,axes=plt.subplots(2,2,figsize=(7.1,3.9))
fig.subplots_adjust(left=.10,right=.985,bottom=.12,top=.92,hspace=.64,wspace=.35)
for ax,title,letter in zip(axes.flat,
    ['Assignment share at sites 0 and 3','Queued tasks by site group','IT power by site group','Cumulative generation cost'],'abcd'):
    ax.set_title(f'({letter}) {title}',loc='left',pad=8)
    ax.set_xlim(24,48);ax.set_xticks([24,30,36,42,48]);ax.set_xlabel('Time (h)')
ax=axes[0,0]
ax.plot(t,get('cpu_small_share_delta_pp'),color=TRACE_BLUE,label='CPU-only',lw=1.25)
ax.plot(t,get('gpu_small_share_delta_pp'),color=TRACE_RED,label='GPU-requesting',lw=1.25)
ax.set_ylabel('Share difference (pp)');ax.legend(loc='upper right',ncol=2,columnspacing=1.1,handlelength=1.6)
ax=axes[0,1]
ax.plot(t,get('small_queue_delta')/1000,color=TRACE_BLUE,label='Sites 0 and 3',lw=1.25)
ax.plot(t,get('other_queue_delta')/1000,color=TRACE_RED,label='Other sites',lw=1.25)
ax.set_ylabel('Queue difference (10³ tasks)');ax.legend(loc='lower left',ncol=2,columnspacing=1.1,handlelength=1.6)
ax=axes[1,0]
ax.step(t,get('small_power_delta_mw'),where='pre',color=TRACE_BLUE,label='Sites 0 and 3',lw=1.25)
ax.step(t,get('other_power_delta_mw'),where='pre',color=TRACE_RED,label='Other sites',lw=1.25)
ax.set_ylabel('Power difference (MW)');ax.legend(loc='upper left',ncol=2,columnspacing=1.1,handlelength=1.6)
ax=axes[1,1]
ax.plot(np.r_[24,t],np.r_[0,get('cumulative_generation_cost_delta')],color=TOTAL_RED,lw=1.25)
ax.set_ylabel('Cost difference (currency)')
save(fig,'fig_joint_trajectory',panels=True)
print(json.dumps({'trajectory_points':len(points),'end_generation_cost_delta':cum,
                  'metric_keys':list(case.keys())}))
