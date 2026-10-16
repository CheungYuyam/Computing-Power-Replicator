from pathlib import Path
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
def configure():
 for p in Path('C:/Windows/Fonts').glob('times*.ttf'):
  fm.fontManager.addfont(str(p))
 names={f.name for f in fm.fontManager.ttflist}
 family=next((n for n in ['Times New Roman','Liberation Serif','DejaVu Serif'] if n in names),'DejaVu Serif')
 plt.rcParams.update({'font.family':family,'mathtext.fontset':'custom','mathtext.rm':family,'mathtext.it':family+':italic','mathtext.bf':family+':bold','pdf.fonttype':42,'svg.fonttype':'none'})
 return family
