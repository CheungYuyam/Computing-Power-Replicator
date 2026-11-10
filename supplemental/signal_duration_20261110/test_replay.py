import unittest
import numpy as np
from replay import energy_bins, assignments, metrics

class ReplayTests(unittest.TestCase):
    def test_exact_partial_bins(self):
        lo,e=energy_bins(10,30,[100,200],20,100)
        self.assertEqual(lo,0)
        np.testing.assert_allclose(e*3.6e9,[1000,3000])
    def test_horizon_clipping(self):
        _,e=energy_bins(90,30,[100,200],20,100)
        self.assertAlmostEqual(e.sum()*3.6e9,1000)
    def test_same_plan_and_waits(self):
        cfg={'seed':17,'class_stream_counts':[1,0],'capacities':[[1,1,1]]}
        tasks=[dict(key='a',stream=0,release=10,start=15,site=0,completion=45),
               dict(key='b',stream=0,release=60,start=80,site=0,completion=100),
               dict(key='c',stream=0,release=110,start=None,site=None,completion=None)]
        plan=assignments(tasks,[dict(key='a',stream=0,time=45,new=0)],cfg)
        self.assertEqual(plan,{'a':(0,0),'b':(45,0),'c':(None,None)})
        self.assertEqual(max(plan['b'][0],tasks[1]['release']),60)
    def test_zero_and_offset_response(self):
        d=np.zeros((864,2));d[432:456]=[-1,2]
        x=metrics(d,d,300)
        self.assertEqual(x['window_target_mwh'],-24)
        self.assertEqual(x['window_other_mwh'],48)
        self.assertEqual(x['window_system_mwh'],24)
        self.assertEqual(x['target_first_response_h'],36)
        self.assertEqual(x['window_sitewise_absolute_discrepancy_mwh'],0)
        self.assertIsNone(metrics(d*0,d*0,300)['target_first_response_h'])

if __name__=='__main__': unittest.main()
