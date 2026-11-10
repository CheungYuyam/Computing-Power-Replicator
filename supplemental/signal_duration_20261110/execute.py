import argparse, copy, csv, json, sys, time
from pathlib import Path
import numpy as np
from metrics import window_metrics


def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')


def main():
    ap=argparse.ArgumentParser()
    for k in ['root','code','source','raw','old_replay']:ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--task',type=int,required=True)
    a=ap.parse_args()
    sys.path.insert(0,str(a.code))
    import run
    import replay
    from analyze import compare
    manifest=json.loads((a.code/'study_manifest.json').read_text())
    chosen=[b for b in manifest['bundles'] if b['group']=='primary' and '_stagger_' in b['name']]
    assert len(chosen)==9 and 0<=a.task<9
    b=chosen[a.task];index=f"{b['index']:03d}";src=a.source/index
    out=a.root/'runs'/index;out.mkdir(parents=True,exist_ok=False)
    dump(out/'status.json',{'status':'running','start':time.time(),'bundle':b})
    protocol=json.loads((a.code/'protocols'/f'{index}.json').read_text())
    pc=next(x for x in protocol['cases'] if x['name']=='reported_pulse')
    durations=[1,4]+([2] if a.task==0 else [])
    protocol['cases']=[]
    for h in durations:
        c=copy.deepcopy(pc);c['name']=f'pulse_{h}h';c.pop('paired_off',None)
        c['pulse']['end_s']=(36+h)*3600;protocol['cases'].append(c)
    dump(out/'protocol.json',protocol)
    priorargv=sys.argv
    sys.argv=['run.py','--raw',str(a.raw),'--out',str(out/'closed_loop'),'--protocol',str(out/'protocol.json')]
    run.main();sys.argv=priorargv
    original_prepared=json.loads((src/'prepared_manifest.json').read_text())
    new_prepared=json.loads((out/'closed_loop'/'prepared_manifest.json').read_text())
    assert original_prepared==new_prepared,'Source preparation differs'
    if a.task==0:
        for k in ['trace','tasks','revisions']:
            assert replay.read_rows(out/'closed_loop'/'pulse_2h'/(k+'.jsonl.gz'))==replay.read_rows(src/'reported_pulse'/(k+'.jsonl.gz')),f'2h reproduction differs: {k}'
        dump(out/'reproduction.json',{'status':'PASS','matching':['trace','tasks','revisions']})
    cfg=json.loads((src/'reported'/'config.json').read_text());origin=cfg['origin']
    prep=out/'replay_prepared';prep.mkdir()
    jobs={j['key']:j for j in run.prepare(a.raw,origin,origin+47*3600,prep)}
    off,ao,io,_=replay.case(src/'reported',jobs)
    old=np.load(a.old_replay/(b['name']+'.npz'))
    assert max(np.max(np.abs(old['off_'+m]-off[m])) for m in off)<1e-12
    off_trace=replay.read_rows(src/'reported'/'trace.jsonl.gz')
    off_summary=json.loads((src/'reported'/'summary.json').read_text())
    rows=[];audits={'off':ao};paired=[]
    for h in [1,2,4]:
        onpath=src/'reported_pulse' if h==2 else out/'closed_loop'/f'pulse_{h}h'
        checks=json.loads((onpath/'checks.json').read_text());assert all(checks.values())
        on,an,ii,cn=replay.case(onpath,jobs);assert ii==io
        omit={'name','paired_off','pulse'}
        assert {k:v for k,v in cfg.items() if k not in omit}=={k:v for k,v in cn.items() if k not in omit}
        assert cn['pulse']=={'site':0,'start_s':129600,'end_s':(36+h)*3600,'surcharge_per_mwh':40}
        for m in off:assert np.max(np.abs((on[m]-off[m])[:432]))<1e-8
        if h==2:assert max(np.max(np.abs(old['on_'+m]-on[m])) for m in on)<1e-12
        sn=json.loads((onpath/'summary.json').read_text());tn=replay.read_rows(onpath/'trace.jsonl.gz')
        paired.append({'duration_h':h,**compare(off_trace,tn,cn['pulse'],off_summary,sn)})
        for m in ['R','C','A']:
            rows.append({'date':protocol['start'],'seed':cfg['seed'],'index':index,'duration_h':h,'representation':m,
                **window_metrics(on[m],off[m],on['R']-off['R'],cfg['settlement_s'],h),
                'actual_completion_delta_pp':100*(an['service']['R']['completion_fraction_48h']-ao['service']['R']['completion_fraction_48h']),
                'actual_wait_delta_min':(sn['cohort_restricted_mean_wait_s']-off_summary['cohort_restricted_mean_wait_s'])/60})
        audits[str(h)]=an
        np.savez_compressed(out/f'arrays_{h}h.npz',**{f'{arm}_{m}':v for arm,z in [('off',off),('on',on)] for m,v in z.items()})
    # Original no-signal reassignment versus fixed allocation: no new intervention.
    fixed=replay.read_rows(src/'fixed'/'trace.jsonl.gz');gridrows=[]
    for f,r in zip(fixed,off_trace):
        assert f['start_s']==r['start_s']
        if not 86400<=r['start_s']<172800:continue
        d={'date':protocol['start'],'seed':cfg['seed'],'hour':r['start_s']/3600,'duration_h':(r['end_s']-r['start_s'])/3600}
        for k in ['generation_cost_per_h','renewable_curtailment_mw','spill_mw','shed_mw','system_demand_mw','max_line_loading']:
            d[k+'_fixed']=f[k];d[k+'_reported']=r[k];d[k+'_delta']=r[k]-f[k]
        for j in range(6):d[f'site_{j}_delta_mw']=r['power_mw'][j]-f['power_mw'][j]
        gridrows.append(d)
    for name,data in [('metrics.csv',rows),('grid_intervals.csv',gridrows)]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    dump(out/'audit.json',audits);dump(out/'paired_metrics.json',paired)
    dump(out/'status.json',{'status':'complete','rows':len(rows),'integrity_pass':True,'bundle':b,'finished':time.time()})
    print('BUNDLE_COMPLETE',index,flush=True)

if __name__=='__main__':main()
