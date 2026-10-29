"""Multi-site completion-triggered controller; no access to future job truth."""
import hashlib
import numpy as np


def stable_int(value):
    return int.from_bytes(hashlib.sha256(str(value).encode()).digest()[:8], 'big')


class Controller:
    def __init__(self, sites, per_class, seed, method='reported_cost', beta=.15, memory_s=21600, class_counts=None):
        self.sites, self.per_class, self.seed = sites, per_class, seed
        self.method, self.beta, self.memory_s = method, beta, memory_s
        self.class_counts = list(class_counts) if class_counts is not None else [per_class, per_class]
        if len(self.class_counts)!=2 or min(self.class_counts)<0 or sum(self.class_counts)==0:
            raise ValueError('Invalid class populations')
        self.offsets = [0, self.class_counts[0], sum(self.class_counts)]
        self.strategy = np.random.default_rng(seed).integers(sites, size=sum(self.class_counts))
        self.u = np.ones((2, sites))
        self.v = np.ones((2, sites))
        self.last = 0.
        self.ordinals = np.zeros(sum(self.class_counts), dtype=int)
        self.revisions = self.switches = self.received = 0

    def receive(self, t, records):
        if t < self.last:
            raise ValueError('Nonmonotone controller clock')
        decay = np.exp(-(t-self.last)/self.memory_s)
        # Rescale the whole class when necessary to avoid stale-site underflow.
        self.u *= decay
        self.v *= decay
        for due, completed, kind, site, cost in records:
            if not completed <= due <= t or not np.isfinite(cost):
                raise ValueError('Noncausal or invalid report')
            self.u[kind,site] += 1
            self.v[kind,site] += cost
            self.received += 1
        self.last = t

    def costs(self, kind):
        return np.divide(self.v[kind],self.u[kind],out=np.ones(self.sites),where=self.u[kind]>1e-200)

    def revise(self, stream):
        ordinal = int(self.ordinals[stream])
        self.ordinals[stream] += 1
        self.revisions += 1
        kind = int(stream >= self.offsets[1])
        rng = np.random.default_rng(np.random.SeedSequence([self.seed,stream,ordinal,713]))
        peer = int(rng.integers(self.class_counts[kind]))
        uniform = float(rng.random())
        old = int(self.strategy[stream])
        candidate = int(self.strategy[self.offsets[kind]+peer])
        costs = self.costs(kind)
        probability = float(np.clip(self.beta*(costs[old]-costs[candidate]),0,1))
        if self.method == 'fixed':
            probability = 0.
        elif self.method not in ('reported_cost','completion_price'):
            raise ValueError('Unknown mechanism')
        if uniform < probability:
            self.strategy[stream] = candidate
        self.switches += int(self.strategy[stream] != old)
        return {'stream':stream,'ordinal':ordinal,'old':old,'candidate':candidate,
                'new':int(self.strategy[stream]),'probability':probability,'uniform':uniform}
