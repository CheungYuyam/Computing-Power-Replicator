import math
from dataclasses import dataclass
@dataclass(frozen=True)
class Truth:
    runtime: float
    power_w: tuple

    def segments(self):
        # Nominal 20 s sample positions; only final sample extends to runtime if needed.
        for i, power in enumerate(self.power_w):
            begin = i * 20.0
            end = min(self.runtime, (i + 1) * 20.0)
            if i == len(self.power_w) - 1:
                end = self.runtime
            if end > begin:
                yield begin, end, power

    def energy_kwh(self):
        return sum((b - a) * p for a, b, p in self.segments()) / 3_600_000

def valid_row(row, counts):
    def reject(reason):
        counts[reason] += 1
        return None
    if str(row["job_state"]).upper() != "COMPLETED":
        return reject("not_completed")
    times = [row.get(k) for k in ("submit_time", "start_time", "end_time")]
    if any(x is None for x in times) or not times[0] <= times[1] < times[2]:
        return reject("invalid_timestamp_order")
    resources = []
    for name in ("nodes", "cores", "gpus"):
        req, alloc = row.get(f"num_{name}_req"), row.get(f"num_{name}_alloc")
        if req is None or alloc is None or req < 0 or int(req) != req or req != alloc:
            return reject("request_allocation_mismatch_or_missing")
        resources.append(int(req))
    if resources[0] <= 0 or resources[1] <= 0:
        return reject("zero_nodes_or_cores")
    runtime = row.get("run_time")
    if runtime is None or not math.isfinite(runtime) or runtime <= 0:
        return reject("invalid_runtime")
    if abs((times[2] - times[1]).total_seconds() - runtime) > max(40, .05 * runtime):
        return reject("runtime_timestamp_disagreement")
    power = row.get("power_consumption")
    if not power or any(p is None or not math.isfinite(p) or p < 0 for p in power):
        return reject("invalid_power")
    if abs(len(power) * 20 - runtime) > max(40, .05 * runtime):
        return reject("nominal_sampling_mismatch")
    truth = Truth(runtime, tuple(power))
    if truth.energy_kwh() <= 0:
        return reject("zero_energy")
    eligible = row.get("eligible_time")
    release = times[0]
    if eligible is not None and eligible.year == 2020 and times[0] <= eligible <= times[1]:
        release = eligible
    else:
        counts["eligible_replaced_by_submit"] += 1
    counts["accepted"] += 1
    return {"key": str(row["job_id"]), "submit": times[0].timestamp(),
            "release": release.timestamp(), "historical_start": times[1].timestamp(),
            "historical_end": times[2].timestamp(), "resources": resources,
            "runtime": runtime, "mean_w": truth.energy_kwh() * 3_600_000 / runtime,
            "peak_w": max(power), "power_w": power}

