"""Portable driver for the 135 paired engineering experiments."""
import argparse,csv,gzip,json,itertools
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from engine import load_parent,load_grid,simulate,GridSettlement,digest,ROOT
from evolution import compare

def native(x):
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 raise TypeError(type(x).__name__)
def write(p,x):p.write_text(json.dumps(x,indent=2,default=native,allow_nan=False),encoding='utf-8')
def table(p,rs):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--prepared',type=Path,default=ROOT/'prepared');ap.add_argument('--one-pair',action='store_true');a=ap.parse_args()
 if a.out.exists() and any(a.out.iterdir()):raise ValueError('Refusing to overwrite output')
 a.out.mkdir(parents=True,exist_ok=True)
 fit=json.loads((a.prepared/'fit_summary.json').read_text());hashes=json.loads((a.prepared/'input_hashes.json').read_text())
 parent=load_parent();grid,base,shunt,buses,meta=load_grid();write(a.out/'grid.json',meta)
 results=[];pairs=[];settings=list(itertools.product(['2020-08-01','2020-08-18','2020-08-31'],[17,43,71,101,137],[0,900,3600],[0,150,300]))
 if a.one_pair:settings=settings[:1]
 cached={}
 for date,seed,lag,admission in settings:
  if date not in cached:
   path=a.prepared/(date+'_jobs_server_only.jsonl.gz')
   if digest(path)!=hashes[date]:raise ValueError('Prepared input hash mismatch')
   with gzip.open(path,'rt',encoding='utf-8') as f:cached[date]=[json.loads(line) for line in f]
  day=datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp();origin=day-43200;pair={}
  for incentive in [False,True]:
   cid=f'{date}_s{seed}_lag{lag}_admit{admission}_'+('on' if incentive else 'off');dest=a.out/cid;dest.mkdir()
   provider=GridSettlement(parent,grid,base,shunt,buses,fit['power_mw_per_w'],origin,day)
   r=simulate(parent,cached[date],fit,provider,origin=origin,daystart=day,seed=seed,lag=lag,admission_period=admission,settlement=300,horizon=172800,incentive=incentive)
   if not all(r['integrity'].values()):raise ValueError('Case integrity failed: '+cid)
   pair[incentive]=r;results.append({'case_id':cid,'date':date,**r['summary']})
   with gzip.open(dest/'records_server_only.json.gz','wt',encoding='utf-8') as f:json.dump({k:v for k,v in r.items() if k!='trace'},f,default=native,allow_nan=False)
   columns=list(r['trace'][0]);np.savez_compressed(dest/'trace_server_only.npz',columns=np.array(columns),values=np.array([[x[k] for k in columns] for x in r['trace']]))
   write(dest/'trace_sha256.json',{'trace_server_only.npz':digest(dest/'trace_server_only.npz')});table(a.out/'matrix_results.csv',results)
  pairs.append(compare(pair[True],pair[False],day,origin));table(a.out/'matrix_pairs.csv',pairs)
  print(f'Completed {len(pairs)}/{len(settings)} pairs',flush=True)
 write(a.out/'status.json',{'stage':'complete','runs':len(results),'pairs':len(pairs)})
if __name__=='__main__':main()
