# Packaging provenance

`source_manifest.json` maps original project-relative source paths to packaged files and records both hashes. Matching hashes indicate byte-for-byte copies. Different hashes may reflect extraction of reusable functions, removal of server deployment dependencies, portable paths, sanitized server path identifiers, or portable font setup.

The numerical solver, event simulation and cost-update/choice equations were retained. The numerical final integrity check had a stale hard-coded snapshot count of 405; it now checks scenario count × configured snapshot times (360 for the supplied protocol).

The engineering package validates bundled parent files using `dual_lag_v1/SHA256SUMS`. This checks the packaged files, not the original remote release-manifest identity. Portable `engineering/run.py` and `prepare_data.py` were added for local use. Data preparation reuses the frozen calibration rather than re-running the original aggregation/refit pipeline.

Historical server deployment, SSH and credential-handling scripts are intentionally excluded. Absolute server identifiers in CSV provenance columns are replaced with logical `release://` identifiers. The manuscript source is maintained separately and was not changed by this packaging operation.

`package_manifest.json` inventories packaged deliverables, excluding generated runs, bytecode and the inventory itself.
