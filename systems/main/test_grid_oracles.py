"""Hand-solvable two-bus dispatch oracles for binding constraints and emergency slacks."""
import csv,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from grid import GridReplay

class GridOracleTests(unittest.TestCase):
    def fixture(self,loads=(80,200,80),pmin=0,wind=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        def write(name,rows):
            with (root/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        write('rts_bus.csv',[{'Bus ID':1,'Area':1,'MW Load':0,'MW Shunt G':0},
                             {'Bus ID':2,'Area':1,'MW Load':100,'MW Shunt G':0}])
        write('rts_branch.csv',[{'From Bus':1,'To Bus':2,'X':.1,'Tr Ratio':0,'Cont Rating':50}])
        generators=[]
        for i,price in ((1,10),(2,50)):
            generators.append({'GEN UID':'g'+str(i),'Bus ID':i,'Fuel':'NG','PMin MW':pmin,
                               'PMax MW':100,'MW Inj':0,'Ramp Rate MW/Min':100,
                               'Fuel Price $/MMBTU':price,'HR_avg_0':1000,'VOM':0})
        if wind:generators.append(dict(generators[0],**{'GEN UID':'w1','Fuel':'Wind','PMin MW':0,'PMax MW':50}))
        write('rts_gen.csv',generators)
        times=[dict(Year=2020,Month=7,Day=27,Period=i+1) for i in range(len(loads))]
        write('rts_rt_load.csv',[dict(t,**{'1':load}) for t,load in zip(times,loads)])
        write('rts_rt_wind.csv',[dict(t,**({'w1':50} if wind else {})) for t in times])
        write('rts_rt_pv.csv',times)
        return GridReplay(root,[1,2],datetime(2020,7,27,tzinfo=timezone.utc).timestamp())

    def test_binding_line_dispatch_and_nodal_prices(self):
        g=self.fixture();r=g(0,300,np.zeros(2))
        np.testing.assert_allclose(g.last_solution['pg'],[50,30],atol=1e-8)
        self.assertAlmostEqual(r['generation_cost_per_h'],2000)
        np.testing.assert_allclose(r['prices'],[10,50],atol=1e-8)
        self.assertAlmostEqual(r['max_line_loading'],1)
        self.assertEqual(r['shed_mw'],0)

    def test_shortage_is_accounted_as_shed_not_hidden_generation(self):
        g=self.fixture();r=g(300,600,np.zeros(2))
        np.testing.assert_allclose(g.last_solution['pg'],[50,100],atol=1e-8)
        self.assertAlmostEqual(r['shed_mw'],50)
        self.assertEqual(r['spill_mw'],0)
        self.assertAlmostEqual(r['prices'][1],10000)

    def test_ramp_bound_changes_dispatch_and_shed(self):
        g=self.fixture(loads=(80,100));g(0,300,np.zeros(2));g.ramp[:]=1
        r=g(300,600,np.zeros(2))
        np.testing.assert_allclose(g.last_solution['pg'],[50,35],atol=1e-8)
        self.assertAlmostEqual(r['shed_mw'],15)
        self.assertLess(r['ramp_excess_mw'],1e-8)

    def test_minimum_generation_spill_and_negative_price(self):
        g=self.fixture(loads=(0,),pmin=20);r=g(0,300,np.zeros(2))
        self.assertAlmostEqual(r['spill_mw'],40)
        self.assertEqual(r['shed_mw'],0)
        np.testing.assert_allclose(r['prices'],[-10000,-10000],atol=1e-8)

    def test_profiled_renewable_curtailment(self):
        g=self.fixture(loads=(20,),wind=True);r=g(0,300,np.zeros(2))
        np.testing.assert_allclose(g.last_solution['pg'],[0,0,20],atol=1e-8)
        self.assertAlmostEqual(r['renewable_curtailment_mw'],30)
        self.assertEqual(r['generation_cost_per_h'],0)

if __name__=='__main__':unittest.main()
