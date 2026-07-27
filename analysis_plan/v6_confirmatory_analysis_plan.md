# V6 confirmatory analysis plan

Status: prospective draft; no V6 confirmation outcomes exist.

## Evidence separation

V5-RC1 remains immutable and is not pooled with V6. New records use:

- `V6-MECH`: decoupling, beta matching, ranking and path mechanisms;
- `V6-EXT`: non-tree, non-UCB and external-dataset validation;
- `V6-SENS`: OOD and campaign-geometry sensitivity;
- `V6-REP`: raw-vector, NLL and reproducibility diagnostics.

## Units of analysis

1. Run-level Monte Carlo stability: paired seeds within one environment.
2. Environment-level robustness: descriptive consistency across task × split × model.
3. Task-level external generalization: descriptive summaries across tasks; `n_task` is small.

Seeds are not independent materials problems. Environment counts are not pooled as independent
replicates.

## Cohorts

- Development: seeds 6000–6009, subject to collision audit.
- Confirmation: seeds 7000–7039, subject to collision audit.
- Hyperparameters, fixed beta and stagewise beta are selected from development only.
- The selection map and its hash must be frozen before confirmation outcomes are read.
- Matched-beta fitting rejects V5 seeds 5000–5039 and confirmation seeds 7000–7039.
- Stage intervals are `[0.00,0.25)`, `[0.25,0.50)`, `[0.50,0.75)`, and
  `[0.75,1.00]`. Thus 0.25, 0.50 and 0.75 enter the later stage; 1.00 enters
  the final stage.
- A development stage with no observations uses the already frozen fixed
  environment-balanced matched beta and is flagged `missing_stage_fallback`.

## Primary endpoints

- L1: campaign-average MACE using the frozen nominal coverage/checkpoint definition.
- L4: top-1% recall nAUC using the frozen budget-fraction definition.

## Secondary endpoints

- top-tail count at fixed budgets;
- full- and retained-pool Spearman agreement;
- Kendall tau, top-k overlap and batch Jaccard;
- first divergence round and cumulative path divergence;
- calibration slope/intercept when identifiable;
- CRPS;
- NLL only when the stability gate below passes.

## Paired inference

Within each environment and prespecified contrast:

- paired seedwise effect;
- mean paired effect as primary location estimate;
- 95% paired bootstrap interval;
- paired sign-flip randomization p value;
- exact raw p value and BH-adjusted p value within the registered family.

Effect size and interval are primary. Evidence labels do not replace estimates.

Bootstrap RNG seed is 610001. Sign-flip RNG seed is 610002. Each environment,
contrast and endpoint derives a deterministic child seed from the SHA-256 of
`family|environment|contrast|endpoint`; no outcome-dependent reseeding is allowed.

## NLL stability gate

NLL is scientifically interpretable only when all conditions hold:

1. all individual NLL values are finite;
2. fraction at the uncertainty floor is at most 1%;
3. no single observation contributes more than 10% of total absolute NLL;
4. no single seed contributes more than 20% of total absolute NLL;
5. the mean contrast direction agrees with the 1% trimmed-mean descriptive contrast;
6. results are not driven by one task/environment under leave-one-environment-out diagnostics.

Failure yields `numerically_unstable_descriptive_only`; it does not delete the endpoint.

## Authority-count reconciliation

The initial Stage-1 script enumerated 17 compact authority files. The later
complete check added `revision_v5/results_v4/confirmation/registry.sqlite`,
whose frozen SHA-256 is
`6a67a54589b809f46883423070c1e8b37599bb49fac0e0f79a58bec65f590dc4`.
Therefore 17 means the original compact-file list; 18 means the same list plus
the authoritative SQLite registry. No V5 file changed.

## Missing and failed jobs

No silent deletion or replacement. Unchanged retries are allowed. Confirmation inference requires
the registered paired seed set or a versioned exclusion/sensitivity analysis with exact reasons.

## Interpretation bounds

Claims are restricted to tested offline composition-based screening environments. Calibration-only
effects support interval interpretation. Acquisition-only effects support decision-path
interpretation. Candidate-specific results do not generalize to candidate-specific scaling as a
class without corroborating ablations.
