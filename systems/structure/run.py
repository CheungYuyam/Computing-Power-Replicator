"""Prepare a versioned development replay and execute bounded pilot cases."""
import argparse
import gzip
import hashlib
import json
import time
import numpy as np
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pm100_filter import valid_row
from grid import GridReplay
from plant import simulate
from workload import assign_lanes, unconstrained_profile


def stamp(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')


def prepare(raw,lo,hi,out):
    cols=['job_id','job_state','submit_time','eligible_time','start_time','end_time','run_time','power_consumption']+[f'num_{r}_{s}' for r in ('nodes','cores','gpus') for s in ('req','alloc')]
    counts=Counter();jobs=[]
    left=pa.scalar(datetime.fromtimestamp(lo,timezone.utc));right=pa.scalar(datetime.fromtimestamp(hi,timezone.utc))
    for batch in pq.ParquetFile(raw/'pm100_v1_job_table.parquet').iter_batches(columns=cols,batch_size=128):
        submit=batch.column(batch.schema.get_field_index('submit_time'))
        batch=batch.filter(pc.and_(pc.greater_equal(submit,left),pc.less(submit,right)))
        for row in batch.to_pylist():
            job=valid_row(row,counts)
            if job is not None and lo<=job['release']<hi: jobs.append(job)
    jobs.sort(key=lambda r:(r['release'],r['key']))
    dump(out/'prepared_manifest.json',{'jobs':len(jobs),'counts':dict(counts),'origin':lo,'end':hi,
        'pm100_sha256':hashlib.sha256((raw/'pm100_v1_job_table.parquet').read_bytes()).hexdigest(),
        'construction':'offline interval-colored synthetic lanes; replicas are synthetic demand, not independent observations'})
    return jobs


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,default=Path(__file__).with_name('protocol.json'))
    a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    if (a.out/'started.json').exists(): raise RuntimeError('Run already exists; inspect, do not silently rerun')
    protocol=json.loads(a.protocol.read_text(encoding='utf-8'))
    dump(a.out/'started.json',{'wall_clock':time.time(),'protocol':protocol})
    origin=stamp(protocol['start'])
    end=stamp(protocol['end'])
    arrival_end=stamp(protocol.get('arrival_end',protocol['end']))
    source_end=stamp(protocol.get('source_end',protocol.get('arrival_end',protocol['end'])))
    jobs=prepare(a.raw,origin,source_end,a.out)
    lanes=assign_lanes(jobs, protocol['common'].get('lane_rule','earliest_available'))
    dump(a.out/'workload_audit.json',{'lane_counts':lanes,
         'unconstrained_profile':unconstrained_profile(jobs,origin,arrival_end-origin),
         'construction':'offline interval coloring of release + measured duration; synthetic lanes, not observed dependencies; no future duration access by controller'})
    reference=json.loads(Path(__file__).with_name('reference.json').read_text())['classes']
    summaries=[]
    for case in protocol['cases']:
        cfg={**protocol['common'],**case,'origin':origin,'horizon_s':end-origin,'arrival_end_s':arrival_end-origin}
        name=case['name']
        out=a.out/name;out.mkdir()
        nodes=cfg.pop('nodes')
        if cfg.get('stream_construction')=='nonoverlapping_release_intervals':
            cfg['lane_counts']=lanes
            cfg['streams_per_class']=max(lanes)*cfg['replicas']
            cfg['class_stream_counts']=[n*cfg['replicas'] for n in lanes]
        cfg['capacities']=[[n,128*n,4*n] for n in nodes]
        grid=GridReplay(a.raw,cfg['site_buses'],origin)
        dump(out/'config.json',cfg);dump(out/'grid_metadata.json',grid.meta)
        print(json.dumps({'event':'case_start','case':name,'source_jobs':len(jobs),'config':cfg}),flush=True)
        begin=time.time()
        def settled_with_intervention(start,stop,energy):
            row=grid(start,stop,energy)
            row['lmp']=row['prices'].copy()
            pulse=cfg.get('pulse')
            if pulse and pulse['start_s']<=start<pulse['end_s']:
                row['prices'][pulse['site']]+=pulse['surcharge_per_mwh']
            row['tariff_intervention_active']=bool(pulse and pulse['start_s']<=start<pulse['end_s'])
            return row
        result=simulate(jobs,reference,settled_with_intervention,cfg)
        from validate_case import validate
        dump(out/'independent_audit.json',validate(result['tasks'],result['trace'],cfg))
        summary={**result['summary'],'case':name,'seconds':time.time()-begin,'config':cfg}
        traces=result['trace'];dt=cfg['settlement_s']/3600
        summary.update(shed_mwh=sum(x['shed_mw']*dt for x in traces),
                       spill_mwh=sum(x['spill_mw']*dt for x in traces),
                       renewable_curtailment_mwh=sum(x['renewable_curtailment_mw']*dt for x in traces),
                       generation_cost=sum(x['generation_cost_per_h']*dt for x in traces),
                       negative_price_intervals=sum(any(p<0 for p in x['prices']) for x in traces),
                       max_line_loading=max(x['max_line_loading'] for x in traces),
                       peak_it_share=max(sum(x['power_mw'])/x['system_demand_mw'] for x in traces))
        bounds=(cfg['warmup_s'],cfg['arrival_end_s'])
        evaluated=[x for x in traces if bounds[0]<=x['start_s']<bounds[1]]
        summary['evaluation_generation_cost']=sum(x['generation_cost_per_h']*dt for x in evaluated)
        summary['evaluation_max_line_loading']=max(x['max_line_loading'] for x in evaluated)
        summary['evaluation_price_site_range_mean']=float(np.mean([max(x['lmp'])-min(x['lmp']) for x in evaluated]))
        dump(out/'summary.json',summary);dump(out/'checks.json',result['checks'])
        for key in ('trace','tasks','revisions'):
            with gzip.open(out/(key+'.jsonl.gz'),'wt',encoding='utf-8') as f:
                for row in result[key]: f.write(json.dumps(row,allow_nan=False)+'\n')
        summaries.append(summary)
        dump(a.out/'progress.json',{'complete':len(summaries),'total':len(protocol['cases']),'last_case':name})
        print(json.dumps({'event':'case_complete','case':name,'seconds':summary['seconds'],'summary':summary}),flush=True)
    from analyze import analyze
    analyze(a.out, protocol)
    dump(a.out/'pilot_summary.json',{'status':'frozen_bundle_complete_pending_cross_bundle_audit','cases':summaries,
        'scope':'Predefined simulated system study; not field validation or continuous-model predictive validation'})


if __name__=='__main__': main()
