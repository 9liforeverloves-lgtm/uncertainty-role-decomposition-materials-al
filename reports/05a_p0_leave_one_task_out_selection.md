# P0 leave-one-task-out beta selection

Status: **CANDIDATE, development-only; not frozen for confirmation**.

Each held-out task map uses only the other three tasks' Original-GG effective-beta rows. The candidate is generated after the final broad development run, but its selection rules were prospectively locked before endpoints were read.

| held-out task | fixed beta | 0–25% | 25–50% | 50–75% | 75–100% | source tasks | source seeds |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| matbench_expt_gap | 3.1292513479848294 | 1.8864560391639924 | 3.0283212979742822 | 3.2426774705523229 | 3.3353450207973276 | matbench_log_gvrh, matbench_log_kvrh, matbench_mp_gap | 6100–6109 |
| matbench_log_gvrh | 2.9358999688254808 | 1.8161893436708065 | 2.8806228468198856 | 2.9831017509738231 | 2.9286726780660173 | matbench_expt_gap, matbench_log_kvrh, matbench_mp_gap | 6100–6109 |
| matbench_log_kvrh | 2.9341190833680884 | 1.851546936943774 | 3.0157896212723956 | 2.9527550758867052 | 2.8963389879456507 | matbench_expt_gap, matbench_log_gvrh, matbench_mp_gap | 6100–6109 |
| matbench_mp_gap | 2.9962726895575917 | 1.7462452244854489 | 2.8806228468198856 | 3.0540850004812166 | 3.0807127642856109 | matbench_expt_gap, matbench_log_gvrh, matbench_log_kvrh | 6100–6109 |

## Consistency checks

All candidate maps were recomputed from the hash-addressed broad effective-beta table before this report. Results:

```json
{
  "matbench_expt_gap": {
    "candidate_equals_recomputed": {
      "fixed": true,
      "source_tasks": true,
      "stage": true
    }
  },
  "matbench_log_gvrh": {
    "candidate_equals_recomputed": {
      "fixed": true,
      "source_tasks": true,
      "stage": true
    }
  },
  "matbench_log_kvrh": {
    "candidate_equals_recomputed": {
      "fixed": true,
      "source_tasks": true,
      "stage": true
    }
  },
  "matbench_mp_gap": {
    "candidate_equals_recomputed": {
      "fixed": true,
      "source_tasks": true,
      "stage": true
    }
  }
}
```

The output intentionally remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`; no confirmation policy has been frozen.
