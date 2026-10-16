from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent / "figure_times_r1"))
from redesign import *
HERE=Path(__file__).resolve().parent / "source_data"
def event(out):
 p=HERE/'event_chain_table.csv';track(p);rs=rows(p);assert len(rs)==4
 fig=plt.figure(figsize=(WIDTH,4.45))

 fields=['first_changed_report_delivery','first_probability_difference_at_revision','first_threshold_strategy_difference','first_routed_task_start']
 names=['Report available','Probability differs','Strategy differs','Next task starts','Power interval']
 colors=[BLUE,BLUE,ORANGE,TEAL,BLUE]
 stamp=lambda s:s.replace('次日 ','D+1 ')
 for i,row in enumerate(rs):
  c=i%2;rr=i//2;left=.14+c*.49;bottom=.68-rr*.49
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
  title=f"({chr(97+i)}) "+('Aug. 1' if i==0 else 'Aug. 31')+f"  |  $T_c={row['communication_s']}$ s; $T_a={row['admission_s']}$ s"
  fig.text(.015+c*.49,bottom+.29,title,fontsize=9,ha='left')
  fig.text(.04+c*.49,bottom+.255,f"Strategy-to-start wait: {float(row['revision_to_next_start_seconds']):g} s",fontsize=7.2,color=ORANGE)
  # The full-clock diamond is a locator, not a widened duration. The separate
  # strip shows the true 300-s interval at an explicitly expanded clock scale.
  zoom=fig.add_axes([left,bottom-.105,.28,.035])
  zoom.set(xlim=(a-60/3600,b+60/3600),ylim=(-.6,.8),yticks=[],xticks=[a,b],xticklabels=[stamp(row['first_power_bin_start'])[:-3],stamp(row['first_power_bin_end']).replace('D+1 ','')[:-3]])
  zoom.axvspan(a,b,facecolor='#D6F6FF',edgecolor='none')
  zoom.plot([a,b],[0,0],color=BLUE,lw=3,marker='|',ms=8,mew=1.2)
  zoom.plot(ts[3],.45,marker='s',ms=4,mfc=TEAL,mec='white',mew=.5,zorder=5)
  zoom.vlines(ts[3],0,.45,color=TEAL,lw=.8)
  zoom.tick_params(axis='x',labelsize=6.8,length=0,pad=4)
  for spine in zoom.spines.values():spine.set_visible(False)
  fig.text(.04+c*.49,bottom-.066,'Power interval: 5-min detail',fontsize=7,color=BLUE)
 fig.text(.04,.010,'Main clock: hours; D+1: next day. Lower strip: five-minute power interval; square: next task start.',fontsize=6.8,color=GRAY)
 save(fig,out,'fig05_event_chain');AUDIT['coverage']['fig05']=4

event(Path(__file__).resolve().parent / "figures/redesigned")
