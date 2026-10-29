"""Run on the server against existing RTS inputs before pilot deployment."""
import os
import unittest
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from grid import GridReplay


class GridTests(unittest.TestCase):
    def test_rt_series_dispatch_and_unit_conversion(self):
        raw=Path(os.environ['CP_RAW'])
        origin=datetime(2020,7,20,tzinfo=timezone.utc).timestamp()
        grid=GridReplay(raw,[101,102,201,202,301,302],origin)
        a=grid(0,300,np.ones(6)*300e6)
        b=grid(300,600,np.ones(6)*300e6)
        self.assertEqual(grid.n,73)
        self.assertGreater(grid.meta['profiled_renewable_units'],0)
        self.assertTrue(np.allclose(a['compute_mw'],1.))
        for r in (a,b):
            for key in ('balance_error_mw','line_excess_mw','generator_excess_mw'):
                self.assertLess(r[key],1e-5)
            self.assertGreaterEqual(r['renewable_curtailment_mw'],-1e-5)


if __name__=='__main__':unittest.main()
