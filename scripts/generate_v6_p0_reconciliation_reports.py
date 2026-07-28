"""Generate the effective-beta reconciliation and full replay reports."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.execution_registry import sha256_file


AUDIT = ROOT / "tables" / "v6_v5_strategy_replay_audit.csv"
AUDIT_SUMMARY = ROOT / "results" / "v6_v5_strategy_replay_audit" / "compatibility_summary.json"
CHECKPOINT_CONTROL = ROOT / "results" / "v6_v5_strategy_replay_audit" / "checkpoint_serialization_control.json"
SENTINEL_BETA = ROOT / "tables" / "v6_p0_sentinel_round_effective_beta.csv"
OUTPUT_TABLE = ROOT / "tables" / "v6_effective_beta_reconciliation.csv"


def environment_balanced_median(frame: pd.DataFrame, column: str) -> float:
    values = frame.groupby("environment", sort=True)[column].median()
    if values.empty:
        raise ValueError("no values available for environment-balanced median")
    return float(values.median())


def collect_v5_gg(adapter: CanonicalV5Adapter, *, v5_strategy: str, nominal_beta: float) -> pd.DataFrame:
    manifest = pd.read_csv(adapter.paths.v5_manifest)
    rows = manifest.loc[manifest.strategy.astype(str) == v5_strategy]
    if len(rows) != 640:
        raise RuntimeError(f"expected 640 frozen V5 rows for {v5_strategy}, found {len(rows)}")
    records: list[pd.DataFrame] = []
    for row in rows.itertuples(index=False):
        path = adapter.paths.v5_root / str(row.expected_output_relative_path) / "rounds.parquet"
        frame = pd.read_parquet(path, columns=["round", "global_scale"])
        frame = frame.loc[frame["round"].astype(int) >= 0].copy()
        frame["environment"] = "__".join((str(row.task), str(row.split_protocol), str(row.model)))
        frame["seed"] = int(row.seed)
        frame["fitted_scale"] = frame["global_scale"].astype(float)
        frame["nominal_beta"] = float(nominal_beta)
        frame["effective_beta"] = frame["nominal_beta"] * frame["fitted_scale"]
        records.append(frame[["environment", "seed", "round", "fitted_scale", "nominal_beta", "effective_beta"]])
    return pd.concat(records, ignore_index=True)


def check_full_compatibility(audit: pd.DataFrame, summary: dict[str, Any]) -> None:
    checks = (
        "source_split_hash",
        "target_split_hash",
        "diagnostic_split_hash",
        "initial_labeled_ids",
        "per_round_predictive_mean_raw_sigma",
        "fitted_scale_or_cs_parameters",
        "acquisition_scores",
        "stable_ranking",
        "selected_batch",
        "checkpoint_values",
        "checkpoint_model_semantics",
        "l1_campaign_mace",
        "l4_top1pct_recall_nauc",
        "logical_trajectory_hash",
    )
    if summary.get("status") != "PASS" or len(audit) != 64 or not audit["passed"].astype(bool).all():
        raise RuntimeError("full historical-strategy compatibility audit has not passed")
    missing = set(checks) - set(audit.columns)
    if missing or not audit.loc[:, list(checks)].astype(bool).all().all():
        raise RuntimeError(f"historical-strategy audit has failed checks: {sorted(missing)}")


def check_checkpoint_serialization_control() -> dict[str, Any]:
    """Validate the explicit V5 self-replay control for raw checkpoint bytes."""

    if not CHECKPOINT_CONTROL.is_file():
        raise RuntimeError("checkpoint serialization control is missing")
    control = json.loads(CHECKPOINT_CONTROL.read_text(encoding="utf-8"))
    if control.get("raw_binary_hash_is_required_semantic_criterion") is not False:
        raise RuntimeError("checkpoint serialization control has an invalid byte-hash policy")
    by_model = {str(item.get("model")): item for item in control.get("controls", []) if isinstance(item, dict)}
    if set(by_model) != {"random_forest", "extra_randomized_bagging"}:
        raise RuntimeError("checkpoint serialization control must contain one RF and one ExtraTrees-compatible replay")
    rf = by_model["random_forest"]
    extra = by_model["extra_randomized_bagging"]
    if not (
        bool(rf.get("raw_checkpoint_bytes_equal"))
        and bool(rf.get("raw_logical_hash_equal"))
        and bool(rf.get("checkpoint_model_semantics_equal"))
        and bool(rf.get("semantic_trajectory_equal"))
    ):
        raise RuntimeError("RF frozen-V5 serialization control did not reproduce raw bytes and semantics")
    if not (
        not bool(extra.get("raw_checkpoint_bytes_equal"))
        and not bool(extra.get("raw_logical_hash_equal"))
        and bool(extra.get("checkpoint_model_semantics_equal"))
        and bool(extra.get("semantic_trajectory_equal"))
    ):
        raise RuntimeError("ExtraTrees frozen-V5 serialization control does not demonstrate the declared byte volatility")
    return control


def write_table(rows: list[dict[str, object]]) -> str:
    frame = pd.DataFrame(rows)
    temporary = OUTPUT_TABLE.with_suffix(OUTPUT_TABLE.suffix + ".tmp")
    frame.to_csv(temporary, index=False, float_format="%.17g", lineterminator="\n")
    os.replace(temporary, OUTPUT_TABLE)
    return sha256_file(OUTPUT_TABLE)


def write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    audit = pd.read_csv(AUDIT)
    summary = json.loads(AUDIT_SUMMARY.read_text(encoding="utf-8"))
    check_full_compatibility(audit, summary)
    checkpoint_control = check_checkpoint_serialization_control()
    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    original_v5 = collect_v5_gg(adapter, v5_strategy="gg_ucb_beta_1", nominal_beta=1.0)
    selected_v5 = collect_v5_gg(adapter, v5_strategy="gg_ucb_beta_0p5", nominal_beta=0.5)
    sentinel = pd.read_csv(SENTINEL_BETA)
    sentinel["environment"] = sentinel["environment"].astype(str)
    original_adapter = audit.loc[audit.v6_strategy.astype(str) == "ORIGINAL_GG"].copy()
    selected_adapter = audit.loc[audit.v6_strategy.astype(str) == "SELECTED_GG"].copy()
    if len(original_adapter) != 16 or len(selected_adapter) != 16:
        raise RuntimeError("audit does not contain both GG adapters for all 16 V5 environments")
    rows = [
        {
            "cohort": "V5 frozen full universe",
            "strategy": "Original GG",
            "environment_count": int(original_v5.environment.nunique()),
            "seed_count": int(original_v5.seed.nunique()),
            "nominal_beta": 1.0,
            "fitted_scale_environment_balanced_median": environment_balanced_median(original_v5, "fitted_scale"),
            "effective_beta_environment_balanced_median": environment_balanced_median(original_v5, "effective_beta"),
            "aggregation": "median within each of 16 task/split/model environments, then median across environments",
        },
        {
            "cohort": "V6 historical adapter paired V5 seed-5000 audit",
            "strategy": "Original GG",
            "environment_count": int(original_adapter[["task", "split", "model"]].drop_duplicates().shape[0]),
            "seed_count": 1,
            "nominal_beta": 1.0,
            "fitted_scale_environment_balanced_median": float(original_adapter.v6_scale_median.median()),
            "effective_beta_environment_balanced_median": float(original_adapter.v6_effective_beta_median.median()),
            "aggregation": "one per environment median over retained active rounds, then median across 16 environments",
        },
        {
            "cohort": "V6-P0-SENTINEL-DEVELOPMENT pre-correction aligned-OOB artifact",
            "strategy": "Original GG label retained for provenance only",
            "environment_count": int(sentinel.environment.nunique()),
            "seed_count": int(sentinel.seed.nunique()),
            "nominal_beta": 1.0,
            "fitted_scale_environment_balanced_median": environment_balanced_median(sentinel, "fitted_scale"),
            "effective_beta_environment_balanced_median": environment_balanced_median(sentinel, "effective_beta"),
            "aggregation": "median within the two expt-gap/RF environments, then median across those environments",
        },
        {
            "cohort": "V5 frozen full universe",
            "strategy": "Selected GG",
            "environment_count": int(selected_v5.environment.nunique()),
            "seed_count": int(selected_v5.seed.nunique()),
            "nominal_beta": 0.5,
            "fitted_scale_environment_balanced_median": environment_balanced_median(selected_v5, "fitted_scale"),
            "effective_beta_environment_balanced_median": environment_balanced_median(selected_v5, "effective_beta"),
            "aggregation": "median within each of 16 task/split/model environments, then median across environments",
        },
        {
            "cohort": "V6 historical adapter paired V5 seed-5000 audit",
            "strategy": "Selected GG",
            "environment_count": int(selected_adapter[["task", "split", "model"]].drop_duplicates().shape[0]),
            "seed_count": 1,
            "nominal_beta": 0.5,
            "fitted_scale_environment_balanced_median": float(selected_adapter.v6_scale_median.median()),
            "effective_beta_environment_balanced_median": float(selected_adapter.v6_effective_beta_median.median()),
            "aggregation": "one per environment median over retained active rounds, then median across 16 environments",
        },
    ]
    table_hash = write_table(rows)
    sentinel_fixed = environment_balanced_median(sentinel, "effective_beta")
    original_v5_value = float(rows[0]["effective_beta_environment_balanced_median"])
    original_adapter_max_abs = float(
        np.max(np.abs(original_adapter.v5_effective_beta_median - original_adapter.v6_effective_beta_median))
    )
    selected_adapter_max_abs = float(
        np.max(np.abs(selected_adapter.v5_effective_beta_median - selected_adapter.v6_effective_beta_median))
    )
    report_04b = f"""# Effective-beta reconciliation

