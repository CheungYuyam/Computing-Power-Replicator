"""Exact event-time multi-site replay; accounting is independent of controller."""
import heapq
import time
from collections import deque
import numpy as np
from controller import Controller, stable_int


class Curve:
    def __init__(self, runtime, power):
        self.runtime = float(runtime)
        self.power = np.asarray(power,dtype=float)
        self.edges = np.minimum(np.arange(len(power)+1)*20.,runtime)
        self.edges[-1] = runtime
        if runtime <= 0 or len(power) == 0 or np.any(np.diff(self.edges)<0) or not np.isfinite(self.power).all() or self.power.min()<0:
            raise ValueError('Invalid measured power curve')
        self.cum = np.r_[0.,np.cumsum(np.diff(self.edges)*self.power)]

    def integral(self, t):
        t = min(max(float(t),0.),self.runtime)
        k = min(np.searchsorted(self.edges,t,side='right')-1,len(self.power)-1)
        return float(self.cum[k]+(t-self.edges[k])*self.power[k])


def simulate(jobs, reference, settlement, config):
    dt, horizon = config['settlement_s'], config['horizon_s']
    per_class, replicas = config['streams_per_class'], config['replicas']
    capacities = np.asarray(config['capacities'],dtype=float)
    class_counts=config.get('class_stream_counts',[per_class,per_class])
    offsets=[0,class_counts[0],sum(class_counts)]
    sites, streams = len(capacities), sum(class_counts)
    if capacities.shape != (sites,3) or capacities.min()<=0 or horizon%dt:
        raise ValueError('Invalid simulation configuration')
    ctl = Controller(sites,per_class,config['seed'],config['method'],
                     beta=config.get('beta',.15), memory_s=config.get('memory_s',21600),class_counts=class_counts)
    waiting = [deque() for _ in range(streams)]
    active, used = {}, np.zeros_like(capacities)
    ready = set()
    site_queues = [[] for _ in range(sites)]
    def enqueue_ready(b,t):
        if b not in active and waiting[b] and b not in ready:
            ready.add(b)
            heapq.heappush(site_queues[int(ctl.strategy[b])],(t,b))
    tasks, queue, unsettled = [], [], []
    serial = 0
    def push(t,event,j=None):
        nonlocal serial
        serial += 1
        heapq.heappush(queue,(float(t),serial,event,j))
    for template in jobs:
        curve = Curve(template['runtime'],template['power_w'])
        if np.any(np.asarray(template['resources']) > capacities.min(axis=0)):
            raise ValueError('Task cannot run at every site: configure capacities or declare eligibility model')
        for replica in range(replicas):
            kind = int(template['resources'][2]>0)
            if config.get('stream_construction') == 'nonoverlapping_release_intervals':
                stream = offsets[kind] + replica*config['lane_counts'][kind] + template['lane']
                if stream >= offsets[kind+1]:
                    raise ValueError('Insufficient stream slots for independently replicated lanes')
            else:
                stream = kind*per_class + stable_int(f"{template['key']}:{replica}")%per_class
            # A constant offset per replica preserves every lane's nominal ordering.
            phase = config.get('phase_span_s',0)*replica/max(1,replicas-1)
            release = template['release']-config['origin']+phase
            if release < 0 or release >= config['arrival_end_s']:
                continue
            task = {'key':f"{template['key']}@{replica}",'source_key':template['key'],
                    'stream':stream,'kind':kind,'release':release,'resources':np.asarray(template['resources']),
                    'curve':curve,'start':None,'site':None,'completion':None,'settled':None,
                    'due':None,'delivered':None,'billed_ws':0.,'bill':0.,'score':None,'raw_score':None,
                    'runtime_s':curve.runtime,'full_energy_ws':curve.integral(curve.runtime),'state':'unreleased'}
            tasks.append(task)
            push(release,'release',len(tasks)-1)
    if not tasks:
        raise ValueError('No tasks')
    for t in np.arange(dt,horizon+dt/2,dt):
        push(t,'settle')
    if config['admission_s']:
        for t in np.arange(0,horizon,config['admission_s']):
            push(t,'admit')
    previous_settlement = 0.
    controller_seconds = 0.
    cursor = completed = released = clipped = queued = 0
    trace, revisions = [], []
    expected_starts = np.zeros(streams)
    max_resource_error = max_energy_error = 0.
    while queue and queue[0][0]<=horizon:
        t = queue[0][0]
        batch = []
        while queue and queue[0][0] == t:
            batch.append(heapq.heappop(queue))
        finished, arrivals, packets = [], [], []
        do_settle = False
        do_admit = config['admission_s']==0
        for _,_,event,j in batch:
            if event=='settle': do_settle=True
            elif event=='admit': do_admit=True
            elif event=='release': arrivals.append(j)
            elif event=='deliver': packets.append(j)
            elif event=='finish':
                r=tasks[j]
                r['completion']=t
                r['state']='completed'
                used[r['site']]-=r['resources']
                del active[r['stream']]
                completed+=1
                finished.append(j)
                unsettled.append(j)
        if do_settle:
            energy=np.zeros(sites)
            increments=[]
            for j in list(active.values())+unsettled:
                r=tasks[j]
                cumulative=r['curve'].integral(t-r['start'])
                delta=cumulative-r['billed_ws']
                if delta < -1e-6: raise ValueError('Energy moved backwards')
                energy[r['site']]+=delta
                increments.append((j,delta,cumulative))
            grid=settlement(previous_settlement,t,energy)
            tariff=np.asarray(grid['prices'])
            if tariff.shape!=(sites,) or not np.isfinite(tariff).all(): raise ValueError('Invalid prices')
            for j,delta,cumulative in increments:
                r=tasks[j]
                # W*s -> MWh: no scenario multiplier.
                r['bill']+=delta/3.6e9*tariff[r['site']]
                r['billed_ws']=cumulative
            for j in unsettled:
                r=tasks[j]
                r['settled']=t
                r['due']=t+config['report_delay_s']
                ref=reference[str(r['kind'])]
                scoring_bill=r['bill']
                if config['method']=='completion_price':
                    # Explicit ablation: full energy priced at final settlement tariff.
                    # Not called the entire classical replicator model.
                    scoring_bill=r['billed_ws']/3.6e9*tariff[r['site']]
                raw=scoring_bill/(ref['mean_energy_kwh']/1000*config['reference_price']) + config['wait_weight']*(r['start']-r['release'])/ref['mean_runtime']
                r['raw_score']=float(raw)
                r['score']=float(np.clip(raw,0,10))
                clipped+=int(raw<0 or raw>10)
                if config['report_delay_s']==0: packets.append(j)
                else: push(r['due'],'deliver',j)
            unsettled=[]
        reports=[]
        for j in sorted(packets,key=lambda j:tasks[j]['key']):
            r=tasks[j]
            if r['delivered'] is not None or not r['completion']<=r['settled']<=r['due']==t:
                raise ValueError('Invalid report order')
            r['delivered']=t
            reports.append((t,r['completion'],r['kind'],r['site'],r['score']))
        controller_begin = time.perf_counter()
        ctl.receive(t,reports)
        for j in sorted(finished,key=lambda j:tasks[j]['stream']):
            r=tasks[j]
            decision=ctl.revise(r['stream'])
            decision.update(time=t,key=r['key'],own_report_visible=r['delivered'] is not None)
            if config['report_delay_s']>0 and decision['own_report_visible']:
                raise ValueError('Used own report before delayed delivery')
            revisions.append(decision)
        controller_seconds += time.perf_counter()-controller_begin
        for j in finished: enqueue_ready(tasks[j]['stream'],t)
        for j in sorted(arrivals,key=lambda j:tasks[j]['key']):
            r=tasks[j]
            r['state']='waiting'
            waiting[r['stream']].append(j)
            queued+=1
            enqueue_ready(r['stream'],t)
            released+=1
        if do_admit and t<horizon:
            # Explicit site FCFS: no future runtime lookahead or backfilling.
            # A large head job may block smaller jobs, identically in all arms.
            for site,q in enumerate(site_queues):
                while q:
                    _,b=q[0]
                    j=waiting[b][0]
                    r=tasks[j]
                    if int(ctl.strategy[b])!=site: raise ValueError('Queued strategy changed without completion')
                    if np.any(used[site]+r['resources']>capacities[site]+1e-8): break
                    if t<expected_starts[b] or t<r['release']: raise ValueError('Nonpreemption/FIFO violation')
                    heapq.heappop(q)
                    waiting[b].popleft()
                    queued-=1
                    ready.remove(b)
                    active[b]=j
                    r.update(start=t,site=site,state='running')
                    expected_starts[b]=t+r['curve'].runtime
                    used[site]+=r['resources']
                    push(expected_starts[b],'finish',j)
        max_resource_error=max(max_resource_error,float(np.maximum(used-capacities,0).max()),float(np.maximum(-used,0).max()))
        if max_resource_error>1e-7: raise ValueError('Resource bound violated')
        qcount=queued
        if completed+len(active)+qcount!=released: raise ValueError('Task conservation')
        if do_settle:
            if queued!=sum(map(len,waiting)):raise ValueError('Queue counter/ledger mismatch')
            waiting_sites=np.zeros(sites,dtype=int)
            running_sites=np.zeros(sites,dtype=int)
            for b,q in enumerate(waiting): waiting_sites[ctl.strategy[b]]+=len(q)
            for j in active.values(): running_sites[tasks[j]['site']]+=1
            trace.append({'start_s':previous_settlement,'end_s':t,'power_mw':grid['compute_mw'],
                          'prices':grid['prices'],'completed':completed,'running':len(active),'waiting':qcount,
                          'node_utilization':(used[:,0]/capacities[:,0]).tolist(),
                          'core_utilization':(used[:,1]/capacities[:,1]).tolist(),
                          'gpu_utilization':(used[:,2]/capacities[:,2]).tolist(),
                          'waiting_by_site':waiting_sites.tolist(),'running_by_site':running_sites.tolist(),
                          'visible_costs':[ctl.costs(k).tolist() for k in range(2)],
                          'shares':[[float(np.mean(ctl.strategy[offsets[k]:offsets[k+1]]==s)) if class_counts[k] else 0. for s in range(sites)] for k in range(2)],
                          'received':ctl.received,'revisions':ctl.revisions,
                          **{k:v for k,v in grid.items() if k not in ('prices','compute_mw')}})
            previous_settlement=t
            if config.get('progress_every_s') and t%config['progress_every_s']==0:
                print(f"simulated_hours={t/3600:.1f} completed={completed} running={len(active)} waiting={qcount}",flush=True)
    for r in tasks:
        expected=0. if r['start'] is None else r['curve'].integral(horizon-r['start'])
        max_energy_error=max(max_energy_error,abs(expected-r['billed_ws'])/max(1.,expected))
    pending=sum(r['due'] is not None and r['delivered'] is None for r in tasks)
    unready=sum(r['completion'] is not None and r['due'] is None for r in tasks)
    checks={'task_conservation':completed+len(active)+sum(map(len,waiting))==released,
            'report_conservation':completed==ctl.received+pending+unready,
            'completion_only_revisions':ctl.revisions==completed,
            'physical_energy_accounting':max_energy_error<1e-8,
            'capacity':max_resource_error<1e-7,
            'settlement_count':len(trace)==horizon//dt}
    if not all(checks.values()): raise ValueError(str(checks))
    warmup=config['warmup_s']
    measured=[r for r in trace if warmup<=r['start_s']<config['arrival_end_s']]
    cohort=[r for r in tasks if warmup<=r['release']<config['arrival_end_s']]
    waits=[r['start']-r['release'] for r in cohort if r['start'] is not None]
    # Tail ages include unfinished jobs: no claim of completed-case mean fairness.
    waiting_ages=[horizon-r['release'] for r in cohort if r['start'] is None]
    completed_cohort=[r for r in cohort if r['completion'] is not None]
    # Fixed-cohort censored measures: unfinished jobs remain in denominators.
    restricted_wait=[(r['start'] if r['start'] is not None else horizon)-r['release'] for r in cohort]
    restricted_response=[(r['completion'] if r['completion'] is not None else horizon)-r['release'] for r in cohort]
    completed_node_hours=sum(r['resources'][0]*r['curve'].runtime/3600 for r in completed_cohort)
    processed_node_hours=sum(r['resources'][0]*min(r['curve'].runtime,max(0.,horizon-r['start']))/3600 for r in cohort if r['start'] is not None)
    report_lags=[r['delivered']-r['completion'] for r in tasks if r['delivered'] is not None]
    # Attribute waiting to an unfinished predecessor versus waiting after it.
    # With nonoverlapping nominal lanes, predecessor waiting is propagated
    # execution delay, rather than overlap introduced by random lane hashing.
    grouped={}
    for r in tasks: grouped.setdefault(r['stream'],[]).append(r)
    predecessor_wait=remaining_wait=0.
    for group in grouped.values():
        previous=None
        for r in sorted(group,key=lambda r:(r['release'],r['key'])):
            if warmup<=r['release']<config['arrival_end_s']:
                end=r['start'] if r['start'] is not None else horizon
                available=0. if previous is None else (previous['completion'] if previous['completion'] is not None else horizon)
                blocked=max(0.,min(end,available)-r['release'])
                predecessor_wait+=blocked
                remaining_wait+=end-r['release']-blocked
            previous=r
    summary={'tasks':len(tasks),'source_jobs':len(jobs),'replicas':replicas,'sites':sites,'streams':streams,
             'completed':completed,'waiting_end':sum(map(len,waiting)),'running_end':len(active),
             'cohort_jobs':len(cohort),'cohort_completed':sum(r['completion'] is not None for r in cohort),
             'cohort_started':len(waits),'cohort_unstarted':len(waiting_ages),
             'cohort_completed_fraction':len(completed_cohort)/len(cohort) if cohort else None,
             'cohort_completed_node_hours':float(completed_node_hours),
             'cohort_processed_node_hours':float(processed_node_hours),
             'cohort_restricted_mean_wait_s':float(np.mean(restricted_wait)) if cohort else None,
             'cohort_restricted_mean_response_s':float(np.mean(restricted_response)) if cohort else None,
             'cohort_mean_predecessor_wait_s':predecessor_wait/len(cohort) if cohort else None,
             'cohort_mean_post_predecessor_wait_s':remaining_wait/len(cohort) if cohort else None,
             'cohort_restricted_p95_response_s':float(np.quantile(restricted_response,.95)) if cohort else None,
             'mean_report_completion_to_delivery_s':float(np.mean(report_lags)) if report_lags else None,
             'controller_seconds':controller_seconds,
             'started_cohort_mean_wait_s':float(np.mean(waits)) if waits else None,
             'started_cohort_p95_wait_s':float(np.quantile(waits,.95)) if waits else None,
             'unstarted_cohort_max_age_s':max(waiting_ages,default=0.),
             'task_energy_mwh':sum(r['billed_ws'] for r in tasks)/3.6e9,
             'task_bill_currency':sum(r['bill'] for r in tasks),'score_clipped_reports':clipped,
             'revisions':ctl.revisions,'switches':ctl.switches,'reports':ctl.received,
             'peak_it_mw':max(sum(r['power_mw']) for r in trace),
             'measurement_it_energy_mwh':sum(sum(r['power_mw'])*(r['end_s']-r['start_s'])/3600 for r in measured),
             'max_resource_error':max_resource_error,'max_energy_relative_error':max_energy_error}
    outputs=[{**{k:v for k,v in r.items() if k not in ('curve','resources')},
              'resources':r['resources'].tolist()} for r in tasks]
    return {'summary':summary,'checks':checks,'trace':trace,'tasks':outputs,'revisions':revisions}
