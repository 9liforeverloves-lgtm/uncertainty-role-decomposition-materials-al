# Stage-2 test-gap audit

## Closed gaps

- Exact end-to-end RAW path identity on synthetic and reduced real data.
- Equal-mean, equal-sigma, equal-score and stable-ID tie behavior.
- Duplicate stable/material/diagnostic ID rejection.
- Selected-CS nominal 2-parameter and Historical-CS nominal 7-parameter controls.
- OOB-only fitting API, deterministic fitting and insufficient-OOB fallback.
- V5, V6-confirmation and smoke seed rejection for matched-beta fitting.
- Exact stage boundaries at 0.25, 0.50, 0.75 and 1.00.
- Missing-stage fixed-beta fallback and selection-map mutation detection.
- Reversed/partial/tied/small-pool ranking behavior and nonfinite rejection.
- NLL overflow protection, nonfinite rejection and distinct floor flags.
- Observation and seed dominance, trimmed-direction and leave-one-environment-out gates.
- Parquet round trip, interrupted-write recovery and duplicate-row rejection.
- Constant residual/sigma, duplicate-sigma isotonic behavior, optimizer failure
  and transform-bound tests.
- Prospective registry coverage and smoke seed/label validation.

## Remaining gaps before development

- Full V6 job registry concurrency and restart testing.
- Crash injection during model checkpoint persistence.
- Large-pool memory and disk stress tests.
- Cross-platform Linux container validation.
- Exact reproduction tests for future non-tree and non-UCB implementations.
- External-dataset checksum/download failure tests.
- Statistical bootstrap/sign-flip implementation tests; only seeds and rules
  are currently registered.

## Remaining gaps before confirmation

- Frozen selection-map content produced from completed development.
- Confirmatory manifest hash and code-tree hash.
- Required 40-pair completeness gate.
- Family-member freeze for development-selected simple baselines.
- Prespecified noninferiority margin for H6, or reclassification of H6.
- P1 model, acquisition and external-dataset family membership.

These gaps block development/confirmation claims, not Stage-2 smoke acceptance.
