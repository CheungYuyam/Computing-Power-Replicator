import unittest
from collections import defaultdict
import numpy as np
from workload import assign_lanes
from plant import simulate
from controller import Controller


class WorkloadTests(unittest.TestCase):
    def jobs(self):
        return [dict(key=str(i), release=t, resources=[1,128,4],runtime=d,
                     power_w=[100.]*(int(d)//20),mean_w=100.)
                for i,(t,d) in enumerate([(0,100),(10,40),(50,40),(100,40),(110,20)])]

    def run_case(self, nodes):
        jobs=self.jobs();lanes=assign_lanes(jobs)
        cfg=dict(settlement_s=300,horizon_s=600,arrival_end_s=300,warmup_s=0,
                 streams_per_class=max(lanes),class_stream_counts=lanes,lane_counts=lanes,
                 stream_construction='nonoverlapping_release_intervals',replicas=1,
                 capacities=[[nodes,128*nodes,4*nodes]],seed=17,method='reported_cost',
                 origin=0,admission_s=0,report_delay_s=150,reference_price=40,wait_weight=.1)
        return simulate(jobs,{str(k):dict(mean_energy_kwh=.01,mean_runtime=100) for k in (0,1)},
                        lambda a,b,e:dict(prices=[40.],compute_mw=(e/(b-a)*1e-6).tolist()),cfg)

    def test_lanes_have_no_intrinsic_overlap(self):
        jobs=self.jobs();counts=assign_lanes(jobs)
        self.assertEqual(counts,[0,2])
        lanes=defaultdict(list)
        for j in jobs:lanes[j['lane']].append(j)
        for lane in lanes.values():
            self.assertTrue(all(a['release']+a['runtime']<=b['release'] for a,b in zip(lane,lane[1:])))

    def test_unlimited_capacity_does_not_create_waiting(self):
        r=self.run_case(10)
        self.assertTrue(all(t['start']==t['release'] for t in r['tasks']))
        self.assertEqual(r['summary']['cohort_restricted_mean_wait_s'],0)

    def test_resource_restriction_creates_waiting_without_dropping_jobs(self):
        r=self.run_case(1)
        self.assertTrue(all(r['checks'].values()))
        self.assertEqual(r['summary']['completed'],5)
        self.assertGreater(r['summary']['cohort_restricted_mean_wait_s'],0)
        s=r['summary']
        self.assertAlmostEqual(s['cohort_restricted_mean_wait_s'],
                               s['cohort_mean_predecessor_wait_s']+s['cohort_mean_post_predecessor_wait_s'])

    def test_unequal_classes_do_not_sample_empty_padding(self):
        c=Controller(2,20,17,class_counts=[1,3])
        c.strategy[:]=[0,1,1,1]
        for stream in range(4):
            self.assertEqual(c.revise(stream)['candidate'],0 if stream==0 else 1)
        self.assertEqual(len(c.strategy),4)


if __name__=='__main__':unittest.main()
