"""Read-only restyling of five existing manuscript figures; no simulator imports."""
from pathlib import Path
import argparse,csv,hashlib,json,os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.colors import Normalize,LinearSegmentedColormap
ROOT=Path('./data/original-layout')
HERE=Path(__file__).resolve().parent
from font_config import configure
BLUE='#04579B';ORANGE='#519D78';TEAL='#3492B2';INK='#233544';GRAY='#73818B';GRID='#E2E7EA'
COLORS=[BLUE,ORANGE,TEAL];STYLES=['solid',(0,(5,2)),(0,(1.2,1.5))]
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':8,'axes.labelsize':8,'axes.titlesize':9,'axes.titleweight':'bold','xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':8,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':GRAY,'axes.linewidth':.65,'xtick.color':INK,'ytick.color':INK,'text.color':INK,'axes.labelcolor':INK,'pdf.fonttype':42,'svg.fonttype':'none','path.simplify':False,'savefig.facecolor':'white'})
configure()
# Dimensions are final manuscript widths; no bounding-box crop changes them.
WIDTH=7.2
AUDIT={'sources':{},'coverage':{},'ranges':{},'exclusions':0,'new_simulations':0}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def track(p):AUDIT['sources'][str(p)]=sha(p)
def save(fig,out,name):
 fig.savefig(out/(name+'.pdf'))
 fig.savefig(out/(name+'.svg'))
 fig.savefig(out/(name+'.png'),dpi=400)
 plt.close(fig)
def basic(ax):
 ax.tick_params(length=3,width=.65,pad=3);ax.grid(axis='y',color=GRID,lw=.5,zorder=-5)
def label(ax,letter,title):
 ax.set_title(title,loc='left',pad=9);ax.text(-.10,1.07,letter,transform=ax.transAxes,fontweight='bold',fontsize=10)
def schematic(out):
 fig,ax=plt.subplots(figsize=(WIDTH,2.55));fig.subplots_adjust(left=.015,right=.985,top=.98,bottom=.04)
 ax.set(xlim=(0,100),ylim=(0,34));ax.axis('off')
 def box(x,y,w,h,title,detail,col,fill):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.35,rounding_size=.65',facecolor=fill,edgecolor=col,lw=.9))
  ax.text(x+1.4,y+h-2.3,title,fontsize=8.5,fontweight='bold',va='top',color=col)
  ax.text(x+1.4,y+2.0,detail,fontsize=7.8,va='bottom',linespacing=1.3)
 def arrow(a,b,col=GRAY,rad=0):
  ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,lw=1.1,color=col,connectionstyle=f'arc3,rad={rad}',shrinkA=0,shrinkB=0))
 ax.text(0,32.5,'Task execution generates opportunities and evidence',fontsize=9,fontweight='bold',color=INK)
 box(.5,17,22,11,'Task execution','Progress + cost history',BLUE,'#D6F6FF')
 box(29,17,19,11,'Completion','Revision opportunity',BLUE,'#D6F6FF')
 box(60,17,18,11,'Revision','Compare costs',INK,'#F4F6F7')
 box(83,17,16,11,'Next task','Admission\nthen power',TEAL,'#E9F7E5')
 arrow((23,22.5),(28.5,22.5),BLUE);arrow((48.5,22.5),(59.5,22.5),BLUE);arrow((78.5,22.5),(82.5,22.5),TEAL)
 box(28.5,1.3,21,10,'Completed report','Accumulated task cost',ORANGE,'#CEEFCC')
 box(59,1.3,21,10,'Visible evidence','Delivery + retention',ORANGE,'#CEEFCC')
 arrow((38.5,16.7),(38.5,11.7),ORANGE);arrow((50,6.3),(58.5,6.3),ORANGE);arrow((69,11.7),(69,16.5),ORANGE)
 # Physical feedback returns through subsequent execution, separate from cost transport.
 ax.plot([91,91,11.5,11.5],[28.5,30,30,28.5],lw=.9,color=TEAL)
 arrow((11.5,30),(11.5,28.5),TEAL)
 ax.text(10.5,8.2,'Task state',color=BLUE,fontsize=8,ha='center',fontweight='bold')
 ax.text(10.5,4.3,'Information state',color=ORANGE,fontsize=8,ha='center',fontweight='bold')
 save(fig,out,'fig01_mechanism');AUDIT['coverage']['fig01']='Conceptual diagram; no quantitative marks'
