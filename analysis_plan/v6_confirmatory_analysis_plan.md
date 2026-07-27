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

## NLL stability gate

NLL is scientifically interpretable only when all conditions hold:

1. all individual NLL values are finite;
2. fraction at the uncertainty floor is at most 1%;
3. no single observation contributes more than 10% of total absolute NLL;
4. no single seed contributes more than 20% of total absolute NLL;
5. the mean contrast direction agrees with the 1% trimmed-mean descriptive contrast;
6. results are not driven by one task/environment under leave-one-environment-out diagnostics.

Failure yields `numerically_unstable_descriptive_only`; it does not delete the endpoint.

## Missing and failed jobs

No silent deletion or replacement. Unchanged retries are allowed. Confirmation inference requires
the registered paired seed set or a versioned exclusion/sensitivity analysis with exact reasons.

## Interpretation bounds

Claims are restricted to tested offline composition-based screening environments. Calibration-only
effects support interval interpretation. Acquisition-only effects support decision-path
interpretation. Candidate-specific results do not generalize to candidate-specific scaling as a
class without corroborating ablations.
