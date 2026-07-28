# P0 development supersession audit

This audit reconstructs the six-lock chain for `V6-P0-SENTINEL-DEVELOPMENT`. The five earlier records are described as superseded prospective locks; the sixth is the final executed development lock. The accepted scope remains matbench_expt_gap only, IID and chemical-system group-disjoint splits, Random Forest, and seeds 6000-6009. It is development-only and non-confirmatory.

## Outcome-blindness conclusion

All six records carry the same manifest SHA-256 (`d862b85f615b8d4525d9d580f00490b1d869adc097c96ac32ea5cae0f9e7b1fc`). Supersessions fixed engineering assertions or reused hash-verified base artifacts; they did not change the registered method list or select a method based on observed endpoints. Where a run reached the predeclared beta calculation, its use was programmatic; no earlier human outcome-view event is recorded.

## Lock sequence

| # | record | lock hash | run | registry counts | endpoints computed / viewed |
| --- | --- | --- | --- | --- | --- |
| 1 | superseded prospective lock | `a3bef9c4b87d` | `initial_p0_execution` | FAILED=60, PLANNED=299, RUNNING=1 | False / False |
| 2 | superseded prospective lock | `ef0607d55cd9` | `rerun_after_seedsequence_fix` | COMPLETED=124, FAILED=52, PLANNED=183, RUNNING=1 | True / False |
| 3 | superseded prospective lock | `a4fb9cfa0aa8` | `rerun_after_calibration_mapping_fix` | COMPLETED=128, FAILED=28, PLANNED=203, RUNNING=1 | True / False |
| 4 | superseded prospective lock | `a9c4b568069d` | `rerun_after_simple_scaler_mapping_fix` | COMPLETED=309, FAILED=16, PLANNED=34, RUNNING=1 | True / False |
| 5 | superseded prospective lock | `3ae582ce4b8a` | `rerun_after_matched_beta_fix` | not started | False / False |
| 6 | final executed development lock | `4213e6a702b8` | `recovered_base_then_matched_beta_retry` | COMPLETED=360 | True / True |

## Engineering assertions and artifact treatment

### 1. superseded prospective lock

- Lock: `locks/v6_p0_development_manifest_lock_superseded_a3bef9c4b87d.json` (`a3bef9c4b87df895ee511b0a3bf9c1ea8834ee5fb5b556a3cd26a5b81d6f7164`).
- Git commit / code tree: `fa4ec4888fdaf4c24dc99e5386f12d6a3a7d6693` / `0e7cf14f0653245bf1b32868efa4301ccf038233ed2690d80ce36363678e16e9`.
- Supersession basis: Recorded P0 canary failure: V6 initial model SeedSequence used negative round key; corrected to canonical round-0 key before any model checkpoint write.
- Failed engineering assertion: Initial model construction supplied a negative SeedSequence round key before any durable checkpoint write.
- Outcome audit: computed=False; viewed=False. No completed jobs and no P0 selection-map write were produced by this run.
- Reused: none.
- Recomputed: none.

### 2. superseded prospective lock

- Lock: `locks/v6_p0_development_manifest_lock_superseded_ef0607d55cd9.json` (`ef0607d55cd9f326abed7165f1c7ce1a681540b1a248e5c4f17353c23e1a0866`).
- Git commit / code tree: `eba8d544bf84cdd01066d323662739155ed55e39` / `fdf751726c8eb0e2f29bc301be508154488a21a315e2a9d61aa4fedea430fdb9`.
- Supersession basis: Recorded P0 calibration-replay failure: equivalent-DoF controls were registered calibration-only but their production acquisition map was scaled_sigma; corrected to exact RAW acquisition before execution.
- Failed engineering assertion: Equivalent-DoF calibration-only controls were registered with scaled acquisition rather than exact RAW acquisition.
- Outcome audit: computed=True; viewed=False. The base phase failed before the predeclared beta-selection routine was reached; no selection-map write is attributable to this run.
- Reused: none.
- Recomputed: 124 completed job artifact directories recorded in rerun_after_seedsequence_fix.

### 3. superseded prospective lock

