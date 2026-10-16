"""Completion-driven evolution under separately specified time assumptions."""
import argparse
import ast
import csv
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy.integrate import solve_ivp, trapezoid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = np.array([[1., 1.4], [2., 2.8]])
REF = np.array([1., 2.])


def positive_quadrature(flow, edges, tolerance=2e-10, max_depth=32):
    """Integrate nonnegative rates using positive weights, never repair counters.

    Compare 8/16 point Gauss rules, subdividing only intervals whose order
    discrepancy exceeds their share of the absolute budget. The discrepancy is
    a numerical diagnostic, not a certified quadrature error bound.
    """
    edges = np.asarray(edges, dtype=float)
    if len(edges)<2 or not np.all(np.diff(edges)>0): raise ValueError('Invalid edges')
    rules = [np.polynomial.legendre.leggauss(order) for order in (8,16)]
    left, right = edges[:-1].copy(), edges[1:].copy()
    owners = np.arange(len(left)); increments = np.zeros((len(left),4))
    discrepancy = 0.; deepest=0; unresolved=0
    for depth in range(max_depth+1):
        approximations=[]
        for nodes,weights in rules:
            points=(left[:,None]+right[:,None])/2+(right-left)[:,None]*nodes/2
            values=np.asarray(flow(points.ravel())).reshape(len(left),len(nodes),4)
            if not np.isfinite(values).all() or (values<0).any():
                raise RuntimeError('Nonfinite or negative transfer rate; not clipped')
            approximations.append(np.einsum('ijk,j->ik',values,weights)*(right-left)[:,None]/2)
        err=abs(approximations[1]-approximations[0]).max(axis=1)
        accept=err <= tolerance*(right-left)/(edges[-1]-edges[0])
        if depth==max_depth:
            unresolved=int((~accept).sum())
            accept=np.ones_like(accept,dtype=bool)
        np.add.at(increments,owners[accept],approximations[1][accept])
        discrepancy+=float(err[accept].sum()); deepest=depth
        if accept.all(): break
        l,r,o=left[~accept],right[~accept],owners[~accept]; mid=(l+r)/2
        left=np.r_[l,mid]; right=np.r_[mid,r]; owners=np.r_[o,o]
    cumulative=np.vstack([np.zeros(4),np.cumsum(increments,axis=0)])
    return cumulative, dict(order_discrepancy_sum=discrepancy, requested_budget=tolerance,
                            max_refinement_depth=deepest, orders=[8,16], negative_rate_clipping=False,
                            unresolved_intervals=unresolved, target_met=discrepancy<=tolerance and unresolved==0)


def native(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    raise TypeError(type(value).__name__)


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False,
                              default=native)+'\n', encoding='utf-8')
    tmp.replace(path)


