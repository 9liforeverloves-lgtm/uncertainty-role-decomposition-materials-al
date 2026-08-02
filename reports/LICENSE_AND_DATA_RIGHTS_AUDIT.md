# License and data-rights audit

Status: **PASS for the authorized release-candidate scope**. This is an engineering audit, not legal advice.

## Project authorization

The author authorized BSD-3-Clause for original project software on 2026-08-02. The root `LICENSE` carries `Copyright (c) 2026 Renjie Li`. The formerly open decision files are preserved as resolved records under `reports/archive/`. `release_config/author_release_decisions.yaml` authorizes public code and the enumerated original processed outputs, while explicitly prohibiting raw-data redistribution.

## Dependency code

All 47 distributions pinned in `requirements-lock.txt` resolve to exact installed metadata and retained upstream license-file evidence; unresolved count is zero. The authoritative package/version/license/source/notice matrix is `reports/LICENSE_COMPATIBILITY_MATRIX.md` and its CSV source is `tables/release_audit/dependency_license_inventory.csv`. Dependencies are not vendored and are not relicensed by BSD-3-Clause.

## Data and outputs

Raw Matbench snapshots, Materials Project records and other third-party raw data are excluded. `data_manifest/upstream_sources.yaml` records official URLs, upstream hashes and snapshot metadata; `scripts/fetch_matbench_data.py` verifies checksums before deterministic conversion and refuses mismatches/unsafe overwrite. The author-authorized release scope is limited to original authority tables, locks, protocols, manifests, split manifests, machine-readable effects, figure-source inventories, generated tables/figures/manuscripts, reproduction scripts, tests and synthetic fixtures.

The detailed task-by-task upstream rights and attribution assessment remains `reports/THIRD_PARTY_DATA_RIGHTS_MATRIX.md`. Matbench software licensing does not automatically relicense each task dataset, and Materials Project-derived records retain upstream attribution/version requirements.

Conclusion: BSD-3-Clause is compatible with the audited original-code release; it does not relicense third-party software or raw data.
