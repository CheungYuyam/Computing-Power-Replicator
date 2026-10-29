# External Data for the Current Study

## PM100

Obtain the PM100 v1 job table from https://zenodo.org/records/8129258 and save it as `data/raw/pm100_v1_job_table.parquet`. The original MD5 is `2a692d9b9dc4a6ee4bc5e3eb3d0fa6f5`. The older package used `job_table.parquet`; current drivers require the prefixed filename.

The 47-hour source windows start on July 27, August 5, and August 21, 2020 and retain 1,386, 852, and 1,154 records. `pm100_filter.py` checks completed status, timestamp order, requested/allocated resources, duration and finite nonnegative power. Each record retains measured execution duration and power, requested resources, and eligibility/submission-based release.

The six-site study uses 192 copies, producing 163,584–266,112 task instances. Streams are constructed separately for CPU/GPU classes from nonoverlapping intervals beginning at release and lasting the measured duration. These are constructed dependencies. Controllers observe completion events rather than future exact completion times. Each staggered copy has a fixed offset of up to one hour; all arrivals precede hour 48.

Each code family includes frozen `reference.json` (normalization from records before July 16) and `calibration.json` (capacity calibration from July 16–19). Replay does not refit these values on evaluation data.

## RTS-GMLC

Obtain the benchmark from https://github.com/GridMod/RTS-GMLC and preserve source column names. Supply the following files in the same raw directory:

| Local Filename | Content |
| --- | --- |
| `rts_bus.csv` | Bus source table |
| `rts_branch.csv` | Branch source table |
| `rts_gen.csv` | Generator source table |
| `rts_rt_load.csv` | Five-minute regional load series |
| `rts_rt_wind.csv` | Five-minute wind series |
| `rts_rt_pv.csv` | Five-minute photovoltaic series |

`grid.py` aligns month/day/interval and distributes regional loads by bus base-load shares. Dispatch uses fixed commitment, DC balance, line/output/ramp constraints and recorded shedding/spillage. Computing demand comes from task IT power; cooling and data-transfer energy are not included.

Pass another directory with `--raw`. Set `CP_RAW` only when running the optional real-input grid test. The legacy data notes retain original network-table hashes in `legacy_20261022/DATA.md`. External datasets retain their providers' terms. Raw inputs and generated ledgers are ignored by Git.
