# Validation of the Current Package

## Checks Repeated for the October 29 Update

`python scripts/check_systems.py` passed 99 tests across four isolated code families:

| Family | Tests Passed |
| --- | ---: |
| main | 25 |
| initialization | 23 |
| mechanisms | 28 |
| structure | 23 |

Tests cover controller rules, task progression, stream construction, resource admission, accounting and period metrics. The main suite includes five hand-solvable grid dispatch oracles. The optional real-input RTS test in each family was not run locally because `CP_RAW` was unset. This omission is printed by the check command; it is not counted as a pass.

All 88 protocol bundles have their expected case counts. Compact evidence checks passed for 27 joint-outcome pairs, 108 site metric rows, 39 signal pairs, three matched event groups, and 36 structure comparisons.

`python scripts/render_current_figures.py` regenerated Figures 2–7 from bundled inputs. The six PDFs opened successfully and were visually compared with approved exports. Figure 2 retains all 1,601 samples per curve. Figure 5 independently reconciles 288 interval records with frozen generation-cost summaries. The render command writes only to the requested output folder.

Core packaged solver/controller files are checked against the source hashes in `provenance/systems_source_manifest.json`. Packaging changes are paths and documentation, not numerical equations. Python sources were syntax-checked. See `provenance/systems_validation.json` for the recorded package checks.

## Historical Full-Study Audits

The frozen main and initialization audits are in `paper/current/source_data/`. The same-rule audit in `same_rule_mechanisms_20261025/FINAL_AUDIT.json` records 72 completed runs and 15,254,361 candidate/probability/destination checks. Its repeated original cases match task, decision and interval records, apart from explicitly added read-only decision diagnostics. Structure comparisons and target-window matched paths are supplied under `system_supplement_20261024/`.

These are preserved server-run results. The October 29 packaging check did not rerun the complete large matrices or re-download external datasets. Full raw-input replay still requires the files described in DATA.md. The original predictor and withdrawn-controller investigations are outside this manuscript package.

## Scope

Tests establish the listed invariants on the tested cases, not universal model validity. The study uses measured task records within constructed streams and deployments and fixed-commitment DC dispatch. Min/max seed ranges describe controller variation for fixed workloads. Negative and unchanged paired outcomes are retained. The completion-price and zero-communication arms are mechanism ablations of the same rule, not a complete classical scheduler.

Historical package checks are retained in `legacy_20261022/VALIDATION.md`.
