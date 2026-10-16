import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import evolution as e
def rev():return {'key':'a','business':0,'ordinal':0,'time':100.,'kind':0,'old':0,'new':1,'candidate':1,'cost0':2.,'cost1':1.,'probability':.2,'uniform':.1,'own_report_visible':False,'reports_visible_count':0}
def task():return {'key':'a','business':0,'kind':0,'release':0.,'start':0.,'runtime':100.,'site':0,'state':'completed','physical_completion':100.,'settlement_ready':300.,'report_due':1200.,'report_delivered':1200.,'revision_time':100.,'raw_cost':1.,'cost':1.}
def data():return {'tasks':[task()],'revisions':[rev()],'draws':[{'business':0,'ordinal':0,'peer_index':1,'candidate':1,'uniform':.1}],'integrity':{'ok':True},'initial_strategy':[0]*64}
class Tests(unittest.TestCase):
    def test_saved_threshold_and_timing(self):
        e.validate_records(data(),900)
        d=data();d['revisions'][0]['new']=0
        with self.assertRaises(ValueError):e.validate_records(d,900)
    def test_positive_lag_own_visibility(self):
        d=data();d['revisions'][0]['own_report_visible']=True
        with self.assertRaises(ValueError):e.validate_records(d,900)
    def test_zero_lag_same_time(self):
        d=data();t=d['tasks'][0];t.update(runtime=300.,physical_completion=300.,settlement_ready=300.,report_due=300.,report_delivered=300.,revision_time=300.)
        d['revisions'][0].update(time=300.,own_report_visible=True);e.validate_records(d,0)
    def test_duplicate_keys(self):
        with self.assertRaises(ValueError):e.unique([rev(),rev()],e.rk)
    def test_candidate_label_not_random_draw(self):
        a=data();b=copy.deepcopy(a);b['draws'][0]['candidate']=0;b['revisions'][0]['candidate']=0
        _,_,ks,c=e.matched_revisions(a,b);self.assertTrue(c['common_event_random_numbers_equal']);self.assertEqual(len(ks),1)
    def test_unaligned_not_forced(self):
        a=data();b=copy.deepcopy(a);b['revisions'][0]['time']=101
        _,_,ks,c=e.matched_revisions(a,b);self.assertEqual(ks,[]);self.assertEqual(c['same_task_different_time'],1)
    def test_empty_first_difference(self):self.assertIsNone(e.first_pair({}, {}, [],lambda a,b:True))
    def test_visibility_before_or_same_time_only(self):
        t=task();t['report_delivered']=100.;r=rev();v=e.report_context({'a':t},{},r);self.assertEqual(v['same_type_visible_report_count'],1)
        t['report_delivered']=100.1;self.assertEqual(e.report_context({'a':t},{},r)['same_type_visible_report_count'],0)
    def test_censored_start(self):
        a=data();b=data();a['tasks'][0]['start']=None;a['tasks'][0]['site']=None
        r=e.task_differences(a,b);self.assertEqual(r['both_started_routing_difference_count'],0);self.assertEqual(r['start_time_or_started_status_difference_count'],1)
    def test_bin_ledger_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders=[];docs=[]
            for i,en in enumerate([6.,3.]):
                p=Path(tmp)/str(i);p.mkdir();f=p/'trace_server_only.npz'
                np.savez(f,columns=np.array(['interval_start','interval_end','site0_mw']),values=np.array([[90000.,90300.,en*.1/300]]))
                e.write(p/'trace_sha256.json',{f.name:e.digest(f)});folders.append(p);docs.append({'ledger':[{'key':'a','interval_start':90000.,'interval_end':90300.,'site':0,'energy_ws':en}]})
            r,_=e.power_context(*docs,*folders,{'site0_first_interval_start_hour':'13'},{'power_mw_per_w':.1})
            self.assertAlmostEqual(r['ledger_reconstructed_site0_delta_mw'],.001);self.assertEqual(r['contributing_task_count'],1)
if __name__=='__main__':unittest.main()
