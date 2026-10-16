from pathlib import Path
import subprocess,sys,csv
root=Path(__file__).resolve().parents[1]
for suite in ['numerical','engineering','event_audit']:
 subprocess.run([sys.executable,'-m','unittest','discover','-s',suite,'-p','test*.py'],cwd=root,check=True)
for name,count in [('case_summary.csv',45),('engineering_all_135_pairs.csv',135),('engineering_all_270_runs.csv',270)]:
 with (root/'paper/source_data'/name).open(encoding='utf-8-sig') as f:assert len(list(csv.DictReader(f)))==count
print('All suites and published-table row counts passed.')
