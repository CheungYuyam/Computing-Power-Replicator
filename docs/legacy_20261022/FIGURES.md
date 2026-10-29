# Manuscript Figures

| Figure | Export Stem | Renderer |
| --- | --- | --- |
| 1 | fig01_framework | Final PDF supplied; current editable construction source not verified |
| 2 | fig_delay_changes | paper/plot_report_delay_changes.py |
| 3 | fig_initial_progress | paper/plot_initial_progress.py |
| 4 | fig_stage_count | paper/plot_stage_count.py |
| 5 | fig_cost_comparisons | paper/plot_remaining_results.py |
| 6 | fig02_cost_formation | figure_times_r1/redesign.py: macro_figure; paper/soften_cost_zero.py |
| 7 | fig03_engineering_paths | figure_times_r1/redesign.py: engineering; final export supplied |
| 8 | fig_response_all_seeds | paper/plot_remaining_results.py |
| 9 | fig05_event_chain | paper/plot_event_compact.py |
| 10 | fig_energy_all_seeds | paper/plot_energy_all_seeds.py |

Run standalone plotting scripts from the repository root. They write to `paper/figures/redesigned/`, replacing the corresponding packaged exports. Commit or copy an export before rerendering if its exact published appearance must be retained. `plot_remaining_results.py` also renders Figures 4, 8 and 10; run the dedicated Figure 4 renderer afterward.

Figures 2–5 and 8–10 use the bundled CSVs. Figures 6–7 require full trajectories absent from this checkout; the legacy shared renderer retains the original release-directory layout. It is supplied for traceability, not advertised as a turnkey reproduction command. Final layout refinements may differ from the older shared renderer. `restyle_vector_titles.py` is a historical Windows/Times New Roman postprocessor and expects the earlier figure set.

Times New Roman is used when installed; portable Matplotlib renderers fall back to Liberation Serif or DejaVu Serif. Proprietary font files are not distributed.
