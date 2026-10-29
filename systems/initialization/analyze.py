"""Paired system-wide response metrics; retain null/censored outcomes."""
import gzip
import json
from pathlib import Path
import numpy as np


def read(path):
    with gzip.open(path,'rt',encoding='utf-8') as f: return [json.loads(line) for line in f]


def compare(off,on,pulse,off_summary,on_summary):
    if len(off)!=len(on) or any(a['start_s']!=b['start_s'] or a['end_s']!=b['end_s'] for a,b in zip(off,on)):
        raise ValueError('Paired time axes differ')
    t=np.array([r['start_s'] for r in off]);dt=np.array([(r['end_s']-r['start_s'])/3600 for r in off])
    p=np.array([r['power_mw'] for r in on])-np.array([r['power_mw'] for r in off])
    before=t<pulse['start_s'];inside=(t>=pulse['start_s'])&(t<pulse['end_s']);after=t>=pulse['end_s']
    if not np.allclose(p[before],0,atol=1e-10,rtol=0): raise ValueError('Pre-intervention physical trajectories differ')
    for a,b,m in zip(off,on,before):
        if m and any(a[k]!=b[k] for k in ('completed','waiting','shares','prices')):
            raise ValueError('Pre-intervention state differs')
    target=p[:,pulse['site']];post=t>=pulse['start_s']
    ix=np.flatnonzero(post & (abs(target)>1e-8))
    delay=None if not len(ix) else float(t[ix[0]]-pulse['start_s'])
    result={'pre_intervention_identical':True,
        'first_power_difference_interval_start_delay_s':delay,
        'first_power_difference_interval_end_delay_s':None if delay is None else delay+float(dt[ix[0]]*3600),
        'no_observed_power_difference':not bool(len(ix)),
        'target_window_reduction_mwh':float((-target[inside]*dt[inside]).sum()),
        'target_window_mean_reduction_mw':float((-target[inside]*dt[inside]).sum()/dt[inside].sum()),
        'total_window_energy_delta_mwh':float((p[inside].sum(axis=1)*dt[inside]).sum()),
        'receiving_sites_window_energy_delta_mwh':float(((p[inside].sum(axis=1)-target[inside])*dt[inside]).sum()),
        'post_window_target_signed_energy_delta_mwh':float((target[after]*dt[after]).sum()),
        'post_window_upward_rebound_peak_mw':float(max(0,target[after].max())) if after.any() else None,
        'cohort_jobs_equal':off_summary['cohort_jobs']==on_summary['cohort_jobs']}
    for key in ['cohort_completed_fraction','cohort_completed_node_hours','cohort_processed_node_hours',
                'cohort_restricted_mean_wait_s','cohort_restricted_mean_response_s','task_bill_currency',
                'evaluation_generation_cost','evaluation_max_line_loading','shed_mwh','spill_mwh']:
        a,b=off_summary[key],on_summary[key]
        result[key+'_delta']=None if a is None or b is None else b-a
    return result


def analyze(out,protocol):
    pairs=[]
    for case in protocol['cases']:
        if not case.get('paired_off'): continue
        off=out/case['paired_off'];on=out/case['name']
        summary=lambda path:json.loads((path/'summary.json').read_text())
        # Shared source/cohort identity is checked, not merely its size.
        tasks_off=read(off/'tasks.jsonl.gz');tasks_on=read(on/'tasks.jsonl.gz')
        identity=lambda tasks:sorted((r['key'],r['release'],r['stream']) for r in tasks)
        if identity(tasks_off)!=identity(tasks_on): raise ValueError('Paired task identities differ')
        pairs.append({'off':off.name,'on':on.name,**compare(read(off/'trace.jsonl.gz'),read(on/'trace.jsonl.gz'),case['pulse'],summary(off),summary(on))})
    (out/'paired_system_metrics.json').write_text(json.dumps({'status':'pilot_descriptive_no_inferential_claim','pairs':pairs},indent=2),encoding='utf-8')
