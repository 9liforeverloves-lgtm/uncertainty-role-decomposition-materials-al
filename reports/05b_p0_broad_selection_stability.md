# P0 broad selection stability

All quantities here are descriptive broad-development diagnostics. They do not trigger a confirmation freeze or alter the predeclared simple-scaling roles.

## Leave-one-development-seed-out fixed-beta ranges

| held-out task | minimum | maximum |
| --- | ---: | ---: |
| matbench_expt_gap | 3.0921321299543432 | 3.1850934950819338 |
| matbench_mp_gap | 2.9538067778957307 | 3.0600535148478913 |
| matbench_log_gvrh | 2.9179238489385915 | 2.9585876312807442 |
| matbench_log_kvrh | 2.9181542186918294 | 2.9397025021364254 |

## Task bootstrap

Each LOTO fold contains only three source tasks, so the bootstrap is reported cautiously as a descriptive sensitivity analysis.

```json
{
  "matbench_expt_gap": {
    "fixed_beta_quantiles": {
      "q025": 3.1107220709068173,
      "q50": 3.1292513479848294,
      "q975": 3.210114825411865
    },
    "interpretation": "descriptive only: each fold has only three source tasks",
    "repetitions": 500,
    "source_task_count": 3
  },
  "matbench_log_gvrh": {
    "fixed_beta_quantiles": {
      "q025": 2.2147865091320704,
      "q50": 2.9358999688254808,
      "q975": 3.210114825411865
    },
    "interpretation": "descriptive only: each fold has only three source tasks",
    "repetitions": 500,
    "source_task_count": 3
  },
  "matbench_log_kvrh": {
    "fixed_beta_quantiles": {
      "q025": 2.2147865091320704,
      "q50": 2.9341190833680884,
      "q975": 3.210114825411865
    },
    "interpretation": "descriptive only: each fold has only three source tasks",
    "repetitions": 500,
    "source_task_count": 3
  },
  "matbench_mp_gap": {
    "fixed_beta_quantiles": {
      "q025": 2.2147865091320704,
      "q50": 2.9962726895575917,
      "q975": 3.154857494941975
    },
    "interpretation": "descriptive only: each fold has only three source tasks",
    "repetitions": 500,
    "source_task_count": 3
  }
}
```

## Model and split stratification

```json
{
  "model_stratified_fixed_beta": {
    "matbench_expt_gap": {
      "extra_randomized_bagging": 3.0798199747604,
      "random_forest": 3.1705572832902167
    },
    "matbench_log_gvrh": {
      "extra_randomized_bagging": 2.8769001911176524,
      "random_forest": 2.966802064971898
    },
    "matbench_log_kvrh": {
      "extra_randomized_bagging": 2.87511930566026,
      "random_forest": 2.9853313420499097
    },
    "matbench_mp_gap": {
      "extra_randomized_bagging": 2.9635897079537816,
      "random_forest": 3.045704062782021
    }
  },
  "split_stratified_fixed_beta": {
    "matbench_expt_gap": {
      "chemical_system_ood": 3.395340766652172,
      "iid_record": 2.9635897079537816
    },
    "matbench_log_gvrh": {
      "chemical_system_ood": 3.3540348313467847,
      "iid_record": 2.847429566531959
    },
    "matbench_log_kvrh": {
      "chemical_system_ood": 3.261181438372159,
      "iid_record": 2.847429566531959
    },
    "matbench_mp_gap": {
      "chemical_system_ood": 3.2198755030667714,
      "iid_record": 2.9635897079537816
    }
  }
}
```

## Prespecified non-identity selected-minus-runner-up margin

```json
{
  "all_nonidentity_scores": {
    "CONFORMAL_INTERVAL_ONLY": 0.02981987455008482,
    "ISOTONIC_ABS_RESIDUAL": 0.048487330476457896,
    "POWER_SCALING": 0.06167585709443403,
    "SCALAR_TEMPERATURE_NLL": 0.10216646308360475,
    "SCALAR_TEMPERATURE_RESIDUAL_RATIO": 0.04966693803400503
  },
  "policy_interpretation": "descriptive selected-minus-runner-up margin only; the selected method was prespecified as the simple non-identity baseline and no outcome-selected winner is created",
  "runner_up_environment_balanced_median_l1": 0.02981987455008482,
  "runner_up_method": "CONFORMAL_INTERVAL_ONLY",
  "selected_environment_balanced_median_l1": 0.04966693803400503,
  "selected_method": "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
  "selected_minus_runner_up_l1": 0.019847063483920208
}
```

Identity remains a negative control. Residual-ratio retains its predeclared role as the selected simple non-identity baseline; the displayed selected-minus-runner-up margin is descriptive and is not an outcome-driven winner selection.
