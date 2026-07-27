# Data dictionary

- `source`: labels available for initial training.
- `calibration_role`: source/OOB record eligible for uncertainty mapping fit.
- `selectable_role`: finite-pool candidate eligible for acquisition.
- `diagnostic_role`: held-out record used only for evaluation.
- `target_revealed`: whether the target was legitimately observed at that round.
- `raw_sigma`: pre-scaling predictive ensemble standard deviation.
- `scaled_sigma`: uncertainty used for the named evaluation mapping.
- `effective_beta`: acquisition beta multiplied by acquisition scale.
- `stable_rank`: deterministic descending-score rank with ascending stable ID ties.
- `L1`: campaign-average mean absolute coverage error.
- `L4`: top-1% recall normalized area under the budget-fraction curve.
