# V5-RC1 prospectively specified revision confirmation protocol

Status: frozen after development selection and before inspecting any
confirmation outcome.

## Cohort and geometry

Confirmation seeds are 5000--5039 and are paired across strategies within each
of 16 task × split × surrogate environments. Four Matbench tasks, IID-record
and chemical-system-OOD splits, Random Forest and ExtraTrees, campaign
geometry, stable-ID ties, and model settings match the reduced-development
specification. No development seed is an inferential replicate.

## Independently evolving confirmation trajectories

Every task includes:

1. Raw UCB beta 1.
2. Original Gaussian-global UCB beta 1.
3. Development-selected Gaussian-global UCB beta 0.5.
4. CS-DA-OOB-HIST, historical minimum OOB-tree threshold 3.
5. Development-selected CS-DA-OOB-PARSIMONIOUS-F1, minimum threshold 10.

The held-out log-KVRH policy additionally includes development-selected Raw
UCB beta 2. On the other three tasks the selected Raw policy is beta 1 and
therefore shares the original Raw trajectory.

GG-CALIBRATION-ONLY is derived diagnostically from Raw beta-1 trajectories and
does not receive an independent sequential run. GG-ACQUISITION-ONLY shares the
original GG beta-1 acquisition trajectory; its raw calibration diagnostics are
derived separately.

## Endpoints and direction

Historical L1 campaign MACE is the primary marginal predictive interval
calibration endpoint; lower is better. Primary L4 sequential value is
selectable-pool top-1% recall normalized AUC including the initial state;
higher is better. L2 replacement and L3 same-state immediate utility retain
their frozen definitions. Top-0.5%, 2%, and 5% recall nAUC, final recall,
enrichment, regret, CRPS, Gaussian NLL, signed coverage, and sharpness are
secondary.

The seed is the inferential unit. Candidates, checkpoints, batches, and rounds
are repeated observations.

## Contrasts and inference

Paired effects, paired percentile-bootstrap 95% intervals, paired sign-flip
tests, valid-pair counts, and prospectively fixed multiplicity families are
reported within environment. Structural-identity contrasts are display-only
with p-values and adjusted values not applicable. Tasks are not pooled as an
independent population.

Primary contrasts include original GG beta 1 versus Raw beta 1, selected GG
versus the held-out-task selected Raw policy, CS-DA-OOB-HIST versus Raw beta 1,
and selected parsimonious candidate-specific versus the selected Raw policy.
Calibration-only versus Raw is structural identity for L2--L4.

## Failure, stopping, and immutability

All 40 paired seeds are required or explicitly excluded with reason. Jobs are
atomic and resumable; unchanged retries become `RECOVERED`. There is no
interim outcome-based stopping. No strategy may be added, removed, retuned, or
renamed after the first confirmation outcome is inspected. The base sigma
floor is `1e-8`; unresolved alternate-floor sensitivity cannot be described as
robustness evidence.

