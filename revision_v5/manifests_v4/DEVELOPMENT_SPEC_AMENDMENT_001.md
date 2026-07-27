# Development specification amendment 001

Status: **FROZEN BEFORE ANY V5 CANDIDATE-SPECIFIC DEVELOPMENT JOB**

## Reason

The historical candidate-specific function reads `min_oob_trees_per_sample` from the `candidate_specific` subconfiguration and otherwise defaults to 3. The frozen V2 protocol stored the intended value 10 under the separate `oob` subconfiguration, so the historical runner did not propagate it. The Review 4.3 Supplement described 10, while the executed historical code used 3.

## Prospective V5 decision

The V5 runner explicitly copies `oob.min_oob_trees_per_sample = 10` into the candidate-specific configuration. All V5 candidate-specific variants therefore require at least 10 OOB trees per scale-fitting case.

## Boundary

- Historical V2/V3 trajectories and their interpretation are not changed.
- No V5 candidate-specific development job had been executed when this amendment was written.
- The two completed V5 development canary jobs were Raw UCB and Gaussian-global calibration-only and do not call the candidate-specific fitter.
- The amendment is implementation-correctness work, not outcome-driven tuning.

