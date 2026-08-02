# P1 compute-only amendment v2 — FROZEN

Status: **OUTCOME-BLIND ENGINEERING AMENDMENT BEFORE ANY 8200–8239 OUTCOME**  
Date: 2026-08-01 (Asia/Shanghai)

## Scope

This amendment changes only orchestration limits. It does not change any task,
split, seed, model, hyperparameter, endpoint, contrast, direction, exclusion,
selection rule, multiplicity family, or aggregation rule in the frozen P1
protocol.

## Evidence and reason

The earlier two-worker projection exceeded the original 24 h wall-time gate.
Direct restartable production benchmarks on this host completed two small-task
development jobs in 10.10 s total and a mixed batch of 30 pending jobs spanning
the small and largest task in 284.03 s with four workers. The campaign writes
atomic state and Parquet checkpoints after every round. The user explicitly
authorized continued execution through ordinary wall-time overruns.

## Amended engineering policy

- Allow up to six CPU worker processes on the audited 12-core/24-thread host.
- Permit the development and confirmation dispatchers to continue beyond 24 h.
- Preserve identical-configuration retry (maximum two retries), checkpoint,
  resume, immutable job IDs, and complete-pair inference blocking.
- Continue to stop for scientific inconsistency, non-finite output, corrupted
  checkpoints, lock/hash mismatch, RAM exhaustion, or projected storage above
  100 GB.
- GPU remains neither required nor used.

No P1 confirmation result existed or was read when this amendment was frozen.
