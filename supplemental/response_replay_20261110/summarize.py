"""Summarize all seeds within date; no pooling of replicated tasks."""
import csv, json
from pathlib import Path
from collections import defaultdict

root=Path(__file__).parent
rows=list(csv.DictReader((root/'results/results.csv').open(encoding='utf-8')))
groups=defaultdict(list)
for r in rows: groups[(r['case'].split('_')[1],r['representation'])].append(r)
fields=['window_target_mwh','window_other_mwh','window_system_mwh',
        'tail_target_mwh','tail_other_mwh','tail_system_mwh',
        'window_sitewise_absolute_discrepancy_mwh']
out=[]
for (date,mode),rs in sorted(groups.items()):
    assert len(rs)==3
    record={'date':date,'representation':mode,'seeds':len(rs)}
    for f in fields:
        v=[float(r[f]) for r in rs]
        record.update({f+'_mean':sum(v)/len(v),f+'_min':min(v),f+'_max':max(v)})
    out.append(record)
with (root/'results/date_summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader();w.writerows(out)
audits=json.loads((root/'results/audit.json').read_text())
error=max(v[a]['max_reconstruction_error_mw'] for v in audits.values() for a in ('on','off'))
lines=['Material Passport','Supplemental frozen-assignment replay, 2026-11-10',
       'Status: completed only if results/status.json confirms integrity gates.',
       f'Maximum original-power reconstruction discrepancy: {error:.12g} MW.',
       'All energy responses below are signal ON minus OFF. Negative means reduction.',
       'R = recorded execution, C = omit resource wait, A = also omit release wait.',
       'All nine date/seed pairs retained. Values are mean [min,max] over three seeds.',
       'These are timing ablations, not deployable policies or online predictions.','']
for r in out:
    lines.append(f"{r['date']} {r['representation']}")
    for f in fields:
        lines.append(f"  {f}: {r[f+'_mean']:.9g} [{r[f+'_min']:.9g}, {r[f+'_max']:.9g}]")
(root/'RESULTS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))