def csv_write(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configuration():
    p = json.loads((HERE/'protocol.json').read_text(encoding='utf-8'))
    cases = p['scenarios']
    fields = ['execution_scale', 'feedback_mean', 'initial_strategy0_fraction',
              'execution_stages', 'accumulated_payoff', 'initial_history']
    if len(cases) != 45 or len({tuple(c[f] for f in fields) for c in cases}) != 45:
        raise ValueError('Expected 45 unique scenarios')
    if len({c['case_id'] for c in cases}) != 45: raise ValueError('Case ids duplicated')
    for c in cases: Model(c)
    return p


class Model:
    def __init__(self, case):
        self.case = case
        self.k = int(case['execution_stages'])
        self.alpha = float(case['execution_scale'])
        self.tau = float(case['feedback_mean'])
        self.p = float(case['initial_strategy0_fraction'])
        self.marked = bool(case['accumulated_payoff'])
        self.history = case['initial_history']
        if self.k < 1 or self.k != case['execution_stages'] or self.alpha <= 0:
            raise ValueError('Invalid execution parameters')
        if self.tau < 0 or not 0 <= self.p <= 1: raise ValueError('Invalid feedback/initial share')
        if self.history not in ('fresh', 'stationary_execution_fresh_observer'):
            raise ValueError('Unknown history')
        self.means = self.alpha * BASE
        self.mu = self.k / self.means
        self.nsize = 4*self.k
        self.size = 2*self.nsize+20

    def unpack(self, y):
        n = y[:self.nsize].reshape(2, 2, self.k)
        a = y[self.nsize:2*self.nsize].reshape(2, 2, self.k)
        F, B, U, V, Z = y[2*self.nsize:].reshape(5, 2, 2)
        return n, a, F, B, U, V, Z

    def initial(self):
        n = np.zeros((2, 2, self.k)); a = n.copy()
        mass = np.tile(.5*np.array([self.p, 1-self.p]), (2, 1))
        if self.history == 'fresh':
            n[:, :, 0] = mass
        else:
            n[:] = mass[:, :, None]/self.k
            c = self.costs(n)
            age = np.arange(1, self.k+1)[None, None, :]/self.mu[:, :, None]
            a = n * age * c[None, :, None]/REF[:, None, None]
        z = np.zeros((2, 2)); U = np.full((2, 2), .1)
        V = U*np.array([1.4, 1.7])
        return np.concatenate([n.ravel(), a.ravel(), z.ravel(), z.ravel(),
                               U.ravel(), V.ravel(), z.ravel()])

    @staticmethod
    def costs(n):
        return np.array([.7, 1.])+1.4*n.sum(axis=(0, 2))

    @staticmethod
    def switching(x, c):
        P = x[None, :]*np.clip(.2*(c[:, None]-c[None, :]), 0, 1)
        np.fill_diagonal(P, 0)
        P[np.diag_indices(2)] = 1-P.sum(axis=1)
        return P

    def rhs(self, t, y):
        n, a, F, B, U, V, Z = self.unpack(y)
        c = self.costs(n)
        f = self.mu*n[:, :, -1]
        b = self.mu*a[:, :, -1]
        if not self.marked: b = f*c[None, :]*self.means/REF[:, None]
        dn = -self.mu[:, :, None]*n
        da = c[None, :, None]*n/REF[:, None, None]-self.mu[:, :, None]*a
        if self.k > 1:
            dn[:, :, 1:] += self.mu[:, :, None]*n[:, :, :-1]
            da[:, :, 1:] += self.mu[:, :, None]*a[:, :, :-1]
        dZ = np.zeros((2, 2))
        for r in range(2):
            x = n[r].sum(axis=1)/.5
            P = self.switching(x, V[r]/np.maximum(U[r], 1e-10))
            dn[r, :, 0] += f[r]@P
            dZ[r, 0] = f[r, 0]*P[0, 1]  # cumulative population mass, 0 -> 1
            dZ[r, 1] = f[r, 1]*P[1, 0]  # 1 -> 0
        if self.tau:
            received, reward = F/self.tau, B/self.tau
            dF, dB = f-received, b-reward
        else:
            received, reward = f, b
            dF, dB = np.zeros_like(F), np.zeros_like(B)
        return np.concatenate([dn.ravel(), da.ravel(), dF.ravel(), dB.ravel(),
            (received-.5*U).ravel(), (reward-.5*V).ravel(), dZ.ravel()])

    def solve(self, horizon=80., step=.05, rtol=2e-10, atol=1e-12, max_step=.05):
        count = round(horizon/step)
        if not np.isclose(count*step, horizon): raise ValueError('Nonintegral output grid')
        ts = np.linspace(0, horizon, count+1)
        # Z is a passive recorder. Exclude it from the dynamical solver and
        # integrate its nonnegative rates independently along that solution.
        def core_rhs(t, y):
            return self.rhs(t, np.r_[y, np.zeros(4)])[:-4]
        sol = solve_ivp(core_rhs, (0., horizon), self.initial()[:-4], t_eval=ts, dense_output=True,
                        rtol=rtol, atol=atol, max_step=max_step)
        if not sol.success: raise RuntimeError(sol.message)
        def rates(t):
            y=sol.sol(t).T
            n=y[:,:self.nsize].reshape(-1,2,2,self.k)
            aux=y[:,2*self.nsize:].reshape(-1,4,2,2)
            x=n.sum(axis=3)/.5; c=aux[:,3]/np.maximum(aux[:,2],1e-10)
            f=n[:,:,:,-1]*self.mu
            z=np.empty((len(t),2,2))
            z[:,:,0]=f[:,:,0]*x[:,:,1]*np.clip(.2*(c[:,:,0]-c[:,:,1]),0,1)
            z[:,:,1]=f[:,:,1]*x[:,:,0]*np.clip(.2*(c[:,:,1]-c[:,:,0]),0,1)
            return z.reshape(-1,4)
        z,self.quadrature_diagnostics=positive_quadrature(rates,ts)
        return sol.t, np.column_stack([sol.y.T,z])

    def observables(self, ys):
        ns = ys[:, :self.nsize].reshape(-1, 2, 2, self.k)
        aux = ys[:, 2*self.nsize:].reshape(-1, 5, 2, 2)
        return dict(strategy=ns.sum(axis=3)/.5, completion=ns[:, :, :, -1]*self.mu,
                    visible_cost=aux[:, 3]/np.maximum(aux[:, 2], 1e-10),
                    in_transit=aux[:, 0], transfers=aux[:, 4], type_mass=ns.sum(axis=(2, 3)))


def analyze(model, ts, ys, spec):
    ob = model.observables(ys)
    x = ob['strategy'][:, :, 0]
    tail = ts >= spec['tail_interval'][0]
    derivatives = np.array([model.rhs(t, y) for t, y in zip(ts[tail], ys[tail])])
    dx = derivatives[:, :model.nsize].reshape(-1, 2, 2, model.k).sum(axis=3)/.5
    balance = .5*(x-x[0])-(-ob['transfers'][:, :, 0]+ob['transfers'][:, :, 1])
    row = dict(model.case)
    for r in range(2):
        row.update({f'x0_type{r}_final': float(x[-1, r]),
            f'x0_type{r}_min': float(x[:, r].min()), f'x0_type{r}_max': float(x[:, r].max()),
            f'x0_type{r}_total_variation': float(abs(np.diff(x[:, r])).sum()),
            f'x0_type{r}_tail_range': float(np.ptp(x[tail, r])),
            f'x0_type{r}_tail_max_abs_derivative': float(abs(dx[:, r, 0]).max()),
            f'type{r}_cumulative_0_to_1': float(ob['transfers'][-1, r, 0]),
            f'type{r}_cumulative_1_to_0': float(ob['transfers'][-1, r, 1])})
    row.update(mass_error=float(abs(ob['type_mass']-.5).max()),
               min_state=float(ys.min()), transfer_balance_error=float(abs(balance).max()))
    snaps = []
    for t in spec['snapshot_times']:
        j = int(np.argmin(abs(ts-t)))
        if abs(ts[j]-t)>1e-9: raise ValueError('Missing snapshot')
        rec = dict(case_id=model.case['case_id'], time=float(t))
        for r in range(2):
            rec[f'x0_type{r}'] = float(x[j, r])
            for i in range(2):
                for name in ('completion', 'visible_cost', 'in_transit'):
                    rec[f'{name}_r{r}_i{i}'] = float(ob[name][j, r, i])
        snaps.append(rec)
    checks = dict(finite=bool(np.isfinite(ys).all()),
        each_type_mass=row['mass_error'] < 1e-7, nonnegative=row['min_state'] >= -1e-8,
        shares_in_simplex=bool((ob['strategy'] >= -1e-8).all() and (ob['strategy'] <= 1+1e-8).all()),
        cumulative_transfers_nondecreasing=bool((np.diff(ob['transfers'], axis=0) >= -1e-9).all()),
        transfer_population_balance=row['transfer_balance_error'] < 1e-7,
        complete_grid=len(ts)==round(spec['horizon']/spec['sample_interval'])+1,
        initial_conditions_preserved=bool(np.allclose(ys[0], model.initial(), atol=1e-12, rtol=0)),
        quadrature_diagnostics_recorded=bool(np.isfinite(model.quadrature_diagnostics['order_discrepancy_sum'])),
        cumulative_transfers_exactly_nondecreasing=bool((np.diff(ob['transfers'],axis=0)>=0).all()))
    row['quadrature_order_discrepancy_sum']=model.quadrature_diagnostics['order_discrepancy_sum']
    row['quadrature_max_refinement_depth']=model.quadrature_diagnostics['max_refinement_depth']
    row['quadrature_target_met']=model.quadrature_diagnostics['target_met']
    row['quadrature_unresolved_intervals']=model.quadrature_diagnostics['unresolved_intervals']
    return row, snaps, checks, ob


def comparisons(cases, small_curves, times):
    rows = []
    for c in cases:
        if c['group'].startswith('E1'): continue
        matches = [p for p in cases if p['group'].startswith('E1') and
            p['execution_scale']==c['execution_scale'] and p['feedback_mean']==c['feedback_mean']
            and p['initial_strategy0_fraction']==c['initial_strategy0_fraction']]
        if len(matches)!=1: raise ValueError('Unmatched contrast')
        parent = matches[0]['case_id']
        diff = small_curves[c['case_id']]-small_curves[parent]
        for r in range(2):
            rows.append(dict(case_id=c['case_id'], reference_case=parent, group=c['group'], type=r,
                max_abs_path_difference=float(abs(diff[:, r]).max()),
                terminal_difference=float(diff[-1, r]),
                signed_time_integral=float(trapezoid(diff[:, r], times)),
                absolute_time_integral=float(trapezoid(abs(diff[:, r]), times)),
                interpretation='scenario_difference_no_ranking_no_equality_target'))
    return rows


def preflight():
    spec = configuration()
    # Compare to the already frozen implementation only in its identical configuration.
    # This is a source regression check, not a cross-assumption equality requirement.
    parent = HERE.parent/'dual_lag_v1/theory.py'
    raw = parent.read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    expected = spec['parent_normalized_sha256']
    if hashlib.sha256(raw.encode()).hexdigest() != expected: raise RuntimeError('Parent SHA mismatch')
    tree = ast.parse(raw)
    names = {'initial', 'costs', 'switching', 'rhs'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {'np': np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(parent), 'exec'), env)
    c = dict(spec['scenarios'][0], execution_scale=1., feedback_mean=.5,
             initial_strategy0_fraction=.7, execution_stages=2, accumulated_payoff=True, initial_history='fresh')
    m = Model(c); y = m.initial()
    err = float(abs(m.rhs(0, y)[:32]-env['rhs'](0, env['initial']())).max())
    if err>1e-12: raise RuntimeError('Identical-scenario derivative changed')
    _, z = m.solve(horizon=.5, step=.05)
    err2 = float(abs(m.rhs(.5, z[-1])[:32]-env['rhs'](.5, z[-1, :32])).max())
    if err2>1e-12: raise RuntimeError('Identical-scenario derivative changed at positive time')
    # Exercise all parameter adapters and summary paths on a short synthetic interval.
    smoke = dict(spec, horizon=.1, snapshot_times=[0., .05, .1], tail_interval=[.05, .1])
    curves = {}
    for c in spec['scenarios']:
        model = Model(c); ts, ys = model.solve(.1)
        _, _, checks, obs = analyze(model, ts, ys, smoke)
        if not all(checks.values()): raise RuntimeError('Short adapter check failed: '+c['case_id'])
        curves[c['case_id']] = obs['strategy'][:, :, 0]
    if len(comparisons(spec['scenarios'], curves, ts)) != 36:
        raise RuntimeError('Comparison adapter count differs')
    return dict(scenarios=45, same_assumption_parent_derivative_max_error=max(err,err2),
                parent_normalized_sha256=expected, short_adapter_cases=45, no_raw_data_read=True)


def run(out):
    spec = configuration()
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()): raise RuntimeError('Refusing to overwrite results')
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    def status(stage, completed, **kw):
        record = dict(stage=stage, completed_conditions=completed, expected_conditions=45,
                      elapsed_seconds=time.time()-started, **kw)
        write_json(out/'status.json', record); print(json.dumps(record), flush=True)
    status('starting', 0)
    try:
        pf = preflight(); rows=[]; snaps=[]; case_checks={}; curves={}; hashes={}
        for c in spec['scenarios']:
            model=Model(c)
            ts, ys=model.solve(spec['horizon'], spec['sample_interval'])
            row, ss, checks, ob=analyze(model, ts, ys, spec)
            dest=out/(c['case_id']+'_trajectory_server_only.npz')
            np.savez_compressed(dest, time=ts, state=ys, **ob)
            hashes[dest.name]=digest(dest)
            rows.append(row); snaps.extend(ss); case_checks[c['case_id']]=checks
            curves[c['case_id']]=ob['strategy'][:, :, 0]
            write_json(out/'case_integrity_server_only.json', case_checks)
            status('integrating', sum(all(v.values()) for v in case_checks.values()),
                   written_conditions=len(rows), last_case=c['case_id'])
            if not all(checks.values()): raise RuntimeError('Case integrity failed: '+c['case_id'])
        csv_write(out/'case_summary.csv', rows); csv_write(out/'snapshots.csv', snaps)
        contrasts=comparisons(spec['scenarios'], curves, ts)
        csv_write(out/'contrasts.csv', contrasts)
        write_json(out/'trajectory_hashes_server_only.json', hashes)
        write_json(out/'numerical_diagnostics.json', dict(
            quadrature_target_is_advisory=True, target=2e-10,
            warning_cases=[r['case_id'] for r in rows if not r['quadrature_target_met']],
            max_order_discrepancy=max(r['quadrature_order_discrepancy_sum'] for r in rows),
            no_counter_clipping=True, no_cross_scenario_alignment=True))
        summary=dict(model='completion_driven_marked_cost_evolution', conditions=45,
            groups={g:sum(c['group']==g for c in spec['scenarios']) for g in sorted({c['group'] for c in spec['scenarios']})},
            horizon=spec['horizon'], time_unit='dimensionless_fixed_across_scenarios',
            max_mass_error=max(r['mass_error'] for r in rows),
            min_state=min(r['min_state'] for r in rows),
            max_transfer_balance_error=max(r['transfer_balance_error'] for r in rows),
            contrast_rows=len(contrasts), snapshot_rows=len(snaps),
            real_dataset_used=False, test_months_used=False, dc_opf_used=False,
            cross_assumption_equality_target=False, convergence_or_novelty_proved=False)
        write_json(out/'summary.json', summary)
        write_json(out/'provenance.json', dict(python=sys.version, scipy=scipy.__version__, numpy=np.__version__,
            platform=platform.platform(), preflight=pf, source_files={p.name:digest(p) for p in HERE.iterdir()
            if p.name in ('evolution.py','protocol.json','STORY_ZH.txt','README.txt','test_evolution.py')},
            solver='RK45_core_only', rtol=2e-10, atol=1e-12, max_step=.05,
            cumulative_transfer_output='positive_weight_adaptive_Gauss_8_16; no clipping or cumulative-max repair',
            quadrature_discrepancy_budget=2e-10,
            no_cross_assumption_curve_alignment=True, fixed_cost_reference=REF, scope='dimensionless_mechanism_experiments'))
        checks={key: all(v[key] for v in case_checks.values()) for key in next(iter(case_checks.values()))}
        checks.update(all_45_conditions=len(rows)==45, all_expected_snapshots=len(snaps)==len(spec['scenarios'])*len(spec['snapshot_times']),
            all_36_contrast_rows=len(contrasts)==36, all_45_trajectories=len(hashes)==45,
            identical_configuration_regression=pf['same_assumption_parent_derivative_max_error']<1e-12,
            no_empirical_or_locked_test_data=True)
        write_json(out/'integrity_checks.json', checks)
        if not all(checks.values()): raise RuntimeError('Final integrity failed')
        status('complete', 45, integrity_checks_passed=True)
    except Exception as exc:
        write_json(out/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        status('failed', sum(all(v.values()) for v in locals().get('case_checks', {}).values()),
               written_conditions=len(locals().get('rows', [])))
        raise


if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--preflight', action='store_true')
    args=ap.parse_args()
    if args.preflight: print(json.dumps(preflight()))
    elif args.out: run(args.out)
    else: ap.error('--out or --preflight required')
