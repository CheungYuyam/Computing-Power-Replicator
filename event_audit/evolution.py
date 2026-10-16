import csv,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def rk(r):return r['business'],r['ordinal']


def unique(records,key):
    d={key(r):r for r in records}
    if len(d)!=len(records):raise ValueError('Duplicate matching key')
    return d


def diff(a,b,tol=1e-10):
    if a is None or b is None:return a!=b
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):return abs(a-b)>tol
    return a!=b


def hour(t):return None if t is None else t/3600-12


def ref(k):return hashlib.sha256(str(k).encode()).hexdigest()[:16]


def task_view(t):
    fields=['business','kind','state','site','raw_cost','cost']
    return {'task_ref':ref(t['key']),**{k:t[k] for k in fields},**{k+'_hour':hour(t[k]) for k in ['release','start','physical_completion','settlement_ready','report_due','report_delivered']}}


def revision_view(r):
    if r is None:return None
    return {'task_ref':ref(r['key']),'time_hour':hour(r['time']),**{k:r[k] for k in ['business','ordinal','kind','old','new','cost0','cost1','candidate','probability','uniform','own_report_visible','reports_visible_count']},'accepted_threshold':r['uniform']<r['probability']}


def validate_records(d,lag):
    tasks=unique(d['tasks'],lambda r:r['key']);revs=unique(d['revisions'],rk);draws=unique(d['draws'],rk)
    if set(revs)!=set(draws):raise ValueError('Revision/draw key mismatch')
    if not all(x is True for x in d['integrity'].values()):raise ValueError('Source integrity failed')
    for t in tasks.values():
        c=t['physical_completion'];s=t['settlement_ready'];due=t['report_due'];delivery=t['report_delivered']
        if c is not None and (t['start'] is None or c<t['start'] or abs(c-t['start']-t['runtime'])>1e-7):raise ValueError('Physical timing')
        if s is not None and (c is None or s<c or due!=s+lag):raise ValueError('Settlement/report timing')
        if delivery is not None and (due is None or delivery!=due):raise ValueError('Delivery timing')
    for key,r in revs.items():
        t=tasks[r['key']];dr=draws[key]
        if r['time']!=t['physical_completion'] or r['time']!=t['revision_time'] or r['business']!=t['business']:raise ValueError('Revision completion link')
        if r['uniform']!=dr['uniform'] or r['candidate']!=dr['candidate']:raise ValueError('Recorded draw mismatch')
        if not 0<=r['probability']<=1 or not 0<=r['uniform']<1:raise ValueError('Probability bounds')
        expected=r['candidate'] if r['uniform']<r['probability'] else r['old']
        if expected!=r['new']:raise ValueError('Saved decision inconsistent with saved threshold')
        visible=t['report_delivered'] is not None and t['report_delivered']<=r['time']
        if bool(r['own_report_visible'])!=visible or (lag>0 and visible):raise ValueError('Own report visibility')
    return tasks,revs,draws


def matched_revisions(on,off):
    a=unique(on['revisions'],rk);b=unique(off['revisions'],rk);da=unique(on['draws'],rk);db=unique(off['draws'],rk)
    common=set(a)&set(b);samekey=[k for k in common if a[k]['key']==b[k]['key']]
    random_equal=all(da[k]['peer_index']==db[k]['peer_index'] and da[k]['uniform']==db[k]['uniform'] for k in common)
    aligned=[k for k in samekey if abs(a[k]['time']-b[k]['time'])<1e-8]
    aligned.sort(key=lambda k:(a[k]['time'],k))
    return a,b,aligned,{'common_ordinals':len(common),'same_task_matches':len(samekey),'same_time_same_task_matches':len(aligned),'same_task_different_time':len(samekey)-len(aligned),'different_task_matches':len(common)-len(samekey),'on_unmatched':len(set(a)-set(b)),'off_unmatched':len(set(b)-set(a)),'common_event_random_numbers_equal':random_equal}