def matrix(out):
 p=HERE/'matrix_pairs.csv';track(p);rs=rows(p);assert len(rs)==27
 fig,axs=plt.subplots(1,3,figsize=(WIDTH,2.65),sharey=True)
 fig.subplots_adjust(left=.105,right=.98,top=.78,bottom=.30,wspace=.15)
 cmap=LinearSegmentedColormap.from_list('onset',[BLUE,'#3492B2','#6FC8CA','#E9F7E5']);norm=Normalize(0,24)
 dates=['2020-08-01','2020-08-18','2020-08-31'];covered=[]
 for ax,lag in zip(axs,[0,900,3600]):
  for y,day in enumerate(dates):
   for x,admit in enumerate([0,150,300]):
    row=[r for r in rs if r['date']==day and int(r['feedback_delay_s'])==lag and int(r['admission_period_s'])==admit];assert len(row)==1
    row=row[0];observed=row['site0_observed_difference']=='True';v=float(row['site0_first_interval_start_hour'])-12 if observed else None
    if observed:assert 0<=v<=24
    face=cmap(norm(v)) if observed else '#F6F7F8'
    ax.add_patch(Rectangle((x-.46,y-.43),.92,.86,facecolor=face,edgecolor=INK if observed and v<2 else 'white',lw=1.1,hatch=None if observed else '///'))
    text=f'{v:.2f}' if observed else 'NR';color='white' if observed and v<8 else INK
    ax.text(x,y,text,ha='center',va='center',fontsize=9.5,color=color,fontweight='bold' if observed and v<2 else 'normal')
    covered.append((day,lag,admit))
  ax.set(xlim=(-.5,2.5),ylim=(2.55,-.6),xticks=[0,1,2],xticklabels=['0','150','300'],yticks=[0,1,2],yticklabels=['Aug. 1','Aug. 18','Aug. 31'])
  ax.set_title(f'Communication {lag} s',pad=11);ax.tick_params(length=0,pad=5)
  for spine in ax.spines.values():spine.set_visible(False)
 fig.text(.54,.195,'Admission period (s)',ha='center',fontsize=8)
 cax=fig.add_axes([.24,.075,.37,.035]);cb=fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cax,orientation='horizontal',ticks=[0,6,12,18,24]);cb.outline.set_visible(False);cb.ax.tick_params(length=2,labelsize=7)
 fig.text(.425,.135,'First differing interval after signal onset (h)',ha='center',fontsize=7.5)
 fig.text(.69,.075,'NR: no difference observed\nwithin 24 h',fontsize=7.5,va='center',linespacing=1.4)
 fig.text(.105,.94,'Response timing across all 27 seed-17 pairs',fontsize=10,fontweight='bold')
 save(fig,out,'fig04_response_matrix');assert len(set(covered))==27;AUDIT['coverage']['fig04']=27
def hour(s):
 offset=24 if s.startswith('次日 ') else 0
 h,m,sec=map(int,s.replace('次日 ','').split(':'));return offset+h+m/60+sec/3600

