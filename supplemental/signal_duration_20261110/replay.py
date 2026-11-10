"""Frozen-assignment startup-wait ablations; never an online predictor."""
import argparse, csv, gzip, hashlib, json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np


def read_rows(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return [json.loads(s) for s in f]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def dump(p, x):
    p.write_text(json.dumps(x, indent=2, allow_nan=False), encoding='utf-8')


def energy_bins(start, duration, power, dt, horizon):
    """Exact piecewise-constant 20-second measured curve, MWh per bin."""
    if start is None or start >= horizon: return 0, np.empty(0)
    assert start >= 0 and duration > 0
    p = np.asarray(power, dtype=float)
    edges = np.minimum(np.arange(len(p)+1)*20., duration)
    edges[-1] = duration
    assert len(p) and np.all(np.diff(edges) >= 0)
    cum = np.r_[0., np.cumsum(np.diff(edges)*p)]
    lo = int(start//dt)
    hi = min(int(np.ceil((start+duration)/dt)), int(horizon/dt))
    times = np.clip(np.arange(lo,hi+1)*dt-start, 0, duration)
    k = np.minimum(np.searchsorted(edges,times,side='right')-1,len(p)-1)
    val = cum[k]+(times-edges[k])*p[k]
    return lo, np.diff(val)/3.6e9


def assignments(tasks, revisions, cfg):
    n = sum(cfg['class_stream_counts'])
    initial = np.random.default_rng(cfg['seed']).integers(len(cfg['capacities']),size=n)
    assert not cfg.get('initialization') or cfg['initialization']=='uniform'
    bykey = {r['key']:r for r in revisions}
    groups = defaultdict(list)
    for t in tasks: groups[t['stream']].append(t)
    result = {}
    for stream, rows in groups.items():
        prev = None
        for t in sorted(rows,key=lambda t:(t['release'],t['key'])):
            if prev is None: a, site = 0., int(initial[stream])
            elif prev['key'] in bykey:
                d = bykey[prev['key']]
                assert d['stream']==stream and d['time']==prev['completion']
                a, site = d['time'], d['new']
            else: a, site = None, None
            if t['start'] is not None:
                assert a is not None and t['site']==site
                assert t['start']+1e-7 >= max(a,t['release'])
            result[t['key']] = (a,site)
            prev=t
    return result


def case(path, jobs):
    cfg=json.loads((path/'config.json').read_text())
    tasks=read_rows(path/'tasks.jsonl.gz')
    rev=read_rows(path/'revisions.jsonl.gz')
    trace=read_rows(path/'trace.jsonl.gz')
    plan=assignments(tasks,rev,cfg)
    dt=cfg['settlement_s']; horizon=cfg['horizon_s']; sites=len(cfg['capacities'])
    arrays={m:np.zeros((int(horizon/dt),sites)) for m in ('R','C','A')}
    waits={m:[] for m in ('R','C')}; completion={m:0 for m in ('R','C')}
    cohort=0; unassigned=0
    for t in tasks:
        job=jobs[t['source_key']]; a,site=plan[t['key']]
        duration=job['runtime']
        assert abs(duration-t['runtime_s'])<1e-6
        starts={'R':t['start'],'C':None if a is None else max(a,t['release']),'A':a}
        unassigned+=int(a is None)
        for m,s in starts.items():
            if s is not None:
                lo,values=energy_bins(s,duration,job['power_w'],dt,horizon)
                arrays[m][lo:lo+len(values),site]+=values
        if cfg['warmup_s']<=t['release']<cfg['arrival_end_s']:
            cohort+=1
            for m in waits:
                s=starts[m]
                waits[m].append(min(horizon,s if s is not None else horizon)-t['release'])
                completion[m]+=int(s is not None and s+duration<=cfg['arrival_end_s'])
    actual=np.array([r['power_mw'] for r in trace])
    err=float(np.max(np.abs(arrays['R']*3600/dt-actual)))
    assert err<1e-8, f'power reconstruction failed: {err}'
    services={m:{'restricted_mean_wait_s':float(np.mean(v)),
                 'restricted_p95_wait_s':float(np.quantile(v,.95)),
                 'completion_fraction_48h':completion[m]/cohort} for m,v in waits.items()}
    audit={'max_reconstruction_error_mw':err,'cohort':cohort,'tasks':len(tasks),
           'unassigned_tasks':unassigned,'service':services,
           'hashes':{n:sha(path/n) for n in ('config.json','tasks.jsonl.gz','revisions.jsonl.gz','trace.jsonl.gz')}}
    identity=sorted((t['key'],t['release'],t['source_key'],t['stream']) for t in tasks)
    return arrays,audit,identity,cfg


def metrics(delta, reference, dt):
    out={}
    for name,(a,b) in {'window':(36,38),'tail':(38,72),'evaluation':(24,48)}.items():
        z=delta[int(a*3600/dt):int(b*3600/dt)]
        e=z.sum(axis=0)
        out.update({name+'_target_mwh':float(e[0]),name+'_other_mwh':float(e[1:].sum()),
                    name+'_system_mwh':float(e.sum()),name+'_target_mean_mw':float(e[0]/(b-a))})
    mask=np.arange(len(delta))*dt>=36*3600
    for name,idx in [('target',slice(0,1)),('other',slice(1,None)),('system',slice(None))]:
        series=delta[:,idx].sum(axis=1)*3600/dt
        found=np.flatnonzero(mask & (np.abs(series)>1e-8))
        out[name+'_first_response_h']=None if not len(found) else float(found[0]*dt/3600)
    out['window_sitewise_absolute_discrepancy_mwh']=float(np.abs((delta-reference)[int(36*3600/dt):int(38*3600/dt)]).sum())
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--code',type=Path,required=True)
    ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.code))
    from run import prepare
    manifest=json.loads((args.code/'study_manifest.json').read_text())
    selected=[b for b in manifest['bundles'] if b['group']=='primary' and '_stagger_' in b['name']]
    assert len(selected)==9
    dump(args.out/'manifest.json',{'scope':'frozen assignment diagnostic; not prospective prediction',
         'selected':selected,'script_sha256':sha(Path(__file__)),'source_code_sha256':sha(args.code/'plant.py')})
    cache={}; rows=[]; audits={}
    for b in selected:
        src=args.source/f"{b['index']:03d}"
        cfg=json.loads((src/'reported'/'config.json').read_text()); origin=cfg['origin']
        if origin not in cache:
            dest=args.out/str(int(origin)); dest.mkdir()
            cache[origin]={j['key']:j for j in prepare(args.raw,origin,origin+47*3600,dest)}
        off,ao,io,cfg=case(src/'reported',cache[origin])
        on,an,inn,_=case(src/'reported_pulse',cache[origin])
        assert io==inn, 'Paired cohorts differ'
        delta={m:on[m]-off[m] for m in off}
        for m in delta:
            assert np.max(np.abs(delta[m][:int(36*3600/cfg['settlement_s'])]))<1e-8
        for m in delta:
            rows.append({'case':b['name'],'seed':cfg['seed'],'representation':m,
                         **metrics(delta[m],delta['R'],cfg['settlement_s'])})
        audits[b['name']]={'off':ao,'on':an}
        np.savez_compressed(args.out/(b['name']+'.npz'),**{f'{a}_{m}':v for a,d in [('off',off),('on',on)] for m,v in d.items()})
        dump(args.out/'progress.json',{'completed_pairs':len(audits),'total':9})
        print('COMPLETE',b['name'],flush=True)
    with (args.out/'results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    dump(args.out/'audit.json',audits)
    dump(args.out/'status.json',{'status':'complete','pairs':len(audits),'rows':len(rows),'all_integrity_gates_passed':True})


if __name__=='__main__': main()
