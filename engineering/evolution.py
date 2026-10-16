from datetime import datetime, timezone
import numpy as np
def compare(on,off,daystart,origin):
    a=on['trace'];b=off['trace']
    if len(a)!=len(b) or any(x['interval_start']!=y['interval_start'] or x['interval_end']!=y['interval_end'] for x,y in zip(a,b)):
        raise ValueError('Pair time mismatch')
    times=np.array([r['interval_start'] for r in a]);ends=np.array([r['interval_end'] for r in a]);hours=(times+origin-daystart)/3600
    p0=np.array([x['site0_mw']-y['site0_mw'] for x,y in zip(a,b)])
    total=np.array([x['site0_mw']+x['site1_mw']-y['site0_mw']-y['site1_mw'] for x,y in zip(a,b)])
    strategy=np.array([.5*(x['strategy0_type0']+x['strategy0_type1']-y['strategy0_type0']-y['strategy0_type1']) for x,y in zip(a,b)])
    dt=(ends-times)/3600;pulse=(hours>=12)&(hours<14);after=(hours>=14)&(hours<18);post=hours>=12
    before=hours<12
    pre_fields=['site0_mw','site1_mw','strategy0_type0','strategy0_type1','completed','waiting','active','price0','price1']
    pre_ok=all(abs(float(x[k])-float(y[k]))<1e-10 for x,y,mask in zip(a,b,before) if mask for k in pre_fields)
    if not pre_ok:raise ValueError('Paired paths differ before intervention')
    row={'date':datetime.fromtimestamp(daystart,timezone.utc).date().isoformat(),'seed':on['summary']['seed'],
        'feedback_delay_s':on['summary']['feedback_delay_s'],'admission_period_s':on['summary']['admission_period_s'],
        'pulse_site0_reduction_mwh':float((-p0[pulse]*dt[pulse]).sum()),
        'after_upward_rebound_peak_mw':float(np.maximum(p0[after],0).max()),
        'after_site0_signed_on_minus_off_mwh':float((p0[after]*dt[after]).sum()),
        'post_observation_hours':float(dt[post].sum()),'pre_intervention_identical':pre_ok,
        'completed_measurement_on_minus_off':on['summary']['completed_measurement']-off['summary']['completed_measurement'],
        'completed_all_on_minus_off':on['summary']['completed_all']-off['summary']['completed_all'],
        'mean_wait_s_on_minus_off':None if on['summary']['mean_wait_s'] is None or off['summary']['mean_wait_s'] is None else on['summary']['mean_wait_s']-off['summary']['mean_wait_s'],
        'generation_cost_scenario_on_minus_off':on['summary']['generation_cost_scenario']-off['summary']['generation_cost_scenario'],
        'tail_waiting_on':on['summary']['waiting_end'],'tail_waiting_off':off['summary']['waiting_end']}
    for name,signal,threshold in [('site0',p0,1e-8),('total_power',total,1e-8),('strategy_mean',strategy,1e-12)]:
        ix=np.flatnonzero((abs(signal)>threshold)&post)
        row[name+'_observed_difference']=bool(len(ix))
        row[name+'_first_interval_start_hour']=None if not len(ix) else float(hours[ix[0]])
        row[name+'_first_interval_end_hour']=None if not len(ix) else float((ends[ix[0]]+origin-daystart)/3600)
        row[name+'_tail_different']=bool(abs(signal[-1])>threshold)
        row[name+'_max_abs_difference']=float(abs(signal[post]).max())
        if name!='strategy_mean':
            row[name+'_post_signed_mwh']=float((signal[post]*dt[post]).sum())
            row[name+'_post_absolute_mwh']=float((abs(signal[post])*dt[post]).sum())
    # Strategy samples are interval-end states, not interval-start states.
    row['strategy_first_observed_state_hour']=row['strategy_mean_first_interval_end_hour']
    a_draw={(r['business'],r['ordinal']):(r['peer_index'],r['uniform']) for r in on['draws']}
    b_draw={(r['business'],r['ordinal']):(r['peer_index'],r['uniform']) for r in off['draws']}
    row['common_event_draws_equal']=all(a_draw[k]==b_draw[k] for k in a_draw.keys()&b_draw.keys())
    if not row['common_event_draws_equal']:raise ValueError('Event random numbers changed')
    return row

