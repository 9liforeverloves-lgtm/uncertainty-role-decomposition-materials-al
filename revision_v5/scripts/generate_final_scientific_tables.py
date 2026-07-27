#!/usr/bin/env python3
"""Generate final, provenance-rich scientific tables from approved evidence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"


def holm_adjust(values):
    values = np.asarray(values, float)
    n = len(values)
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    adjusted = np.maximum.accumulate(ranked * (n - np.arange(n)))
    result = np.empty(n, float)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def main():
    with open(ROOT / "19_selected_policy_lock.json", encoding="utf-8") as handle:
        policy = json.load(handle)
    with open(ROOT / "CONFIRMATION_RESULT_LOCK_V5_RC1.json", encoding="utf-8") as handle:
        result_lock = json.load(handle)
    with open(
        ROOT / "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json",
        encoding="utf-8",
    ) as handle:
        trajectory_lock = json.load(handle)

    policy_hash = policy["selection_table_sha256"]
    result_hash = result_lock["execution_registry"]["sha256"]
    tree_hash = trajectory_lock["deterministic_tree_hash"]

    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_v3.csv")
    reconstruction = pd.read_csv(
        ROOT / "audits_v5" / "l4_exact_execution_reconstruction_final.csv"
    ).set_index("job_id")
    endpoints["l4_top1pct_recall_nauc"] = endpoints["job_id"].map(
        reconstruction["recomputed_primary_nauc"]
    )
    endpoints["l4_independently_validated"] = "case_A_bitwise_exact"
    endpoints["l4_validation_note"] = (
        "Execution-semantic reconstruction; budget_fraction x-axis; "
        "3360/3360 bitwise exact; max absolute difference 0"
    )
    endpoints["selected_policy_lock_hash"] = policy_hash
    endpoints["result_lock_hash"] = result_hash
    endpoints["trajectory_content_tree_hash"] = tree_hash
    endpoints["analysis_classification"] = "confirmatory"
    endpoints.to_csv(TABLES / "v5_rc1_seed_level_endpoints_final.csv", index=False)

    previous = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_v3.csv")
    l1 = previous[previous["endpoint"] == "l1_campaign_mace"].copy()
    l4 = pd.read_csv(TABLES / "v5_rc1_l4_inference_recomputed_final.csv")
    for frame in (l1, l4):
        frame["split"] = frame["environment"].str.split("__").str[1]
        frame["surrogate"] = frame["environment"].str.split("__").str[2]
        frame["bh_family_id"] = frame["environment"] + "|primary_8"
        frame["direction"] = frame["effect_direction"]
        frame["selected_policy_lock_hash"] = policy_hash
        frame["result_lock_hash"] = result_hash
        frame["trajectory_content_tree_hash"] = tree_hash
        frame["l1_validation_status"] = "validated_4_of_4_checkpoints"
        frame["l4_validation_status"] = "case_A_bitwise_exact"
        frame["analysis_classification"] = "confirmatory"
    final = pd.concat([l1, l4], ignore_index=True, sort=False)
    final = final.sort_values(
        ["task", "split", "surrogate", "contrast_name", "endpoint"],
        kind="stable",
    ).reset_index(drop=True)
    final.to_csv(TABLES / "v5_rc1_primary_contrasts_final.csv", index=False)

    sensitivity = pd.read_csv(
        TABLES / "recovered_job_exclusion_sensitivity.csv"
    )
    sensitivity["task"] = sensitivity["environment"].str.split("__").str[0]
    sensitivity["split"] = sensitivity["environment"].str.split("__").str[1]
    sensitivity["surrogate"] = sensitivity["environment"].str.split("__").str[2]
    sensitivity["selected_policy_lock_hash"] = policy_hash
    sensitivity["result_lock_hash"] = result_hash
    sensitivity["trajectory_content_tree_hash"] = tree_hash
    sensitivity["analysis_classification"] = "recovery_exclusion_sensitivity"
    sensitivity.to_csv(
        TABLES / "v5_rc1_recovery_sensitivity_final.csv", index=False
    )

    multiplicity = final.copy()
    multiplicity["p_value_bonferroni"] = np.nan
    multiplicity["p_value_holm"] = np.nan
    for family in multiplicity["bh_family_id"].unique():
        mask = multiplicity["bh_family_id"] == family
        p = multiplicity.loc[mask, "p_value_unadjusted"].to_numpy(float)
        multiplicity.loc[mask, "p_value_bonferroni"] = np.minimum(p * len(p), 1.0)
        multiplicity.loc[mask, "p_value_holm"] = holm_adjust(p)
    multiplicity["bh_significant"] = multiplicity["p_value_bh_adjusted"] < 0.05
    multiplicity["bonferroni_significant"] = (
        multiplicity["p_value_bonferroni"] < 0.05
    )
    multiplicity["holm_significant"] = multiplicity["p_value_holm"] < 0.05
    multiplicity["analysis_classification"] = "multiplicity_sensitivity"
    multiplicity.to_csv(
        TABLES / "v5_rc1_multiplicity_sensitivity_final.csv", index=False
    )

    summary = (
        final.groupby(
            ["task", "split", "surrogate", "contrast_name", "endpoint"],
            as_index=False,
        )
        .agg(
            environment_count=("environment", "nunique"),
            descriptive_mean_effect=("mean_diff", "mean"),
            descriptive_median_effect=("mean_diff", "median"),
            minimum_effect=("mean_diff", "min"),
            maximum_effect=("mean_diff", "max"),
            bh_significant_count=("significant_after_bh", "sum"),
        )
    )
    summary["analysis_classification"] = (
        "descriptive_cross_environment_summary_no_pooled_inference"
    )
    summary["selected_policy_lock_hash"] = policy_hash
    summary["result_lock_hash"] = result_hash
    summary["trajectory_content_tree_hash"] = tree_hash
    summary.to_csv(
        TABLES / "v5_rc1_environment_summary_final.csv", index=False
    )

    main_dir = TABLES / "final_main_text_tables"
    supp_dir = TABLES / "final_supplement_tables"
    main_dir.mkdir(parents=True, exist_ok=True)
    supp_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "v5_rc1_primary_contrasts_final.csv",
        "v5_rc1_environment_summary_final.csv",
    ]:
        shutil.copy2(TABLES / name, main_dir / name)
    for name in [
        "v5_rc1_seed_level_endpoints_final.csv",
        "v5_rc1_recovery_sensitivity_final.csv",
        "v5_rc1_multiplicity_sensitivity_final.csv",
    ]:
        shutil.copy2(TABLES / name, supp_dir / name)

    print(
        json.dumps(
            {
                "endpoint_rows": len(endpoints),
                "primary_contrast_rows": len(final),
                "recovery_sensitivity_rows": len(sensitivity),
                "multiplicity_rows": len(multiplicity),
                "environment_summary_rows": len(summary),
                "log_kvrh_selected_baselines": sorted(
                    final[
                        (final["task"] == "matbench_log_kvrh")
                        & final["contrast_name"].str.startswith("Selected")
                    ]["baseline_strategy"].unique()
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
