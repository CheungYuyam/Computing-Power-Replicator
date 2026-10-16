# External data

## PM100

Obtain `job_table.parquet` from the PM100 record at https://zenodo.org/records/8129258 . Place it in `data/raw/`. The preparation script requires MD5 `2a692d9b9dc4a6ee4bc5e3eb3d0fa6f5`.

The script applies the original job validity filter, selects the replay windows for August 1, 18 and 31, 2020, and copies `data/calibration/fit_summary.json` into the prepared directory. This is frozen-calibration replay, not a fresh training/refitting pipeline.

## RTS-GMLC

Obtain the bus, branch and generator source CSVs from https://github.com/GridMod/RTS-GMLC and save them as `data/raw/rts_bus.csv`, `rts_branch.csv`, and `rts_gen.csv`.

The paper input SHA-256 hashes are:

| File | SHA-256 |
| --- | --- |
| rts_bus.csv | cec3f776222812d43eaeaf7ac85b577719dc565f354a04e120c12a647ddb710e |
| rts_branch.csv | e92d16d13b1c5d2899f7871c0c99c3eb94605528beef157bf9e1ccbcffe5ef4e |
| rts_gen.csv | 988466f29132b73739de60c9204dd4a2a9ceb0adf572e5966c086611272f4068 |

Set `CP_DATA_ROOT` to use a different data directory. Raw inputs, prepared data and generated simulation runs are excluded from Git. Historical `_server_only` filenames are retained for compatibility; the packaged drivers run locally.
