"""Lossless DC dispatch and bounded five-minute redispatch with explicit emergency slacks."""
import numpy as np


def network_matrices(n,branches,base_mva=100.):
    inc=np.zeros((len(branches),n));b=[];limits=[]
    for k,(i,j,x,tap,rating) in enumerate(branches):
        if i==j or x<=0 or rating<=0 or tap<0:raise ValueError('Invalid branch')
        inc[k,i]=1;inc[k,j]=-1;b.append(base_mva/(x*(tap or 1.)));limits.append(rating)
    bf=np.array(b)[:,None]*inc;bb=inc.T@bf
    if np.linalg.matrix_rank(bb)!=n-1:raise ValueError('Disconnected network')
    return bf,bb,np.array(limits)


class Grid:
    def __init__(self,n,branches,gen_bus,pmin,pmax,cost,ramp):
        self.n=n;self.g=len(gen_bus);self.bf,self.bb,self.limit=network_matrices(n,branches)
        self.pmin=np.asarray(pmin,float);self.pmax=np.asarray(pmax,float);self.cost=np.asarray(cost,float);self.ramp=np.asarray(ramp,float)
        if np.any(self.pmin<0) or np.any(self.pmax<self.pmin) or np.any(self.ramp<0):raise ValueError('Invalid generator bounds')
        self.cg=np.zeros((n,self.g));self.cg[gen_bus,np.arange(self.g)]=1
        self.theta=slice(self.g,self.g+n-1);self.shed=slice(self.g+n-1,self.g+2*n-1);self.spill=slice(self.g+2*n-1,self.g+3*n-1)
        self.nvar=self.g+3*n-1
        self.eq=np.c_[self.cg,-self.bb[:,1:],np.eye(n),-np.eye(n)]
        flow=np.zeros((len(branches),self.nvar));flow[:,self.theta]=self.bf[:,1:]
        self.ub=np.r_[flow,-flow];self.ubrhs=np.r_[self.limit,self.limit]

    def solve(self,demand,reference_pg=None,minutes=5.):
        from scipy.optimize import linprog
        d=np.asarray(demand,float)
        if d.shape!=(self.n,) or not np.all(np.isfinite(d)) or d.min()<0:raise ValueError('Invalid demand')
        lower=self.pmin.copy();upper=self.pmax.copy();eq=self.eq;ub=self.ub;rhs=self.ubrhs
        c=np.r_[self.cost,np.zeros(self.n-1),np.full(2*self.n,10000.)]
        bounds=list(zip(lower,upper))+[(None,None)]*(self.n-1)+[(0,float(x)) for x in d]+[(0,None)]*self.n
        if reference_pg is not None:
            pg=np.asarray(reference_pg,float)
            lower=np.maximum(lower,pg-self.ramp*minutes);upper=np.minimum(upper,pg+self.ramp*minutes)
            bounds[:self.g]=list(zip(lower,upper));bounds+=[(0,None)]*self.g
            eq=np.c_[eq,np.zeros((self.n,self.g))];ub=np.c_[ub,np.zeros((len(ub),self.g))]
            positive=np.zeros((self.g,self.nvar+self.g));positive[:,:self.g]=np.eye(self.g);positive[:,self.nvar:]=-np.eye(self.g)
            negative=positive.copy();negative[:,:self.g]=-np.eye(self.g)
            ub=np.r_[ub,positive,negative];rhs=np.r_[rhs,pg,-pg]
            c=np.r_[np.zeros(self.g+self.n-1),np.full(2*self.n,10000.),np.ones(self.g)]
        sol=linprog(c,A_ub=ub,b_ub=rhs,A_eq=eq,b_eq=d,bounds=bounds,method='highs')
        if not sol.success:raise RuntimeError('DC LP failure: '+sol.message)
        x=sol.x;angles=np.r_[0.,x[self.theta]];flows=self.bf@angles
        residual=float(np.max(np.abs(eq@x-d)));violation=float(np.max(np.maximum(abs(flows)-self.limit,0)))
        if residual>1e-5 or violation>1e-5:raise RuntimeError('DC solution residual too large')
        gen=x[:self.g]
        if np.max(np.maximum(lower-gen,0))>1e-5 or np.max(np.maximum(gen-upper,0))>1e-5:raise RuntimeError('Generator bound violation')
        return {'pg':gen,'flows':flows,'shed_mw':float(x[self.shed].sum()),'spill_mw':float(x[self.spill].sum()),
                'dispatch_fuel_proxy_per_hour':float(self.cost@gen),'redispatch_l1_mw':float(abs(gen-reference_pg).sum()) if reference_pg is not None else 0.,
                'max_line_loading':float(np.max(abs(flows)/self.limit)),'balance_residual_mw':residual,'line_violation_mw':violation}
