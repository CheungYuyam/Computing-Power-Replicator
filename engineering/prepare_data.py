"""Prepare the published PM100 replay cohort using the frozen calibration."""
import argparse,gzip,json,hashlib,shutil
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from pm100_filter import valid_row

def stamp(s):return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()
def main():
 import pyarrow as pa
 import pyarrow.compute as pc
 import pyarrow.parquet as pq
 ap=argparse.ArgumentParser();ap.add_argument('--parquet',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 h=hashlib.md5()
 with a.parquet.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 if h.hexdigest()!='2a692d9b9dc4a6ee4bc5e3eb3d0fa6f5':raise ValueError('PM100 checksum mismatch')
 if a.out.exists() and any(a.out.iterdir()):raise ValueError('Refusing overwrite')
 a.out.mkdir(parents=True,exist_ok=True);dates=['2020-08-01','2020-08-18','2020-08-31'];counts=Counter();selected=Counter()
 streams={d:gzip.open(a.out/(d+'_jobs_server_only.jsonl.gz'),'wt',encoding='utf-8') for d in dates}
 cols=['job_id','job_state','submit_time','eligible_time','start_time','end_time','run_time','power_consumption']+[f'num_{r}_{s}' for r in ('nodes','cores','gpus') for s in ('req','alloc')]
 lo=pa.scalar(datetime(2020,5,1,tzinfo=timezone.utc));hi=pa.scalar(datetime(2020,9,1,tzinfo=timezone.utc))
 try:
  for batch in pq.ParquetFile(a.parquet).iter_batches(batch_size=32,columns=cols):
   submit=batch.column(batch.schema.get_field_index('submit_time'));end=batch.column(batch.schema.get_field_index('end_time'))
   mask=pc.and_(pc.and_(pc.greater_equal(submit,lo),pc.less(submit,hi)),pc.less(end,hi))
   for row in batch.filter(mask).to_pylist():
    job=valid_row(row,counts)
    if job:
     for d in dates:
      if stamp(d)-43200<=job['release']<stamp(d)+86400:streams[d].write(json.dumps(job,separators=(',',':'))+'\n');selected[d]+=1
 finally:
  for f in streams.values():f.close()
 shutil.copyfile(Path(__file__).resolve().parents[1]/'data/calibration/fit_summary.json',a.out/'fit_summary.json')
 hashes={d:hashlib.sha256((a.out/(d+'_jobs_server_only.jsonl.gz')).read_bytes()).hexdigest() for d in dates}
 (a.out/'input_hashes.json').write_text(json.dumps(hashes,indent=2));(a.out/'preparation.json').write_text(json.dumps({'selected':selected,'quality_counts':counts,'calibration':'frozen supplied calibration; not a fresh refit'},indent=2))
if __name__=='__main__':main()
