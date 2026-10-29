"""Guard shared time windows and accounting against misleading system claims."""
import copy
import unittest
from system_report import period_metrics, case_metrics


def row(start, end, powers, tariffs, waiting=0):
    n = len(powers)
    return dict(start_s=start, end_s=end, power_mw=powers, prices=tariffs,
                generation_cost_per_h=100., shed_mw=0., spill_mw=1.,
                renewable_curtailment_mw=2., max_line_loading=.8, waiting=waiting,
                waiting_by_site=[waiting] + [0] * (n-1),
                node_utilization=[.5]*n, core_utilization=[.4]*n, gpu_utilization=[.3]*n)


class SystemReportTests(unittest.TestCase):
    def test_cost_and_energy_use_same_window_and_physical_units(self):
        trace = [row(0, 300, [1, 2], [10, 20]), row(300, 600, [3, 4], [30, 40])]
        result = period_metrics(trace, 300, 600)
        self.assertAlmostEqual(result['task_it_energy_mwh'], 7/12)
        self.assertAlmostEqual(result['task_bill_currency'], 250/12)
        self.assertAlmostEqual(result['generation_cost_currency'], 100/12)

    def test_negative_prices_retained(self):
        result = period_metrics([row(0, 300, [2], [-10])], 0, 300)
        self.assertLess(result['task_bill_currency'], 0)
        self.assertEqual(result['negative_tariff_intervals'], 1)

    def test_partial_or_gapped_period_rejected(self):
        trace = [row(0, 300, [1], [10]), row(600, 900, [1], [10])]
        for start, end in [(0, 900), (100, 300), (0, 200), (900, 1200)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                period_metrics(trace, start, end)

    def test_tail_not_mixed_into_evaluation_and_ledger_checked(self):
        trace = [row(0, 300, [1], [10]), row(300, 600, [2], [20], 5),
                 row(600, 900, [3], [30])]
        summary = dict(case='example', config=dict(warmup_s=300, arrival_end_s=600,
                       horizon_s=900, site_buses=[101]), task_energy_mwh=.5,
                       task_bill_currency=140/12, peak_it_share=.01, score_clipped_reports=0,
                       negative_price_intervals=0, waiting_end=2, running_end=1,
                       reports=3, switches=1, controller_seconds=.01, seconds=1)
        result = case_metrics(summary, trace)
        self.assertAlmostEqual(result['periods']['evaluation']['task_it_energy_mwh'], 2/12)
        self.assertAlmostEqual(result['periods']['tail']['task_it_energy_mwh'], 3/12)
        self.assertEqual(result['sites'][0]['queue_snapshot_peak'], 5)
        bad = copy.deepcopy(summary)
        bad['task_bill_currency'] += 1
        with self.assertRaises(ValueError):
            case_metrics(bad, trace)


if __name__ == '__main__':
    unittest.main()
