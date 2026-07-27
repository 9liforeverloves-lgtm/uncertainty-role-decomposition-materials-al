#!/usr/bin/env python3
"""Editorial-only tables for submission candidate v2.

Reads frozen manifests, audits, and locked final tables. Does not recompute
scientific endpoints, intervals, p-values, or multiplicity adjustments.
"""

from pathlib import Path
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tables_v5" / "submission_candidate_v2"
OUT.mkdir(parents=True, exist_ok=True)


development = pd.read_csv(ROOT / "manifests_v4" / "DEVELOPMENT_JOB_MANIFEST_V5.csv")
inventory = (
    development[["strategy", "candidate_specific_config_json"]]
    .drop_duplicates()
    .sort_values("strategy")
    .reset_index(drop=True)
)
inventory.insert(0, "configuration_id", range(1, len(inventory) + 1))
inventory["family"] = inventory["strategy"].map(
    lambda value: (
        "candidate-specific"
        if value.startswith("candidate_specific")
        else "Gaussian-global"
        if value.startswith("gg_")
        else "Raw UCB"
        if value.startswith("raw_ucb")
        else "mechanism/control"
    )
)
inventory["manifest_job_count"] = inventory["strategy"].map(
    development["strategy"].value_counts()
)
assert len(inventory) == 36
inventory.to_csv(OUT / "development_configuration_inventory_36.csv", index=False)


selected = pd.read_csv(ROOT / "tables_v5" / "loto_selected_policies.csv")
selected.to_csv(OUT / "development_selection_by_fold.csv", index=False)


ood = pd.read_csv(ROOT / "audits_v4" / "ood_disjointness_audit.csv")
ood_summary = (
    ood.groupby("task", as_index=False)
    .agg(
        audited_seeds=("seed", "nunique"),
        source_records=("source_records", "first"),
        target_records=("target_records", "first"),
        diagnostic_records=("diagnostic_records", "first"),
        maximum_group_overlap=("source_target_diagnostic_group_overlap", "max"),
        maximum_candidate_id_overlap=("candidate_id_overlap", "max"),
        all_audits_passed=("pass", "all"),
    )
)
ood_summary.to_csv(OUT / "chemical_system_ood_split_summary.csv", index=False)


primary = pd.read_csv(ROOT / "tables_v5" / "v5_rc1_primary_contrasts_final.csv")
complete = primary.rename(
    columns={
        "p_value_unadjusted": "p_raw",
        "p_value_bh_adjusted": "p_BH",
    }
)
complete.to_csv(OUT / "complete_primary_128_with_p_raw_p_BH.csv", index=False)
assert len(complete) == 128
assert complete["p_raw"].notna().all()
assert complete["p_BH"].notna().all()


parameters = pd.DataFrame(
    [
        ("OOB validity threshold", "min_oob_trees_per_sample", 3, 10, "Frozen executable identities"),
        ("Minimum queried cases", "min_queried_for_DA", 30, 30, "Identity fallback below threshold"),
        ("Feature indices", "feature_indices", "0–5", "0", "Historical six-feature vs selected log-sigma only"),
        ("Top-tail fraction", "top_q_fraction", 0.10, 0.10, "Pair weighting cutoff"),
        ("Top-tail pair weight", "top_q_pair_weight", 2.0, 1.0, "Selected method removes extra weighting"),
        ("Maximum sampled pairs", "maximum_pairs", 20000, 20000, "Deterministic RNG by frozen seed"),
        ("Pair-score temperature", "pair_score_temperature", 1.0, 1.0, "Logistic ranking loss"),
        ("L2 regularization", "l2_regularization", 0.01, 0.01, "Slope coefficients only"),
        ("Mean log-scale penalty", "mean_log_scale_squared_regularization", 0.01, 0.01, "Centers scale near identity"),
        ("Optimizer iterations", "optimizer_maxiter", 100, 100, "L-BFGS-B"),
        ("Minimum scale", "scale_min", 0.25, 0.25, "Applied by log-scale clipping"),
        ("Maximum scale", "scale_max", 4.0, 4.0, "Applied by log-scale clipping"),
        ("Uncertainty floor", "floor", "1e-8", "1e-8", "Frozen acquisition floor"),
        ("Fallback scale", "fallback", 1.0, 1.0, "Raw UCB fallback"),
    ],
    columns=[
        "parameter",
        "code_key",
        "historical_CS",
        "selected_parsimonious_CS",
        "interpretation",
    ],
)
parameters.to_csv(OUT / "candidate_specific_parameter_table.csv", index=False)


summary = {
    "schema_version": "submission-candidate-v2-editorial-tables-1",
    "scientific_recomputation": False,
    "development_configurations": len(inventory),
    "primary_rows": len(complete),
    "primary_has_p_raw": True,
    "primary_has_p_BH": True,
    "ood_tasks": len(ood_summary),
    "ood_audits_passed": bool(ood["pass"].all()),
    "candidate_specific_parameters": len(parameters),
}
(OUT / "editorial_table_manifest.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
print(summary)
