"""Gate model identity before running a system comparison."""
import unittest,json,hashlib
from pathlib import Path
import numpy as np
from controller import Controller
import test_plant

def pairwise_rhs(x,c,beta,lam):
    P=x[None,:]*np.clip(beta*(c[:,None]-c[None,:]),0,1)
    np.fill_diagonal(P,0.)
    P[np.diag_indices(len(x))]=1-P.sum(axis=1)
    return (lam*x)@P-lam*x

def classical_rhs(x,c,beta,lam):return lam*beta*x*(x@c-c)

def rk4(rhs,x,dt):
    a=rhs(x);b=rhs(x+dt*a/2);c=rhs(x+dt*b/2);d=rhs(x+dt*c)
    return x+dt*(a+2*b+2*c+d)/6

class ConsistencyTests(unittest.TestCase):
    def test_classical_derivatives_many_states(self):
        rng=np.random.default_rng(713)
        for n in (2,6,12):
            for lam in (.001,.25,1.):
                for _ in range(20):
                    x=rng.dirichlet(np.ones(n));c=rng.uniform(0,5,n)
                    np.testing.assert_allclose(pairwise_rhs(x,c,.15,lam),classical_rhs(x,c,.15,lam),atol=3e-16,rtol=1e-12)

    def test_classical_full_trajectories(self):
        max_error=0.
        for n in (2,6,12):
            x=np.arange(1,n+1,dtype=float);x/=x.sum();y=x.copy()
            costs=lambda z:np.linspace(.4,1.4,n)+.8*z
            for _ in range(2000):
                x=rk4(lambda z:pairwise_rhs(z,costs(z),.15,.25),x,.02)
                y=rk4(lambda z:classical_rhs(z,costs(z),.15,.25),y,.02)
                max_error=max(max_error,float(np.max(abs(x-y))))
                self.assertGreaterEqual(x.min(),0)
            np.testing.assert_allclose(x,y,atol=2e-13,rtol=0)
            self.assertAlmostEqual(x.sum(),1,places=12)
        self.assertLess(max_error,2e-13)

    def test_identical_information_identical_production_decisions(self):
        a=Controller(6,100,17,method='reported_cost');b=Controller(6,100,17,method='completion_price')
        for t in range(30):
            records=[(t,t,kind,site,float((site+2*t)%7)) for kind in (0,1) for site in range(6)]
            a.receive(t,records);b.receive(t,records)
            for stream in range(200):self.assertEqual(a.revise(stream),b.revise(stream))
            np.testing.assert_array_equal(a.strategy,b.strategy)

    def test_expensive_candidates_are_rejected(self):
        c=Controller(6,100,17);c.v[:]=np.arange(6)
        for stream in range(200):
            d=c.revise(stream)
            if d['candidate']>=d['old']:self.assertEqual(d['probability'],0)

    def test_constant_price_complete_executor_agrees(self):
        helper=test_plant.PlantTests();cfg=helper.config();cfg['report_delay_s']=0
        a=helper.replay(cfg);cfg['method']='completion_price';b=helper.replay(cfg)
        for x,y in zip(a['tasks'],b['tasks']):
            for field in ('key','start','site','completion'):self.assertEqual(x[field],y[field])
            self.assertAlmostEqual(x['score'],y['score'],places=12)
        for x,y in zip(a['revisions'],b['revisions']):
            for field in ('old','candidate','new','uniform'):self.assertEqual(x[field],y[field])
            self.assertAlmostEqual(x['probability'],y['probability'],places=12)
        for r in (a,b):self.assertTrue(all(r['checks'].values()))

if __name__=='__main__':unittest.main()
