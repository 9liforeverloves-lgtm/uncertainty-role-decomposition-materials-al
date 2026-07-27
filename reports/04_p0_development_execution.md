# P0 development execution

Status: **COMPLETED - development only**. The locked manifest `d862b85f615b8d4525d9d580f00490b1d869adc097c96ac32ea5cae0f9e7b1fc` planned 360 jobs and the final registry records 360 completed, 0 failed, and 0 excluded jobs.

- Final execution root: `results/v6_development/recovered_base_then_matched_beta_retry`
- Required final snapshot: `results/v6_development/registry_snapshot.csv`
- Environments: IID-record and chemical-system-OOD `matbench_expt_gap`, Random Forest only.
- Seeds: the registered ten development seeds only.
- No confirmation manifest was created and no confirmation job was run.

## Recovery audit

Three pre-final canary runs exposed deterministic engineering defects before a final result was accepted: a negative SeedSequence round key, calibration-only strategies inheriting a scaled acquisition map, and omitted matched-beta identity dispatch. Their registries and superseded locks remain on disk. The final run used verified recovery: all 300 completed base artifacts from `rerun_after_simple_scaler_mapping_fix` had matching registry and trace hashes before copying into the final run ledger; only the 60 matched-beta paths were recomputed.

- Source recovery-run registry counts: `{'COMPLETED': 309, 'FAILED': 16, 'PLANNED': 34, 'RUNNING': 1}`
- Final registry counts: `{'COMPLETED': 360}`

This is an execution/recovery record, not inferential evidence.
