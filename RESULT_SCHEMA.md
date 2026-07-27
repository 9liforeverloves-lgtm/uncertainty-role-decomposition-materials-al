# V6 result schema

## Full-pool round records

Required fields:

`task`, `split`, `model`, `seed`, `strategy`, `round`, `budget_fraction`,
`candidate_id`, `predictive_mean`, `raw_sigma`, `scaled_sigma`, `scale_factor`,
`raw_beta`, `effective_beta`, `acquisition_score`, `stable_rank`, `queried`,
`target`, `target_revealed`, `calibration_role`, `selectable_role`,
`diagnostic_role`.

Unrevealed targets must be missing. Roles must not overlap.

## Individual NLL vectors

Required fields:

`candidate_id`, `task`, `split`, `model`, `seed`, `strategy`, `round`,
`environment`, `y`, `mu`, `sigma_raw`, `sigma_scaled`,
`uncertainty_floor_before`, `uncertainty_floor_after`,
`standardized_residual`, `gaussian_log_term`,
`gaussian_squared_residual_term`, `individual_nll`.

Storage: Zstandard-compressed Parquet with atomic replacement.
