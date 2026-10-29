from pathlib import Path
import hashlib,json
import numpy as np
from test_consistency import pairwise_rhs,classical_rhs,rk4
R=Path(__file__).resolve().parent
meta=json.loads((R/'study_metadata.json').read_text())
assert hashlib.sha256((R/'controller.py').read_bytes()).hexdigest()==meta['original_controller_sha256']
rng=np.random.default_rng(713);derivative_error=0.;trajectory_error=0.
for n in (2,6,12):
    for lam in (.001,.25,1.):
        for _ in range(20):
            x=rng.dirichlet(np.ones(n));c=rng.uniform(0,5,n)
            derivative_error=max(derivative_error,float(np.max(abs(pairwise_rhs(x,c,.15,lam)-classical_rhs(x,c,.15,lam)))))
    x=np.arange(1,n+1,dtype=float);x/=x.sum();y=x.copy()
    costs=lambda z:np.linspace(.4,1.4,n)+.8*z
    for _ in range(2000):
        x=rk4(lambda z:pairwise_rhs(z,costs(z),.15,.25),x,.02)
        y=rk4(lambda z:classical_rhs(z,costs(z),.15,.25),y,.02)
        trajectory_error=max(trajectory_error,float(np.max(abs(x-y))))
assert derivative_error<1e-13 and trajectory_error<2e-13
import sys
result=dict(status='PASS',original_controller_identical=True,derivative_cases=180,
            trajectory_cases=3,max_derivative_error=derivative_error,max_trajectory_error=trajectory_error,
            scope='Canonical classical limit with shared costs, common revision rate, unsaturated acceptance. Engineering arms are mechanism ablations, not a complete classical-model controller.')
(Path(sys.argv[1])/'consistency_gate.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
