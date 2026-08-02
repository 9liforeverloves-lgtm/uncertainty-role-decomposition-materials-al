# P1 extension compute amendment v1 — FROZEN

Status: **OUTCOME-BLIND ENGINEERING AMENDMENT BEFORE ANY 8200–8239 OUTCOME**  
Created: 2026-08-01T18:30:00+08:00  
Baseline Git commit: `8553ccff60c1a691f81913edfad4e64d297d3486`

## Reason and measured benchmark

The original gate stopped confirmation when projected wall time exceeded 24 h.
The frozen candidate estimate was 96–110 CPU-hours and 48–55 wall-hours at
two workers. Direct restartable production benchmarks on the audited host
completed two small-task development jobs in 10.10 s total and a mixed batch
of 30 pending jobs spanning small and largest tasks in 284.03 s at four
workers. Ordinary wall time was explicitly authorized by the user and all
jobs provide atomic round-level checkpoint/resume.

## Old gate

- Two workers.
- Stop before confirmation if projected wall time exceeds 24 h.
- Stop above 100 GB temporary storage, if GPU is required but absent, or if
  projected RAM exceeds the host.

## New gate

- Up to six CPU worker processes on one audited 12-core/24-thread node.
- Wall time may exceed 24 h; the dispatcher continues until all registered
  jobs complete or a scientific/integrity blocker occurs.
- Identical-configuration retry remains capped at two retries per job.
- Atomic checkpoint, resume, immutable job ID, hash verification and full-pair
  completeness blocking remain mandatory.
- The 100 GB storage gate, host-RAM gate and CPU-only implementation remain.

## Scientific invariance

This amendment changes only worker count, permitted wall time and scheduling.
It changes no seed, task, split, strategy, model, hyperparameter, endpoint,
direction, contrast, multiplicity family, exclusion, aggregation or inference
method. No P1 confirmation output existed or was read before this amendment.
