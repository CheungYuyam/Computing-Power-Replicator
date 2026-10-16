"""Completion-event plant with causal interval settlement and delayed evidence.

Real runtimes/power curves exist only inside the plant. The frozen controller
receives completed delivered reports and peer strategy labels.
"""
import hashlib
import heapq
import importlib.util
import sys
from collections import deque
from pathlib import Path
import numpy as np

import os
ROOT=Path(os.environ.get('CP_DATA_ROOT', str(Path(__file__).resolve().parents[1]/'data')))
PARENT=Path(__file__).resolve().parent.parent/'dual_lag_v1'

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def load_parent():
    for line in (PARENT/'SHA256SUMS').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if digest(PARENT/n)!=h:raise ValueError('Frozen parent modified: '+n)
    spec=importlib.util.spec_from_file_location('engineering_frozen_plant',PARENT/'plant.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def load_grid():
    sys.path.insert(0,str(PARENT))
    from rts_adapter import load_network, rows
    grid,base,shunt,_,meta=load_network()
    index={int(b['Bus ID']):i for i,b in enumerate(rows(ROOT/'raw/rts_bus.csv'))}
    meta={**meta,'actual_compute_bus_ids':[101,201],'legacy_three_bus_allocation_used':False}
    return grid,base,shunt,[index[101],index[201]],meta

class EventTape:
    """Same exogenous draws for each business/completion ordinal across cases."""
    def __init__(self,seed):
        self.seed=seed;self.ordinals=[0]*64;self.business=None;self.pending=None;self.records=[]
    def choice(self,peers):
        if self.pending is not None:raise ValueError('Unconsumed draw')
        b=self.business;n=self.ordinals[b]
        rng=np.random.default_rng(np.random.SeedSequence([self.seed,b,n]))
        index=int(rng.integers(len(peers)));u=float(rng.random())
        self.pending={'business':b,'ordinal':n,'peer_index':index,'uniform':u,'candidate':int(peers[index])}
        return peers[index]
    def random(self):
        if self.pending is None:raise ValueError('Missing candidate draw')
        record=self.pending;self.pending=None;self.ordinals[self.business]+=1;self.records.append(record)
        return record['uniform']

class GridSettlement:
    def __init__(self,parent,grid,base,shunt,buses,scale,origin,daystart,background=1.):
        self.parent=parent;self.grid=grid;self.base=base;self.shunt=shunt;self.buses=buses
        self.scale=scale;self.origin=origin;self.daystart=daystart;self.background=background;self.pg=None
    def __call__(self,start,end,energy_ws):
        mw=np.asarray(energy_ws)/(end-start)*self.scale
        hour=(self.origin+start-self.daystart)/3600
        demand=self.background*(.85+.15*np.sin(2*np.pi*(hour-6)/24))*self.base+self.shunt
        demand=demand.copy()
        for site,bus in enumerate(self.buses):demand[bus]+=mw[site]
        sol=self.parent.economic_dispatch(self.grid,demand,self.pg,(end-start)/60)
        pg=sol['pg'];sol['generator_excess']=float(max(np.maximum(self.grid.pmin-pg,0).max(),np.maximum(pg-self.grid.pmax,0).max()))
        self.pg=pg.copy()
        return {**{k:float(v) for k,v in sol.items() if k not in ('pg','lmp')},
                'prices':sol['lmp'][self.buses].tolist(),'compute_mw':mw.tolist()}

def rectangle_energy(runtime,power,elapsed):
    """Independent clipped rectangle integral for final physical accounting."""
    stop=max(0.,min(float(elapsed),runtime));total=0.
    for j,w in enumerate(power):
        start=20.*j;end=min(20.*(j+1),runtime)
        if j==len(power)-1:end=runtime
        total+=max(0.,min(stop,end)-start)*float(w)
        if end>=stop:break
    return total

def simulate(parent,jobs,fit,price_provider,*,origin=0.,daystart=0.,seed=17,lag=900.,
             admission_period=0.,settlement=300.,horizon=172800.,incentive=True):
    if lag<0 or admission_period not in (0,150,300) or horizon<=0 or horizon%settlement:
        raise ValueError('Unsupported time protocol')
    capacity=np.asarray(fit['capacity_per_center'],float)
    if capacity.shape==(3,):capacity=np.tile(capacity,(2,1))
    if capacity.shape!=(2,3) or (capacity<0).any():raise ValueError('Invalid resource capacity')
    ctl=parent.EvidenceController(seed);initial_strategy=ctl.strategy.copy()
    tape=EventTape(seed);ctl.rng=tape
    rows=[]
    for j in jobs:
        resources=np.asarray(j['resources'],float);runtime=float(j['runtime']);power=np.asarray(j['power_w'],float)
        if resources.shape!=(3,) or (resources<0).any() or runtime<=0 or len(power)<1 or not np.isfinite(power).all() or (power<0).any():
            raise ValueError('Invalid prepared task')
        kind=int(resources[2]>0);business=kind*32+parent.stable_int(j['key'])%32
        rows.append({'key':j['key'],'kind':kind,'business':business,'release':float(j['release'])-origin,
            'runtime':runtime,'power':power,'resources':resources,'curve':parent.Curve(runtime,power),
            'state':'unreleased','start':None,'site':None,'physical_completion':None,'settlement_ready':None,
            'report_due':None,'report_delivered':None,'revision_time':None,'own_report_at_revision':None,
            'energy_ws':0.,'billed_ws':0.,'normalized_bill':0.,'raw_cost':None,'cost':None})
    rows.sort(key=lambda r:(r['release'],r['key']))
    if len({r['key'] for r in rows})!=len(rows):raise ValueError('Duplicate keys')
    bykey={r['key']:r for r in rows};waiting=[deque() for _ in range(64)];active={};used=np.zeros((2,3));cursor=0
    queue=[];serial=0;last=0.;settled=0.;interval_energy={};unsettled=[];delivered=set();revisions=[];ledger=[];trace=[];events=[]
    max_resource=0.;finished_count=0;infeasible=0;released=0;interval_completed=[0,0];interval_delivered=[0,0]
    def push(t,kind,key=None):
        nonlocal serial
        if t<0:raise ValueError('Negative event time')
        serial+=1;heapq.heappush(queue,(float(t),serial,kind,key))
    for r in rows:
        if r['release']<horizon:push(max(0.,r['release']),'release',r['key'])
    for t in np.arange(settlement,horizon+settlement/2,settlement):push(t,'settle')
    if admission_period:
        for t in np.arange(0,horizon,admission_period):push(t,'admit')
    while queue and queue[0][0]<=horizon:
        t=queue[0][0]
        for r in active.values():
            e=r['curve'].between(last-r['start'],t-r['start'])
            if e < -1e-7:raise ValueError('Negative elapsed energy')
            r['energy_ws']+=e;interval_energy[r['key']]=interval_energy.get(r['key'],0.)+e
        last=t;batch=[]
        while queue and queue[0][0]==t:batch.append(heapq.heappop(queue))
        finished=[];arrivals=[];packets=[];do_settle=False;do_admit=admission_period==0
        for _,_,event,key in batch:
            if event=='settle':do_settle=True;continue
            if event=='admit':do_admit=True;continue
            r=bykey[key]
            if event=='release':arrivals.append(r)
            elif event=='finish':
                r['state']='completed';r['physical_completion']=t;finished.append(r);unsettled.append(r)
                used[r['site']]-=r['resources'];del active[r['business']]
                finished_count+=1;interval_completed[r['kind']]+=1
            elif event=='deliver':packets.append(r)
        grid_row=None
        if do_settle:
            energy=np.zeros(2)
            for key,e in interval_energy.items():energy[bykey[key]['site']]+=e
            grid_row=price_provider(settled,t,energy.copy())
            tariff=np.asarray(grid_row['prices'],float)
            if tariff.shape!=(2,) or not np.isfinite(tariff).all():raise ValueError('Invalid settled prices')
            hour=(origin+settled-daystart)/3600
            for key,e in interval_energy.items():
                r=bykey[key];site=r['site'];toll=float(incentive and site==0 and 12<=hour<14)
                r['billed_ws']+=e;r['normalized_bill']+=e/3600000*(tariff[site]/40.+toll)
                ledger.append({'key':key,'interval_start':settled,'interval_end':t,'site':site,'energy_ws':e,
                    'price':float(tariff[site]),'incentive_normalized':toll})
            interval_energy={}
            for r in sorted(unsettled,key=lambda r:(r['physical_completion'],r['key'])):
                r['settlement_ready']=t;r['report_due']=t+lag
                reference=fit['classes'][str(r['kind'])]
                r['raw_cost']=r['normalized_bill']/max(reference['mean_energy_kwh'],1e-6)+.1*(r['start']-r['release'])/reference['mean_runtime']
                r['cost']=float(np.clip(r['raw_cost'],0,10))
                if lag==0:packets.append(r)
                else:push(t+lag,'deliver',r['key'])
            unsettled=[]
        reports=[]
        for r in sorted(packets,key=lambda r:(r['report_due'],r['key'])):
            if r['key'] in delivered or r['report_due']>t or r['settlement_ready']<r['physical_completion']:
                raise ValueError('Invalid report timing')
            delivered.add(r['key']);r['report_delivered']=t;interval_delivered[r['kind']]+=1
            reports.append((r['report_due'],r['physical_completion'],r['kind'],r['site'],r['cost']))
        ctl.receive(t,reports)
        for r in sorted(finished,key=lambda r:r['business']):
            b=r['business'];old=int(ctl.strategy[b]);costs=(ctl.V[r['kind']]/np.maximum(ctl.U[r['kind']],1e-12)).copy()
            tape.business=b;ctl.revise(b);draw=tape.records[-1]
            prob=float(np.clip(.15*(costs[old]-costs[draw['candidate']]),0,1))
            r['revision_time']=t;r['own_report_at_revision']=r['key'] in delivered
            revisions.append({'key':r['key'],'time':t,'business':b,'kind':r['kind'],'old':old,'new':int(ctl.strategy[b]),
                'cost0':float(costs[0]),'cost1':float(costs[1]),'candidate':draw['candidate'],'probability':prob,
                'uniform':draw['uniform'],'ordinal':draw['ordinal'],'own_report_visible':r['own_report_at_revision'],
                'reports_visible_count':len(delivered)})
        for r in sorted(arrivals,key=lambda r:(r['release'],r['key'])):
            released+=1
            if not any(np.all(r['resources']<=capacity[s]+1e-9) for s in (0,1)):
                r['state']='infeasible';infeasible+=1
            else:r['state']='waiting';waiting[r['business']].append(r)
        if do_admit and t<horizon:
            while True:
                started=False
                for offset in range(64):
                    b=(cursor+offset)%64
                    if b in active or not waiting[b]:continue
                    r=waiting[b][0];site=int(ctl.strategy[b])
                    if np.any(used[site]+r['resources']>capacity[site]+1e-9):continue
                    waiting[b].popleft();r.update(state='active',start=t,site=site);active[b]=r
                    used[site]+=r['resources'];cursor=(b+1)%64;push(t+r['runtime'],'finish',r['key']);started=True;break
                if not started:break
        max_resource=max(max_resource,float(np.maximum(used-capacity,0).max()),float(np.maximum(-used,0).max()))
        expected=np.zeros((2,3))
        for r in active.values():expected[r['site']]+=r['resources']
        if not np.allclose(used,expected,atol=1e-7,rtol=0) or max_resource>1e-7:raise ValueError('Resource accounting')
        counts={'completed':finished_count,'active':len(active),'waiting':sum(map(len,waiting)),'infeasible':infeasible,'unreleased':len(rows)-released}
        if sum(counts.values())!=len(rows):raise ValueError('Task conservation')
        events.append({'time':t,**counts,'revisions':ctl.revisions,'reported':len(delivered),'unsettled_completed':len(unsettled),
            'strategy0_type0':float(np.mean(ctl.strategy[:32]==0)),'strategy0_type1':float(np.mean(ctl.strategy[32:]==0))})
        if grid_row is not None:
            visible=ctl.V/np.maximum(ctl.U,1e-12)
            trace.append({'interval_start':settled,'interval_end':t,'state_sample_time':t,
                'site0_mw':float(grid_row['compute_mw'][0]),'site1_mw':float(grid_row['compute_mw'][1]),
                **counts,'revisions':ctl.revisions,'switches':ctl.switches,'reported':len(delivered),
                'strategy0_type0':float(np.mean(ctl.strategy[:32]==0)),'strategy0_type1':float(np.mean(ctl.strategy[32:]==0)),
                'completion_type0':interval_completed[0],'completion_type1':interval_completed[1],
                'delivered_type0':interval_delivered[0],'delivered_type1':interval_delivered[1],
                'visible_c00':float(visible[0,0]),'visible_c01':float(visible[0,1]),'visible_c10':float(visible[1,0]),'visible_c11':float(visible[1,1]),
                'price0':float(grid_row['prices'][0]),'price1':float(grid_row['prices'][1]),
                **{k:float(grid_row.get(k,0)) for k in ['balance','line_excess','ramp_excess','generator_excess','loading','shed','spill','fuel']}})
            settled=t;interval_completed=[0,0];interval_delivered=[0,0]
    max_energy=0.;max_bill=0.;expected_total=0.
    for r in rows:
        expected=0. if r['start'] is None else rectangle_energy(r['runtime'],r['power'],horizon-r['start'])
        max_energy=max(max_energy,abs(r['energy_ws']-expected)/max(expected,1.))
        max_bill=max(max_bill,abs(r['billed_ws']-r['energy_ws'])/max(r['energy_ws'],1.));expected_total+=expected
    for b in range(64):
        ordered=[r for r in rows if r['business']==b and r['state']!='infeasible' and r['release']<horizon]
        seen_waiting=False;end=-np.inf
        for r in ordered:
            if r['start'] is None:seen_waiting=True;continue
            if seen_waiting or r['start']<end-1e-8 or r['start']<max(0,r['release'])-1e-8:raise ValueError('FIFO/nonpreemption')
            end=r['start']+r['runtime']
    done=[r for r in rows if r['state']=='completed']
    pending=sum(r['settlement_ready'] is not None and r['report_delivered'] is None for r in done)
    unready=sum(r['settlement_ready'] is None for r in done)
    waits=[r['start']-r['release'] for r in rows if r['start'] is not None and daystart<=origin+r['start']<daystart+86400]
    measured=[r for r in trace if daystart<=origin+r['interval_start']<daystart+86400]
    row={'seed':seed,'feedback_delay_s':lag,'admission_period_s':admission_period,'settlement_s':settlement,'incentive':incentive,
        'tasks':len(rows),'released':released,'completed_all':len(done),'completed_measurement':sum(daystart<=origin+r['physical_completion']<daystart+86400 for r in done),
        'waiting_end':sum(map(len,waiting)),'active_end':len(active),'infeasible':infeasible,'unreleased_end':len(rows)-released,
        'reports_generated':sum(r['settlement_ready'] is not None for r in done),'reports_delivered':len(delivered),
        'completed_unsettled_end':unready,'pending_reports_end':pending,'revisions':ctl.revisions,'switches':ctl.switches,
        'wait_sample_count':len(waits),'mean_wait_s':float(np.mean(waits)) if waits else None,'p95_wait_s':float(np.quantile(waits,.95)) if waits else None,
        'raw_energy_kwh':expected_total/3600000,'peak_compute_mw':max((r['site0_mw']+r['site1_mw'] for r in measured),default=0.),
        'generation_cost_scenario':sum(r['fuel']*(r['interval_end']-r['interval_start'])/3600 for r in measured),
        'shed_mwh':sum(r['shed']*(r['interval_end']-r['interval_start'])/3600 for r in measured),
        'spill_mwh':sum(r['spill']*(r['interval_end']-r['interval_start'])/3600 for r in measured),
        'max_line_loading':max((r['loading'] for r in trace),default=0.),'resource_excess':max_resource,
        'physical_energy_relative_error':max_energy,'billing_energy_relative_error':max_bill,
        'max_settlement_wait_s':max((r['settlement_ready']-r['physical_completion'] for r in done if r['settlement_ready'] is not None),default=0.)}
    for k in ['balance','line_excess','ramp_excess','generator_excess']:row['max_'+k]=max((r[k] for r in trace),default=0.)
    checks={'task_conservation':len(rows)==len(done)+len(active)+sum(map(len,waiting))+infeasible+len(rows)-released,
        'report_conservation':len(done)==pending+unready+len(delivered),'completion_only_revisions':ctl.revisions==len(done),
        'physical_energy':max_energy<1e-8,'billing_energy':max_bill<1e-8,'capacity':max_resource<1e-7,
        'feedback_timing':all(r['report_due']==r['settlement_ready']+lag and r['settlement_ready']>=r['physical_completion'] and (r['report_delivered'] is None or r['report_delivered']==r['report_due']) for r in done if r['settlement_ready'] is not None),
        'positive_lag_excludes_own_report':lag==0 or all(not r['own_report_at_revision'] for r in done),
        'settlement_interval_count':len(trace)==int(horizon/settlement),'grid_constraints':all(row['max_'+k]<1e-5 for k in ['balance','line_excess','ramp_excess','generator_excess']),
        'fifo_nonpreemptive':True,'no_future_feedback':ctl.max_future==0}
    if not all(checks.values()):raise ValueError('Case integrity '+str(checks))
    tasks=[{k:v for k,v in r.items() if k not in ['curve','power']} for r in rows]
    return {'summary':row,'integrity':checks,'tasks':tasks,'revisions':revisions,'ledger':ledger,'trace':trace,'events':events,
        'draws':tape.records,'initial_strategy':initial_strategy.tolist(),'final_strategy':ctl.strategy.tolist()}