The frozen V5 Original-GG value and the accepted sentinel DRAFT value are not interchangeable. The sentinel records are now explicitly classified as `V6-P0-SENTINEL-DEVELOPMENT`: matbench_expt_gap only, two splits, Random Forest only, seeds 6000–6009, development-only.

## Paired compatibility result

For one frozen V5 seed (5000) in every 16 task/split/model environments, V6 Original-GG and Selected-GG adapters reproduce every retained V5 trajectory field exactly. The maximum absolute difference of the per-environment active-round effective-beta medians is `{original_adapter_max_abs:.17g}` for Original-GG and `{selected_adapter_max_abs:.17g}` for Selected-GG. The full field-level evidence is in `tables/v6_v5_strategy_replay_audit.csv`.

Here, exact trajectory agreement requires exact split, retained round, endpoint, checkpoint-metadata, and canonical-domain checkpoint-model semantics. Raw checkpoint payload bytes are reported separately because the frozen V5 ExtraTrees-compatible serializer is byte-volatile even in a V5 self-replay; that explicitly controlled serialization artifact is not a scientific trajectory difference.

## Aggregated comparison

| cohort / strategy | environments | seeds | nominal beta | fitted-scale environment-balanced median | effective-beta environment-balanced median | aggregation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
"""
    for row in rows:
        report_04b += (
            f"| {row['cohort']} / {row['strategy']} | {row['environment_count']} | {row['seed_count']} | "
            f"{float(row['nominal_beta']):.17g} | {float(row['fitted_scale_environment_balanced_median']):.17g} | "
            f"{float(row['effective_beta_environment_balanced_median']):.17g} | {row['aggregation']} |\n"
        )
    report_04b += f"""

