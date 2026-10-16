import unittest
from types import SimpleNamespace
import sys
import numpy as np
from engine import load_parent,PARENT,simulate,rectangle_energy,EventTape,GridSettlement
from evolution import compare

P=load_parent()
class FixedInitialController(P.EvidenceController):
    def __init__(self,seed):
        super().__init__(seed);self.strategy[:]=0  # synthetic resource/FIFO fixture only

FIXTURE=SimpleNamespace(Curve=P.Curve,EvidenceController=FixedInitialController,
    stable_int=lambda key:int(key.split('_')[0][1:]))
FIT={'capacity_per_center':[1,1,1],'power_mw_per_w':1e-6,
    'classes':{'0':{'mean_runtime':300.,'mean_energy_kwh':1.},'1':{'mean_runtime':300.,'mean_energy_kwh':1.}}}

def job(key,release=0,runtime=100,power=1000,resources=(1,1,0)):
    return {'key':key,'release':release,'runtime':runtime,'power_w':[power]*int(np.ceil(runtime/20)), 'resources':list(resources)}

def provider(start,end,energy):
    return {'prices':[40.,40.],'compute_mw':(np.asarray(energy)/(end-start)*1e-6).tolist()}

class EngineeringTests(unittest.TestCase):
    def run_case(self,jobs,**kw):
        return simulate(FIXTURE,jobs,FIT,provider,horizon=1200,incentive=False,**kw)

    def test_non_multiple_duration_independent_energy(self):
        j=job('b0_a',runtime=25);j['power_w']=[1000,2000]
        r=self.run_case([j]);self.assertAlmostEqual(r['tasks'][0]['energy_ws'],30000)
        self.assertEqual(r['tasks'][0]['physical_completion'],25)
        self.assertEqual(rectangle_energy(25,j['power_w'],22),24000)

    def test_terminal_partial_curve(self):
        r=self.run_case([job('b0_a',runtime=1500,power=2000)])
        self.assertEqual(r['summary']['active_end'],1);self.assertEqual(r['summary']['revisions'],0)
        self.assertAlmostEqual(r['tasks'][0]['energy_ws'],2400000)

    def test_fifo_and_admission_scenarios(self):
        tasks=[job('b0_a'),job('b0_b',runtime=100)]
        expected={0:[0,100],150:[0,150],300:[0,300]}
        for period in expected:
            r=self.run_case(tasks,admission_period=period)
            self.assertEqual([t['start'] for t in r['tasks']],expected[period])
            self.assertEqual([t['physical_completion'] for t in r['tasks']],[x+100 for x in expected[period]])
            self.assertAlmostEqual(r['summary']['raw_energy_kwh'],200000/3600000)

    def test_capacity_competition_and_infeasible(self):
        r=self.run_case([job('b0_a'),job('b1_a',resources=(1,1,1)),job('b2_bad',resources=(2,1,0))])
        self.assertEqual(r['summary']['infeasible'],1)
        tasks={x['key']:x for x in r['tasks']}
        self.assertEqual(tasks['b0_a']['start'],0);self.assertEqual(tasks['b1_a']['start'],100)
        self.assertEqual(r['summary']['resource_excess'],0)

    def test_completion_settlement_feedback_distinct(self):
        r=self.run_case([job('b0_a')],lag=150)['tasks'][0]
        self.assertEqual((r['physical_completion'],r['settlement_ready'],r['report_delivered']),(100,300,450))
        self.assertEqual(r['revision_time'],100);self.assertFalse(r['own_report_at_revision'])

    def test_zero_lag_boundary_order(self):
        r=self.run_case([job('b0_a',runtime=300)],lag=0)['tasks'][0]
        self.assertTrue(r['own_report_at_revision']);self.assertEqual(r['report_delivered'],300)
        r=self.run_case([job('b0_a')],lag=0)['tasks'][0]
        self.assertFalse(r['own_report_at_revision']);self.assertEqual(r['report_delivered'],300)

    def test_positive_lag_boundary_own_report_not_visible(self):
        r=self.run_case([job('b0_a',runtime=300)],lag=900)
        self.assertFalse(r['tasks'][0]['own_report_at_revision']);self.assertEqual(r['summary']['revisions'],1)
        self.assertEqual(r['tasks'][0]['report_delivered'],1200)

    def test_terminal_states_and_pending_reports(self):
        r=self.run_case([job('b0_a',runtime=1200),job('b0_b'),job('b1_c',release=1200)],lag=900)
        self.assertEqual(r['summary']['completed_all'],1);self.assertEqual(r['summary']['waiting_end'],1)
        self.assertEqual(r['summary']['unreleased_end'],1);self.assertEqual(r['summary']['pending_reports_end'],1)

    def test_future_settlement_cannot_change_past_revisions(self):
        jobs=[job('b0_a',runtime=100),job('b0_b',runtime=400),job('b0_c',runtime=400)]
        a=simulate(FIXTURE,jobs,FIT,provider,horizon=1200,incentive=False,lag=0)
        def future(start,end,energy):
            r=provider(start,end,energy)
            if end>600:r['prices']=[400.,60.]
            return r
        b=simulate(FIXTURE,jobs,FIT,future,horizon=1200,incentive=False,lag=0)
        self.assertEqual([r for r in a['revisions'] if r['time']<=600],[r for r in b['revisions'] if r['time']<=600])

    def test_event_tape_independent_of_event_order(self):
        a=EventTape(17);b=EventTape(17);peers=np.arange(32)%2
        for tape,order in [(a,[0,1,0]),(b,[1,0,0])]:
            for business in order:tape.business=business;tape.choice(peers);tape.random()
        self.assertEqual(sorted(a.records,key=lambda r:(r['business'],r['ordinal'])),sorted(b.records,key=lambda r:(r['business'],r['ordinal'])))

    def test_parent_initial_strategies_preserved_real_entry(self):
        result=simulate(P,[],FIT,provider,horizon=300,incentive=False)
        np.testing.assert_array_equal(result['initial_strategy'],P.EvidenceController(17).strategy)
        self.assertEqual(result['summary']['tasks'],0)

    def test_grid_constraints_and_prices(self):
        sys.path.insert(0,str(PARENT));from dc_grid import Grid
        grid=Grid(2,[(0,1,.1,1.,20.)],[0,1],[0.,0.],[100.,100.],[10.,50.],[.1,.1])
        settled=GridSettlement(P,grid,np.array([0.,0.]),np.array([0.,0.]),[0,1],1e-6,0.,43200.)
        a=settled(0,300,np.array([0.,50.e6*300]));b=settled(300,600,np.array([0.,60.e6*300]))
        self.assertAlmostEqual(a['loading'],1.,places=8)
        self.assertLess(a['prices'][0],a['prices'][1])
        self.assertGreater(b['shed'],0)
        for r in [a,b]:
            for k in ['balance','line_excess','ramp_excess','generator_excess']:self.assertLess(r[k],1e-7)

    def test_incentive_bill_uses_past_interval_energy(self):
        # Place the synthetic intervention start at simulation t=0.
        a=simulate(FIXTURE,[job('b0_a',runtime=100)],FIT,provider,daystart=-43200,horizon=1200,lag=900,incentive=True)
        b=simulate(FIXTURE,[job('b0_a',runtime=100)],FIT,provider,daystart=-43200,horizon=1200,lag=900,incentive=False)
        self.assertAlmostEqual(a['tasks'][0]['normalized_bill'],2*b['tasks'][0]['normalized_bill'])
        self.assertEqual(a['revisions'][0],b['revisions'][0])
        self.assertEqual(a['tasks'][0]['report_delivered'],1200)

    def test_repeatability_and_same_date_pair(self):
        jobs=[job('b0_a'),job('b0_b')]
        a=self.run_case(jobs);b=self.run_case(jobs)
        self.assertEqual(a['trace'],b['trace']);self.assertEqual(a['revisions'],b['revisions'])

    def test_complete_horizon_zero_pair_and_censoring(self):
        a=simulate(FIXTURE,[],FIT,provider,origin=0,daystart=43200,horizon=172800,incentive=True)
        b=simulate(FIXTURE,[],FIT,provider,origin=0,daystart=43200,horizon=172800,incentive=False)
        row=compare(a,b,43200,0)
        self.assertTrue(row['pre_intervention_identical']);self.assertFalse(row['site0_observed_difference'])
        self.assertIsNone(row['site0_first_interval_start_hour']);self.assertEqual(row['post_observation_hours'],24.)
        self.assertEqual(row['pulse_site0_reduction_mwh'],0.)

if __name__=='__main__':unittest.main()
