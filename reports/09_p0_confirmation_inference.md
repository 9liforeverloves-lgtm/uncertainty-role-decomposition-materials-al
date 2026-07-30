# V6 P0 frozen confirmation inference

Status: **FROZEN INFERENTIAL ANALYSIS COMPLETE AND LOCK-READY**

The independent paired unit for pooled inference is the registered seed. For each seed, the paired strategy-minus-baseline effect is averaged equally over all 16 task x split x model environments before the registered paired bootstrap and sign-flip procedures are applied (40 paired seed blocks). Environment, task, split, and model results are prespecified heterogeneity diagnostics and do not replace the pooled inference.

## Multiplicity-adjusted confirmatory conclusions

| ID | Endpoint | Effect (strategy - baseline) | 95% paired bootstrap CI | Raw p | BH-adjusted p | Conclusion |
|---|---|---:|---:|---:|---:|---|
| H1 | L1 | 0.065777022 | [0.062781843, 0.06897125] | 1 | 1 | do not reject registered null after BH correction |
| H2A | L4 | -0.076312726 | [-0.085282536, -0.067685593] | 1 | 1 | do not reject registered null after BH correction |
| H2B | L4 | -0.076312726 | [-0.085393325, -0.067612595] | 1 | 1 | do not reject registered null after BH correction |
| H3 | L4 | -0.00023554277 | [-0.0059915774, 0.005445998] | 0.936106 | 0.936106 | do not reject registered null after BH correction |
| H4 | L4 | 0.031618859 | [0.025535082, 0.037613063] | 9.999e-05 | 0.00019998 | reject registered null after BH correction |
| H5A | L1 | 0.095898456 | [0.09082734, 0.10088754] | 1 | 1 | do not reject registered null after BH correction |
| H5B | L4 | -0.034083937 | [-0.039446183, -0.02859859] | 1 | 1 | do not reject registered null after BH correction |
| H5C | L4 | -0.034083937 | [-0.03960593, -0.028612379] | 1 | 1 | do not reject registered null after BH correction |
| H6A | L1 | 0.061161571 | [0.056963035, 0.06534071] | 1 | 1 | do not reject registered null after BH correction |
| H6B | L1 | -0.021441843 | [-0.023666974, -0.019147304] | 9.999e-05 | 0.00019998 | reject registered null after BH correction |

## Descriptive H6 and H7 results

H6 (SCALAR_TEMPERATURE_RESIDUAL_RATIO - SELECTED_CS, L1) had a pooled paired effect of -0.11152654 (95% paired bootstrap CI [-0.11623486, -0.10687575]; 40 paired seed blocks). No p-value, binary conclusion, or noninferiority claim was generated.

| H7 row | Endpoint | Strategy - baseline | Effect | Direction relative to endpoint |
|---|---|---|---:|---|
| H1 | L1 | GG_CALIBRATION_ONLY - RAW | 0.065777022 | unfavorable |
| H5A | L1 | CS_CALIBRATION_ONLY - RAW | 0.095898456 | unfavorable |
| H2A | L4 | GG_ACQUISITION_ONLY - RAW | -0.076312726 | unfavorable |
| H2B | L4 | ORIGINAL_GG - RAW | -0.076312726 | unfavorable |
| H5B | L4 | CS_ACQUISITION_ONLY - RAW | -0.034083937 | unfavorable |
| H5C | L4 | SELECTED_CS - RAW | -0.034083937 | unfavorable |
| H3 | L4 | RAW_FIXED_BETA_MATCHED - ORIGINAL_GG | -0.00023554277 | unfavorable |
| H4 | L4 | RAW_STAGE_BETA_MATCHED - ORIGINAL_GG | 0.031618859 | favorable |
| H6A | L1 | SCALAR_TEMPERATURE_NLL - IDENTITY_CONTROL | 0.061161571 | unfavorable |
| H6B | L1 | SCALAR_TEMPERATURE_RESIDUAL_RATIO - IDENTITY_CONTROL | -0.021441843 | favorable |
| H6 | L1 | SCALAR_TEMPERATURE_RESIDUAL_RATIO - SELECTED_CS | -0.11152654 | favorable |

## Prespecified heterogeneity diagnostics

| ID | Same pooled direction across environments | Environment-effect range | Pair count per environment |
|---|---:|---:|---:|
| H1 | 16/16 | [0.004556213, 0.12927011] | 40 |
| H2A | 11/16 | [-0.22311425, 0.056584821] | 40 |
| H2B | 11/16 | [-0.22311425, 0.056584821] | 40 |
| H3 | 7/16 | [-0.038727399, 0.038616071] | 40 |
| H4 | 16/16 | [0.0036885685, 0.093914103] | 40 |
| H5A | 8/16 | [-0.021730983, 0.28725061] | 40 |
| H5B | 16/16 | [-0.073210306, -0.013215469] | 40 |
| H5C | 16/16 | [-0.073210306, -0.013215469] | 40 |
| H6 | 16/16 | [-0.25799912, -0.0098998635] | 40 |
| H6A | 11/16 | [-0.024223159, 0.17646156] | 40 |
| H6B | 8/16 | [-0.064398541, 0.019515361] | 40 |

All task-level (4 per contrast), split-level (2), model-level (2), and environment-level (16) paired estimates and intervals are reported in `tables/v6_p0_confirmation_environment_effects.csv`. These diagnostics were not substituted for the pooled confirmatory analyses.

## Completeness gates

- Passed environments: 176/176.
- Failed completeness gates: 0.
- Each registered contrast/environment contains exactly seeds 7000-7039, both strategy and baseline, no duplicate seed, no unregistered exclusion, and no endpoint missingness.

No post-hoc contrast, exclusion, endpoint, multiplicity family, method change, environment selection, or exploratory analysis was introduced.
