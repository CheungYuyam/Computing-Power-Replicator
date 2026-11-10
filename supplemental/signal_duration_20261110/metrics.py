import numpy as np


def window_metrics(on, off, recorded_delta, dt, duration):
    assert on.shape == off.shape == recorded_delta.shape
    start, end = 36., 36.+duration
    delta = on-off
    result = {}
    for name, (a,b) in {'window':(start,end), 'post4':(end,end+4),
                        'tail':(end,72), 'evaluation':(24,48)}.items():
        sl = slice(int(a*3600/dt),int(b*3600/dt))
        d=delta[sl].sum(axis=0); base=off[sl].sum(axis=0)
        result.update({name+'_target_kwh':float(d[0]*1000),
            name+'_other_kwh':float(d[1:].sum()*1000),
            name+'_system_kwh':float(d.sum()*1000),
            name+'_baseline_target_kwh':float(base[0]*1000),
            name+'_target_mean_kw':float(d[0]*1000/(b-a)),
            name+'_target_percent':None if base[0]==0 else float(100*d[0]/base[0])})
    sl=slice(int(start*3600/dt),int(end*3600/dt))
    result['window_response_discrepancy_kwh']=float((delta[sl,0]-recorded_delta[sl,0]).sum()*1000)
    result['window_response_discrepancy_percent']=None if result['window_baseline_target_kwh']==0 else 100*result['window_response_discrepancy_kwh']/result['window_baseline_target_kwh']
    for name,idx in [('target',slice(0,1)),('other',slice(1,None)),('system',slice(None))]:
        series=delta[:,idx].sum(axis=1)*3600/dt
        found=np.flatnonzero((np.arange(len(series))*dt>=start*3600)&(np.abs(series)>1e-8))
        result[name+'_first_response_h']=None if not len(found) else float(found[0]*dt/3600)
    return result
