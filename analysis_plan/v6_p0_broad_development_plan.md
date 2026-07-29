# V6 P0 broad development plan

Evidence class: `V6-P0-BROAD-DEVELOPMENT`.

Scope: all four frozen Matbench tasks, IID-record and chemical-system group-disjoint splits, Random Forest and ExtraTrees-compatible (`extra_randomized_bagging`) ensembles, and seeds 6100--6109 only. This is development-only and excludes all confirmation seeds.

The manifest contains 16 environments × 10 seeds × 17 registered jobs = 2720 jobs. Eight calibration-only strategies are exact RAW-acquisition replays and declare their RAW dependency. Nine strategies are independent full trajectories because acquisition can change.

Matched-beta maps use leave-one-task-out source tasks, an environment-balanced median rule, four fixed stages, lexical deterministic reductions, and a fixed-beta missing-stage fallback. No simple-scaling method is selected by observed sentinel outcomes: identity is a negative control; residual-ratio is the candidate non-identity scalar baseline; NLL, power, isotonic, and conformal retain their prespecified roles.

Prospective manifest SHA-256: `b8d0eca1d3d0625203d04458fcd07232999ecadaa5ca94241292cd271e71b496`.
Prospective selection-rules SHA-256: `6c6de14f482184b1e5a8775889910537ee53f64843b838fddf156fd788bca2a4`.