def event(out):
 p=HERE/'event_chain_table.csv';track(p);rs=rows(p);assert len(rs)==4
 fig=plt.figure(figsize=(WIDTH,6.0))

 fields=['first_changed_report_delivery','first_probability_difference_at_revision','first_threshold_strategy_difference','first_routed_task_start']
 names=['Report available','Probability differs','Strategy differs','Next task starts','Power interval']
 colors=[BLUE,BLUE,ORANGE,TEAL,BLUE]
 stamp=lambda s:s.replace('次日 ','D+1 ')
 for i,row in enumerate(rs):
  c=i%2;rr=i//2;left=.14+c*.49;bottom=.65-rr*.45
  ax=fig.add_axes([left,bottom,.22,.23])
  ax.set(xlim=(11.8,29.5),ylim=(-.65,4.65),xticks=[12,18,24],xticklabels=['12:00','18:00','D+1 00:00'],yticks=range(5),yticklabels=names[::-1])
  ax.tick_params(axis='y',length=0,pad=5,labelsize=7);ax.tick_params(axis='x',length=2,pad=4,labelsize=6.7)
  ax.spines['left'].set_visible(False);ax.grid(axis='x',color=GRID,lw=.5)
  ax.axvspan(12,14,color='#E9F7E5',zorder=-5)
  for j in range(5):ax.axhline(4-j,color=GRID,lw=.5,zorder=-4)
  ts=[hour(row[k]) for k in fields]
  assert all(b>=a for a,b in zip(ts,ts[1:]))
  assert abs((ts[3]-ts[2])*3600-float(row['revision_to_next_start_seconds']))<1e-8
  for j,k in enumerate(fields):
   ax.plot(ts[j],4-j,'o',color=colors[j],ms=4.5)
   ax.text(1.06,4-j,stamp(row[k]),transform=ax.get_yaxis_transform(),va='center',fontsize=7.2,color=colors[j])
  a,b=hour(row['first_power_bin_start']),hour(row['first_power_bin_end'])
  assert abs((b-a)*3600-300)<1e-8 and a<=ts[3]<b
  ax.plot([a,b],[0,0],lw=2.4,color=BLUE,solid_capstyle='butt')
  ax.plot((a+b)/2,0,marker='D',ms=5.5,mfc='#D6F6FF',mec=BLUE,mew=1.1,zorder=5)
  time_label=stamp(row['first_power_bin_start'])[:-3]+'–'+stamp(row['first_power_bin_end']).replace('D+1 ','')[:-3]
  ax.text(1.06,0,time_label,transform=ax.get_yaxis_transform(),va='center',fontsize=7.1,color=BLUE)
  title=f"{chr(97+i)}  "+('Aug. 1' if i==0 else 'Aug. 31')+f"  |  $T_c={row['communication_s']}$ s; $T_a={row['admission_s']}$ s"
  fig.text(.04+c*.49,bottom+.29,title,fontsize=8,fontweight='bold')
  fig.text(.04+c*.49,bottom+.262,f"Strategy-to-start wait: {float(row['revision_to_next_start_seconds']):g} s",fontsize=7.2,color=ORANGE)
  # The full-clock diamond is a locator, not a widened duration. The separate
  # strip shows the true 300-s interval at an explicitly expanded clock scale.
  zoom=fig.add_axes([left,bottom-.09,.28,.035])
  zoom.set(xlim=(a-60/3600,b+60/3600),ylim=(-.6,.8),yticks=[],xticks=[a,b],xticklabels=[stamp(row['first_power_bin_start'])[:-3],stamp(row['first_power_bin_end']).replace('D+1 ','')[:-3]])
  zoom.axvspan(a,b,facecolor='#D6F6FF',edgecolor='none')
  zoom.plot([a,b],[0,0],color=BLUE,lw=3,marker='|',ms=8,mew=1.2)
  zoom.plot(ts[3],.45,marker='s',ms=4,mfc=TEAL,mec='white',mew=.5,zorder=5)
  zoom.vlines(ts[3],0,.45,color=TEAL,lw=.8)
  zoom.tick_params(axis='x',labelsize=6.8,length=0,pad=4)
  for spine in zoom.spines.values():spine.set_visible(False)
  fig.text(.04+c*.49,bottom-.055,'Power interval: 5-min detail',fontsize=7,color=BLUE)
 fig.text(.04,.042,'Diamond: power-interval location. Lower strip: expanded 5-min interval; square: next task start.',fontsize=6.8,color=GRAY)
 fig.text(.04,.020,'Common main clock; D+1: next day. Earliest evidence markers can involve different businesses.',fontsize=6.8,color=GRAY)
 save(fig,out,'fig05_event_chain');AUDIT['coverage']['fig05']=4