def first_pair(a,b,ks,predicate):
    for k in ks:
        if predicate(a[k],b[k]):return a[k],b[k]
    return None


def report_context(tasks,other,r):
    visible=[t for t in tasks.values() if t['kind']==r['kind'] and t['report_delivered'] is not None and t['report_delivered']<=r['time']]
    changed=[]
    for t in visible:
        q=other.get(t['key']);other_visible=q is not None and q['report_delivered'] is not None and q['report_delivered']<=r['time']
        if not other_visible or any(diff(t[k],q[k]) for k in ['cost','site','report_delivered']):changed.append(t)
    changed.sort(key=lambda t:(t['report_delivered'],t['key']))
    selected=changed[:3]+[t for t in changed[-3:] if t not in changed[:3]]
    return {'same_type_visible_report_count':len(visible),'different_or_unavailable_in_other_path_count':len(changed),'first_and_last_up_to_six_changed_reports':[task_view(t) for t in selected],'interpretation':'Reports were eligible in stored information history; individual marginal causal contribution not identified. Visible aggregate costs are taken directly from saved revision record, not recomputed.'}


def last_revision(d,task):
    if task['start'] is None:return None
    rr=[r for r in d['revisions'] if r['business']==task['business'] and r['time']<=task['start']]
    return max(rr,key=lambda r:(r['time'],r['ordinal'])) if rr else None


def task_differences(on,off):
    a=unique(on['tasks'],lambda t:t['key']);b=unique(off['tasks'],lambda t:t['key'])
    if set(a)!=set(b):raise ValueError('Task sets differ')
    routing=[k for k in a if a[k]['start'] is not None and b[k]['start'] is not None and a[k]['site']!=b[k]['site']]
    timing=[k for k in a if diff(a[k]['start'],b[k]['start'])]
    sort=lambda k:(min(x for x in [a[k]['start'],b[k]['start']] if x is not None),k)
    routing.sort(key=sort);timing.sort(key=sort)
    def example(keys):
        if not keys:return None
        k=keys[0];ra=last_revision(on,a[k]);rb=last_revision(off,b[k])
        for task,r,d in [(a[k],ra,on),(b[k],rb,off)]:
            site=r['new'] if r is not None else d['initial_strategy'][task['business']]
            if task['start'] is not None and site!=task['site']:raise ValueError('Recorded routing not linked to last business strategy')
        return {'on':task_view(a[k]),'off':task_view(b[k]),'last_business_revision_before_on_start':revision_view(ra),'last_business_revision_before_off_start':revision_view(rb)}
    return {'both_started_routing_difference_count':len(routing),'start_time_or_started_status_difference_count':len(timing),'first_routing_difference':example(routing),'first_start_difference':example(timing)}


