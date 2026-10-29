# Reproducing the Current Study

## Frozen Code Families

| Family | Source Release | Bundles | Runs |
| --- | --- | ---: | ---: |
| main | e02728b10095 | 34 | 212 |
| initialization | ab3a8acf66d3 | 9 | 36 |
| mechanisms | 385d590e351f | 9 | 72 |
| structure | 77eca5991b89 | 36 | 144 |

These are matrix counts, not independent sample counts. Eighteen mechanism runs repeat earlier configurations. Keep families in separate processes because their frozen modules share filenames. Structure protocol objects are extracted from executed `started.json` records. The predictor investigation and withdrawn comparator are excluded.

## Commands

```sh
python -m pip install -r requirements.txt
python scripts/check_systems.py
python scripts/render_current_figures.py
python systems/initialization/run.py --raw data/raw --protocol systems/initialization/protocols/000.json --out runs/init_000
```

Arrange raw inputs using [DATA.md](DATA.md). The final command executes all arms of one bundle and writes ledgers and audits. For a full matrix, run each family's protocol JSON separately. Use new output directories; a `started.json` marker prevents silent reuse. Independent bundles may run on a server according to available CPU and memory. Full workloads contain hundreds of thousands of task instances and are not lightweight smoke tests.

`check_systems.py` tests code families independently, then checks protocol and compact evidence counts. Without `CP_RAW`, the real-input RTS test is explicitly omitted; hand-solvable grid oracles still run using generated fixtures. Historical checks remain available through `python scripts/check.py`.

## Definitions

Paired arms share task records, initial placement and indexed random draws. Main comparisons use accumulated-cost feedback minus fixed allocation. Same-rule ablations use variant minus accumulated-cost feedback with 900-second communication. Completion-price accounting applies the final settlement tariff to all task energy. Zero communication still retains settlement waiting.

Completion counts the fixed cohort released in hours 24–48 and completed by hour 48. Restricted waiting includes unfinished/unstarted tasks through hour 72. Electrical outcomes cover hours 24–48; the signal acts at site 0 in hours 36–38. Seed ranges are descriptive minima/maxima, not confidence intervals.

## Provenance

`provenance/systems_source_manifest.json` records original and packaged hashes. Core solver/controller files retain their equations byte-for-byte. Plotting paths are adapted; private path prefixes in compact provenance become logical identifiers. Full raw inputs, full task/decision logs, credentials, server deployment scripts and submission correspondence are not included. Compact historical audit records do not imply that all large experiments were rerun during packaging.
