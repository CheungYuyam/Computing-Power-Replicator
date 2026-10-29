# Computing-Power-Replicator

Research code for **A Replicator Model Coupling Task Execution and Delayed Feedback on Accumulated Costs for Computing–Power Coordination**.

The model tracks task execution, accumulated costs and delayed reports to examine when assignment changes produce site power responses. This repository contains numerical experiments, engineering simulations, event audits, plotting code and the summary results used in the paper.

## Contents

| Directory | Contents |
| --- | --- |
| `numerical/` | Replicator evolution, 45-scenario protocol and 18 tests |
| `engineering/` | Completion-event simulator, paired-run driver, data preparation, analysis and 15 tests |
| `dual_lag_v1/` | Frozen controller, power-system solver and grid adapter |
| `event_audit/` | Event-chain attribution functions and 10 tests |
| `paper/source_data/` | Numerical summaries, 270 engineering runs, 135 paired comparisons and event evidence |
| `paper/` | Plotting scripts and the current manuscript figure exports |
| `figure_times_r1/` | Earlier shared figure renderer and trajectory-based rendering functions |
| `data/calibration/` | Frozen PM100 calibration used by the engineering experiments |
| `provenance/` | Source mapping, checksums and packaging notes |

## Quick Start

Use Python 3.10 or later in a virtual environment:

```sh
python -m pip install -r requirements.txt
python scripts/check.py
python numerical/evolution.py --preflight
python numerical/evolution.py --out runs/numerical
```

Outputs must be new or empty directories. Numerical experiments are dimensionless mechanism experiments; engineering experiments use the external inputs described in [docs/DATA.md](docs/DATA.md).

```sh
python engineering/prepare_data.py --parquet data/raw/job_table.parquet --out data/prepared
python engineering/run.py --out runs/engineering_smoke --one-pair
python engineering/run.py --out runs/engineering
```

The full engineering matrix contains three dates × five seeds × three communication delays × three admission periods = 135 paired comparisons (270 runs). The preparation command uses the supplied frozen calibration; it does not refit that calibration.

See [figure mapping](docs/FIGURES.md), [verification scope](docs/VALIDATION.md) and [packaging changes](provenance/README.md).

## Scope and Licensing

Large raw datasets and full server trajectories are not bundled. Current figure exports and compact numerical results are included. Core tests have passed. This repository is initially private. No new open-source license has been assigned; third-party datasets retain their original terms.