def power_context(on,off,pa,pb,pair,cfg):
    zs=[];hs={}
    for path in [pa,pb]:
        p=path/'trace_server_only.npz';h=digest(p)
        if h!=read(path/'trace_sha256.json')[p.name]:raise ValueError('Trace hash differs')
        hs[str(p)]=h
        with np.load(p,allow_pickle=False) as z:zs.append(dict(zip(z['columns'].tolist(),z['values'].T)))
    a,b=zs
    if not np.array_equal(a['interval_start'],b['interval_start']) or not np.array_equal(a['interval_end'],b['interval_end']):raise ValueError('Power interval mismatch')
    ix=np.flatnonzero((a['interval_start']>=86400)&(abs(a['site0_mw']-b['site0_mw'])>1e-8))
    if not len(ix):return {'observed':False,'right_censored':True},hs
    i=int(ix[0]);start=float(a['interval_start'][i]);end=float(a['interval_end'][i])
    if not math.isclose(hour(start),float(pair['site0_first_interval_start_hour']),abs_tol=1e-9):raise ValueError('Power onset not reproduced')
    contributions=[]
    ledgers=[]
    for d in [on,off]:
        bins=[r for r in d['ledger'] if r['interval_start']==start and r['interval_end']==end]
        ledgers.append({r['key']:r for r in bins})
    la,lb=ledgers;energy=0.
    for k in set(la)|set(lb):
        x=la.get(k);y=lb.get(k);ea=x['energy_ws'] if x and x['site']==0 else 0.;eb=y['energy_ws'] if y and y['site']==0 else 0.;delta=ea-eb;energy+=delta
        if abs(delta)>1e-8:contributions.append({'task_ref':ref(k),'site0_energy_difference_ws':delta,'on_site':None if x is None else x['site'],'off_site':None if y is None else y['site']})
    power=energy*cfg['power_mw_per_w']/(end-start);saved=float(a['site0_mw'][i]-b['site0_mw'][i])
    if not math.isclose(power,saved,abs_tol=1e-9,rel_tol=1e-8):raise ValueError('Ledger does not account for first power difference')
    contributions.sort(key=lambda r:(-abs(r['site0_energy_difference_ws']),r['task_ref']))
    return {'observed':True,'interval_start_hour':hour(start),'interval_end_hour':hour(end),'saved_site0_delta_mw':saved,'ledger_reconstructed_site0_delta_mw':power,'contributing_task_count':len(contributions),'largest_eight_task_contributions':contributions[:8],'all_contributions_accounted_in_sum':True,'instantaneous_power_onset_identified':False},hs


def analyze(on,off,pa,pb,pair,cfg):
    ta=unique(on['tasks'],lambda t:t['key']);tb=unique(off['tasks'],lambda t:t['key'])
    a,b,ks,counts=matched_revisions(on,off)
    if not counts['common_event_random_numbers_equal']:raise ValueError('Event draws differ')
    specs={'visible_cost_difference':lambda x,y:diff(x['cost0'],y['cost0']) or diff(x['cost1'],y['cost1']),
        'probability_difference':lambda x,y:diff(x['probability'],y['probability']),
        'threshold_acceptance_difference':lambda x,y:(x['uniform']<x['probability'])!=(y['uniform']<y['probability']),
        'post_revision_strategy_difference':lambda x,y:x['new']!=y['new']}
    stages={}
    for label,predicate in specs.items():
        hits=[k for k in ks if predicate(a[k],b[k])];v=first_pair(a,b,ks,predicate)
        stages[label]={'matched_event_count':len(hits),'first':None if v is None else {'on':revision_view(v[0]),'off':revision_view(v[1])}}
        if v is not None and label=='threshold_acceptance_difference':
            stages[label]['first']['on_report_context']=report_context(ta,tb,v[0]);stages[label]['first']['off_report_context']=report_context(tb,ta,v[1])
    costdiff=[k for k in ta.keys()&tb.keys() if ta[k]['cost'] is not None and tb[k]['cost'] is not None and diff(ta[k]['cost'],tb[k]['cost'])]
    delivered=[k for k in costdiff if ta[k]['report_delivered'] is not None and tb[k]['report_delivered'] is not None]
    delivered.sort(key=lambda k:(max(ta[k]['report_delivered'],tb[k]['report_delivered']),k))
    first=delivered[0] if delivered else None
    power,hashes=power_context(on,off,pa,pb,pair,cfg)
    return {'date':pair['date'],'communication_s':int(pair['feedback_delay_s']),'admission_s':int(pair['admission_period_s']),
        'matching':counts,'reports':{'both_cost_recorded_differ_count':len(costdiff),'both_delivered_changed_report_count':len(delivered),'first_changed_report_both_delivered_order':None if first is None else {'on':task_view(ta[first]),'off':task_view(tb[first])}},
        'first_stages_in_time_aligned_same_task_events':stages,'subsequent_tasks':task_differences(on,off),'first_power_difference':power,
        'limits':'Posthoc descriptive selection. Earliest stages can involve different businesses and are not automatically one causal chain. Information-context reports are eligible historical evidence, not individually proven causes. Nonaligned revisions counted, not forcibly aligned. No counterfactual simulation or missing-state reconstruction.'},hashes

