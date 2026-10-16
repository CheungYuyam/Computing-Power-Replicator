"""A specified completion-clock model; numerical validation is not a novelty proof.

n[r,i,l]: Erlang execution phase mass. a: accumulated normalized cost mass.
F,B: reports in transmission (count and cost). U,V: exponentially retained
received evidence. A completion resets accumulated cost and selects next strategy.
"""
import argparse
import numpy as np
from scipy.integrate import solve_ivp
from common import run_dir,Progress,write_json,csv_write

def switching(x,c,beta=.2):
    # Rows are origin, columns destination. Candidate drawn within task class.
    p=x[None,:]*np.clip(beta*(c[:,None]-c[None,:]),0,1)
    np.fill_diagonal(p,0); p[np.diag_indices(len(x))]=1-p.sum(axis=1)
    return p

def costs(n):
    # Dimensionless illustrative congestion, not money or measured grid prices.
    load=n.sum(axis=(0,2)); return np.array([.7,1.]) + 1.4*load

def initial():
    n=np.zeros((2,2,2)); n[:,0,0]=.35; n[:,1,0]=.15
    a=np.zeros_like(n); z=np.zeros((2,2)); U=np.ones((2,2))*.1
    V=U*np.array([1.4,1.7]); return np.r_[n.ravel(),a.ravel(),z.ravel(),z.ravel(),U.ravel(),V.ravel()]

def rhs(t,y,tau=.5,heterogeneous=True,marked=True):
    n=y[:8].reshape(2,2,2); a=y[8:16].reshape(2,2,2)
    F,B,U,V=[y[i:i+4].reshape(2,2) for i in (16,20,24,28)]
    means=np.array([[1.,1.4],[2.,2.8]]) if heterogeneous else np.ones((2,2))
    mu=2/means; ref=np.array([1.,2.]) if heterogeneous else np.ones(2)
    c=costs(n); dn=np.zeros_like(n); da=c[None,:,None]*n/ref[:,None,None]-mu[:,:,None]*a
    completed=mu*n[:,:,-1]; cost_completed=mu*a[:,:,-1]
    if not marked:
        # Explicit approximation: cost at completion times expected relative duration.
        # Preserves completion count mechanism, removes within-task accumulated payoff.
        cost_completed=completed*c[None,:]*means/ref[:,None]
    for r in range(2):
        x=n[r].sum(axis=1)/.5; chat=V[r]/np.maximum(U[r],1e-10)
        p=switching(x,chat)
        dn[r,:,0]=completed[r]@p-mu[r]*n[r,:,0]
        dn[r,:,1]=mu[r]*(n[r,:,0]-n[r,:,1])
        da[r,:,1]+=mu[r]*a[r,:,0]
    if tau>0:
        dF=completed-F/tau; dB=cost_completed-B/tau; received=F/tau; reward=B/tau
    else:
        dF=np.zeros_like(F); dB=np.zeros_like(B); received=completed; reward=cost_completed
    return np.r_[dn.ravel(),da.ravel(),dF.ravel(),dB.ravel(),(received-.5*U).ravel(),(reward-.5*V).ravel()]

def integrate(tau=.5,heterogeneous=True,dt=.05,marked=True):
    t=np.arange(0,20+dt/2,dt)
    sol=solve_ivp(lambda t,y:rhs(t,y,tau,heterogeneous,marked),(0,20),initial(),t_eval=t,rtol=2e-8,atol=1e-10,max_step=dt)
    if not sol.success: raise RuntimeError(sol.message)
    return t,sol.y.T

