"""Causal plant/controller separation. Curves are accessed by plant only.
Task assignment to persistent businesses is a synthetic protocol, not inferred behavior.
"""
import hashlib,heapq
from collections import deque
import numpy as np
from scipy.optimize import linprog

def stable_int(key): return int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:8],'big')

class Curve:
    def __init__(self,runtime,power):
        self.runtime=float(runtime); self.p=np.asarray(power,float)
        edges=np.minimum(np.arange(len(self.p)+1)*20.,self.runtime); edges[-1]=self.runtime
        self.edges=edges; self.cum=np.r_[0.,np.cumsum(np.maximum(np.diff(edges),0)*self.p)]
    def integral(self,t):
        t=float(np.clip(t,0,self.runtime)); k=min(np.searchsorted(self.edges,t,side='right')-1,len(self.p)-1)
        return float(self.cum[k]+self.p[k]*(t-self.edges[k]))
    def between(self,a,b): return self.integral(b)-self.integral(a)

def economic_dispatch(grid,demand,previous=None,minutes=5):
    lo=grid.pmin.copy(); hi=grid.pmax.copy()
    if previous is not None:
        lo=np.maximum(lo,previous-grid.ramp*minutes); hi=np.minimum(hi,previous+grid.ramp*minutes)
    bounds=list(zip(lo,hi))+[(None,None)]*(grid.n-1)+[(0,float(x)) for x in demand]+[(0,None)]*grid.n
    c=np.r_[grid.cost,np.zeros(grid.n-1),np.full(2*grid.n,10000.)]
    sol=linprog(c,A_ub=grid.ub,b_ub=grid.ubrhs,A_eq=grid.eq,b_eq=demand,bounds=bounds,method='highs')
    if not sol.success: raise RuntimeError('Economic DC-OPF '+sol.message)
    x=sol.x; pg=x[:grid.g]; flow=grid.bf@np.r_[0.,x[grid.theta]]
    return {'pg':pg,'lmp':sol.eqlin.marginals,'fuel':float(grid.cost@pg),'shed':float(x[grid.shed].sum()),'spill':float(x[grid.spill].sum()),'balance':float(abs(grid.eq@x-demand).max()),'line_excess':float(np.maximum(abs(flow)-grid.limit,0).max()),'loading':float((abs(flow)/grid.limit).max()),'ramp_excess':float(np.maximum(abs(pg-previous)-grid.ramp*minutes,0).max()) if previous is not None else 0.}

class EvidenceController:
    """Receives only delivered, completed reports and observable peer strategies."""
    def __init__(self,seed,businesses=64):
        self.rng=np.random.default_rng(seed); self.strategy=self.rng.integers(0,2,businesses)
        self.U=np.ones((2,2)); self.V=np.ones((2,2)); self.last_t=0.; self.revisions=0; self.switches=0; self.max_future=0.
    def receive(self,t,records):
        decay=np.exp(-(t-self.last_t)/21600); self.U*=decay; self.V*=decay; self.last_t=t
        for sent,completed,kind,site,cost in records:
            if sent>t+1e-8 or completed>sent+1e-8: raise RuntimeError('Future feedback')
            self.U[kind,site]+=1; self.V[kind,site]+=cost
    def revise(self,business):
        kind=business//32; peers=self.strategy[kind*32:(kind+1)*32]; candidate=int(self.rng.choice(peers)); old=self.strategy[business]
        c=self.V[kind]/np.maximum(self.U[kind],1e-12)
        prob=float(np.clip(.15*(c[old]-c[candidate]),0,1)); self.revisions+=1
        if self.rng.random()<prob: self.strategy[business]=candidate; self.switches+=int(candidate!=old)