The frozen-manuscript Original-GG summary is approximately 2.938; the V5 full-universe calculation above retains its exact source-specific aggregation. The sentinel DRAFT fixed beta is exactly `{sentinel_fixed:.17g}` and is reproduced from its compact table, but it is a pre-correction aligned-OOB sentinel quantity rather than a transferable V5 Original-GG estimate.

## Mechanistic reconciliation

| item | V5 Original/Selected GG and corrected V6 adapters | accepted sentinel artifact |
| --- | --- | --- |
| scale convention | `effective beta = nominal beta × fitted scale` | same multiplicative convention |
| OOB residual target pairing | frozen V5 query-order target vector (`y[queried]`) paired with OOB predictions after the model's stable-ID ordering | aligned `model.y_train_` pairing used before the correction |
| minimum valid OOB observations | 8 | 8 |
| scale objective | V5 Gaussian-consistent global residual-ratio objective | same named objective but different pairing implementation |
| scale bounds | none | none |
| checkpoint weighting | equal weights for frozen initial/25/50/75% definitions; initial retains V5 `iloc[-1]` execution semantics | same endpoint convention in the accepted artifact |
| environment aggregation | frozen V5 universe versus paired 16-environment audit | two expt-gap/RF environments only |

The discrepancy is not an inverse-scale convention. Scope and aggregation differ, but the decisive implementation mismatch was OOB target ordering: the pre-correction V6 sentinel adapter used aligned targets, whereas frozen V5 uses the historical query-order target vector after the surrogate sorts its training records. The production adapter was corrected before broad development by preserving that legacy order only for named V5-derived GG/CS strategies. The accepted sentinel artifacts were not altered; they remain a clearly labeled, non-transferable development record.