def remote_inputs():
 source=ROOT/'experiments/replicator_evolution_v1r2/runs/82cee51de58e';verified=ROOT/'experiments/replicator_evolution_finalize_r1/runs/f0e323454239'
 assert read(verified/'status.json')['stage']=='complete' and all(read(verified/'integrity_checks.json').values())
 hashes=read(source/'trajectory_hashes_server_only.json');macro={}
 for cid in ['evolution_019','evolution_033']:
  p=source/(cid+'_trajectory_server_only.npz');assert sha(p)==hashes[p.name];track(p)
  with np.load(p,allow_pickle=False) as z:macro[cid]={k:z[k].copy() for k in ['time','strategy','completion','visible_cost','transfers']}
  assert len(macro[cid]['time'])==1601 and macro[cid]['time'][0]==0 and macro[cid]['time'][-1]==80
 run=ROOT/'experiments/replicator_engineering_matrix_v1/runs/af8249830c8b';p=run/'matrix_results.csv';track(p)
 assert read(run/'status.json')['stage']=='complete' and all(read(run/'integrity_checks.json').values())
 expected=read(HERE/'sources.json')['matrix_results_sha256'];assert sha(p)==expected
 selected=[r for r in rows(p) if r['date']=='2020-08-31' and r['incentive']=='False'];assert len(selected)==9
 eng={};origins=[]
 for row in selected:
  p=Path(row['source_run'])/row['source_case_id']/'trace_server_only.npz';assert p.is_relative_to(ROOT/'experiments')
  assert sha(p)==read(p.parent/'trace_sha256.json')[p.name];track(p)
  with np.load(p,allow_pickle=False) as z:trace={str(c):z['values'][:,i].copy() for i,c in enumerate(z['columns'])}
  assert len(trace['interval_start'])==576 and np.array_equal(trace['interval_start'],np.arange(576)*300)
  assert np.array_equal(trace['interval_end'],trace['state_sample_time'])
  assert int(trace['completed'][-1])==int(row['completed_all'])
  eng[(int(row['feedback_delay_s']),int(row['admission_period_s']))]=trace;origins.append(row['source_case_id'])
 assert set(eng)=={(l,a) for l in [0,900,3600] for a in [0,150,300]}
 return macro,eng

def macro_figure(out,traces):
 fig=plt.figure(figsize=(WIDTH,4.05));gs=fig.add_gridspec(2,3,height_ratios=[1.2,1],left=.095,right=.98,bottom=.13,top=.87,wspace=.40,hspace=.60)
 hero=fig.add_subplot(gs[0,:]);lower=[fig.add_subplot(gs[1,j]) for j in range(3)]
 for cid,col,ls,name in [('evolution_019',BLUE,'solid','Accumulated task cost'),('evolution_033',ORANGE,(0,(5,2)),'Completion-time approximation')]:
  z=traces[cid];t=z['time'];x=z['strategy'][:,0];f=z['completion'][:,0];c=z['visible_cost'][:,0]
  flow=(f[:,1]*x[:,0]*np.clip(.2*(c[:,1]-c[:,0]),0,1)-f[:,0]*x[:,1]*np.clip(.2*(c[:,0]-c[:,1]),0,1))/.5
  balance=np.max(abs(.5*(x[:,0]-x[0,0])-(z['transfers'][:,0,1]-z['transfers'][:,0,0])));assert balance<1e-7
  hero.plot(t,x[:,0],color=col,ls=ls,lw=1.6,label=name)
  for ax,v in zip(lower,[f.sum(axis=1),c[:,0]-c[:,1],flow]):ax.plot(t,v,color=col,ls=ls,lw=1.35)
 hero.set(ylim=(.45,1),ylabel='Site-0 share',xticks=[0,20,40,60,80]);label(hero,'a','Strategy evolution')
 for ax,letter,title,ylabel in zip(lower,'bcd',['Completion opportunities','Visible cost ranking','Strategy transfer'],['Completion flow',r'$\hat c_0-\hat c_1$',r'$\dot x_0$']):
  label(ax,letter,title);ax.set(ylabel=ylabel,xlabel='Time',xticks=[0,40,80])
 for ax in [hero]+lower:ax.set_xlim(0,80);basic(ax)
 for ax in lower[1:]:ax.axhline(0,color=GRAY,lw=.8,zorder=-3)
 fig.legend(*hero.get_legend_handles_labels(),loc='upper right',bbox_to_anchor=(.98,.995),ncol=2,frameon=False)
 fig.text(.095,.975,'Type 0  |  '+r'$\alpha=2,\ \tau=0$',fontsize=8,va='top')
 fig.text(.98,.02,'Original dimensionless time; all saved samples retained',ha='right',fontsize=7,color=GRAY)
 save(fig,out,'fig02_cost_formation');AUDIT['coverage']['fig02']={'cases':2,'samples_each':1601,'all_four_variables':True}

