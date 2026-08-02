# P1 execution provenance

The immutable manifest contains 3,520 completed jobs. Execution began at `2026-08-01T11:45:33.733115Z` and ended at `2026-08-01T20:51:14.238681Z`, an elapsed wall time of 9.094584879 h. The run used one audited 12-core/24-thread, 31.2-GiB host, with maximum inferred concurrency six and no GPU. There were zero failed-job and zero retry markers. Durable output occupied 68.592643496 GiB.

The sum of per-job process wall times was 53.650284476 job-hours. This is concurrency-weighted wall time, not measured CPU time. CPU-hours, peak resident memory and peak temporary-disk use were not instrumented and are not estimated.

The outcome-blind compute-only amendment was timestamped `2026-08-01T18:30:00+08:00`, before any confirmation outcome. It changed scheduling/resource limits only; it did not change seeds, strategies, contrasts, endpoints, directions, models, hyperparameters or multiplicity families.

Machine-readable sources:

- `tables/p1_confirmation_execution_provenance.csv`
- `tables/p1_compute_provenance_summary.csv`
- `manifests/p1_confirmation_manifest.csv`
- `locks/p1_confirmation_manifest_lock.json`
- `analysis_plan/p1_compute_amendment_v2_FROZEN.md`
- `locks/p1_extension_protocol_lock.json`

The missing telemetry is documented in `reports/compute_gate_provenance_gap.md`.
