import csv, hashlib, os
from pathlib import Path
import numpy as np
from dc_grid import Grid
ROOT=Path(os.environ.get('CP_DATA_ROOT', str(Path(__file__).resolve().parents[1]/'data')))
RTS_HASH={'rts_bus.csv':'cec3f776222812d43eaeaf7ac85b577719dc565f354a04e120c12a647ddb710e',
          'rts_branch.csv':'e92d16d13b1c5d2899f7871c0c99c3eb94605528beef157bf9e1ccbcffe5ef4e',
          'rts_gen.csv':'988466f29132b73739de60c9204dd4a2a9ceb0adf572e5966c086611272f4068'}
def rows(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def load_network():
    raw=ROOT/'raw'
    for n,h in RTS_HASH.items():assert hashlib.sha256((raw/n).read_bytes()).hexdigest()==h
    buses=rows(raw/'rts_bus.csv');branches=rows(raw/'rts_branch.csv');gens=rows(raw/'rts_gen.csv')
    index={int(b['Bus ID']):i for i,b in enumerate(buses)}
    assert len(index)==len(buses)
    edges=[(index[int(b['From Bus'])],index[int(b['To Bus'])],float(b['X']),float(b['Tr Ratio']),float(b['Cont Rating'])) for b in branches]
    gb=[];pmin=[];pmax=[];cost=[];ramp=[];thermal=0
    for g in gens:
        gb.append(index[int(g['Bus ID'])]);is_thermal=g['Fuel'] in {'Oil','Coal','NG','Nuclear'}
        if is_thermal:
            thermal+=1;pmin.append(float(g['PMin MW']));pmax.append(float(g['PMax MW']))
            cost.append(float(g['Fuel Price $/MMBTU'])*float(g['HR_avg_0'])/1000+float(g['VOM']))
        else:
            pmin.append(0.);pmax.append(0. if g['Fuel'] in {'Storage','Sync_Cond'} else min(float(g['PMax MW']),max(0.,float(g['MW Inj']))));cost.append(0.)
        ramp.append(float(g['Ramp Rate MW/Min']))
    grid=Grid(len(buses),edges,gb,pmin,pmax,cost,ramp)
    base=np.array([float(b['MW Load']) for b in buses]);shunt=np.array([float(b['MW Shunt G']) for b in buses])
    allocation=np.zeros(len(buses))
    for bid,share in [(101,.6),(201,.3),(301,.1)]:allocation[index[bid]]=share
    meta={'buses':len(buses),'branches':len(branches),'generators':len(gens),'thermal_generators_fixed_online':thermal,
          'base_load_mw':float(base.sum()),'generation_lower_total_mw':sum(pmin),'generation_upper_total_mw':sum(pmax),
          'compute_bus_shares':{'101':.6,'201':.3,'301':.1},'base_mva':100.,'source_sha256':RTS_HASH}
    return grid,base,shunt,allocation,meta

