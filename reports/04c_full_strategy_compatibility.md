# Full historical-strategy compatibility

Status: **PASS**. The audit directly compared V6 production-adapter replays with frozen V5 artifacts at seed 5000 across all 16 task/split/model environments: 4 tasks × IID/chemical-system group-disjoint splits × Random Forest/ExtraTrees-compatible ensembles × 4 strategies = 64 cases. All 64 V6 adapter comparisons passed. A separate frozen-V5-runner smoke replay validates the read-only wrapper without duplicating every large reference computation.

## Methods covered

| V5 strategy | V6 adapter |
| --- | --- |
| `gg_ucb_beta_1` | `ORIGINAL_GG` |
| `cs_da_oob_hist` | `HISTORICAL_CS` |
| `gg_ucb_beta_0p5` | `SELECTED_GG` |
| `cs_da_oob_parsimonious_f1` | `SELECTED_CS` |

Each case checked `source_split_hash, target_split_hash, diagnostic_split_hash, initial_labeled_ids, per_round_predictive_mean_raw_sigma, fitted_scale_or_cs_parameters, acquisition_scores, stable_ranking, selected_batch, checkpoint_values, checkpoint_model_semantics, l1_campaign_mace, l4_top1pct_recall_nauc, logical_trajectory_hash`. For GG, fitted global scale is compared exactly; for CS, the retained candidate-specific scale vectors are compared exactly. The semantic logical trajectory hash combines split hashes, initial labels, retained candidate audit, selected batches, checkpoint values, L1, and L4.

Checkpoint comparison is deliberately two-layered. Checkpoint labels, thresholds, acquisition rounds, queried counts, and realized progress must match exactly; each checkpoint model must also have the same canonical-domain semantic fingerprint (training arrays/IDs, fitted hyperparameters, full-domain predictive mean/raw-standard-deviation, and full-domain leaf/local representation). Raw `joblib` payload hashes are preserved in the audit table but are not included in the semantic trajectory hash: the frozen-V5 self-replay control reproduces Random-Forest bytes but demonstrates that the frozen ExtraTrees-compatible serializer changes bytes despite identical checkpoint semantics and identical scientific trajectory. The control is `results/v6_v5_strategy_replay_audit/checkpoint_serialization_control.json` (SHA-256 `5ff6dc7d6acc8f5399513ea28764a822bf17bbaa1a30e28151281e5e3ed77030`), and contains `2` model controls.

The frozen V5 runner writes only to `results/v6_v5_strategy_replay_audit/frozen_v5_runner_exact`; V6 adapter outputs are stored in model-specific reconciled namespaces under `results/v6_v5_strategy_replay_audit`. No V5 artifact was modified. The audit uses historical seed 5000 only and did not read or run V6 confirmation seeds 7000–7039.

Audit table: `tables/v6_v5_strategy_replay_audit.csv` (SHA-256 `65218e9516c042fc5f14194d8340bb215c6831a28cb642eeb59b8cdc32a53240`).
