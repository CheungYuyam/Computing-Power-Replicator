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
# Rebuild only Figure 10 from the verified 135-pair summary.
p=pd.read_csv(DATA/'engineering_all_135_pairs.csv')
keys=['date','seed','feedback_delay_s','admission_period_s']
assert len(p)==135 and not p.duplicated(keys).any()
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
fig,axes=plt.subplots(1,2,figsize=(7.16,3.65),sharey=True)
fig.subplots_adjust(left=.15,right=.985,bottom=.24,top=.84,wspace=.18)
for k,(ax,col,title) in enumerate(zip(axes,['site0_post_signed_mwh','total_power_post_signed_mwh'],['(a) Site-0 energy','(b) Total energy'])):
    vals=matrix(col); vals[np.abs(vals)<1e-7]=0
    bounds=np.arange(-5,1,1) if k==0 else np.arange(0,11,2)
    palette=plt.get_cmap('YlGnBu')
    shades=palette(np.linspace(.08,.78,5))
    cmap=colors.ListedColormap(shades[::-1] if k==0 else shades)
    cmap.set_under(palette(.99)); cmap.set_over(palette(.99))
    cmap.set_bad(palette(0))
    norm=colors.BoundaryNorm(bounds,cmap.N)
    im=ax.imshow(np.ma.masked_where(vals==0,vals),aspect='auto',cmap=cmap,norm=norm)
    heat_axes(ax,full=(k==0))
    fig.text(.015 if k==0 else ax.get_position().x0,.95,title,ha='left',va='bottom',fontsize=9)
    if k==1: ax.set_ylabel('')
    for y in range(15):
        for x in range(9):
            val=vals[y,x]
            if val!=0:
                text=f'{val:.1f}' if abs(val)>=.1 else (f'{val:.3f}' if abs(val)>=.001 else f'{val:.0e}')
                if k==1: text+='*'
                rgb=cmap(norm(val))[:3]
                luminance=sum(v*w for v,w in zip(rgb,[.2126,.7152,.0722]))
                ax.text(x,y,text,ha='center',va='center',fontsize=6.4,color='white' if luminance<.48 else '#111111')
            else:
                ax.text(x,y,'·',ha='center',va='center',fontsize=7,color='#999999')
    pos=ax.get_position()
    cax=fig.add_axes([pos.x0,.105,pos.width,.022])
    cb=fig.colorbar(im,cax=cax,orientation='horizontal',ticks=bounds,spacing='uniform',extend='min' if k==0 else 'max')
    labels=[f'{v:g}' for v in bounds]
    labels[0 if k==0 else -1]='≤ −5' if k==0 else '≥ 10'
    cb.ax.set_xticklabels(labels)
    cb.set_label('On − off (MWh)',fontsize=8)
    cb.ax.tick_params(labelsize=8)
save(fig,'fig_energy_all_seeds')
print('Figure 10 exported; data unchanged; capped discrete YlGnBu color scales.')
