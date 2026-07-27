#!/usr/bin/env python3
"""Final L4 execution-semantic reconstruction and dual-inference audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORIES = ROOT / "results_v4" / "confirmation" / "trajectories"
TABLES = ROOT / "tables_v5"
AUDITS = ROOT / "audits_v5"
N_BOOTSTRAP = 10_000
N_PERMUTATION = 10_000


def normalized_auc(x, values):
    """Byte-for-byte semantic equivalent of metrics.normalized_auc."""
    x = np.asarray(x, float)
    values = np.asarray(values, float)
    order = np.argsort(x, kind="stable")
    x = x[order]
    values = values[order]
    if len(x) < 2 or x[-1] <= x[0]:
        return float("nan")
    return float(np.trapezoid(values, x) / (x[-1] - x[0]))


def bh_adjust(values):
    values = np.asarray(values, float)
    n = len(values)
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty(n, float)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def paired_inference(baseline, test, endpoint, higher_is_better, contrast_key, lock_hash):
    merged = baseline[["seed", endpoint]].merge(
        test[["seed", endpoint]], on="seed", suffixes=("_baseline", "_test")
    ).dropna()
    diffs = (
        merged[f"{endpoint}_test"].to_numpy(float)
        - merged[f"{endpoint}_baseline"].to_numpy(float)
    )
    n = len(diffs)
    digest = hashlib.md5((contrast_key + lock_hash).encode()).hexdigest()
    boot_seed = int(digest[:8], 16) % (2**31)
    perm_seed = int(digest[8:16], 16) % (2**31)
    boot_rng = np.random.RandomState(boot_seed)
    perm_rng = np.random.RandomState(perm_seed)
    boot = np.empty(N_BOOTSTRAP, float)
    perm = np.empty(N_PERMUTATION, float)
    for i in range(N_BOOTSTRAP):
        boot[i] = np.mean(diffs[boot_rng.choice(n, size=n, replace=True)])
    mean_diff = float(np.mean(diffs))
    for i in range(N_PERMUTATION):
        perm[i] = np.mean(diffs * perm_rng.choice([-1, 1], size=n))
    p = float((np.count_nonzero(np.abs(perm) >= abs(mean_diff)) + 1) / (N_PERMUTATION + 1))
    if higher_is_better:
        direction = (
            "favors_test" if mean_diff > 0 and p < 0.05
            else "favors_baseline" if mean_diff < 0 and p < 0.05
            else "inconclusive"
        )
    else:
        direction = (
            "favors_test" if mean_diff < 0 and p < 0.05
            else "favors_baseline" if mean_diff > 0 and p < 0.05
            else "inconclusive"
        )
    return {
        "n_pairs": n,
        "mean_diff": mean_diff,
        "ci_lower": float(np.percentile(boot, 2.5)),
        "ci_upper": float(np.percentile(boot, 97.5)),
        "p_value_unadjusted": p,
        "effect_direction": direction,
        "rng_seed_bootstrap": boot_seed,
        "rng_seed_permutation": perm_seed,
    }


def infer(endpoints, value_column, lock_hash, l1_reference):
    contrasts = [
        ("Original GG vs Raw", "gg_ucb_beta_1", "raw_ucb_beta_1"),
        ("Historical CS vs Raw", "cs_da_oob_hist", "raw_ucb_beta_1"),
        ("Selected GG vs Raw", "gg_ucb_beta_0p5", "TASK_SPECIFIC"),
        ("Selected CS vs Raw", "cs_da_oob_parsimonious_f1", "TASK_SPECIFIC"),
    ]
    rows = []
    for environment in sorted(endpoints["environment"].unique()):
        env = endpoints[endpoints["environment"] == environment]
        task = env["task"].iloc[0]
        selected_baseline = env["selected_baseline_strategy"].iloc[0]
        for contrast_name, test_strategy, baseline_strategy in contrasts:
            baseline_strategy = (
                selected_baseline if baseline_strategy == "TASK_SPECIFIC" else baseline_strategy
            )
            baseline = env[env["strategy"] == baseline_strategy]
            test = env[env["strategy"] == test_strategy]
            key = f"{environment}|{contrast_name}|l4_top1pct_recall_nauc"
            result = paired_inference(
                baseline, test, value_column, True, key, lock_hash
            )
            rows.append(
                {
                    "task": task,
                    "environment": environment,
                    "contrast_name": contrast_name,
                    "baseline_strategy": baseline_strategy,
                    "test_strategy": test_strategy,
                    "endpoint": "l4_top1pct_recall_nauc",
                    "endpoint_name": "L4 Top-1% Recall nAUC",
                    "higher_is_better": True,
                    **result,
                }
            )
    frame = pd.DataFrame(rows)
    frame["p_value_bh_adjusted"] = np.nan
    for environment in frame["environment"].unique():
        mask = frame["environment"] == environment
        l4_rows = frame.loc[mask].copy()
        l1_rows = l1_reference[
            (l1_reference["environment"] == environment)
            & (l1_reference["endpoint"] == "l1_campaign_mace")
        ][["contrast_name", "p_value_unadjusted"]].copy()
        family = pd.concat(
            [
                l1_rows.assign(source="l1"),
                l4_rows[["contrast_name", "p_value_unadjusted"]].assign(source="l4"),
            ],
            ignore_index=True,
        )
        if len(family) != 8:
            raise ValueError(f"{environment}: expected 8-test family, found {len(family)}")
        family["adjusted"] = bh_adjust(family["p_value_unadjusted"].to_numpy(float))
        l4_adjusted = family[family["source"] == "l4"].set_index("contrast_name")[
            "adjusted"
        ]
        frame.loc[mask, "p_value_bh_adjusted"] = frame.loc[
            mask, "contrast_name"
        ].map(l4_adjusted)
    frame["significant_after_bh"] = frame["p_value_bh_adjusted"] < 0.05
    frame["evidence_label"] = np.where(
        frame["significant_after_bh"],
        "significant_after_BH",
        np.where(
            frame["p_value_unadjusted"] < 0.05,
            "nominally_significant",
            "not_significant",
        ),
    )
    frame["adjustment_method"] = "within_environment_BH"
    frame["adjustment_family_size"] = 8
    frame["alpha_level"] = 0.05
    frame["prospectively_specified"] = True
    return frame


def main():
    registry = pd.read_csv(
        ROOT / "results_v4" / "confirmation" / "registry_snapshot.csv"
    )
    registry = registry[registry["status"].isin(["COMPLETED", "RECOVERED"])].copy()
    endpoint_source = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_v3.csv")
    contrast_reference = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_v3.csv")
    with open(ROOT / "CONFIRMATION_RESULT_LOCK_V5_RC1.json", encoding="utf-8") as handle:
        lock_hash = json.load(handle)["execution_registry"]["sha256"][:16]

    reconstruction = []
    for i, row in enumerate(registry.itertuples(index=False), 1):
        job_id = row.job_id
        directory = TRAJECTORIES / job_id
        with open(directory / "state.json", encoding="utf-8") as handle:
            state = json.load(handle)
        rounds = pd.read_parquet(directory / "rounds.parquet")
        recomputed = normalized_auc(
            rounds["budget_fraction"].to_numpy(float),
            rounds["top1_recall"].to_numpy(float),
        )
        state_value = float(state["primary_nauc"])
        reconstruction.append(
            {
                "job_id": job_id,
                "registry_status": row.status,
                "state_primary_nauc": state_value,
                "recomputed_primary_nauc": recomputed,
                "absolute_difference": abs(state_value - recomputed),
                "bitwise_equal_float64": (
                    np.float64(state_value).tobytes() == np.float64(recomputed).tobytes()
                ),
                "n_round_rows": len(rounds),
                "initial_state_included": bool((rounds["round"] == -1).any()),
                "x_axis": "budget_fraction",
                "y_axis": "top1_recall",
                "integration": "np.trapezoid",
                "normalization": "(x_max-x_min)",
                "terminal_batch_rule": "stored final budget_fraction included",
                "source_semantics": (
                    "runner.py final frame -> normalized_auc("
                    "frame['budget_fraction'], frame['top1_recall'])"
                ),
            }
        )
        if i % 500 == 0:
            print(f"reconstructed {i}/{len(registry)}")

    reconstruction = pd.DataFrame(reconstruction)
    reconstruction.to_csv(
        AUDITS / "l4_exact_execution_reconstruction_final.csv", index=False
    )
    value_map = reconstruction.set_index("job_id")
    endpoints = endpoint_source.copy()
    endpoints["l4_state_final"] = endpoints["job_id"].map(
        value_map["state_primary_nauc"]
    )
    endpoints["l4_recomputed_final"] = endpoints["job_id"].map(
        value_map["recomputed_primary_nauc"]
    )

    state_inference = infer(
        endpoints, "l4_state_final", lock_hash, contrast_reference
    )
    recomputed_inference = infer(
        endpoints, "l4_recomputed_final", lock_hash, contrast_reference
    )
    state_inference.to_csv(TABLES / "v5_rc1_l4_inference_state_final.csv", index=False)
    recomputed_inference.to_csv(
        TABLES / "v5_rc1_l4_inference_recomputed_final.csv", index=False
    )

    keys = ["task", "environment", "contrast_name"]
    paired = state_inference.merge(
        recomputed_inference,
        on=keys,
        suffixes=("_state", "_recomputed"),
        validate="one_to_one",
    )
    paired["mean_diff_delta"] = (
        paired["mean_diff_recomputed"] - paired["mean_diff_state"]
    )
    paired["ci_lower_delta"] = (
        paired["ci_lower_recomputed"] - paired["ci_lower_state"]
    )
    paired["ci_upper_delta"] = (
        paired["ci_upper_recomputed"] - paired["ci_upper_state"]
    )
    paired["p_value_delta"] = (
        paired["p_value_unadjusted_recomputed"]
        - paired["p_value_unadjusted_state"]
    )
    paired["p_bh_delta"] = (
        paired["p_value_bh_adjusted_recomputed"]
        - paired["p_value_bh_adjusted_state"]
    )
    paired["direction_changed"] = (
        paired["effect_direction_recomputed"] != paired["effect_direction_state"]
    )
    paired["evidence_label_changed"] = (
        paired["evidence_label_recomputed"] != paired["evidence_label_state"]
    )
    paired["ci_zero_status_changed"] = (
        (paired["ci_lower_state"] <= 0) & (paired["ci_upper_state"] >= 0)
    ) != (
        (paired["ci_lower_recomputed"] <= 0)
        & (paired["ci_upper_recomputed"] >= 0)
    )
    paired.to_csv(
        AUDITS / "l4_paired_error_cancellation_final.csv", index=False
    )

    robustness = paired[
        keys
        + [
            "n_pairs_state",
            "mean_diff_state",
            "mean_diff_recomputed",
            "mean_diff_delta",
            "ci_lower_state",
            "ci_upper_state",
            "ci_lower_recomputed",
            "ci_upper_recomputed",
            "p_value_unadjusted_state",
            "p_value_unadjusted_recomputed",
            "p_value_bh_adjusted_state",
            "p_value_bh_adjusted_recomputed",
            "direction_changed",
            "evidence_label_changed",
            "ci_zero_status_changed",
        ]
    ].copy()
    robustness["l4_case"] = np.where(
        reconstruction["bitwise_equal_float64"].all(), "A", "B"
    )
    if (
        robustness["direction_changed"].any()
        or robustness["evidence_label_changed"].any()
        or robustness["ci_zero_status_changed"].any()
    ):
        robustness["l4_case"] = "C"
    robustness.to_csv(
        TABLES / "v5_rc1_l4_inference_robustness_final.csv", index=False
    )

    print(
        json.dumps(
            {
                "trajectories": len(reconstruction),
                "bitwise_exact": int(reconstruction["bitwise_equal_float64"].sum()),
                "max_absolute_difference": float(
                    reconstruction["absolute_difference"].max()
                ),
                "inference_rows_each": len(state_inference),
                "direction_changes": int(robustness["direction_changed"].sum()),
                "evidence_label_changes": int(
                    robustness["evidence_label_changed"].sum()
                ),
                "ci_zero_status_changes": int(
                    robustness["ci_zero_status_changed"].sum()
                ),
                "case": robustness["l4_case"].iloc[0],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
