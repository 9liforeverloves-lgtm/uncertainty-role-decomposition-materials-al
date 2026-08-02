# Data reproduction

The release candidate does not redistribute the four local Matbench snapshots. External users retrieve official upstream objects, accept applicable terms, verify upstream SHA-256 values, and generate composition-only `material_id,formula,target` files outside the repository.

```bash
python scripts/fetch_matbench_data.py --task matbench_expt_gap --output-dir ../study-data
python scripts/fetch_matbench_data.py --task matbench_expt_gap --output-dir ../study-data --verify-only
```

The script refuses a checksum mismatch and never overwrites a mismatching file. Structural tasks require the locked pymatgen dependency to derive reduced formulae. Stable IDs preserve upstream row order as `MB-000001`, etc. No original Matbench folds are used; the paper's IID-record and chemical-system group-disjoint protocols are study-defined and bound in per-job state hashes.

See `data_manifest/upstream_sources.yaml`, `data_manifest/task_snapshots.csv`, `data_manifest/file_checksums.csv` and `reports/THIRD_PARTY_DATA_RIGHTS_MATRIX.md` for versions, checksums, citations and rights status. The synthetic file `tests/fixtures/tiny_materials.csv` is unrestricted test data and must never be used for scientific inference.

