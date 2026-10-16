"""Descriptive finite-seed summaries; never treat a missing response as onset zero."""
import json,csv
from pathlib import Path
import numpy as np
def flag(v):
    if v is True or v=='True':return True
    if v is False or v=='False':return False
    raise ValueError('Invalid bool')
def num(v):return None if v in (None,'') else float(v)
def stats(values):
    x=[num(v) for v in values];x=[v for v in x if v is not None]
    return {'n_observed':len(x),'min':min(x) if x else None,'median':float(np.median(x)) if x else None,'max':max(x) if x else None}
def response_stats(rows,signal='site0'):
    yes=[r for r in rows if flag(r[signal+'_observed_difference'])]
    return {'n':len(rows),'responding':len(yes),'right_censored':len(rows)-len(yes),
        'first_interval_start_hour_responders_only':stats([r[signal+'_first_interval_start_hour'] for r in yes]),
        'first_interval_end_hour_responders_only':stats([r[signal+'_first_interval_end_hour'] for r in yes])}
def write(p,obj):Path(p).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvwrite(p,rows):
    with Path(p).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def analyze(out,rows,pairs,loader,cfg):
    seeds=cfg['seeds_all'];bykey={};byrow={}
    for r in rows:
        k=(r['date'],int(r['seed']),int(float(r['feedback_delay_s'])),int(float(r['admission_period_s'])),flag(r['incentive']))
        if k in bykey:raise ValueError('Duplicate trace')
        bykey[k]=loader(r);byrow[k]=r
    snapshots=[];envelopes={};groups=[];contrasts=[]
    for d in cfg['dates']:
        for l in cfg['communication_seconds']:
            for a in cfg['admission_seconds']:
                selected=[r for r in pairs if (r['date'],int(float(r['feedback_delay_s'])),int(float(r['admission_period_s'])))==(d,l,a)]
                if len(selected)!=5 or {int(r['seed']) for r in selected}!=set(seeds):raise ValueError('Pair seed coverage')
                groups.append(dict(date=d,feedback_delay_s=l,admission_period_s=a,site0=response_stats(selected),
                    total_power=response_stats(selected,'total_power'),strategy_mean=response_stats(selected,'strategy_mean'),
                    pulse_site0_reduction_mwh=stats([r['pulse_site0_reduction_mwh'] for r in selected]),
                    site0_post_signed_mwh=stats([r['site0_post_signed_mwh'] for r in selected]),
                    site0_post_absolute_mwh=stats([r['site0_post_absolute_mwh'] for r in selected]),
                    completed_all_on_minus_off=stats([r['completed_all_on_minus_off'] for r in selected]),
                    mean_wait_s_on_minus_off=stats([r['mean_wait_s_on_minus_off'] for r in selected]),
                    tail_different=sum(flag(r['site0_tail_different']) for r in selected)))
                for on in [False,True]:
                    traces=[bykey[(d,s,l,a,on)] for s in seeds]
                    signals={k:np.stack([c[k] for c in traces]) for k in ['strategy0_type0','strategy0_type1','site0_mw','completed']}
                    signals['strategy0_mean']=.5*(signals.pop('strategy0_type0')+signals.pop('strategy0_type1'))
                    for name,array in signals.items():
                        q=np.quantile(array,[0,.5,1],axis=0);envelopes[f'{d}_lag{l}_admit{a}_{on}_{name}']=q
                    for hour in cfg['analysis']['snapshot_state_hours']:
                        t=(hour+12)*3600;idx=int(t/300)-1
                        row=dict(date=d,feedback_delay_s=l,admission_period_s=a,incentive=on,state_hour=hour,power_interval_start_hour=hour-1/12)
                        for name,array in signals.items():
                            for label,val in zip(['min','median','max'],np.quantile(array[:,idx],[0,.5,1])):row[name+'_'+label]=float(val)
                        snapshots.append(row)
                    for s in seeds:
                        if (l,a)==(900,0):continue
                        c=bykey[(d,s,l,a,on)];b=bykey[(d,s,900,0,on)];r=byrow[(d,s,l,a,on)];br=byrow[(d,s,900,0,on)]
                        diff=.5*(c['strategy0_type0']+c['strategy0_type1']-b['strategy0_type0']-b['strategy0_type1'])
                        wait=num(r['mean_wait_s']);bw=num(br['mean_wait_s'])
                        contrasts.append(dict(date=d,seed=s,feedback_delay_s=l,admission_period_s=a,incentive=on,
                            reference_feedback_delay_s=900,reference_admission_period_s=0,
                            strategy_max_abs_share_difference=float(np.max(abs(diff))),strategy_terminal_signed_difference=float(diff[-1]),
                            site0_max_abs_power_difference_mw=float(np.max(abs(c['site0_mw']-b['site0_mw']))),
                            completed_terminal_signed_difference=int(c['completed'][-1]-b['completed'][-1]),
                            mean_wait_signed_difference_s=None if wait is None or bw is None else wait-bw))
    np.savez_compressed(out/'path_envelopes_server_only.npz',**envelopes)
    csvwrite(out/'path_snapshots.csv',snapshots);csvwrite(out/'timing_contrasts.csv',contrasts)
    write(out/'repeat_analysis.json',{'groups':groups,'quantiles':'min/median/max over five seeds, not confidence intervals',
        'onset':'300-second power interval; strategy measured at interval end; missing onset remains right-censored',
        'seed_scope':cfg['seed_semantics'],'dates_are_groups_not_independent_configurations':True,
        'snapshots':len(snapshots),'temporal_contrasts':len(contrasts),'no_significance_tests':True})
    return {'all_270_traces_sha_verified':len(bykey)==270,'all_27_five_seed_groups':len(groups)==27,
        'all_378_snapshots':len(snapshots)==378,'all_240_temporal_contrasts':len(contrasts)==240,
        'small_reports_bounded':all((out/n).stat().st_size<1048576 for n in ['repeat_analysis.json','path_snapshots.csv','timing_contrasts.csv'])}
