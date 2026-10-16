"""Plot all matched report-delay endpoint contrasts; no new simulations."""
from pathlib import Path
import csv, json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib import font_manager
from matplotlib.transforms import blended_transform_factory

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'figures/redesigned'
OUT.mkdir(parents=True, exist_ok=True)
with (ROOT / 'source_data/report_delay_all_27.csv').open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 27
lookup = {(float(r['alpha']), float(r['p']), float(r['tau'])): r for r in rows}
assert len(lookup) == 27
pairs = [(a,p) for a in (0.5,1,2) for p in (0.2,0.5,0.8)]
derived = []
matrices = []
for group in ('short','long'):
    matrix = np.zeros((9,2))
    for row,(alpha,p) in enumerate(pairs):
        base = lookup[alpha,p,0]
        for col,tau in enumerate((0.5,2)):
            case = lookup[alpha,p,tau]
            key = group + '_site0_percent'
            delta = float(case[key]) - float(base[key])
            matrix[row,col] = delta
            derived.append(dict(group=group,alpha=alpha,p=p,tau=tau,baseline_case=base['case_id'],delayed_case=case['case_id'],baseline_percent=base[key],delayed_percent=case[key],change_percentage_points=delta))
    matrices.append(matrix)
with (ROOT/'source_data/report_delay_changes.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=derived[0].keys()); writer.writeheader(); writer.writerows(derived)
for filename in ('times.ttf', 'timesi.ttf', 'timesbd.ttf', 'timesbi.ttf'):
    if Path(str(Path('C:/Windows/Fonts') / filename)).exists(): font_manager.fontManager.addfont(str(Path('C:/Windows/Fonts') / filename))
plt.rcParams.update({
    'font.family': 'Times New Roman', 'font.size': 9,
    'mathtext.fontset': 'custom', 'mathtext.rm': 'Times New Roman',
    'mathtext.it': 'Times New Roman:italic',
    'mathtext.bf': 'Times New Roman:bold', 'mathtext.fallback': None,
    'axes.titlesize': 10, 'axes.labelsize': 9,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    'savefig.facecolor': 'white',
})
from portable_fonts import configure; configure()
cmap=LinearSegmentedColormap.from_list('delay_change',['#306998','#f7f7f7','#bb5735'])
norm=TwoSlopeNorm(vmin=-2.5,vcenter=0,vmax=2.5)
fig,axes=plt.subplots(1,2,figsize=(7.05,3.0))
fig.subplots_adjust(left=.115,right=.845,bottom=.055,top=.80,wspace=.52)
labels=[]
alignment_columns=[]
for idx,(ax,values,title) in enumerate(zip(axes,matrices,('Short tasks','Long tasks'))):
    image=ax.imshow(values,cmap=cmap,norm=norm,aspect='auto',interpolation='nearest')
    pos = ax.get_position()
    title_x = .015 if idx == 0 else pos.x0 - .30 * pos.width
    fig.text(title_x, .925, f'({chr(97+idx)}) {title}', ha='left', va='bottom', fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
    # All column headings share one baseline; each numeric column has a fixed x.
    row_transform = blended_transform_factory(ax.transAxes, ax.transData)
    for x, heading, numbers in (
        (-.255, r'$\alpha$', [a for a,p in pairs]),
        (-.10, r'$p$', [p for a,p in pairs]),
    ):
        column = [ax.text(x, 1.045, heading, transform=ax.transAxes,
                          ha='center', va='bottom')]
        column.extend(ax.text(x, row, f'{value:g}', transform=row_transform,
                              ha='center', va='center')
                      for row,value in enumerate(numbers))
        alignment_columns.append(column)
    for x, heading in ((.25, r'$\tau=0.5$'), (.75, r'$\tau=2$')):
        ax.text(x, 1.045, heading, transform=ax.transAxes,
                ha='center', va='bottom')
    for boundary in (2.5,5.5): ax.axhline(boundary,color='#555555',lw=.6)
    ax.set_xticks([-.5,.5,1.5],minor=True)
    ax.set_yticks(np.arange(-.5,9,.1)[::10],minor=True)
    ax.grid(which='minor',color='white',linewidth=.6); ax.tick_params(which='minor',length=0)
    for spine in ax.spines.values(): spine.set_visible(False)
    for row in range(9):
        for col in range(2):
            value=values[row,col]
            text=('+' if value>0 else '\N{MINUS SIGN}')+'<0.01' if 0<abs(value)<.005 else f'{value:+.2f}'.replace('-','\N{MINUS SIGN}')
            if value==0: text='0.00'
            labels.append(ax.text(col,row,text,ha='center',va='center',fontsize=9,color='white' if abs(value)>1.65 else '#202020'))
cax=fig.add_axes([.885,.10,.018,.65])
cb=fig.colorbar(image,cax=cax,ticks=[-2,-1,0,1,2])
cb.set_label('Change in site-0 share (percentage points)',labelpad=7)
cb.outline.set_visible(False)
fig.canvas.draw()
renderer=fig.canvas.get_renderer()
for text in fig.findobj(matplotlib.text.Text):
    if not text.get_visible() or not text.get_text():
        continue
    box=text.get_window_extent(renderer)
    assert fig.bbox.contains(box.x0,box.y0) and fig.bbox.contains(box.x1,box.y1), text.get_text()
for column in alignment_columns:
    centers=[(t.get_window_extent(renderer).x0+t.get_window_extent(renderer).x1)/2 for t in column]
    assert max(centers)-min(centers)<0.01, centers
print('Verified Times New Roman text, four aligned parameter columns, and text bounds.')
fig.savefig(OUT/'fig_delay_changes.pdf')
fig.savefig(OUT/'fig_delay_changes.svg')
fig.savefig(OUT/'fig_delay_changes.png',dpi=600)
plt.close(fig)
assert len(derived)==36
assert len({r['baseline_case'] for r in derived}|{r['delayed_case'] for r in derived})==27
print(json.dumps({'scenarios':27,'contrasts':36,'minimum_pp':min(r['change_percentage_points'] for r in derived),'maximum_pp':max(r['change_percentage_points'] for r in derived)}))
