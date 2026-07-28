# P0 development execution

Status: **V6-P0-SENTINEL-DEVELOPMENT, completed development-only**. The locked manifest `d862b85f615b8d4525d9d580f00490b1d869adc097c96ac32ea5cae0f9e7b1fc` planned 360 jobs and the final registry records 360 completed, 0 failed, and 0 excluded jobs.

- Final execution root: `results/v6_development/recovered_base_then_matched_beta_retry`
- Required final snapshot: `results/v6_development/registry_snapshot.csv`
- Scope: `matbench_expt_gap` only; IID-record and chemical-system group-disjoint splits; Random Forest only.
- Seeds: 6000–6009 only.
- Inferential status: development-only and non-confirmatory; this sentinel cohort is not transferable to all 16 V5 environments.
- The accepted DRAFT remains unchanged at `analysis_plan/v6_selection_map_SENTINEL_DRAFT.json`; it is not a confirmation selection map.
- No confirmation manifest was created and no confirmation job was run.

## Recovery audit

Five superseded prospective locks recorded deterministic engineering defects or a recovery transition before the final executed development lock was accepted: a negative SeedSequence round key, calibration-only acquisition-map mismatches, omitted matched-beta identity dispatch, and the final verified-recovery handoff. Their registries and lock lineage remain on disk. The final run used verified recovery: all 300 completed base artifacts from `rerun_after_simple_scaler_mapping_fix` had matching registry and trace hashes before copying into the final run ledger; only the 60 matched-beta paths were recomputed.

- Source recovery-run registry counts: `{'COMPLETED': 309, 'FAILED': 16, 'PLANNED': 34, 'RUNNING': 1}`
- Final registry counts: `{'COMPLETED': 360}`

This is an execution/recovery record, not inferential evidence.
