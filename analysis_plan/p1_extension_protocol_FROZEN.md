# Prespecified P1 extension protocol — FROZEN

Status: **FROZEN BEFORE ANY P1 CONFIRMATION OUTCOME**  
Freeze date: 2026-08-01 (Asia/Shanghai)  
Relationship to V6: independent extension; no pooled effects, shared multiplicity family, or confirmation-seed reuse.

## Scientific aim

Test whether the V6 role-decomposition conclusions transport to (i) direct exploration-pressure controls against RAW and (ii) a non-bagged-tree conditional-quantile uncertainty mechanism, while adding prespecified calibration/discovery diagnostics. P1 does not relabel or amend a V6 hypothesis.

## Evidence classes

1. `P1_SENTINEL_IMPLEMENTATION_VALIDATION`: seeds 8000–8004; reduced jobs; no inference.
2. `P1_DEVELOPMENT_EXPLORATORY`: seeds 8100–8109; hyperparameter feasibility, one-factor-at-a-time sensitivity, and cost measurement; never confirmatory.
3. `P1_INDEPENDENT_CONFIRMATION`: seeds 8200–8239; untouched until the code, endpoints, contrasts, exclusions, model parameters, job manifest, and compute gate are frozen.

## Environments and representation

- Tasks: `matbench_expt_gap`, `matbench_mp_gap`, `matbench_log_gvrh`, `matbench_log_kvrh`.
- Splits: study-defined `iid_record` and `chemical_system_ood`.
- Existing matched-beta/constant-beta contrasts: Random Forest and ExtraTrees, with their frozen shared V6 hyperparameters.
- New UQ family: one histogram-free gradient-boosted quantile interval model per task/split; composition representation identical to V6.
- Crystal-structure features are excluded from the confirmatory core. Any later structure experiment is exploratory and requires consistent source structures.

## Frozen new-model definition

The new model is `QUANTILE_GRADIENT_BOOSTING` using scikit-learn `GradientBoostingRegressor`, a sequential boosting mechanism rather than a bagged-tree ensemble. Three regressors share `n_estimators=200`, `learning_rate=0.05`, `max_depth=3`, `min_samples_leaf=5`, `subsample=1.0`, and the same deterministic seed. The central predictor uses squared-error loss. Quantile regressors use alpha 0.16 and 0.84. Predictive uncertainty is

`sigma_q(x) = max((q_0.84(x)-q_0.16(x))/(2*Phi^{-1}(0.84)), 1e-8)`.

Quantile crossing is recorded and corrected only by the positive floor; it is a failure if non-finite. This width is a conditional predictive-spread proxy. It is not labelled epistemic uncertainty and is not decomposed into aleatoric/epistemic components.

All acquisition strategies using this surrogate share identical model parameters. No strategy-specific surrogate tuning is permitted.

## Frozen acquisition/mapping definitions

- `P1_QGB_RAW`: central mean plus `beta=1` times raw `sigma_q`; raw interval evaluation.
- `P1_QGB_CALIBRATION_ONLY_RR`: acquisition identical to `P1_QGB_RAW`; at each step, a residual-ratio scalar fitted only from currently labelled development/cross-fit residuals transforms evaluation uncertainty.
- `P1_QGB_ACQUISITION_ONLY_RR`: residual-ratio-scaled `sigma_q` for acquisition; raw `sigma_q` for evaluation.
- Development-selected constant-beta UCB chooses from `{0,0.25,0.5,1,2,4}` using only seeds 8100–8109, leave-one-task-out, environment-balanced top-1% recall nAUC; ties use worst-environment value then smaller beta. The selected task-specific beta is frozen before confirmation.
- Existing task-specific fixed/stagewise matched-beta maps remain those frozen before V6; P1 does not refit them from V6 confirmation outcomes.

## Confirmatory endpoints and inference

- L1 campaign MACE at initial/25/50/75% checkpoints; lower is favorable.
- L4 top-1% recall nAUC including the initial state; higher is favorable.
- Effect is strategy minus baseline.
- Unit: paired P1 confirmation seed block. Within a seed, environments are averaged equally after all registered pairs pass completeness.
- 10,000 paired bootstrap resamples for 95% percentile intervals and 10,000 paired sign flips with add-one p-values.
- Benjamini–Hochberg correction is applied separately to the two P1 families in `p1_extension_contrasts_FROZEN.csv`. No P1 p-value enters a V6 family.
- Missing or failed environment pairs block pooled analysis. Retry uses the identical configuration, at most two automatic retries.

## Exploratory sensitivity and mechanism diagnostics

One-factor-at-a-time around the frozen baseline, development seeds only unless explicitly listed: beta `{0,0.25,0.5,1,2,4}`; query budget `{5%,10%,20%}`; initial fraction `{1%,5%,10%}`; batch `{single,1%,5%}`; target fraction `{1%,5%,10%}`; tree/boosting count `{80,200,500}` where applicable; uncertainty floor `{1e-10,1e-8,1e-6}`. All are labelled exploratory and cannot revise V6 conclusions or P1 confirmation choices.

## Frozen exclusions and gates

- Exclude a job only for non-finite inputs/outputs, invalid disjoint roles, missing required pair, corrupted checkpoint, or deterministic configuration/hash mismatch.
- Do not exclude an environment for poor performance, quantile width, sign, or outlier status.
- Before full confirmation, measure sentinel wall time and peak RAM; estimate CPU hours, peak RAM, disk, job count, and wall time.
- Stop after sentinel/development and emit a resumable manifest if projected wall time exceeds 24 h, temporary storage exceeds 100 GB, GPU is required but unavailable, or RAM exceeds the host.
- Checkpoint, resume, and identical-config retry are mandatory. Partial success is never pooled.

## Outcome-blind freeze rule

After any P1 confirmation outcome exists, endpoint definitions, directions, exclusions, model parameters, contrasts, environments, selection rules, and multiplicity families above cannot change. Amendments require a new version, reason, timestamp, and explicit separation from this protocol; they cannot retroactively govern existing outcomes.

