# Verification During Packaging

- Numerical suite: 18 tests passed.
- Engineering suite: 15 tests passed.
- Event audit suite: 10 tests passed.
- Event tests were rerun outside the filesystem sandbox because temporary-directory access was denied inside it.

These 43 tests validate core mechanisms and existing regression checks. They do not constitute a fresh replay of all 270 engineering runs. Raw PM100 and grid inputs and full historical trajectories were not available in this checkout. The newly added portable preparation and full-matrix wrappers have not been validated by a complete real-data replay.

Published summary CSVs retain 45 numerical scenarios, 270 engineering runs and 135 paired comparisons. Plot exports are supplied alongside their available source data.

Packaging checks: all 27 Python files passed syntax parsing. CSV row counts were verified (45 / 270 / 135). Numerical preflight passed for 45 scenarios; the maximum same-assumption parent derivative difference was 5.551115123125783e-17.
