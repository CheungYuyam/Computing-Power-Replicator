import unittest
import numpy as np
from evolution import Model, configuration, preflight, analyze, positive_quadrature


def case(**kw):
    c=dict(case_id='test',group='test',execution_scale=1.,feedback_mean=.5,
        initial_strategy0_fraction=.5,execution_stages=2,accumulated_payoff=True,initial_history='fresh')
    c.update(kw); return c


class EvolutionTests(unittest.TestCase):
    def test_declared_matrix(self):
        p=configuration(); self.assertEqual(len(p['scenarios']),45)

    def test_probability_mass_and_sign(self):
        P=Model.switching(np.array([.2,.8]),np.array([2.,1.]))
        np.testing.assert_allclose(P.sum(axis=1),1.)
        self.assertGreater(P[0,1],0); self.assertEqual(P[1,0],0)
        self.assertTrue((P>=0).all())

    def test_no_switch_at_equal_payoff(self):
        np.testing.assert_array_equal(Model.switching(np.array([.2,.8]),np.ones(2)),np.eye(2))

    def test_type_mass_derivative(self):
        rng=np.random.default_rng(17)
        for k in [1,2,4]:
            m=Model(case(execution_stages=k)); y=m.initial()
            n=rng.random((2,2,k)); n*=.5/n.sum(axis=(1,2),keepdims=True)
            y[:m.nsize]=n.ravel()
            np.testing.assert_allclose(m.rhs(0,y)[:m.nsize].reshape(2,2,k).sum(axis=(1,2)),0,atol=1e-14)

    def test_history_same_share_different_inventory(self):
        a=Model(case()); b=Model(case(initial_history='stationary_execution_fresh_observer'))
        na,aa,*_=a.unpack(a.initial()); nb,ab,*_=b.unpack(b.initial())
        np.testing.assert_allclose(na.sum(axis=2),nb.sum(axis=2))
        self.assertEqual(float(aa.sum()),0.); self.assertGreater(float(ab.sum()),0.)
        # Independent stationary age identity: mean elapsed age = mean*(k+1)/(2k).
        c=b.costs(nb)
        expected=.25*b.means*3/4*c[None,:]/np.array([1.,2.])[:,None]
        np.testing.assert_allclose(ab.sum(axis=2),expected)

    def test_mean_fixed_when_shape_changes(self):
        for k in [1,2,4]:
            m=Model(case(execution_stages=k))
            np.testing.assert_allclose(k/m.mu,np.array([[1,1.4],[2,2.8]]))

    def test_feedback_delivery_at_tau_zero(self):
        m=Model(case(feedback_mean=0.,execution_stages=1)); y=m.initial()
        n,a,F,B,U,V,Z=m.unpack(y)
        _,_,dF,dB,dU,dV,_=m.unpack(m.rhs(0,y))
        np.testing.assert_allclose(dU+.5*U,m.mu*n[:,:,-1])
        np.testing.assert_array_equal(dF,np.zeros((2,2)))
        np.testing.assert_array_equal(dB,np.zeros((2,2)))

    def test_tau_delays_initial_delivery(self):
        m=Model(case(execution_stages=1)); y=m.initial()
        n,a,F,B,U,V,Z=m.unpack(y)
        _,_,dF,dB,dU,dV,_=m.unpack(m.rhs(0,y))
        np.testing.assert_allclose(dU,-.5*U)
        np.testing.assert_allclose(dF,m.mu*n[:,:,-1])

    def test_completion_payoff_uses_declared_mean(self):
        m=Model(case(execution_stages=1,accumulated_payoff=False)); y=m.initial()
        n,a,F,B,U,V,Z=m.unpack(y)
        b=m.unpack(m.rhs(0,y))[3]
        np.testing.assert_allclose(b,n[:,:,0]*m.costs(n)[None,:]/np.array([1.,2.])[:,None])

    def test_integrated_flux_population_balance(self):
        m=Model(case(execution_stages=4)); ts,y=m.solve(2.)
        o=m.observables(y); x=o['strategy'][:,:,0]; z=o['transfers']
        np.testing.assert_allclose(.5*(x-x[0]),-z[:,:,0]+z[:,:,1],atol=1e-9)

    def test_time_step_is_only_numerical(self):
        m=Model(case()); t,a=m.solve(1.,max_step=.1); _,b=m.solve(1.,max_step=.05)
        np.testing.assert_allclose(a,b,rtol=2e-6,atol=1e-8)

    def test_alpha_does_not_renormalize_payoff(self):
        a=Model(case(execution_scale=.5)); b=Model(case(execution_scale=2.))
        ra=a.unpack(a.rhs(0,a.initial()))[1]
        rb=b.unpack(b.rhs(0,b.initial()))[1]
        np.testing.assert_allclose(ra,rb)
        np.testing.assert_allclose(a.mu,4*b.mu)

    def test_frozen_same_scenario_reference(self):
        self.assertLess(preflight()['same_assumption_parent_derivative_max_error'],1e-12)

    def test_fold_interpolation_regression(self):
        p=configuration()
        for index in (5,25):
            m=Model(p['scenarios'][index]); ts,ys=m.solve()
            _,_,checks,_=analyze(m,ts,ys,p)
            self.assertTrue(all(checks.values()), (index,checks))

    def test_positive_quadrature_kink_and_plateau(self):
        ts=np.linspace(0,2,41)
        flow=lambda t: np.column_stack([np.maximum(.73-t,0),np.maximum(t-.73,0),t**2,np.ones_like(t)])
        z,info=positive_quadrature(flow,ts)
        exact=np.column_stack([(.73**2-np.maximum(.73-ts,0)**2)/2,
             np.maximum(ts-.73,0)**2/2,ts**3/3,ts])
        np.testing.assert_allclose(z,exact,atol=3e-10,rtol=0)
        self.assertTrue((np.diff(z,axis=0)>=0).all())
        np.testing.assert_array_equal(z[ts>=.75,0],np.repeat(z[-1,0],sum(ts>=.75)))

    def test_negative_quadrature_rate_is_not_hidden(self):
        with self.assertRaises(RuntimeError):
            positive_quadrature(lambda t: -np.ones((len(t),4)),np.array([0.,1.]))

    def test_refinement_budget_is_not_silently_ignored(self):
        z,info=positive_quadrature(lambda t: np.tile(np.maximum(t-.731,0)[:,None],(1,4)),
                                  np.array([0.,1.]),max_depth=0)
        self.assertFalse(info['target_met'])
        self.assertEqual(info['unresolved_intervals'],1)
        self.assertTrue((np.diff(z,axis=0)>=0).all())

    def test_invalid_condition_rejected(self):
        with self.assertRaises(ValueError): Model(case(feedback_mean=-1))


if __name__=='__main__': unittest.main()