- Lock: `locks/v6_p0_development_manifest_lock_superseded_a4fb9cfa0aa8.json` (`a4fb9cfa0aa848975329f83f5560e10c89586c434c019da2e93a03ba4c3354dd`).
- Git commit / code tree: `287c8bccb7f354d75d56fbef89dc5f7b61b6d29b` / `09a64f0eadf0b40f458a6c7c08965c07d5a1266454ba3d35dc3bccdbec5467bd`.
- Supersession basis: Recorded P0 calibration-replay failure: simple scalers in the calibration-only manifest inherited scaled_sigma acquisition; all calibration replay specifications now explicitly use exact RAW acquisition.
- Failed engineering assertion: Simple scalar calibration replays inherited scaled acquisition rather than exact RAW acquisition.
- Outcome audit: computed=True; viewed=False. The base phase failed before the predeclared beta-selection routine was reached; no selection-map write is attributable to this run.
- Reused: none.
- Recomputed: 128 completed job artifact directories recorded in rerun_after_calibration_mapping_fix.

### 4. superseded prospective lock

- Lock: `locks/v6_p0_development_manifest_lock_superseded_a9c4b568069d.json` (`a9c4b568069d27799f70cd3882990cc22c8b6bc7029ced4a911a69f1f9c29e4d`).
- Git commit / code tree: `c35ada9c895b818e2a95b09a4647f3e1bf7159c2` / `f45c7f9f5fdf3d8f3f6abb3648799902cc9570b300344d6ade320e89f183ed24`.
- Supersession basis: Recorded P0 post-selection failure: RAW_FIXED_BETA_MATCHED and RAW_STAGE_BETA_MATCHED were registered but omitted from the production identity-scale dispatch; added explicit RAW identity dispatch.
- Failed engineering assertion: RAW_FIXED_BETA_MATCHED and RAW_STAGE_BETA_MATCHED were registered but absent from the production identity-scale dispatch.
- Outcome audit: computed=True; viewed=False. The predeclared routine programmatically formed a DRAFT beta map after the base phase; no human outcome-view event is recorded, and the method list/rule was not altered.
- Reused: none.
- Recomputed: 309 completed job artifacts recorded in rerun_after_simple_scaler_mapping_fix.

### 5. superseded prospective lock

- Lock: `locks/v6_p0_development_manifest_lock_superseded_3ae582ce4b8a.json` (`3ae582ce4b8ae249a949c457c30dfaefe5b9c713c5cd606d2f8a21073e0e9ed2`).
- Git commit / code tree: `c096a454a5ea3029fbdaba3057f9ce38c56b49d6` / `9dc9f9b995678f847bc710dd79c2ecbb02a29c381d86d1fe31df9f308ed96b55`.
- Supersession basis: Verified recovery: 300 completed base P0 artifacts from rerun_after_simple_scaler_mapping_fix have matching registry and trajectory hashes; reuse them unchanged and rerun only the matched-beta post-selection jobs after dispatch fix.
- Failed engineering assertion: No execution was started under this prospective lock; the dispatch correction was replaced by a verified-artifact recovery protocol.
- Outcome audit: computed=False; viewed=False. No run directory exists for rerun_after_matched_beta_fix.
- Reused: none.
- Recomputed: none.

### 6. final executed development lock

- Lock: `locks/v6_p0_development_manifest_lock.json` (`4213e6a702b8e90f78c247296a42c2e4950eec590a8e34832a0d05cfdc11b973`).
- Git commit / code tree: `ade26c790d9cc9a675424fc838e7cfecc4549325` / `3295b351fc74b4df63a5ae3b43d9e41cbf51139b7c45a4e073edd1c0bd489ae0`.
- Supersession basis: Accepted final execution after hash-verified recovery of 300 base artifacts and recomputation of 60 post-selection paths.
- Failed engineering assertion: None; this is the final executed development lock.
- Outcome audit: computed=True; viewed=True. The accepted DRAFT and execution report were generated only after the 360-job registry completed.
- Reused: 300 verified base artifacts from rerun_after_simple_scaler_mapping_fix.
- Recomputed: 60 matched-beta post-selection artifacts under recovered_base_then_matched_beta_retry.

## Lineage integrity

The machine-readable lineage record has SHA-256 `c5bc32d0ee406977dac1a9f7e79bc587ef2e45cfc75a02fe9b6859eed7a0a1ad`. It preserves the original lock hashes as identifiers without recasting superseded records as final evidence.
