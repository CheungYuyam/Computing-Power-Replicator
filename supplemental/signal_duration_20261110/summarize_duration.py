"""Validate returned arrays and summarize every date/seed, without selection."""
import argparse,csv,json
from pathlib import Path
import numpy as np


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--allow-partial',action='store_true');a=ap.parse_args()
    allrows=[];maxerr=0.;audits={}
    for folder in sorted(a.results.glob('[0-9][0-9][0-9]')):
        status=json.loads((folder/'status.json').read_text());assert status['status']=='complete' and status['integrity_pass']
        audit=json.loads((folder/'audit.json').read_text());audits[folder.name]=audit
        rows=list(csv.DictReader((folder/'metrics.csv').open()))
        assert len(rows)==9 and len({(r['duration_h'],r['representation']) for r in rows})==9
        for h in [1,2,4]:
            z=np.load(folder/f'arrays_{h}h.npz')
            for r in [q for q in rows if int(q['duration_h'])==h]:
                service= audit[str(h)]['service']['R'];reference=audit['off']['service']['R']
                assert abs(float(r['actual_completion_delta_pp'])-100*(service['completion_fraction_48h']-reference['completion_fraction_48h']))<1e-10
                assert abs(float(r['actual_wait_delta_min'])-(service['restricted_mean_wait_s']-reference['restricted_mean_wait_s'])/60)<1e-7
                m=r['representation'];delta=z['on_'+m]-z['off_'+m]
                for win,(begin,end) in {'window':(36,36+h),'post4':(36+h,40+h),'tail':(36+h,72),'evaluation':(24,48)}.items():
                    values=delta[begin*12:end*12].sum(axis=0)*1000
                    for key,value in [('target',values[0]),('other',values[1:].sum()),('system',values.sum())]:
                        err=abs(value-float(r[win+'_'+key+'_kwh']));assert err<1e-7;maxerr=max(maxerr,err)
                actualbaseline=float(z['off_R'][432:(36+h)*12,0].sum()*1000)
                actualdelta=float((z['on_R']-z['off_R'])[432:(36+h)*12,0].sum()*1000)
                discrepancy=float(r['window_target_kwh'])-actualdelta
                r['recorded_baseline_kwh']=actualbaseline
                r['discrepancy_percent_recorded']=None if actualbaseline==0 else discrepancy/actualbaseline*100
                r['discrepancy_mean_kw']=discrepancy/h
                r['actual_window_percent']=None if actualbaseline==0 else actualdelta/actualbaseline*100
                assert abs(float(r['window_response_discrepancy_kwh'])-discrepancy)<1e-7
                assert float(r['window_target_mean_kw'])==float(r['window_target_kwh'])/h
                assert np.max(np.abs(delta[:432]))<1e-8
                allrows.append(r)
    complete=len(audits)==9
    if not a.allow_partial:assert complete,'All nine bundles required'
    if complete:
        assert json.loads((a.results/'001/reproduction.json').read_text())['status']=='PASS'
        assert len(allrows)==81 and {r['date'] for r in allrows}=={'2020-07-27','2020-08-05','2020-08-21'}
    summary=[]
    fields=['window_target_kwh','window_target_mean_kw','window_other_kwh','window_system_kwh','recorded_baseline_kwh','actual_window_percent','discrepancy_percent_recorded','discrepancy_mean_kw','post4_target_kwh','post4_other_kwh','tail_target_kwh','tail_other_kwh','actual_completion_delta_pp','actual_wait_delta_min']
    for date in sorted({r['date'] for r in allrows}):
        for h in [1,2,4]:
            for m in ['R','C','A']:
                selected=[r for r in allrows if r['date']==date and int(r['duration_h'])==h and r['representation']==m]
                if complete:assert len(selected)==3 and {int(r['seed']) for r in selected}=={17,29,43}
                row={'date':date,'duration_h':h,'representation':m,'seeds':len(selected)}
                for k in fields:
                    v=[float(r[k]) for r in selected if r[k] is not None and r[k]!='']
                    for stat,value in [('mean',np.mean(v)),('min',min(v)),('max',max(v))] if v else [('mean',None),('min',None),('max',None)]:row[k+'_'+stat]=None if value is None else float(value)
                summary.append(row)
    for name,rows in [('all_metrics.csv',allrows),('date_summary.csv',summary)]:
        with (a.results/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    verification={'complete':complete,'bundles':len(audits),'rows':len(allrows),'independent_npz_energy_error_kwh':maxerr,
        'max_power_reconstruction_error_mw':max(v['max_reconstruction_error_mw'] for x in audits.values() for v in x.values()),
        'scope':'descriptive; controller seeds are not independent workload samples; frozen timing replays are not prospective prediction'}
    (a.results/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps(verification))
    for r in summary:
        if r['representation'] in ['R','C']:print({k:r[k] for k in ['date','duration_h','representation','seeds','window_target_kwh_mean','discrepancy_percent_recorded_mean','post4_target_kwh_mean']})

if __name__=='__main__':main()
