# P0 broad selection stability — corrected endpoint layer

## Before/after L1 ordering

```json
{
  "before": [
    {
      "rank": 1,
      "strategy": "CONFORMAL_INTERVAL_ONLY",
      "environment_balanced_median_l1": 0.029819874550084773
    },
    {
      "rank": 2,
      "strategy": "ISOTONIC_ABS_RESIDUAL",
      "environment_balanced_median_l1": 0.048487330476457875
    },
    {
      "rank": 3,
      "strategy": "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
      "environment_balanced_median_l1": 0.04966693803400497
    },
    {
      "rank": 4,
      "strategy": "RAW_STAGE_BETA_MATCHED",
      "environment_balanced_median_l1": 0.05509210782198798
    },
    {
      "rank": 5,
      "strategy": "SELECTED_GG",
      "environment_balanced_median_l1": 0.056187650949844195
    },
    {
      "rank": 6,
      "strategy": "RAW_FIXED_BETA_MATCHED",
      "environment_balanced_median_l1": 0.05623199227354245
    },
    {
      "rank": 7,
      "strategy": "GG_ACQUISITION_ONLY",
      "environment_balanced_median_l1": 0.05740785202356187
    },
    {
      "rank": 8,
      "strategy": "IDENTITY_CONTROL",
      "environment_balanced_median_l1": 0.059175948213361675
    },
    {
      "rank": 9,
      "strategy": "RAW",
      "environment_balanced_median_l1": 0.0612373448617377
    },
    {
      "rank": 10,
      "strategy": "POWER_SCALING",
      "environment_balanced_median_l1": 0.061675857094433996
    },
    {
      "rank": 11,
      "strategy": "HISTORICAL_CS",
      "environment_balanced_median_l1": 0.06540093816857155
    },
    {
      "rank": 12,
      "strategy": "CS_ACQUISITION_ONLY",
      "environment_balanced_median_l1": 0.06703349301213721
    },
    {
      "rank": 13,
      "strategy": "SELECTED_CS",
      "environment_balanced_median_l1": 0.06703349301213721
    },
    {
      "rank": 14,
      "strategy": "SCALAR_TEMPERATURE_NLL",
      "environment_balanced_median_l1": 0.1021664630836047
    },
    {
      "rank": 15,
      "strategy": "GG_CALIBRATION_ONLY",
      "environment_balanced_median_l1": 0.13361747317188521
    },
    {
      "rank": 16,
      "strategy": "CS_CALIBRATION_ONLY",
      "environment_balanced_median_l1": 0.14031586930415813
    },
    {
      "rank": 17,
      "strategy": "ORIGINAL_GG",
      "environment_balanced_median_l1": 0.1744082840236686
    }
  ],
  "after": [
    {
      "rank": 1,
      "strategy": "CONFORMAL_INTERVAL_ONLY",
      "environment_balanced_median_l1": 0.029819874550084773
    },
    {
      "rank": 2,
      "strategy": "ISOTONIC_ABS_RESIDUAL",
      "environment_balanced_median_l1": 0.048487330476457875
    },
    {
      "rank": 3,
      "strategy": "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
      "environment_balanced_median_l1": 0.04966693803400497
    },
    {
      "rank": 4,
      "strategy": "GG_ACQUISITION_ONLY",
      "environment_balanced_median_l1": 0.05281716131389314
    },
    {
      "rank": 5,
      "strategy": "RAW_STAGE_BETA_MATCHED",
      "environment_balanced_median_l1": 0.0571589840083976
    },
    {
      "rank": 6,
      "strategy": "RAW_FIXED_BETA_MATCHED",
      "environment_balanced_median_l1": 0.05915691037081955
    },
    {
      "rank": 7,
      "strategy": "IDENTITY_CONTROL",
      "environment_balanced_median_l1": 0.059175948213361675
    },
    {
      "rank": 8,
      "strategy": "RAW",
      "environment_balanced_median_l1": 0.059175948213361675
    },
    {
      "rank": 9,
      "strategy": "SELECTED_GG",
      "environment_balanced_median_l1": 0.06093130154286988
    },
    {
      "rank": 10,
      "strategy": "POWER_SCALING",
      "environment_balanced_median_l1": 0.061675857094433996
    },
    {
      "rank": 11,
      "strategy": "HISTORICAL_CS",
      "environment_balanced_median_l1": 0.0632681530855668
    },
    {
      "rank": 12,
      "strategy": "CS_ACQUISITION_ONLY",
      "environment_balanced_median_l1": 0.06636104110851981
    },
    {
      "rank": 13,
      "strategy": "SCALAR_TEMPERATURE_NLL",
      "environment_balanced_median_l1": 0.1021664630836047
    },
    {
      "rank": 14,
      "strategy": "GG_CALIBRATION_ONLY",
      "environment_balanced_median_l1": 0.13361747317188521
    },
    {
      "rank": 15,
      "strategy": "SELECTED_CS",
      "environment_balanced_median_l1": 0.13518460792206527
    },
    {
      "rank": 16,
      "strategy": "CS_CALIBRATION_ONLY",
      "environment_balanced_median_l1": 0.14031586930415813
    },
    {
      "rank": 17,
      "strategy": "ORIGINAL_GG",
      "environment_balanced_median_l1": 0.14251803058360601
    }
  ]
}
```

- Simple-scaling summaries changed: False
- Residual-ratio role changed: False
- Conformal summary changed: False
- Isotonic summary changed: False
- Prospective confirmation contrasts removed: None

Changes arise only from checkpoint-index reconciliation and the prospectively registered
Selected-CS joint evaluation mapping.
