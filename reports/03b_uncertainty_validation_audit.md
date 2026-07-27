# Uncertainty validation audit

Status: **PASS**. Calibration, strategy scoring, records, and NLL diagnostics reject negative, NaN, and infinite uncertainty; record finite sub-floor values as explicit floor events; reject nonpositive scales, malformed beta, duplicate IDs, invalid reveal states, invalid stable-rank permutations, and invalid role membership.

NLL summaries now report raw sigma and post-floor effective sigma quantiles separately. `nll_stability_gate` combines finite-NLL, floor-rate, observation-dominance, seed-dominance, trimmed-direction, and leave-one-environment-out conditions into one auditable result.
