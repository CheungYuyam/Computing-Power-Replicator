"""Reconstruct invariants from exported task ledgers, independently of event loop."""
from collections import defaultdict
import numpy as np
from compare_methods import service_at_evaluation_end

def validate(tasks,trace,cfg):
    groups=defaultdict(list);events=defaultdict(list)
    keys=set();complete=0;energy=0.;bill=0.
    for r in tasks:
        if r['key'] in keys:raise AssertionError('Duplicate task')
        keys.add(r['key']);groups[r['stream']].append(r)
        assert 0<=r['release']<cfg['arrival_end_s']
        if r['start'] is None:
            assert r['completion'] is None and r['billed_ws']==0
        else:
            assert r['start']>=r['release']
            finish=r['start']+r['runtime_s']
            assert r['completion']==(finish if finish<=cfg['horizon_s'] else None)
            events[r['site']].append((r['start'],1,r['resources']))
            events[r['site']].append((min(finish,cfg['horizon_s']),-1,r['resources']))
            assert -.01<=r['billed_ws']<=r['full_energy_ws']+.01
        if r['completion'] is not None:
            complete+=1
            assert abs(r['billed_ws']-r['full_energy_ws'])<=max(.01,r['full_energy_ws']*1e-9)
            assert r['completion']<=r['settled']<r['completion']+cfg['settlement_s']+1e-7
            assert r['due']==r['settled']+cfg['report_delay_s']
            assert r['delivered']==(r['due'] if r['due']<=cfg['horizon_s'] else None)
        energy+=r['billed_ws']/3.6e9;bill+=r['bill']
    for group in groups.values():
        ordered=sorted(group,key=lambda r:(r['release'],r['key']))
        for a,b in zip(ordered,ordered[1:]):
            if b['start'] is not None:assert a['completion'] is not None and b['start']>=a['completion']
    for site,rows in events.items():
        used=np.zeros(3)
        for t,sign,resources in sorted(rows,key=lambda v:(v[0],v[1])):
            used+=sign*np.array(resources)
            assert np.all(used>=-1e-8) and np.all(used<=np.array(cfg['capacities'][site])+1e-8)
        assert np.all(used==0)
    grid_energy=sum(sum(r['power_mw'])*(r['end_s']-r['start_s'])/3600 for r in trace)
    grid_bill=sum(sum(p*c for p,c in zip(r['power_mw'],r['prices']))*(r['end_s']-r['start_s'])/3600 for r in trace)
    assert abs(energy-grid_energy)<1e-7*max(1,abs(energy))
    assert abs(bill-grid_bill)<1e-7*max(1,abs(bill))
    grid_errors={k:max(r[k] for r in trace) for k in ('balance_error_mw','line_excess_mw','generator_excess_mw','ramp_excess_mw')}
    assert max(grid_errors.values())<1e-5
    return dict(status='PASS',tasks=len(tasks),streams=len(groups),completed=complete,
                service_at_evaluation_end=service_at_evaluation_end(tasks,cfg),grid_max_errors=grid_errors,
                independent_task_energy_mwh=energy,independent_task_bill_currency=bill)
