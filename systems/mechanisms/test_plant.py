"""Small deterministic integrity tests; no real-data experiment is launched."""
import unittest
import numpy as np
from controller import Controller
from plant import Curve, simulate


class PlantTests(unittest.TestCase):
    def config(self, sites=6):
        return {'settlement_s':300,'horizon_s':1200,'arrival_end_s':900,
                'warmup_s':0,'streams_per_class':2,'replicas':1,
                'capacities':[[2,256,8] for _ in range(sites)],'seed':17,
                'method':'reported_cost','origin':0,'admission_s':0,
                'report_delay_s':150,'reference_price':40,'wait_weight':.1}

    def jobs(self):
        return [{'key':str(i),'release':float(i*10),'resources':[1,128,4],
                 'runtime':110.,'power_w':[100.,200.,300.,400.,500.,600.]} for i in range(12)]

    def replay(self, cfg):
        ref={str(k):{'mean_energy_kwh':.01,'mean_runtime':110} for k in (0,1)}
        def settlement(a,b,e):
            return {'prices':[40.]*len(e),'compute_mw':(e/(b-a)*1e-6).tolist()}
        return simulate(self.jobs(),ref,settlement,cfg)

    def test_exact_curve_and_last_partial_sample(self):
        c=Curve(110,[100,200,300,400,500,600])
        self.assertEqual(c.integral(110),36000)
        self.assertEqual(c.integral(200),36000)
        self.assertEqual(c.integral(30),4000)

    def test_multisite_energy_capacity_and_causal_feedback(self):
        for sites in (3,6,12):
            result=self.replay(self.config(sites))
            self.assertTrue(all(result['checks'].values()))
            self.assertEqual(result['summary']['completed'],12)
            self.assertAlmostEqual(result['summary']['task_energy_mwh'],12*36000/3.6e9)
            self.assertTrue(all(not r['own_report_visible'] for r in result['revisions']))
            self.assertTrue(all(len(r['power_mw'])==sites for r in result['trace']))

    def test_no_overlap_within_stream(self):
        result=self.replay(self.config())
        for stream in range(4):
            tasks=sorted([r for r in result['tasks'] if r['stream']==stream],key=lambda r:r['start'])
            self.assertTrue(all(b['start']>=a['completion'] for a,b in zip(tasks,tasks[1:])))

    def test_replicas_scale_both_work_and_physical_energy(self):
        cfg=self.config();cfg['replicas']=2;cfg['horizon_s']=2400
        result=self.replay(cfg)
        self.assertEqual(result['summary']['completed'],24)
        self.assertAlmostEqual(result['summary']['task_energy_mwh'],24*36000/3.6e9)

    def test_fixed_baseline_keeps_assignments(self):
        cfg=self.config();cfg['method']='fixed'
        result=self.replay(cfg)
        self.assertEqual(result['summary']['switches'],0)

    def test_future_report_rejected(self):
        ctl=Controller(6,2,17)
        with self.assertRaises(ValueError): ctl.receive(10,[(11,9,0,0,1.)])

    def test_common_random_numbers_by_completion_ordinal(self):
        a=Controller(6,2,17);b=Controller(6,2,17)
        a.receive(0,[(0,0,1,2,10)])
        for stream in (2,3,2,2):
            x,y=a.revise(stream),b.revise(stream)
            self.assertEqual(x['uniform'],y['uniform'])
            self.assertEqual(x['ordinal'],y['ordinal'])

    def test_unsupported_resource_request_is_not_silently_dropped(self):
        cfg=self.config();cfg['capacities']=[[.5,256,8] for _ in range(6)]
        with self.assertRaises(ValueError): self.replay(cfg)


if __name__=='__main__': unittest.main()
