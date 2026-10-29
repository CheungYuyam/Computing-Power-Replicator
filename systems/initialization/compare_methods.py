"""Explicit mechanism comparisons within identical physical scenarios."""
import argparse
import json
from pathlib import Path
from analyze import read


def service_at_evaluation_end(tasks, config):
    warm,end=config['warmup_s'],config['arrival_end_s']
    cohort=[r for r in tasks if warm<=r['release']<end]
    done=[r for r in cohort if r['completion'] is not None and r['completion']<=end]
    return {'cohort_completed_by_evaluation_end_fraction':len(done)/len(cohort) if cohort else None,
            'cohort_completed_by_evaluation_end_node_hours':sum(r['resources'][0]*(r['completion']-r['start'])/3600 for r in done),
            'all_jobs_completed_during_evaluation':sum(r['completion'] is not None and warm<r['completion']<=end for r in tasks)}


def compare_methods(out):
    cases={s['case']:s for s in json.loads((out/'pilot_summary.json').read_text())['cases']}
    comparisons=[]
    allowed={'name','paired_off','method','report_delay_s','arm'}
    fields=['cohort_completed_fraction','cohort_completed_node_hours','cohort_processed_node_hours',
            'cohort_restricted_mean_wait_s','cohort_restricted_mean_response_s',
            'cohort_mean_predecessor_wait_s','cohort_mean_post_predecessor_wait_s',
            'measurement_it_energy_mwh','evaluation_generation_cost','evaluation_max_line_loading']
    service={}
    identity=lambda rows:sorted((r['key'],r['release'],r['stream'],tuple(r['resources'])) for r in rows)
    for baseline in cases.values():
        if baseline['config']['method']!='fixed':continue
        baseline_tasks=read(out/baseline['case']/'tasks.jsonl.gz')
        baseline_identity=identity(baseline_tasks)
        service[baseline['case']]=service_at_evaluation_end(baseline_tasks,baseline['config'])
        del baseline_tasks
        for candidate in cases.values():
            if candidate['config']['method']=='fixed':continue
            a={k:v for k,v in baseline['config'].items() if k not in allowed}
            b={k:v for k,v in candidate['config'].items() if k not in allowed}
            if a!=b:continue
            candidate_tasks=read(out/candidate['case']/'tasks.jsonl.gz')
            if baseline_identity!=identity(candidate_tasks):
                raise ValueError('Method comparison changes task identities/resources')
            service[candidate['case']]=service_at_evaluation_end(candidate_tasks,candidate['config'])
            del candidate_tasks
            comparisons.append({'reference':baseline['case'],'candidate':candidate['case'],
                                'shared_inputs_verified':True,
                                'evaluation_end_service_delta':{k:None if v is None else service[candidate['case']][k]-v
                                                               for k,v in service[baseline['case']].items()},
                                'delta_candidate_minus_reference':{
                                    k:None if baseline[k] is None or candidate[k] is None else candidate[k]-baseline[k]
                                    for k in fields}})
    result={'status':'single_seed_development_descriptive_only',
            'scope':'Same capacity, same arrivals, same FCFS admission, different allocation/communication; no superiority claim from one seed',
            'service_at_evaluation_end':service,'comparisons':comparisons}
    (out/'method_comparisons.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    compare_methods(p.parse_args().out)
