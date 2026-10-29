"""Validate frozen code families separately and current evidence counts."""
from pathlib import Path
import csv, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
expected={'main':(34,212),'initialization':(9,36),'mechanisms':(9,72),'structure':(36,144)}
for family,(bundles,runs) in expected.items():
    folder=ROOT/'systems'/family
    files=sorted((folder/'protocols').glob('*.json'))
    assert len(files)==bundles,(family,len(files))
    assert sum(len(json.loads(p.read_text())['cases']) for p in files)==runs,family
    tests=[p.stem for p in sorted(folder.glob('test_*.py')) if p.stem!='test_grid' or os.environ.get('CP_RAW')]
    if not os.environ.get('CP_RAW'):print(f'{family}: external RTS test not run (CP_RAW unset)',flush=True)
    subprocess.run([sys.executable,'-m','unittest',*tests],cwd=folder,check=True)
data=ROOT/'paper/current/source_data'
assert len(json.loads((data/'joint_outcome_pairs.json').read_text()))==27
assert len(json.loads((data/'reported_signal_pairs.json').read_text()))==39
assert len(json.loads((data/'same_stream_events.json').read_text()))==3
with (data/'site_metrics.csv').open(encoding='utf-8-sig') as f:assert len(list(csv.DictReader(f)))==108
with (data/'system_supplement_20261024/structure_pairs.csv').open() as f:assert len(list(csv.DictReader(f)))==36
audit=json.loads((data/'same_rule_mechanisms_20261025/FINAL_AUDIT.json').read_text())
assert audit['status']=='PASS' and audit['cases']==72
print('Current code suites, frozen protocols, and compact evidence checks passed.')
