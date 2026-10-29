"""Render Figures 2-7 from bundled inputs without replacing approved exports."""
from pathlib import Path
import argparse, shutil, subprocess, sys

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--out',type=Path,default=root/'runs/current_figures')
args=parser.parse_args();out=args.out.resolve()
if out.exists() and any(out.iterdir()):raise SystemExit('Choose a new or empty output directory.')
for folder in ['tools','source_data']:
    shutil.copytree(root/'paper/current'/folder,out/folder,dirs_exist_ok=True)
for folder in ['figures/systems','figures/redesigned','qa/figures','qa/user_palette_20261027']:
    (out/folder).mkdir(parents=True,exist_ok=True)
for name in ['make_controlled_cost_figure.py','make_joint_outcome_matrix.py','make_site_bars.py','make_joint_system_figures.py','make_signal_figure.py','make_event_figure.py']:
    print('Rendering',name,flush=True)
    subprocess.run([sys.executable,str(out/'tools'/name)],cwd=out,check=True)
print('Rendered figures:',out/'figures')