def engineering(out,traces):
 fig,axes=plt.subplots(3,3,figsize=(WIDTH,5.15),sharex=True,sharey='row');fig.subplots_adjust(left=.105,right=.985,bottom=.12,top=.80,wspace=.20,hspace=.20)
 shares=np.concatenate([.5*(z['strategy0_type0']+z['strategy0_type1']) for z in traces.values()]);lo=max(0,np.floor((shares.min()-.02)*20)/20);hi=min(1,np.ceil((shares.max()+.02)*20)/20)
 pmax=max(z['site0_mw'].max() for z in traces.values());cmax=max(z['completed'].max() for z in traces.values())
 for col,lag in enumerate([0,900,3600]):
  for j,admit in enumerate([0,150,300]):
   z=traces[(lag,admit)];state=z['state_sample_time']/3600-12;edges=np.r_[z['interval_start'][0],z['interval_end']]/3600-12
   axes[0,col].step(state,.5*(z['strategy0_type0']+z['strategy0_type1']),where='post',color=COLORS[j],ls=STYLES[j],lw=1.35,label=f'{admit} s')
   axes[1,col].stairs(z['site0_mw'],edges,baseline=None,color=COLORS[j],ls=STYLES[j],lw=1.15)
   axes[2,col].step(state,z['completed'],where='post',color=COLORS[j],ls=STYLES[j],lw=1.35)
  axes[0,col].set_title(f'{chr(97+col)}  Communication {lag} s',loc='left',pad=13)
  for row in range(3):
   ax=axes[row,col];ax.axvspan(12,14,color='#E9F7E5',alpha=.65,zorder=-6);ax.set_xlim(-12,36);ax.set_xticks([-12,0,12,24,36]);basic(ax)
  axes[0,col].set_ylim(lo,hi);axes[1,col].set_ylim(0,pmax*1.08);axes[2,col].set_ylim(0,cmax*1.06)
  axes[2,col].set_xlabel('Measurement-day hour')
 for ax,text in zip(axes[:,0],['Site-0 strategy share','Site-0 power (MW)','Completed tasks']):ax.set_ylabel(text,labelpad=7)
 fig.text(.105,.975,'From preferences to executed work',fontsize=10,fontweight='bold',va='top')
 fig.text(.105,.933,'Aug. 31  |  Incentive off  |  Seed 17',fontsize=8,color=GRAY,va='top')
 fig.legend(*axes[0,0].get_legend_handles_labels(),loc='upper right',bbox_to_anchor=(.985,.955),title='Admission period',ncol=3,frameon=False,title_fontsize=8,handlelength=2.8,columnspacing=1.3)
 fig.text(.105,.027,'Shaded: 12–14 h reference. States: interval ends. Power: interval averages.',fontsize=7,color=GRAY)
 save(fig,out,'fig03_engineering_paths');AUDIT['coverage']['fig03']={'cases':9,'samples_each':576,'time_hours':[-12,36]};AUDIT['ranges']['fig03_share']=[float(lo),float(hi)]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--local',action='store_true');ap.add_argument('--preflight',action='store_true');args=ap.parse_args();out=Path(args.out)
 if args.preflight:
  a,b=remote_inputs();print(json.dumps({'macro_cases':len(a),'engineering_cases':len(b),'sources':len(AUDIT['sources'])}));return
 out.mkdir(parents=True,exist_ok=True)
 if not args.local:
  assert os.name=='posix' and out.resolve().is_relative_to(ROOT/'experiments/figure_times_r1/runs')
  assert not any(out.iterdir()),'Refusing overwrite of remote outputs'
  write(out/'status.json',{'stage':'drawing','new_simulations':0})
 for fn in [schematic,matrix,event]:fn(out)
 if not args.local:
  macro,eng=remote_inputs();macro_figure(out,macro);engineering(out,eng)
 assert all(sha(p)==h for p,h in AUDIT['sources'].items())
 manifest={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.suffix in ['.pdf','.svg','.png']}
 checks={'sources_unchanged':True,'all_requested_exports':len(manifest)==(9 if args.local else 15),'no_excluded_rows':AUDIT['exclusions']==0,'no_simulations':True,'matrix_27':AUDIT['coverage']['fig04']==27,'event_4':AUDIT['coverage']['fig05']==4,'fixed_timestamp_checks':True}
 assert all(checks.values())
 write(out/'figure_manifest.json',manifest);write(out/'integrity_checks.json',checks);write(out/'provenance.json',AUDIT);write(out/'status.json',{'stage':'complete','figures':3 if args.local else 5,'exports':len(manifest),'new_simulations':0})
 print(json.dumps({'stage':'complete','exports':len(manifest)}))
if __name__=='__main__':main()