def micro(N=2000,seed=17,tau=.5,dt=.005):
    # Synchronous Bernoulli approximation of the SAME marked CTMC; dt convergence tested.
    rng=np.random.default_rng(seed); r=np.repeat([0,1],N//2); N=len(r)
    i=np.tile(np.r_[np.zeros(int(.35*N),int),np.ones(N//2-int(.35*N),int)],2)
    phase=np.zeros(N,int); reward=np.zeros(N); means=np.array([[1.,1.4],[2.,2.8]]); ref=np.array([1.,2.])
    U=np.full((2,2),.1); V=U*np.array([1.4,1.7]); reports=[]; history=[]
    for step in range(round(20/dt)+1):
        t=step*dt; n=np.zeros((2,2,2)); np.add.at(n,(r,i,phase),1/N)
        if step%round(.05/dt)==0: history.append(n.sum(axis=2).copy())
        if step==round(20/dt): break
        c=costs(n); reward+=dt*c[i]/ref[r]
        U*=np.exp(-.5*dt); V*=np.exp(-.5*dt)
        keep=[]
        for arrival,rr,ii,cc in reports:
            if arrival<=t: U[rr,ii]+=1/N; V[rr,ii]+=cc/N
            else: keep.append((arrival,rr,ii,cc))
        reports=keep
        event=rng.random(N)<1-np.exp(-2*dt/means[r,i]); finish=np.flatnonzero(event&(phase==1)); advance=event&(phase==0)
        # All switches use the same pre-event empirical population/evidence.
        Ps=[switching(n[rr].sum(axis=1)/.5,V[rr]/np.maximum(U[rr],1e-10)) for rr in range(2)]
        for k in finish:
            rr,ii=r[k],i[k]; lag=rng.exponential(tau) if tau else 0
            reports.append((t+dt+lag,rr,ii,reward[k])); i[k]=rng.choice(2,p=Ps[rr][ii]); phase[k]=0; reward[k]=0
        phase[advance]=1
    return np.array(history)

def main(out):
    out=run_dir(out); p=Progress(out); p.set('mechanism_and_limit_checks'); rows=[]
    t,y=integrate(); target=y[:,:8].reshape(-1,2,2,2).sum(axis=3)
    masserr=float(abs(y[:,:8].sum(axis=1)-1).max())
    for N in (400,1600,6400):
        for seed in (17,43,71):
            z=micro(N,seed); rows.append({'experiment':'micro_meanfield','N':N,'seed':seed,'dt':.005,'rmse':float(np.sqrt(np.mean((z-target)**2)))})
            p.set('micro_meanfield',finished=len(rows),expected=9)
    for dt in (.01,.0025):
        z=micro(1600,17,dt=dt); rows.append({'experiment':'time_resolution','N':1600,'seed':17,'dt':dt,'rmse':float(np.sqrt(np.mean((z-target)**2)))})
    contrasts=[]; event_spectrum=[]
    for tau in (0.,.5,2.):
        for hetero in (False,True):
            _,full=integrate(tau,hetero); _,approx=integrate(tau,hetero,marked=False)
            contrasts.append({'feedback_mean':tau,'heterogeneous_clocks':hetero,'strategy_rmse_marked_vs_completion_snapshot':float(np.sqrt(np.mean((full[:,:8]-approx[:,:8])**2))),'terminal_difference':float(np.linalg.norm(full[-1,:8]-approx[-1,:8]))})
            if tau>0:
                # Numeric equilibrium residual and tangent spectrum, no proof of global stability.
                sol=solve_ivp(lambda t,y:rhs(t,y,tau,hetero),(0,400),initial(),rtol=1e-8,atol=1e-10,max_step=.2)
                eq=sol.y[:,-1]; f0=rhs(400,eq,tau,hetero); free=[i for i in range(32) if i not in (3,7)]
                basis=np.eye(32)[:,free]
                for k,i in enumerate(free):
                    if i<8: basis[3 if i<4 else 7,k]=-1
                J=np.column_stack([(rhs(400,eq+1e-6*basis[:,k],tau,hetero)-f0)[free]/1e-6 for k in range(30)])
                eig=np.linalg.eigvals(J)
                event_spectrum.append({'feedback_mean':tau,'heterogeneous_clocks':hetero,'equilibrium_residual':float(abs(f0).max()),'max_real_tangent_root':float(eig.real.max()),'valid_local_equilibrium':bool(abs(f0).max()<1e-7),'interpretation':'Numerical local Jacobian only; no analytic stability theorem'})
    # Known serial-filter spectrum, not a new theorem or the event-model stability proof.
    stability=[]
    for a,b in ((.25,1.75),(.5,1.5),(1.,1.)):
        threshold=1/a+1/b
        for ratio in (.5,.9,1.1,1.5):
            K=ratio*threshold; eig=np.roots([a*b,a+b,1,K])
            stability.append({'tau_p':a,'tau_o':b,'K':K,'known_threshold':threshold,'max_real_root':float(eig.real.max()),'sign_agrees':bool((eig.real.max()<0)==(ratio<1))})
    # Pure delay equivalence and classic pairwise-flow identity.
    w=np.linspace(0,10,101); serial=np.exp(-1j*w*.7)*np.exp(-1j*w*1.3)
    equivalent=np.exp(-1j*w*2); err=float(abs(serial-equivalent).max())
    x=np.array([.3,.7]); c=np.array([1.,2.]); P=switching(x,c)
    flow=x@P-x; classic=.2*x*(x@c-c)
    csv_write(out/'micro_results.csv',rows); csv_write(out/'known_stability_controls.csv',stability)
    csv_write(out/'marked_feedback_contrasts.csv',contrasts); csv_write(out/'event_model_local_spectrum.csv',event_spectrum)
    np.savez_compressed(out/'theory_trajectory_server_only.npz',time=t,state=y)
    write_json(out/'summary.json',{'model':'Erlang completion-gated marked-cost meanfield','pure_delay_equivalence_error':err,'classic_flow_error':float(abs(flow-classic).max()),'micro_meanfield':rows,'new_stability_theorem_proved':False,'novelty_established':False,'limits':'Common evidence and type-homogeneous Markov completion within each phase; not arbitrary individual feedback.'})
    p.complete({'mass_conserved':masserr<1e-8,'nonnegative_states':y.min()>-1e-8,'classic_limit':abs(flow-classic).max()<1e-12,'pure_delay_equivalence':err<1e-12,'known_spectrum':all(v['sign_agrees'] for v in stability),'all_micro_cases_recorded':len(rows)==11,'finite_results':all(np.isfinite(v['rmse']) for v in rows)})

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--out',required=True); args=ap.parse_args(); main(args.out)
