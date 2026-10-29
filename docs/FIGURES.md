# Current Manuscript Figures

Approved exports in `paper/current/figures/` match the October 29 manuscript.

| Figure | Export Stem | Renderer / Evidence |
| --- | --- | --- |
| 1 | systems/fig_system_architecture | Approved PDF/SVG supplied; no standalone generator claimed |
| 2 | redesigned/fig02_cost_formation | make_controlled_cost_figure.py; both frozen short/long trajectories |
| 3 | systems/fig_joint_outcomes | make_joint_outcome_matrix.py; 27 paired results |
| 4 | systems/fig_site_constraints | make_site_bars.py; 108 site-level rows |
| 5 | systems/fig_joint_trajectory | make_joint_system_figures.py; interval traces and summary reconciliation |
| 6 | systems/fig_signal_consequences | make_signal_figure.py + design_signal_options.py; 39 pairs and temporal trace |
| 7 | systems/fig_same_stream_events | make_event_figure.py + design_figure7_options.py; matched successors |

Run `python scripts/render_current_figures.py`. It copies compact inputs and renderers into `runs/current_figures/`, creates output/QA directories and renders Figures 2–7. Approved exports are not overwritten. Alternate design functions remain in helper modules but are not called.

Times New Roman is retained for manuscript consistency. Without it, Matplotlib may substitute fonts and change wrapping. Proprietary fonts are not bundled. Approved PDF/SVG exports preserve the final appearance.

Current table fragments are in `paper/current/tables/main/` and `paper/current/tables/appendix/`. Data are in `paper/current/source_data/`, including the same-rule and structure paired CSVs. Table fragments retain manuscript references and are not standalone LaTeX documents. Legacy figure numbering is in `legacy_20261022/FIGURES.md`.
