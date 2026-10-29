"""Offline synthetic stream construction; never exposed to the controller.

Interval coloring uses measured durations only to construct nonoverlapping
template sequences, not to make allocation decisions. It does not reconstruct
user workflows. Original release times, resource requests and curves survive.
"""
import heapq
import numpy as np


def assign_lanes(jobs, rule='earliest_available'):
    if rule not in ('earliest_available', 'latest_available'):
        raise ValueError('Unknown lane construction')
    counts = []
    for kind in (0, 1):
        available = []
        idle = []
        count = 0
        for job in sorted((j for j in jobs if int(j['resources'][2] > 0) == kind),
                          key=lambda j: (j['release'], j['key'])):
            if rule == 'latest_available':
                while available and available[0][0] <= job['release']:
                    end, lane = heapq.heappop(available)
                    heapq.heappush(idle, (-end, lane))
                if idle:
                    _, lane = heapq.heappop(idle)
                else:
                    lane = count
                    count += 1
            elif available and available[0][0] <= job['release']:
                _, lane = heapq.heappop(available)
            else:
                lane = count
                count += 1
            job['lane'] = lane
            heapq.heappush(available, (job['release'] + job['runtime'], lane))
        counts.append(count)
    return counts


def unconstrained_profile(jobs, origin, horizon, step=300):
    """Preallocation workload audit; approximate power uses each job's mean W."""
    events = []
    for job in jobs:
        begin = job['release'] - origin
        end = begin + job['runtime']
        r = np.array([*job['resources'], job['mean_w'], 1.], dtype=float)
        events.extend([(begin, 1, r), (end, -1, r)])
    events.sort(key=lambda x: x[0])
    rows = []; current = np.zeros(5); index = 0
    for t in range(0, int(horizon), step):
        while index < len(events) and events[index][0] <= t:
            _, sign, resources = events[index]
            current += sign * resources
            index += 1
        rows.append(current.copy())
    a = np.array(rows)
    return {name: {'mean': float(a[:, k].mean()), 'p95': float(np.quantile(a[:, k], .95)),
                   'peak': float(a[:, k].max())}
            for k, name in enumerate(('nodes', 'cores', 'gpus', 'mean_curve_power_w', 'active_jobs'))}
