"""RTS 5-minute time-series economic dispatch for an explicitly bounded pilot.

Thermal units remain online. This is not unit commitment, an AC grid validation,
or an observed multi-datacenter deployment. Emergency slacks are always reported.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix


def rows(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


class GridReplay:
    def __init__(self, raw, site_buses, origin):
        buses=rows(raw/'rts_bus.csv')
        branches=rows(raw/'rts_branch.csv')
        gens=rows(raw/'rts_gen.csv')
        self.origin=origin
        self.index={int(b['Bus ID']):i for i,b in enumerate(buses)}
        self.n,self.g=len(buses),len(gens)
        self.sites=[self.index[x] for x in site_buses]
        self.area=np.array([int(b['Area']) for b in buses])
        self.base=np.array([float(b['MW Load']) for b in buses])
        self.shunt=np.array([float(b['MW Shunt G']) for b in buses])
        self.weights=np.zeros(self.n)
        for area in np.unique(self.area):
            mask=self.area==area
            self.weights[mask]=self.base[mask]/self.base[mask].sum()
        inc=np.zeros((len(branches),self.n))
        susceptance=[]
        self.limit=[]
        for k,b in enumerate(branches):
            inc[k,self.index[int(b['From Bus'])]]=1
            inc[k,self.index[int(b['To Bus'])]]=-1
            susceptance.append(100/(float(b['X'])*(float(b['Tr Ratio']) or 1)))
            self.limit.append(float(b['Cont Rating']))
        self.limit=np.asarray(self.limit)
        self.bf=np.asarray(susceptance)[:,None]*inc
        bb=inc.T@self.bf
        cg=np.zeros((self.n,self.g))
        self.lo=[];self.hi=[];self.ramp=[];self.cost=[];self.ids=[];self.fuels=[]
        for j,g in enumerate(gens):
            cg[self.index[int(g['Bus ID'])],j]=1
            thermal=g['Fuel'] in ('Oil','Coal','NG','Nuclear')
            self.ids.append(g['GEN UID']);self.fuels.append(g['Fuel'])
            self.lo.append(float(g['PMin MW']) if thermal else 0.)
            self.hi.append(float(g['PMax MW']) if thermal else 0. if g['Fuel'] in ('Storage','Sync_Cond') else max(0.,min(float(g['PMax MW']),float(g['MW Inj']))))
            self.ramp.append(float(g['Ramp Rate MW/Min']))
            self.cost.append(float(g['Fuel Price $/MMBTU'])*float(g['HR_avg_0'])/1000+float(g['VOM']) if thermal else 0.)
        self.lo=np.asarray(self.lo);self.hi=np.asarray(self.hi)
        self.ramp=np.asarray(self.ramp);self.cost=np.asarray(self.cost)
        self.thermal=np.array([x in ('Oil','Coal','NG','Nuclear') for x in self.fuels])
        self.theta=slice(self.g,self.g+self.n-1)
        self.eq=csr_matrix(np.c_[cg,-bb[:,1:],np.eye(self.n),-np.eye(self.n)])
        flow=np.zeros((len(branches),self.g+3*self.n-1));flow[:,self.theta]=self.bf[:,1:]
        self.ub=csr_matrix(np.r_[flow,-flow]);self.ubrhs=np.r_[self.limit,self.limit]
        self.c=np.r_[self.cost,np.zeros(self.n-1),np.full(2*self.n,10000.)]
        self.load=self.read_series(raw/'rts_rt_load.csv')
        self.wind=self.read_series(raw/'rts_rt_wind.csv')
        self.pv=self.read_series(raw/'rts_rt_pv.csv')
        renewable_cols=set(next(iter(self.wind.values())))|set(next(iter(self.pv.values())))
        missing=renewable_cols-set(self.ids)
        if missing: raise ValueError('Unmapped renewable units: '+str(missing))
        self.profiled=np.array([uid in renewable_cols for uid in self.ids])
        self.previous=None
        self.meta={'buses':self.n,'branches':len(branches),'generators':self.g,
                   'site_bus_ids':site_buses,'profiled_renewable_units':int(self.profiled.sum()),
                   'thermal_commitment':'fixed_all_online_pilot_limitation',
                   'other_generators':'legacy static injection; storage and synchronous condensers disabled',
                   'grid_model':'lossless DC economic dispatch; emergency spill and shed penalized at 10000',
                   'load_source':'RTS RT regional profiles distributed by bus base load',
                   'power_conversion':'1e-6 MW/W, no scenario scaling; task IT power only'}

    @staticmethod
    def read_series(path):
        result={}
        for r in rows(path):
            key=(int(r['Year']),int(r['Month']),int(r['Day']),int(r['Period']))
            if key in result: raise ValueError('Duplicate time-series row')
            result[key]={k:float(v) for k,v in r.items() if k not in ('Year','Month','Day','Period')}
        return result

    def __call__(self,start,end,energy_ws):
        if end-start!=300: raise ValueError('RTS pilot requires 300-s intervals')
        date=datetime.fromtimestamp(self.origin+start,timezone.utc)
        period=(date.hour*3600+date.minute*60+date.second)//300+1
        key=(date.year,date.month,date.day,period)
        if key not in self.load or key not in self.wind or key not in self.pv:
            raise ValueError('Missing RTS interval '+str(key))
        area_load=self.load[key]
        demand=np.array([area_load[str(a)] for a in self.area])*self.weights+self.shunt
        mw=np.asarray(energy_ws)/(end-start)*1e-6
        for bus,p in zip(self.sites,mw): demand[bus]+=p
        lo=self.lo.copy();hi=self.hi.copy()
        available={**self.wind[key],**self.pv[key]}
        for j,uid in enumerate(self.ids):
            if uid in available: hi[j]=max(0.,available[uid])
        if self.previous is not None:
            mask=self.thermal
            lo[mask]=np.maximum(lo[mask],self.previous[mask]-self.ramp[mask]*(end-start)/60)
            hi[mask]=np.minimum(hi[mask],self.previous[mask]+self.ramp[mask]*(end-start)/60)
        if np.any(lo>hi): raise ValueError('Inconsistent generator bounds')
        bounds=list(zip(lo,hi))+[(None,None)]*(self.n-1)+[(0.,float(x)) for x in demand]+[(0.,None)]*self.n
        sol=linprog(self.c,A_ub=self.ub,b_ub=self.ubrhs,A_eq=self.eq,b_eq=demand,bounds=bounds,method='highs')
        if not sol.success: raise RuntimeError(sol.message)
        x=sol.x;pg=x[:self.g]
        flows=self.bf@np.r_[0.,x[self.theta]]
        balance=float(abs(self.eq@x-demand).max())
        line=float(np.maximum(abs(flows)-self.limit,0).max())
        bound=float(max(np.maximum(lo-pg,0).max(),np.maximum(pg-hi,0).max()))
        if max(balance,line,bound)>1e-5: raise ValueError('Grid constraint violation')
        ramp_error=0. if self.previous is None else float(np.maximum(
            abs(pg[self.thermal]-self.previous[self.thermal])-self.ramp[self.thermal]*(end-start)/60,0).max())
        self.last_solution={'demand':demand.copy(),'pg':pg.copy(),'lo':lo.copy(),'hi':hi.copy(),
                            'flows':flows.copy(),'objective':float(sol.fun),'lmp':sol.eqlin.marginals.copy()}
        self.previous=pg.copy()
        return {'prices':sol.eqlin.marginals[self.sites].tolist(),'compute_mw':mw.tolist(),
                'system_demand_mw':float(demand.sum()),'generation_cost_per_h':float(self.cost@pg),
                'shed_mw':float(x[self.g+self.n-1:self.g+2*self.n-1].sum()),
                'spill_mw':float(x[self.g+2*self.n-1:].sum()),
                'renewable_curtailment_mw':float((hi[self.profiled]-pg[self.profiled]).sum()),
                'max_line_loading':float((abs(flows)/self.limit).max()),
                'balance_error_mw':balance,'line_excess_mw':line,'generator_excess_mw':bound,
                'ramp_excess_mw':ramp_error}