def simulate(jobs,fit,grid,base,shunt,dc_buses,origin,daystart,seed,clock,lag,background=1.,dt=300.,horizon=172800.):
    ctl=EvidenceController(seed); capacity=np.asarray(fit['capacity_per_center'],float); used=np.zeros((2,3)); waiting=[deque() for _ in range(64)]; active={}; inbox=[]; records=[]
    # Truth stays in these plant objects; controller has no reference to them.
    items=[]
    for job in jobs:
        kind=int(job['resources'][2]>0); business=kind*32+stable_int(job['key'])%32
        items.append({'release':job['release']-origin,'business':business,'kind':kind,'resources':np.asarray(job['resources'],float),'curve':Curve(job['runtime'],job['power_w']),'key':job['key']})
    items.sort(key=lambda x:(x['release'],x['key'])); cursor=0; pg=None; prices=np.ones(2)*40.; completed=0; reported=0; released=0; infeasible=0
    waits=[]; finished_measure=0; waits_measure=[]; total_integrated=0.; total_expected=0.; balance=0.; line=0.; ramp=0.; total_shed=0.; total_spill=0.; fuel=0.; peak=0.; power_series=[]; switch0=0
    periods=np.array([fit['classes'][str(i//32)]['mean_runtime'] for i in range(64)]); next_tick=periods.copy()
    max_capacity=0.; max_report_age=0.; total_reports=0; measured_energy=0.
    end=horizon; serial=0
    for step in range(int(round(end/dt))):
        t=step*dt; absolute=origin+t; measure=daystart<=absolute<daystart+86400
        # Delivered packets first, then periodic updates; completion reports below can be immediate.
        delivered=[]
        while inbox and inbox[0][0]<=t+1e-8:
            sent,_,completed_t,kind,site,cost=heapq.heappop(inbox); delivered.append((sent,completed_t,kind,site,cost)); reported+=1; max_report_age=max(max_report_age,t-completed_t)
        ctl.receive(t,delivered)
        if clock=='periodic':
            for b in range(64):
                if t>=next_tick[b]: ctl.revise(b); next_tick[b]+=periods[b]
        while cursor<len(items) and items[cursor]['release']<=t:
            item=items[cursor]; cursor+=1; released+=1
            if np.any(item['resources']>capacity): infeasible+=1; continue
            waiting[item['business']].append(item)
        # FIFO within business, deterministic rotating round-robin across businesses.
        for offset in range(64):
            b=(offset+step)%64
            if b in active or not waiting[b]: continue
            item=waiting[b][0]; site=int(ctl.strategy[b])
            if np.all(used[site]+item['resources']<=capacity+1e-8):
                waiting[b].popleft(); item.update(start=t,site=site,cost=0.,energy=0.); active[b]=item; used[site]+=item['resources']
                wait=t-item['release']; waits.append(wait)
                if measure: waits_measure.append(wait)
        max_capacity=max(max_capacity,float(np.maximum(used-capacity,0).max()))
        energy=np.zeros(2); individual=[]
        for b,item in active.items():
            e=item['curve'].between(t-item['start'],t+dt-item['start']); energy[item['site']]+=e; item['energy']+=e; individual.append((b,item,e))
        mw=energy/dt*fit['power_mw_per_w']; total_integrated+=float(energy.sum())
        hour=(absolute-daystart)/3600
        # Fixed, transparent synthetic background profile, not observed RTS time series.
        bg=background*(.85+.15*np.sin(2*np.pi*(hour-6)/24))
        demand=bg*base+shunt
        for site,bus in enumerate(dc_buses): demand[bus]+=mw[site]
        sol=economic_dispatch(grid,demand,pg,dt/60); pg=sol['pg']; prices=sol['lmp'][dc_buses]
        balance=max(balance,sol['balance']); line=max(line,sol['line_excess']); ramp=max(ramp,sol['ramp_excess'])
        if measure:
            measured_energy+=float(energy.sum())/3600000; total_shed+=sol['shed']*dt/3600; total_spill+=sol['spill']*dt/3600; fuel+=sol['fuel']*dt/3600; peak=max(peak,float(mw.sum())); switch0=ctl.switches
        # Payoffs are generated by completed consumption, then delivered with known injected delay.
        finished=[]; immediate=[]
        for b,item,e in individual:
            # Predeclared synthetic congestion incentive: +40 currency/MWh at site 0,
            # 12:00-14:00 of the measurement day. It is not an observed market tariff.
            toll=1. if item['site']==0 and 12<=hour<14 else 0.
            item['cost']+=e/3600000*(prices[item['site']]/40.+toll)
            if t+dt-item['start']>=item['curve'].runtime-1e-8:
                completed_t=t+dt; kind=item['kind']; observed=fit['classes'][str(kind)]
                cost=item['cost']/max(observed['mean_energy_kwh'],1e-6)+.1*(item['start']-item['release'])/observed['mean_runtime']
                cost=float(np.clip(cost,0,10)); serial+=1; total_reports+=1
                if lag==0: immediate.append((completed_t,completed_t,kind,item['site'],cost)); reported+=1
                else: heapq.heappush(inbox,(completed_t+lag,serial,completed_t,kind,item['site'],cost))
                used[item['site']]-=item['resources']; finished.append(b); completed+=1; total_expected+=item['curve'].cum[-1]
                if measure: finished_measure+=1
        if immediate: ctl.receive(t+dt,immediate)
        for b in finished:
            del active[b]
            if clock=='completion': ctl.revise(b)
        power_series.append((absolute,*mw,ctl.strategy.mean(),len(active),sum(map(len,waiting)),*prices,sol['loading'],sol['shed']))
    remaining_energy=sum(x['energy'] for x in active.values())
    err=abs(total_integrated-total_expected-remaining_energy)/max(total_integrated,1)
    row={'seed':seed,'clock':clock,'feedback_delay_s':lag,'background_scale':background,'dt_s':dt,'released':released,'completed_all':completed,'completed_measurement':finished_measure,'waiting_end':sum(map(len,waiting)),'active_end':len(active),'infeasible_resource_jobs':infeasible,'pending_reports_end':len(inbox),'reported':reported,'report_generated':total_reports,'max_report_age_s':max_report_age,'switches':ctl.switches,'revisions':ctl.revisions,'mean_wait_s':float(np.mean(waits_measure)) if waits_measure else 0.,'p95_wait_s':float(np.quantile(waits_measure,.95)) if waits_measure else 0.,'wait_sample_count':len(waits_measure),'measurement_energy_kwh_unscaled':measured_energy,'peak_compute_mw':peak,'shed_mwh':total_shed,'spill_mwh':total_spill,'generation_cost_scenario':fuel,'energy_accounting_error':err,'balance_residual_mw':balance,'line_excess_mw':line,'ramp_excess_mw':ramp,'resource_excess':max_capacity,'task_balance_error':released-completed-sum(map(len,waiting))-len(active)-infeasible}
    return row,np.array(power_series)
