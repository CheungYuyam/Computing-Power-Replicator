"""Analytic oracles for settlement, causal reports, admission and phase construction."""
import unittest
import numpy as np
from plant import simulate
from workload import assign_lanes
from controller import Controller

class MechanismTests(unittest.TestCase):
    def fixture(self,method='reported_cost',phase=0):
        jobs=[dict(key='a',release=0,resources=[1,128,0],runtime=600,power_w=[1000.]*30,mean_w=1000.),
              dict(key='b',release=600,resources=[1,128,0],runtime=300,power_w=[1000.]*15,mean_w=1000.)]
        lanes=assign_lanes(jobs)
        cfg=dict(settlement_s=300,horizon_s=1800,arrival_end_s=1200,warmup_s=0,
                 streams_per_class=1,class_stream_counts=[2,0],lane_counts=lanes,
                 stream_construction='nonoverlapping_release_intervals',replicas=2,phase_span_s=phase,
                 capacities=[[10,1280,40]],seed=17,method=method,origin=0,admission_s=0,
                 report_delay_s=150,reference_price=40,wait_weight=.1)
        def price(a,b,e):return dict(prices=[20. if a<300 else 60.],compute_mw=(e/(b-a)*1e-6).tolist())
        ref={str(k):dict(mean_energy_kwh=1/6,mean_runtime=600) for k in (0,1)}
        return jobs,cfg,price,ref

    def test_integrated_cost_vs_final_tariff_analytic(self):
        for method,expected in [('reported_cost',1.),('completion_price',1.5)]:
            jobs,cfg,price,ref=self.fixture(method)
            r=simulate(jobs,ref,price,cfg)
            a=next(x for x in r['tasks'] if x['key']=='a@0')
            self.assertAlmostEqual(a['bill'],.001*300/3600*(20+60))
            self.assertAlmostEqual(a['raw_score'],expected)
            self.assertEqual((a['completion'],a['settled'],a['due'],a['delivered']),(600,600,750,750))
            # Following task is allocated before this task's report arrives.
            rev=next(x for x in r['revisions'] if x['key']=='a@0')
            self.assertFalse(rev['own_report_visible'])

    def test_constant_replica_phase_preserves_no_intrinsic_queue(self):
        jobs,cfg,price,ref=self.fixture(phase=120)
        r=simulate(jobs,ref,price,cfg)
        for task in r['tasks']:
            offset=120 if task['key'].endswith('@1') else 0
            release=(0 if task['source_key']=='a' else 600)+offset
            self.assertEqual(task['start'],release)
            self.assertEqual(task['completion'],release+task['runtime_s'])

    def test_cost_memory_exact_report_weighting(self):
        c=Controller(2,1,17,memory_s=100)
        c.receive(100,[(100,80,0,0,3)])
        decay=np.exp(-1)
        self.assertAlmostEqual(c.costs(0)[0],(decay+3)/(decay+1))
        c.receive(200,[])
        self.assertAlmostEqual(c.costs(0)[0],(decay+3)/(decay+1))

    def test_classical_pairwise_drift_limit(self):
        # Independent enumeration of pairwise imitation, equal completion rate.
        x=np.array([.2,.3,.5]);cost=np.array([1.,3.,2.]);beta=.15;mu=.25
        dx=np.zeros(3)
        for i in range(3):
            for j in range(3):
                rate=mu*x[i]*x[j]*max(0,beta*(cost[i]-cost[j]))
                dx[i]-=rate;dx[j]+=rate
        np.testing.assert_allclose(dx,mu*beta*x*(x@cost-cost),atol=1e-16)
        self.assertAlmostEqual(dx.sum(),0)

if __name__=='__main__':unittest.main()
