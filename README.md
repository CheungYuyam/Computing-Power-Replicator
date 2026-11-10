# Computing-Power-Replicator

Research code and derived experimental data for **Modeling Data Center Demand Response in Power Systems With Task Execution and Delayed Cost Feedback**.

The model connects completion-driven task allocation, receiving-site resource admission, grid dispatch, and delayed accumulated-cost feedback. It jointly evaluates task service, resource pressure, and electrical outcomes using measured PM100 task/power records and RTS-GMLC network/time-series data.

## November 10, 2026 Update

The current manuscript focuses on achievable data-center demand response in power systems. This update adds all nine paired startup-wait replays and the 1/2/4-hour signal-duration study, including numerical arrays, seed-level metrics, summaries, audit records, tests, and table generation. See [Supplemental experiments](docs/SUPPLEMENTAL_20261110.md).

The repository provides our code and derived experimental results. PM100 and RTS-GMLC remain separately sourced reference datasets; their official access links are in [Data](docs/DATA.md). The manuscript itself is not posted here.

## Current Study

Three workload dates (July 27, August 5, and August 21, 2020), six- and twelve-site deployments, and controller seeds 17/29/43 are evaluated over 72 hours: 24-hour warmup, evaluation, and follow-up periods. Capacity, release patterns, initialization, cost accounting, communication, task dependencies, and admission are varied in separate paired comparisons.

PM100 supplies measured task properties and power profiles. Sequential dependencies, workload copies, and site deployments are constructed experimental inputs. RTS-GMLC supplies the network benchmark. Replicated tasks are not independent workload samples; the study does not claim an observed multi-site field deployment.

## Repository Map

| Directory | Current Role |
| --- | --- |
| `systems/main/` | Main, capacity, scale and waiting checks: 34 frozen bundles, 212 runs |
| `systems/initialization/` | Capacity-proportional initialization: 9 bundles, 36 runs |
| `systems/mechanisms/` | Same-rule cost-history × communication factorial: 9 bundles, 72 runs (18 regression repeats) |
| `systems/structure/` | Stream construction × resource admission: 36 bundles, 144 runs |
| `numerical/` | Controlled replicator model and historical 45-case protocol |
| `paper/current/` | Current Figures 1–7, compact evidence, renderers, and table exports |
| `supplemental/` | November 10 startup-wait replays and duration-study code/results |
| `docs/` | Data, reproduction, figure mapping and validation instructions |
| `provenance/` | Source mappings and SHA-256 inventories |

`engineering/`, `dual_lag_v1/`, `event_audit/`, older `paper/` files outside `paper/current/`, and `figure_times_r1/` remain historical code. Their older dates, 270-run matrix and ten-figure mapping are documented in `docs/legacy_20261022/`. They are not the current manuscript design. The withdrawn target-share comparator and separate runtime-prediction investigation are not part of the current package.

## Quick Start

Use Python 3.10 or later in a virtual environment:

```sh
python -m pip install -r requirements.txt
python scripts/check_systems.py
python scripts/render_current_figures.py
```

These checks and renderers use bundled compact data and synthetic test fixtures. No raw PM100 download is needed. Figure 1 is supplied as approved vector artwork; Figures 2–7 render to `runs/current_figures/` without replacing approved exports.

For full replay, arrange the external inputs described in [Data](docs/DATA.md), then run a frozen bundle:

```sh
python systems/main/run.py --raw data/raw --protocol systems/main/protocols/001.json --out runs/main_001
python systems/mechanisms/run.py --raw data/raw --protocol systems/mechanisms/protocols/000.json --out runs/mechanisms_000
python systems/structure/run.py --raw data/raw --protocol systems/structure/protocols/000.json --out runs/structure_000
```

Each command runs all arms in one bundle. Use new output directories. Full workloads require substantially more resources than unit tests. See [Reproduction](docs/REPRODUCING.md), [Figures](docs/FIGURES.md), and [Validation](docs/VALIDATION.md).

## Data and Licensing

Large raw datasets and full task/decision ledgers are not bundled. Compact results and the interval traces needed by current figures are included. Historical server audits and checks on this packaged version are identified separately. No new open-source license has been assigned; third-party materials retain their own terms. Manuscript text, cover letters and editorial correspondence are maintained separately.
