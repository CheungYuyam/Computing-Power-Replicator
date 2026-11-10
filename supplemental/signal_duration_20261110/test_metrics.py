import unittest
import numpy as np
from metrics import window_metrics


class Tests(unittest.TestCase):
    def test_windows_units_and_sign(self):
        off=np.ones((72,2));on=off.copy();on[36:38,0]-=.1;on[38:42,1]+=.2
        m=window_metrics(on,off,on-off,3600,2)
        self.assertAlmostEqual(m['window_target_kwh'],-200)
        self.assertAlmostEqual(m['window_target_mean_kw'],-100)
        self.assertAlmostEqual(m['window_target_percent'],-10)
        self.assertAlmostEqual(m['post4_other_kwh'],800)
        self.assertEqual(m['target_first_response_h'],36)
        self.assertEqual(m['other_first_response_h'],38)
        self.assertEqual(m['window_response_discrepancy_kwh'],0)

    def test_null_denominator_and_no_response(self):
        a=np.zeros((72,2));m=window_metrics(a,a,a,3600,1)
        self.assertIsNone(m['window_target_percent'])
        self.assertIsNone(m['target_first_response_h'])

    def test_end_boundary_and_discrepancy(self):
        off=np.ones((72,2));on=off.copy();on[37,0]=0
        m=window_metrics(on,off,np.zeros_like(off),3600,1)
        self.assertEqual(m['window_target_kwh'],0)
        self.assertEqual(m['post4_target_kwh'],-1000)
        m=window_metrics(on,off,np.zeros_like(off),3600,4)
        self.assertEqual(m['window_response_discrepancy_kwh'],-1000)

if __name__=='__main__': unittest.main()