Reconciliation table SHA-256: `{table_hash}`.
"""
    write(ROOT / "reports" / "04b_effective_beta_reconciliation.md", report_04b)

    all_checks = [
        "source_split_hash",
        "target_split_hash",
        "diagnostic_split_hash",
        "initial_labeled_ids",
        "per_round_predictive_mean_raw_sigma",
        "fitted_scale_or_cs_parameters",
        "acquisition_scores",
        "stable_ranking",
        "selected_batch",
        "checkpoint_values",
        "checkpoint_model_semantics",
        "l1_campaign_mace",
        "l4_top1pct_recall_nauc",
        "logical_trajectory_hash",
    ]
    check_text = ", ".join(all_checks)
    report_04c = f"""# Full historical-strategy compatibility

Status: **PASS**. The audit directly compared V6 production-adapter replays with frozen V5 artifacts at seed 5000 across all 16 task/split/model environments: 4 tasks × IID/chemical-system group-disjoint splits × Random Forest/ExtraTrees-compatible ensembles × 4 strategies = 64 cases. All 64 V6 adapter comparisons passed. A separate frozen-V5-runner smoke replay validates the read-only wrapper without duplicating every large reference computation.

## Methods covered

| V5 strategy | V6 adapter |
| --- | --- |
| `gg_ucb_beta_1` | `ORIGINAL_GG` |
| `cs_da_oob_hist` | `HISTORICAL_CS` |
| `gg_ucb_beta_0p5` | `SELECTED_GG` |
| `cs_da_oob_parsimonious_f1` | `SELECTED_CS` |

Each case checked `{check_text}`. For GG, fitted global scale is compared exactly; for CS, the retained candidate-specific scale vectors are compared exactly. The semantic logical trajectory hash combines split hashes, initial labels, retained candidate audit, selected batches, checkpoint values, L1, and L4.

Checkpoint comparison is deliberately two-layered. Checkpoint labels, thresholds, acquisition rounds, queried counts, and realized progress must match exactly; each checkpoint model must also have the same canonical-domain semantic fingerprint (training arrays/IDs, fitted hyperparameters, full-domain predictive mean/raw-standard-deviation, and full-domain leaf/local representation). Raw `joblib` payload hashes are preserved in the audit table but are not included in the semantic trajectory hash: the frozen-V5 self-replay control reproduces Random-Forest bytes but demonstrates that the frozen ExtraTrees-compatible serializer changes bytes despite identical checkpoint semantics and identical scientific trajectory. The control is `results/v6_v5_strategy_replay_audit/checkpoint_serialization_control.json` (SHA-256 `{sha256_file(CHECKPOINT_CONTROL)}`), and contains `{len(checkpoint_control['controls'])}` model controls.

The frozen V5 runner writes only to `results/v6_v5_strategy_replay_audit/frozen_v5_runner_exact`; V6 adapter outputs are stored in model-specific reconciled namespaces under `results/v6_v5_strategy_replay_audit`. No V5 artifact was modified. The audit uses historical seed 5000 only and did not read or run V6 confirmation seeds 7000–7039.

Audit table: `tables/v6_v5_strategy_replay_audit.csv` (SHA-256 `{sha256_file(AUDIT)}`).
"""
    write(ROOT / "reports" / "04c_full_strategy_compatibility.md", report_04c)
    print(json.dumps({"reconciliation_table": OUTPUT_TABLE.relative_to(ROOT).as_posix(), "table_sha256": table_hash}, ensure_ascii=False))


if __name__ == "__main__":
    main()
