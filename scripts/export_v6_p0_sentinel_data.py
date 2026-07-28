"""Export a compact, hash-locked audit layer for the accepted sentinel cohort.

The script is intentionally read-only with respect to the 360 original job
artifacts.  It writes derived tables, locks, and a byte-identical archive of
the pre-existing DRAFT selection map.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.execution_registry import sha256_file
from transportability_v6.registry_freeze import code_tree_sha256


EVIDENCE_CLASS = "V6-P0-SENTINEL-DEVELOPMENT"
MANIFEST = ROOT / "manifests" / "v6_p0_development_manifest.csv"
LOCK = ROOT / "locks" / "v6_p0_development_manifest_lock.json"
OUTPUT = ROOT / "results" / "v6_development"
FINAL_RUN = OUTPUT / "recovered_base_then_matched_beta_retry"
TABLES = ROOT / "tables"
LOCKS = ROOT / "locks"


def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def write_once(path: Path, content: bytes, *, refresh: bool = False) -> str:
    digest = hashlib.sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if sha256_file(path) != digest:
            if not refresh:
                raise FileExistsError(f"refusing to overwrite divergent compact artifact: {path}")
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(content)
            os.replace(temporary, path)
        return digest
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return digest


def write_frame(path: Path, frame: pd.DataFrame, *, refresh: bool = False) -> tuple[str, list[str]]:
    ordered = frame.copy()
    content = ordered.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    return write_once(path, content, refresh=refresh), list(ordered.columns)


def frame_bytes(frame: pd.DataFrame) -> tuple[bytes, list[str]]:
    """Serialize a compact table exactly as ``write_frame`` would, without writing."""

    ordered = frame.copy()
    return (
        ordered.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8"),
        list(ordered.columns),
    )


def read_registry(path: Path) -> pd.DataFrame:
    connection = sqlite3.connect(path)
    try:
        return pd.read_sql_query("SELECT * FROM jobs ORDER BY job_id", connection)
    finally:
        connection.close()


def environment_id(row: pd.Series | dict[str, object]) -> str:
    return "__".join((str(row["task"]), str(row["split_protocol"]), str(row["model"])))


def source_hash(trace: dict[str, Any], registry_row: pd.Series) -> str:
    if "source_trajectory_sha256" in trace:
        return str(trace["source_trajectory_sha256"])
    return str(registry_row["output_hash"])


def top1_discovery_counts(row: pd.Series, output_dir: Path, adapter: CanonicalV5Adapter) -> str:
    if str(row["job_kind"]) != "trajectory":
        return json.dumps({"status": "not_applicable_calibration_replay"}, sort_keys=True)
    rounds = pd.read_parquet(output_dir / "rounds.parquet").sort_values("round", kind="stable")
    _, _, split, _ = adapter.v5_run_config(
        str(row["task"]), str(row["split_protocol"]), int(row["seed"]), "raw_ucb_beta_1", model=str(row["model"])
    )
    top_count = max(1, int(math.ceil(len(split.target) * 0.01)))
    values: dict[str, int] = {}
    for label, threshold in (("initial", 0.0), ("25pct", 0.25), ("50pct", 0.50), ("75pct", 0.75), ("final", 1.0)):
        subset = rounds.loc[rounds["budget_fraction"].astype(float) >= threshold - 1e-12]
        selected = subset.iloc[-1] if label == "final" else subset.iloc[0]
        values[label] = int(round(float(selected["top1_recall"]) * top_count))
    values["top1_target_set_size"] = top_count
    return json.dumps(values, sort_keys=True)


def endpoint_table(manifest: pd.DataFrame, final_registry: pd.DataFrame, final_lock: dict[str, Any], adapter: CanonicalV5Adapter) -> pd.DataFrame:
    registry = final_registry.set_index("job_id")
    rows: list[dict[str, object]] = []
    for item in manifest.sort_values("job_id", kind="stable").itertuples(index=False):
        row = pd.Series(item._asdict())
        stored = registry.loc[str(row.job_id)]
        trace = json.loads((Path(str(stored.output_path)) / "trajectory.json").read_text(encoding="utf-8"))
        endpoints = dict(trace.get("endpoints", {}))
        rows.append(
            {
                "job_id": str(row.job_id),
                "task": str(row.task),
                "split": str(row.split_protocol),
                "model": str(row.model),
                "strategy": str(row.strategy),
                "seed": int(row.seed),
                "evidence_class": EVIDENCE_CLASS,
                "l1_campaign_mace": endpoints.get("l1_campaign_mace", np.nan),
                "l4_top1pct_recall_nauc": endpoints.get("l4_top1pct_recall_nauc", np.nan),
                "fixed_budget_discovery_counts": top1_discovery_counts(row, Path(str(stored.output_path)), adapter),
                "completion_status": str(stored.status),
                "source_trajectory_sha256": source_hash(trace, stored),
                "artifact_trace_sha256": sha256_file(Path(str(stored.output_path)) / "trajectory.json"),
                "endpoint_generation_code_sha256": str(final_lock["v6_code_tree_sha256"]),
            }
        )
    return pd.DataFrame(rows)


def ordered_labels_before_round(row: pd.Series, trace: dict[str, Any], rounds: pd.DataFrame, adapter: CanonicalV5Adapter) -> list[int]:
    frame, _, _, _ = adapter.v5_run_config(
        str(row.task), str(row.split_protocol), int(row.seed), "raw_ucb_beta_1", model=str(row.model)
    )
    lookup = {str(value): index for index, value in enumerate(frame.material_id.to_numpy(str))}
    ordered = [lookup[str(value)] for value in trace["initial_labeled_ids"]]
    return ordered


def effective_beta_table(manifest: pd.DataFrame, final_registry: pd.DataFrame, adapter: CanonicalV5Adapter) -> pd.DataFrame:
    registry = final_registry.set_index("job_id")
    output: list[dict[str, object]] = []
    subset = manifest.loc[(manifest.strategy == "ORIGINAL_GG") & (manifest.execution_phase == "base")]
    # Preserve the original P0 collector's manifest and parquet row order.  The
    # accompanying hexadecimal fields make the compact CSV a lossless source for
    # the selection reduction, rather than merely a display-oriented export.
    source_row_order = 0
    for item in subset.itertuples(index=False):
        row = pd.Series(item._asdict())
        stored = registry.loc[str(row.job_id)]
        directory = Path(str(stored.output_path))
        trace = json.loads((directory / "trajectory.json").read_text(encoding="utf-8"))
        rounds = pd.read_parquet(directory / "rounds.parquet")
        frame, X, _, config = adapter.v5_run_config(
            str(row.task), str(row.split_protocol), int(row.seed), "raw_ucb_beta_1", model=str(row.model)
        )
        y = frame.target.to_numpy(float)
        stable = np.arange(len(frame), dtype=np.int64)
        ids = frame.material_id.to_numpy(str)
        lookup = {str(value): index for index, value in enumerate(ids)}
        queried = [lookup[str(value)] for value in trace["initial_labeled_ids"]]
        for record in rounds.itertuples(index=False):
            if int(record.round) < 0:
                continue
            code = 11 if str(row.model) == "random_forest" else 17
            model_seed = int(np.random.SeedSequence([int(row.seed), int(record.round), code]).generate_state(1)[0])
            model = adapter.modules["surrogates"].make_surrogate(
                str(row.model),
                n_estimators=int(config["model"]["n_estimators"]),
                min_samples_leaf=int(config["model"]["min_samples_leaf"]),
                n_jobs=1,
            )
            model.fit(X[queried], y[queried], model_seed, stable[queried])
            mean, sigma, counts = model.oob_or_crossfit_predict_mean_std()
            valid = np.isfinite(mean) & np.isfinite(sigma) & (counts >= 8)
            reconstructed, status = adapter.modules["strategies"].gaussian_global_scale(
                mean, sigma, model.y_train_, counts, 8, float(config["oob"]["uncertainty_floor"])
            )
            stored_beta = float(record.effective_beta_median)
            if not np.isclose(reconstructed, stored_beta, rtol=0.0, atol=1e-12):
                raise AssertionError(f"sentinel Original GG scale reconstruction diverged for {row.job_id} round {record.round}")
            output.append(
                {
                    "source_row_order": source_row_order,
                    "environment": environment_id(row),
                    "strategy": "ORIGINAL_GG",
                    "seed": int(row.seed),
                    "round": int(record.round),
                    "budget_fraction": float(record.budget_fraction),
                    "budget_fraction_hex": float(record.budget_fraction).hex(),
                    "fitted_scale": float(reconstructed),
                    "fitted_scale_hex": float(reconstructed).hex(),
                    "nominal_beta": 1.0,
                    "nominal_beta_hex": float(1.0).hex(),
                    "effective_beta": stored_beta,
                    "effective_beta_hex": stored_beta.hex(),
                    "valid_oob_observation_count": int(valid.sum()),
                    "fallback_status": str(status),
                    "source_trajectory_sha256": str(stored.output_hash),
                    "oob_residual_order": "aligned_model_training_order_pre_correction_sentinel",
                }
            )
            source_row_order += 1
            selected = getattr(record, "selected_batch_ids")
            if isinstance(selected, str):
                selected_ids = json.loads(selected)
            else:
                selected_ids = np.asarray(selected, dtype=object).tolist()
            queried.extend(lookup[str(value)] for value in selected_ids)
    return pd.DataFrame(output)


def simple_scaler_inputs(manifest: pd.DataFrame, final_registry: pd.DataFrame) -> pd.DataFrame:
    registry = final_registry.set_index("job_id")
    strategies = {"IDENTITY_CONTROL", "SCALAR_TEMPERATURE_NLL", "SCALAR_TEMPERATURE_RESIDUAL_RATIO"}
    rows: list[dict[str, object]] = []
    subset = manifest.loc[(manifest.job_kind == "calibration_replay") & manifest.strategy.isin(strategies)]
    source_row_order = 0
    for item in subset.itertuples(index=False):
        manifest_row = pd.Series(item._asdict())
        registry_row = registry.loc[str(manifest_row.job_id)]
        trace = json.loads((Path(str(registry_row.output_path)) / "trajectory.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "source_row_order": source_row_order,
                "environment": environment_id(manifest_row),
                "task": str(manifest_row.task),
                "split": str(manifest_row.split_protocol),
                "model": str(manifest_row.model),
                "seed": int(manifest_row.seed),
                "strategy": str(manifest_row.strategy),
                "l1_campaign_mace": float(trace["endpoints"]["l1_campaign_mace"]),
                "l1_campaign_mace_hex": float(trace["endpoints"]["l1_campaign_mace"]).hex(),
                "source_job_id": str(trace["source_job_id"]),
                "source_trajectory_sha256": str(trace["source_trajectory_sha256"]),
                "calibration_trace_sha256": sha256_file(Path(str(registry_row.output_path)) / "trajectory.json"),
                "evidence_class": EVIDENCE_CLASS,
            }
        )
        source_row_order += 1
    return pd.DataFrame(rows)


def balanced_summary(frame: pd.DataFrame) -> tuple[str, dict[str, float], dict[str, int]]:
    values = {
        str(strategy): float(group.groupby("environment", sort=True)["l1_campaign_mace"].median().median())
        for strategy, group in frame.groupby("strategy", sort=True)
    }
    winner = min(values, key=lambda key: (values[key], key))
    wins: dict[str, int] = {}
    for seed in sorted(set(frame.seed.astype(int))):
        subset = frame.loc[frame.seed.astype(int) != seed]
        scores = {
            str(strategy): float(group.groupby("environment", sort=True)["l1_campaign_mace"].median().median())
            for strategy, group in subset.groupby("strategy", sort=True)
        }
        selected = min(scores, key=lambda key: (scores[key], key))
        wins[selected] = wins.get(selected, 0) + 1
    return winner, values, wins


def selection_summary(
    draft: dict[str, Any], beta: pd.DataFrame, simple: pd.DataFrame, final_lock: dict[str, Any]
) -> pd.DataFrame:
    winner, scores, wins = balanced_summary(simple)
    expected = {
        "fixed_matched_beta": float(draft["selection"]["fixed_matched_beta"]),
        "stage_matched_beta": draft["selection"]["stage_matched_beta"],
        "simple_scaling_environment_balanced_median_l1": scores,
        "simple_scaling_leave_one_seed_out_winner_count": wins,
        "simple_scaling_observed_descriptive_minimum": winner,
    }
    metadata = {
        key: value
        for key, value in draft.items()
        if key not in {"selection", "simple_scaling_development_summary", "draft_selection_map_sha256"}
    }
    rows = [
        {"record_type": "metadata", "name": "draft_payload_metadata", "value_json": json.dumps(metadata, sort_keys=True)},
        {"record_type": "source", "name": "effective_beta_table", "value_json": json.dumps({"row_count": int(len(beta))}, sort_keys=True)},
        {"record_type": "expected", "name": "selection_values", "value_json": json.dumps(expected, sort_keys=True)},
        {"record_type": "provenance", "name": "final_sentinel_lock", "value_json": json.dumps({"immutable_lock_sha256": final_lock["immutable_lock_sha256"], "manifest_sha256": final_lock["manifest_sha256"]}, sort_keys=True)},
    ]
    return pd.DataFrame(rows)


def recovery_inventory(manifest: pd.DataFrame, final_registry: pd.DataFrame) -> pd.DataFrame:
    prior_path = OUTPUT / "rerun_after_simple_scaler_mapping_fix" / "job_registry.sqlite"
    prior = read_registry(prior_path).set_index("job_id")
    final = final_registry.set_index("job_id")
    rows: list[dict[str, object]] = []
    for job_id in sorted(final.index.astype(str)):
        current = final.loc[job_id]
        previous = prior.loc[job_id] if job_id in prior.index else None
        reused = "verified reuse" in str(current.get("last_error", "")).lower()
        rows.append(
            {
                "job_id": job_id,
                "final_status": str(current.status),
                "final_output_path": str(current.output_path),
                "final_output_sha256": str(current.output_hash),
                "reuse_class": "verified_base_reuse" if reused else "recomputed_post_selection",
                "source_run_id": "rerun_after_simple_scaler_mapping_fix" if reused else "",
                "source_status": "" if previous is None else str(previous.status),
                "source_output_path": "" if previous is None else str(previous.output_path),
                "source_output_sha256": "" if previous is None else str(previous.output_hash),
                "source_final_hash_match": bool(reused and previous is not None and str(previous.output_hash) == str(current.output_hash)),
            }
        )
    return pd.DataFrame(rows)


def job_artifact_inventory(manifest: pd.DataFrame, final_registry: pd.DataFrame) -> pd.DataFrame:
    kinds = manifest.set_index("job_id")["job_kind"].to_dict()
    rows: list[dict[str, object]] = []
    for record in final_registry.sort_values("job_id", kind="stable").itertuples(index=False):
        directory = Path(str(record.output_path))
        files = [
            directory / "trajectory.json",
            directory / "rounds.parquet",
            directory / "diagnostic_metrics.parquet",
            directory / "round_audit.parquet",
            directory / "checkpoint_initial.joblib",
            directory / "checkpoint_25pct.joblib",
            directory / "checkpoint_50pct.joblib",
            directory / "checkpoint_75pct.joblib",
        ]
        inventory = {
            file.name: sha256_file(file)
            for file in files
            if file.is_file()
        }
        rows.append(
            {
                "job_id": str(record.job_id),
                "job_kind": str(kinds[str(record.job_id)]),
                "completion_status": str(record.status),
                "output_path": str(record.output_path),
                "registry_output_sha256": str(record.output_hash),
                "artifact_file_sha256_json": json.dumps(inventory, sort_keys=True),
                "artifact_inventory_sha256": canonical_hash(inventory),
            }
        )
    return pd.DataFrame(rows)


def compact_table_lock(path: Path, digest: str, columns: list[str], row_count: int, final_lock: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-sentinel-compact-table-lock-v1",
        "status": "V6_P0_SENTINEL_DEVELOPMENT_COMPACT_TABLE_LOCKED",
        "evidence_class": EVIDENCE_CLASS,
        "table_path": path.relative_to(ROOT).as_posix(),
        "table_sha256": digest,
        "row_count": int(row_count),
        "columns": columns,
        "final_sentinel_lock_sha256": str(final_lock["immutable_lock_sha256"]),
        "source_v6_code_tree_sha256": str(final_lock["v6_code_tree_sha256"]),
    }
    payload["table_lock_sha256"] = canonical_hash(payload)
    return payload


def main(*, refresh: bool = False, verify_only: bool = False) -> None:
    if refresh and verify_only:
        raise ValueError("--refresh and --verify-only are mutually exclusive")
    final_lock = json.loads(LOCK.read_text(encoding="utf-8"))
    manifest = pd.read_csv(MANIFEST, dtype={"seed": int}).fillna("")
    final_registry = read_registry(FINAL_RUN / "job_registry.sqlite")
    if len(final_registry) != 360 or set(final_registry.status.astype(str)) != {"COMPLETED"}:
        raise RuntimeError("accepted sentinel run is not a completed 360-job registry")
    draft_path = ROOT / "analysis_plan" / "v6_selection_map_DRAFT.json"
    sentinel_archive = ROOT / "analysis_plan" / "v6_selection_map_SENTINEL_DRAFT.json"
    draft_bytes = draft_path.read_bytes()
    if sentinel_archive.exists() and sentinel_archive.read_bytes() != draft_bytes:
        raise FileExistsError("sentinel archive exists but differs from the accepted DRAFT map")
    if not sentinel_archive.exists():
        temporary = sentinel_archive.with_suffix(sentinel_archive.suffix + ".tmp")
        temporary.write_bytes(draft_bytes)
        os.replace(temporary, sentinel_archive)
    if sha256_file(draft_path) != sha256_file(sentinel_archive):
        raise AssertionError("sentinel archive is not byte-identical to the accepted DRAFT map")
    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    tables: list[tuple[Path, pd.DataFrame]] = []
    tables.append((TABLES / "v6_p0_sentinel_seed_endpoints.csv", endpoint_table(manifest, final_registry, final_lock, adapter)))
    beta = effective_beta_table(manifest, final_registry, adapter)
    tables.append((TABLES / "v6_p0_sentinel_round_effective_beta.csv", beta))
    simple = simple_scaler_inputs(manifest, final_registry)
    tables.append((TABLES / "v6_p0_sentinel_simple_scaler_inputs.csv", simple))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    tables.append((TABLES / "v6_p0_sentinel_selection_summary.csv", selection_summary(draft, beta, simple, final_lock)))
    tables.append((TABLES / "v6_p0_sentinel_recovery_hash_inventory.csv", recovery_inventory(manifest, final_registry)))
    tables.append((TABLES / "v6_p0_sentinel_job_artifact_inventory.csv", job_artifact_inventory(manifest, final_registry)))
    aggregate: list[dict[str, Any]] = []
    for path, frame in tables:
        content, columns = frame_bytes(frame)
        digest = hashlib.sha256(content).hexdigest()
        if verify_only:
            if not path.is_file() or sha256_file(path) != digest:
                raise RuntimeError(f"compact table bytes do not reproduce: {path}")
        else:
            digest, columns = write_frame(path, frame, refresh=refresh)
        lock = compact_table_lock(path, digest, columns, len(frame), final_lock)
        per_table_lock = LOCKS / f"{path.stem}_lock.json"
        lock_bytes = (json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if verify_only:
            if not per_table_lock.is_file() or per_table_lock.read_bytes() != lock_bytes:
                raise RuntimeError(f"compact table lock does not reproduce: {per_table_lock}")
        else:
            write_once(per_table_lock, lock_bytes, refresh=refresh)
        aggregate.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest, "row_count": int(len(frame)), "lock_path": per_table_lock.relative_to(ROOT).as_posix(), "lock_sha256": lock["table_lock_sha256"]})
    aggregate_path = LOCKS / "v6_p0_sentinel_compact_tables_lock.json"
    if verify_only:
        if not aggregate_path.is_file():
            raise FileNotFoundError("compact-table aggregate lock is missing")
        existing = json.loads(aggregate_path.read_text(encoding="utf-8"))
        recorded_hash = str(existing.pop("compact_tables_lock_sha256", ""))
        if recorded_hash != canonical_hash(existing):
            raise RuntimeError("compact-table aggregate lock has an invalid self-hash")
        required = {
            "schema_version": "v6-p0-sentinel-compact-tables-lock-v1",
            "status": "V6_P0_SENTINEL_DEVELOPMENT_COMPACT_DATA_LOCKED",
            "evidence_class": EVIDENCE_CLASS,
            "archive_selection_map_path": sentinel_archive.relative_to(ROOT).as_posix(),
            "archive_selection_map_sha256": sha256_file(sentinel_archive),
            "tables": aggregate,
            "final_sentinel_lock_sha256": final_lock["immutable_lock_sha256"],
        }
        mismatches = {
            key: {"expected": value, "observed": existing.get(key)}
            for key, value in required.items()
            if existing.get(key) != value
        }
        if mismatches:
            raise RuntimeError(f"compact-table aggregate lock does not reproduce: {mismatches}")
        print(
            json.dumps(
                {
                    "status": "VERIFY_PASS",
                    "archive": sentinel_archive.relative_to(ROOT).as_posix(),
                    "tables": aggregate,
                    "aggregate_lock_sha256": recorded_hash,
                    "aggregate_recorded_v6_code_tree_sha256": existing.get("current_v6_code_tree_sha256"),
                    "current_v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
                },
                indent=2,
            )
        )
        return
    aggregate_payload: dict[str, Any] = {
        "schema_version": "v6-p0-sentinel-compact-tables-lock-v1",
        "status": "V6_P0_SENTINEL_DEVELOPMENT_COMPACT_DATA_LOCKED",
        "evidence_class": EVIDENCE_CLASS,
        "archive_selection_map_path": sentinel_archive.relative_to(ROOT).as_posix(),
        "archive_selection_map_sha256": sha256_file(sentinel_archive),
        "tables": aggregate,
        "final_sentinel_lock_sha256": final_lock["immutable_lock_sha256"],
        "current_v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
    }
    aggregate_payload["compact_tables_lock_sha256"] = canonical_hash(aggregate_payload)
    write_once(
        aggregate_path,
        (json.dumps(aggregate_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        refresh=refresh,
    )
    print(json.dumps({"archive": sentinel_archive.relative_to(ROOT).as_posix(), "tables": aggregate}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="replace only prior generated compact-table bytes")
    parser.add_argument("--verify-only", action="store_true", help="recompute and verify compact tables/locks without writing")
    arguments = parser.parse_args()
    main(refresh=arguments.refresh, verify_only=arguments.verify_only)
