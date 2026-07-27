# Stage-2 smoke validation

Status: **PASS**

Label: **NON-INFERENTIAL ENGINEERING VALIDATION**

No V6 development or confirmation campaign was run.

## Test results

- Cross-revision/V5 tests: 11 collected.
- V6 unit and end-to-end tests: 48 collected.
- Combined clean-environment result: **59 passed, 0 failed, 0 skipped**.
- V5 authority/table/registry regression subset: **5 passed**.
- End-to-end identity test environments: deterministic synthetic and reduced
  `matbench_expt_gap`.

## Runtime smoke campaigns

Manifest: `configs/smoke/v6_smoke_manifest.json`

- Synthetic campaign seed: 91000.
- Reduced real-task campaign seed: 91001.
- Strategies per environment: `RAW`, `GG_CALIBRATION_ONLY`,
  `GG_NORMALIZED_ACQUISITION`, `CS_CALIBRATION_ONLY`.
- Jobs: 8.
- Completed: 8.
- Failed: 0.
- Identity audit: 150/150 exact checks passed.

Exact identity covered initial labels, round scores, stable ordering, selected
batches, queried path, retraining IDs, round count, recall trajectory and L4.
Evaluation sigma was allowed to differ where prescribed.

## Engineering-only smoke summaries

These values only verify pipeline execution. They are not scientific evidence.

- Synthetic RAW: 4 rounds; L4 smoke value 0.375.
- Reduced `matbench_expt_gap` RAW: 4 rounds; L4 smoke value 0.625.
- All three calibration-only/normalized identity controls exactly reproduced
  the corresponding RAW discovery path and L4 within each smoke environment.

## Clean installation

- New environment: `.venv_stage2_clean`.
- Python: 3.12.13.
- Installation: `requirements.txt`, then editable root package.
- `pip check`: no broken requirements.
- Console entry point: `transportability-v6`.
- Clean-environment tests: 59/59 passed.
- Clean-environment smoke: 8/8 jobs completed.

## PDF/build sanity

Stage-2 did not modify manuscript or figure sources. Stage-1 isolated rebuild
remains valid: main 9 pages and supplement 14 pages, with identical extracted
text hashes to the current PDFs. No manuscript result uses smoke output.

## Artifacts

- `results/v6_smoke/smoke_registry.csv`
- `results/v6_smoke/smoke_run.log`
- `results/v6_smoke/smoke_identity_audit.json`
- `results/v6_smoke/smoke_result_manifest.json`
- eight compact per-strategy JSON results

## Failures and blockers

- Final Stage-2 suite: no failed tests.
- During implementation, one optimizer-fallback exact-equality test initially
  failed by `5.55e-17`; the fallback now returns the raw vector exactly.
- Historical V5 suite still contains two stale traceability-ID assertions
  identified in Stage 1. V5 evidence hashes remain valid; these tests were not
  rewritten because V5 is immutable.
- V6 development/confirmation remains blocked pending explicit user approval.
