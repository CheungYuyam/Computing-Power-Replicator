"""Read-only postprocessing of a completed pilot; no simulation or submission.

Power and cost are interval averages/totals. Resource and queue observations
are settlement-end snapshots and are explicitly not time-average occupancy.
"""
import argparse
import csv
import json
from pathlib import Path

from analyze import analyze, read


def period_metrics(trace, start, end):
    rows = [r for r in trace if start <= r['start_s'] < end]
    if (not rows or rows[0]['start_s'] != start or rows[-1]['end_s'] != end
            or any(a['end_s'] != b['start_s'] for a, b in zip(rows, rows[1:]))):
        raise ValueError('Evaluation period is incomplete or not interval-aligned')
    hours = [(r['end_s'] - r['start_s']) / 3600 for r in rows]
    result = {'start_s': start, 'end_s': end,
              'task_it_energy_mwh': sum(sum(r['power_mw']) * h for r, h in zip(rows, hours)),
              'task_bill_currency': sum(sum(p * c for p, c in zip(r['power_mw'], r['prices'])) * h
                                        for r, h in zip(rows, hours)),
              'max_line_loading': max(r['max_line_loading'] for r in rows),
              'queue_snapshot_peak': max(r['waiting'] for r in rows),
              'negative_tariff_intervals': sum(any(c < 0 for c in r['prices']) for r in rows)}
    for source, target in [('generation_cost_per_h', 'generation_cost_currency'),
                           ('shed_mw', 'shed_mwh'), ('spill_mw', 'spill_mwh'),
                           ('renewable_curtailment_mw', 'renewable_curtailment_mwh')]:
        result[target] = sum(r[source] * h for r, h in zip(rows, hours))
    return result


def case_metrics(summary, trace):
    cfg = summary['config']
    periods = {'evaluation': period_metrics(trace, cfg['warmup_s'], cfg['arrival_end_s']),
               'tail': period_metrics(trace, cfg['arrival_end_s'], cfg['horizon_s'])}
    whole = period_metrics(trace, 0, cfg['horizon_s'])
    for key, recorded in [('task_it_energy_mwh', summary['task_energy_mwh']),
                          ('task_bill_currency', summary['task_bill_currency'])]:
        if abs(whole[key] - recorded) > 1e-7 * max(1., abs(recorded)):
            raise ValueError('Interval/task accounting mismatch: ' + key)
    measured = [r for r in trace if cfg['warmup_s'] <= r['start_s'] < cfg['arrival_end_s']]
    sites = []
    for site, bus in enumerate(cfg['site_buses']):
        item = {'site': site, 'bus': bus,
                'evaluation_energy_mwh': sum(r['power_mw'][site] * (r['end_s'] - r['start_s']) / 3600 for r in measured),
                'queue_snapshot_peak': max(r['waiting_by_site'][site] for r in measured)}
        for resource in ('node', 'core', 'gpu'):
            values = [r[resource + '_utilization'][site] for r in measured]
            item[resource + '_utilization_snapshot_mean'] = sum(values) / len(values)
            item[resource + '_utilization_snapshot_peak'] = max(values)
        sites.append(item)
    return {'case': summary['case'], 'periods': periods, 'sites': sites,
            'cohort': {k: v for k, v in summary.items() if k.startswith('cohort_')},
            'diagnostics': {k: summary[k] for k in ('peak_it_share', 'score_clipped_reports',
                            'negative_price_intervals', 'waiting_end', 'running_end',
                            'reports', 'switches', 'controller_seconds', 'seconds')}}


def make_report(out):
    # Require final marker: partial runs cannot silently become a final report.
    pilot = json.loads((out / 'pilot_summary.json').read_text(encoding='utf-8'))
    protocol = json.loads((out / 'started.json').read_text(encoding='utf-8'))['protocol']
    expected = [c['name'] for c in protocol['cases']]
    actual = [s['case'] for s in pilot['cases']]
    if actual != expected:
        raise ValueError('Missing, duplicated or reordered pilot cases')
    cases = {}
    for summary in pilot['cases']:
        directory = out / summary['case']
        checks = json.loads((directory / 'checks.json').read_text(encoding='utf-8'))
        required = {'task_conservation', 'report_conservation', 'completion_only_revisions',
                    'physical_energy_accounting', 'capacity', 'settlement_count'}
        if not required <= checks.keys() or not all(v is True for v in checks.values()):
            raise ValueError('Case integrity checks failed: ' + summary['case'])
        cases[summary['case']] = case_metrics(summary, read(directory / 'trace.jsonl.gz'))
    # Revalidate source identities and preintervention equality before reporting.
    analyze(out, protocol)
    pairs = json.loads((out / 'paired_system_metrics.json').read_text())['pairs']
    for pair in pairs:
        off, on = cases[pair['off']], cases[pair['on']]
        pair['evaluation_period_deltas_on_minus_off'] = {
            k: on['periods']['evaluation'][k] - v
            for k, v in off['periods']['evaluation'].items() if k not in ('start_s', 'end_s')}
    output = {'status': 'development_pilot_descriptive_only', 'cases': list(cases.values()), 'pairs': pairs,
              'notes': ['Evaluation-period outcomes and arrival-cohort outcomes have different denominators.',
                        'Cohort service outcomes include follow-up through the tail horizon.',
                        'Resource occupancy and queues are settlement-end snapshots.',
                        'First power difference is a numerical diagnostic, not a service qualification threshold.',
                        'Single-seed pilot; synthetic replicas are not independent observations.']}
    (out / 'system_report.json').write_text(json.dumps(output, indent=2, allow_nan=False), encoding='utf-8')
    rows = []
    for name, case in cases.items():
        for period, metrics in case['periods'].items():
            rows.append({'case': name, 'period': period, **metrics})
    with (out / 'system_periods.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = ['# 系统开发试跑核查', '', '本报告仅描述开发试跑，不作为正式性能结论。', '',
             '功率、电量与经济结果采用同一评价期；任务服务针对评价期到达的固定任务集合，并追踪至收尾结束。', '',
             '| 配对案例 | 目标窗口降电量 MWh | 接收站增电量 MWh | 全系统窗口电量差 MWh | 完成比例差（百分点） | 限时平均等待差 s | 评价期发电成本差 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    def fmt(value):
        return 'NA' if value is None else f'{value:.6g}'
    for p in pairs:
        completion = p['cohort_completed_fraction_delta']
        vals = [p['target_window_reduction_mwh'], p['receiving_sites_window_energy_delta_mwh'],
                p['total_window_energy_delta_mwh'], None if completion is None else 100 * completion,
                p['cohort_restricted_mean_wait_s_delta'],
                p['evaluation_period_deltas_on_minus_off']['generation_cost_currency']]
        lines.append('| ' + p['on'] + ' | ' + ' | '.join(map(fmt, vals)) + ' |')
    lines += ['', '目标降电量正值表示目标站点用电减少；其余差值均为信号开启减去关闭。电费和发电成本分别记账，不能直接相加。', '',
              '## 必须结合检查的条件', '',
              '- 全部案例检查通过并通过相同任务集合、处理前状态核查，才生成本报告。',
              '- 各站点资源占用与队列为结算末快照，详见 system_report.json。',
              '- 核查负价格、评分截断、未完成任务、计算负荷占比和电网松弛，保留无响应与负效应。',
              '- 固定全部常规机组在线、无跨站数据传输、仅任务IT功率仍是开发版本限制。',
              '- 首次功率差异只是数值诊断，不能等同符合需求响应服务要求。']
    (out / 'SYSTEM_REPORT_ZH.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    make_report(parser.parse_args().out)
