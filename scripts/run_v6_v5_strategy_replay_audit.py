"""Run the read-only V5/V6 historical-strategy compatibility audit.

The audit deliberately uses one frozen V5 seed (5000) in every one of the
four tasks × two split protocols × two ensemble implementations.  It first
uses the frozen V5 runner in a V6-owned directory to prove the reference
artifact can be reproduced, then runs the V6 production adapter and compares
the retained trajectory semantics field-by-field.  It never creates or reads
V6 confirmation jobs or seeds 7000--7039.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.production_campaign import ProductionCampaignConfig, run_production_campaign


SEED = 5000
EVIDENCE_CLASS = "V6-HISTORICAL-REPLAY"
TASKS = (
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
)
SPLITS = ("iid_record", "chemical_system_ood")
MODELS = ("random_forest", "extra_randomized_bagging")
STRATEGIES = (
    ("ORIGINAL_GG", "gg_ucb_beta_1", 1.0),
    ("HISTORICAL_CS", "cs_da_oob_hist", 1.0),
    ("SELECTED_GG", "gg_ucb_beta_0p5", 0.5),
    ("SELECTED_CS", "cs_da_oob_parsimonious_f1", 1.0),
)
CHECKPOINTS = ("initial", "25pct", "50pct", "75pct")
# Earlier interrupted adapter attempts are retained for provenance.  A
# reconciled namespace prevents a stale trajectory (whose configuration hash
# intentionally excludes source-code text) from being mistaken for an output
# of the corrected adapter implementation.
ADAPTER_OUTPUT_NAMESPACES = {
    # V7 is a fresh namespace after the bitwise-validated, temporary V5
    # local-feature acceleration.  Output configuration hashes deliberately
    # do not include source text, so retaining an older namespace could mask
    # a code-path change even when the scientific trajectory is identical.
    "random_forest": "v6_production_adapter_reconciled_v7_exact_cs_local_feature_acceleration",
    "extra_randomized_bagging": "v6_production_adapter_reconciled_v7_exact_cs_local_feature_acceleration",
}


# ``ProcessPoolExecutor`` workers persist across several independent cases.
# Reusing one adapter per worker reuses the adapter's read-only task-descriptor
# cache without sharing mutable V5 module state across processes.
_WORKER_ADAPTER: CanonicalV5Adapter | None = None


def worker_adapter() -> CanonicalV5Adapter:
    global _WORKER_ADAPTER
    if _WORKER_ADAPTER is None:
        _WORKER_ADAPTER = CanonicalV5Adapter(ROOT)
    return _WORKER_ADAPTER


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def id_hash(values: np.ndarray) -> str:
    return canonical_hash([str(value) for value in np.asarray(values, dtype=str).tolist()])


def json_id_list(value: object) -> list[str]:
    if isinstance(value, str):
        value = json.loads(value)
    return [str(item) for item in np.asarray(value, dtype=object).tolist()]


def _normalize_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value):
            return {"float": "nan"}
        if math.isinf(value):
            return {"float": "inf" if value > 0 else "-inf"}
        return {"float_hex": value.hex()}
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    return str(value)


def frame_semantic_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    records: list[dict[str, object]] = []
    for row in frame.loc[:, columns].itertuples(index=False, name=None):
        records.append({column: _normalize_scalar(value) for column, value in zip(columns, row, strict=True)})
    return canonical_hash(records)


def exact_frame_equal(left: pd.DataFrame, right: pd.DataFrame, columns: list[str]) -> bool:
    if len(left) != len(right) or any(column not in left or column not in right for column in columns):
        return False
    for column in columns:
        a = left[column].to_numpy()
        b = right[column].to_numpy()
        if pd.api.types.is_float_dtype(left[column]) or pd.api.types.is_float_dtype(right[column]):
            if not np.array_equal(np.asarray(a, float), np.asarray(b, float), equal_nan=True):
                return False
        elif not np.array_equal(np.asarray(a, dtype=object), np.asarray(b, dtype=object)):
            return False
    return True


def active_rounds(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame["round"].astype(int) >= 0].sort_values("round", kind="stable").reset_index(drop=True)


def checkpoint_metadata_semantics(directory: Path) -> dict[str, dict[str, object]]:
    """Read strict checkpoint metadata while excluding volatile payload bytes."""

    fields = (
        "checkpoint_label",
        "checkpoint_threshold",
        "acquisition_round",
        "queried_count",
        "realized_campaign_progress",
    )
    output: dict[str, dict[str, object]] = {}
    for label in CHECKPOINTS:
        payload = json.loads((directory / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
        output[label] = {field: payload.get(field) for field in fields}
    return output


def checkpoint_binary_hashes(directory: Path) -> dict[str, str]:
    """Return raw payload hashes and reject internally inconsistent checkpoints."""

    output: dict[str, str] = {}
    for label in CHECKPOINTS:
        metadata = json.loads((directory / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
        payload = directory / f"checkpoint_{label}.joblib"
        digest = sha256_file(payload)
        if metadata.get("model_state_hash") != digest:
            raise RuntimeError(f"checkpoint payload/metadata hash mismatch: {directory}/{label}")
        output[label] = digest
    return output


def _update_array_digest(digest: Any, *, name: str, values: object) -> None:
    """Append an exact, platform-independent ndarray representation to a digest."""

    array = np.asarray(values)
    if array.dtype.hasobject:
        raise TypeError(f"semantic checkpoint fingerprint does not permit object dtype: {name}")
    # The V5 runs are little-endian, but normalize explicitly so the fingerprint
    # remains a scientific comparison rather than a host-endianness comparison.
    normalized = np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<"), copy=False))
    header = json.dumps(
        {"name": name, "dtype": normalized.dtype.str, "shape": list(normalized.shape)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(normalized.tobytes(order="C"))


def canonical_domain_model_hash(model: Any, X: np.ndarray) -> str:
    """Fingerprint the model on all canonical rows used by the campaign.

    This is stricter than comparing observed trajectory rows: it includes
    training data/IDs, fitted hyperparameters, full-domain mean/std outputs,
    and the full-domain leaf/local representation.  It therefore covers every
    source, target, and diagnostic prediction the V5 campaign can consume,
    while avoiding raw pickle bytes that V5 cannot reproduce for ExtraTrees.
    """

    required = ("predict_mean_std", "leaf_or_local_representation", "X_train_", "y_train_", "stable_ids_")
    missing = [name for name in required if not hasattr(model, name)]
    if missing:
        raise TypeError(f"checkpoint model lacks canonical semantic fields: {missing}")
    canonical_X = np.asarray(X, dtype=float)
    mean, raw_std = model.predict_mean_std(canonical_X)
    leaves = model.leaf_or_local_representation(canonical_X)
    hyperparameters = {
        "model_type": f"{type(model).__module__}.{type(model).__qualname__}",
        "n_estimators": _normalize_scalar(getattr(model, "n_estimators", None)),
        "min_samples_leaf": _normalize_scalar(getattr(model, "min_samples_leaf", None)),
        "n_jobs": _normalize_scalar(getattr(model, "n_jobs", None)),
        "seed": _normalize_scalar(getattr(model, "seed_", None)),
    }
    digest = hashlib.sha256()
    digest.update(b"v6-canonical-domain-model-semantic-fingerprint-v1\0")
    digest.update(json.dumps(hyperparameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    for name, values in (
        ("X_train", model.X_train_),
        ("y_train", model.y_train_),
        ("stable_ids", model.stable_ids_),
        ("canonical_domain_predictive_mean", mean),
        ("canonical_domain_raw_predictive_std", raw_std),
        ("canonical_domain_leaf_or_local_representation", leaves),
    ):
        _update_array_digest(digest, name=name, values=values)
    return digest.hexdigest()


def checkpoint_model_semantics(directory: Path, X: np.ndarray) -> dict[str, str]:
    """Fingerprint every retained checkpoint model on the full canonical domain."""

    output: dict[str, str] = {}
    for label in CHECKPOINTS:
        output[label] = canonical_domain_model_hash(joblib.load(directory / f"checkpoint_{label}.joblib"), X)
    return output


def strategy_reference_row(manifest: pd.DataFrame, *, task: str, split: str, model: str, v5_strategy: str) -> pd.Series:
    rows = manifest.loc[
        (manifest.task.astype(str) == task)
        & (manifest.split_protocol.astype(str) == split)
        & (manifest.model.astype(str) == model)
        & (manifest.strategy.astype(str) == v5_strategy)
        & (manifest.seed.astype(int) == SEED)
    ]
    if len(rows) != 1:
        raise RuntimeError(
            f"expected one V5 row for {task}/{split}/{model}/{v5_strategy}/seed{SEED}, found {len(rows)}"
        )
    return rows.iloc[0]


def scale_median(*, strategy: str, rounds: pd.DataFrame, selected: pd.DataFrame) -> float:
    if strategy in {"ORIGINAL_GG", "SELECTED_GG"}:
        return float(np.median(rounds["global_scale"].to_numpy(float)))
    return float(np.median(selected["scale"].to_numpy(float)))


def v6_scale_median(*, strategy: str, rounds: pd.DataFrame, audit: pd.DataFrame) -> float:
    if strategy in {"ORIGINAL_GG", "SELECTED_GG"}:
        return float(np.median(rounds["fitted_scale_median"].to_numpy(float)))
    return float(np.median(audit["scale"].to_numpy(float)))


def reference_endpoints(adapter: CanonicalV5Adapter, directory: Path) -> tuple[float, float]:
    return float(adapter._l1(directory)), float(adapter._l4(directory))


def semantic_logical_hash(
    *,
    split_hashes: dict[str, str],
    initial_ids: list[str],
    selected: pd.DataFrame,
    rounds: pd.DataFrame,
    checkpoint_metadata: dict[str, dict[str, object]],
    checkpoint_model_hashes: dict[str, str],
    endpoints: tuple[float, float],
    selected_columns: list[str],
) -> str:
    selected_payload = json.loads(
        json.dumps(
            [
                {
                    column: _normalize_scalar(value)
                    for column, value in zip(selected_columns, row, strict=True)
                }
                for row in selected.loc[:, selected_columns].itertuples(index=False, name=None)
            ],
            sort_keys=True,
        )
    )
    rounds_payload = [json_id_list(value) for value in rounds["selected_batch_ids"].tolist()]
    return canonical_hash(
        {
            "split_hashes": split_hashes,
            "initial_labeled_ids": initial_ids,
            "retained_candidate_audit": selected_payload,
            "selected_batches": rounds_payload,
            "checkpoint_metadata": checkpoint_metadata,
            "checkpoint_model_semantic_hashes": checkpoint_model_hashes,
            "l1_campaign_mace_hex": float(endpoints[0]).hex(),
            "l4_top1pct_recall_nauc_hex": float(endpoints[1]).hex(),
        }
    )


def compare_adapter(
    *,
    adapter: CanonicalV5Adapter,
    v5_row: pd.Series,
    v6_strategy: str,
    v5_strategy: str,
    beta: float,
    output_root: Path,
    run_frozen_v5_runner: bool,
) -> dict[str, object]:
    task = str(v5_row.task)
    split = str(v5_row.split_protocol)
    model = str(v5_row.model)
    reference = adapter.paths.v5_root / str(v5_row.expected_output_relative_path)
    output_id = "v6_historical_adapter__" + "__".join((task, split, model, v6_strategy.lower(), f"seed{SEED}"))
    exact = (
        adapter.replay_historical_strategy(
            job_id=str(v5_row.job_id), output_root=output_root / "frozen_v5_runner_exact"
        )
        if run_frozen_v5_runner
        else None
    )
    result = run_production_campaign(
        ProductionCampaignConfig(
            job_id=output_id,
            task=task,
            split_protocol=split,
            model=model,
            strategy=v6_strategy,
            seed=SEED,
            evidence_class=EVIDENCE_CLASS,
            beta=beta,
            phase="historical_replay",
            manifest_sha256="v6-v5-historical-strategy-compatibility-audit-v1",
            v5_strategy=v5_strategy,
        ),
        output_root=output_root / ADAPTER_OUTPUT_NAMESPACES[model],
        adapter=adapter,
    )
    production = Path(str(result["output_dir"]))
    v5_rounds = active_rounds(pd.read_parquet(reference / "rounds.parquet"))
    v6_rounds = active_rounds(pd.read_parquet(production / "rounds.parquet"))
    v5_selected = pd.read_parquet(reference / "selected.parquet").sort_values(["round", "rank"], kind="stable").reset_index(drop=True)
    v6_selected = pd.read_parquet(production / "round_audit.parquet").sort_values(["round", "rank"], kind="stable").reset_index(drop=True)
    v5_trace = json.loads((reference / "state.json").read_text(encoding="utf-8"))
    v6_trace = json.loads((production / "trajectory.json").read_text(encoding="utf-8"))
    # Loading checkpoint joblib payloads requires the frozen V5 modules to be
    # registered before unpickling.  ``v5_run_config`` also gives the complete
    # canonical descriptor domain used by every source/target/diagnostic call.
    _ = adapter.modules
    frame, canonical_X, split_data, _ = adapter.v5_run_config(task, split, SEED, v5_strategy, model=model)
    ids = frame.material_id.to_numpy(str)
    expected_split_hashes = {
        "source": id_hash(ids[split_data.source]),
        "target": id_hash(ids[split_data.target]),
        "diagnostic": id_hash(ids[split_data.diagnostic]),
    }
    v5_initial = json_id_list(v5_rounds.iloc[0]["queried_ids_before"])
    v6_initial = [str(value) for value in v6_trace["initial_labeled_ids"]]
    predictive_columns = [
        "round",
        "rank",
        "candidate_id",
        "predicted_mean",
        "raw_predicted_std",
        "effective_predicted_std",
    ]
    candidate_scale_columns = ["round", "rank", "candidate_id", "scale"]
    score_columns = ["round", "rank", "candidate_id", "score"]
    ranking_columns = ["round", "rank", "candidate_id", "stable_candidate_id", "selected"]
    selected_columns = predictive_columns + ["scale", "score", "stable_candidate_id", "selected"]
    if v6_strategy in {"ORIGINAL_GG", "SELECTED_GG"}:
        v5_scale_rounds = v5_rounds.loc[:, ["round", "global_scale", "scale_status"]].rename(
            columns={"global_scale": "fitted_scale"}
        )
        v6_scale_rounds = v6_rounds.loc[:, ["round", "fitted_scale_median", "scale_status"]].rename(
            columns={"fitted_scale_median": "fitted_scale"}
        )
        scale_check = exact_frame_equal(
            v5_scale_rounds,
            v6_scale_rounds,
            ["round", "fitted_scale", "scale_status"],
        )
    else:
        scale_check = exact_frame_equal(v5_selected, v6_selected, candidate_scale_columns)
    v5_checkpoint_metadata = checkpoint_metadata_semantics(reference)
    v6_checkpoint_metadata = checkpoint_metadata_semantics(production)
    v5_checkpoint_binary = checkpoint_binary_hashes(reference)
    v6_checkpoint_binary = checkpoint_binary_hashes(production)
    v5_checkpoint_models = checkpoint_model_semantics(reference, canonical_X)
    v6_checkpoint_models = checkpoint_model_semantics(production, canonical_X)
    v5_endpoints = reference_endpoints(adapter, reference)
    v6_endpoints = (float(result["l1_campaign_mace"]), float(result["l4_top1pct_recall_nauc"]))
    checks = {
        "source_split_hash": v6_trace.get("source_ids_hash") == expected_split_hashes["source"],
        "target_split_hash": v6_trace.get("target_ids_hash") == expected_split_hashes["target"],
        "diagnostic_split_hash": v6_trace.get("diagnostic_ids_hash") == expected_split_hashes["diagnostic"],
        "initial_labeled_ids": v5_initial == v6_initial,
        "per_round_predictive_mean_raw_sigma": exact_frame_equal(v5_selected, v6_selected, predictive_columns),
        "fitted_scale_or_cs_parameters": scale_check,
        "acquisition_scores": exact_frame_equal(v5_selected, v6_selected, score_columns),
        "stable_ranking": exact_frame_equal(v5_selected, v6_selected, ranking_columns),
        "selected_batch": [json_id_list(value) for value in v5_rounds["selected_batch_ids"].tolist()]
        == [json_id_list(value) for value in v6_rounds["selected_batch_ids"].tolist()],
        "checkpoint_values": v5_checkpoint_metadata == v6_checkpoint_metadata,
        "checkpoint_model_semantics": v5_checkpoint_models == v6_checkpoint_models,
        # Preserved as an explicit diagnostic, but deliberately excluded from
        # the required semantic checks below.  The frozen V5 ExtraTrees
        # serializer produces different raw bytes in a V5 self-replay.
        "checkpoint_model_state_hash_bytes": v5_checkpoint_binary == v6_checkpoint_binary,
        "l1_campaign_mace": v5_endpoints[0] == v6_endpoints[0],
        "l4_top1pct_recall_nauc": v5_endpoints[1] == v6_endpoints[1],
    }
    v5_semantic = semantic_logical_hash(
        split_hashes=expected_split_hashes,
        initial_ids=v5_initial,
        selected=v5_selected,
        rounds=v5_rounds,
        checkpoint_metadata=v5_checkpoint_metadata,
        checkpoint_model_hashes=v5_checkpoint_models,
        endpoints=v5_endpoints,
        selected_columns=selected_columns,
    )
    v6_semantic = semantic_logical_hash(
        split_hashes={
            "source": str(v6_trace.get("source_ids_hash")),
            "target": str(v6_trace.get("target_ids_hash")),
            "diagnostic": str(v6_trace.get("diagnostic_ids_hash")),
        },
        initial_ids=v6_initial,
        selected=v6_selected,
        rounds=v6_rounds,
        checkpoint_metadata=v6_checkpoint_metadata,
        checkpoint_model_hashes=v6_checkpoint_models,
        endpoints=v6_endpoints,
        selected_columns=selected_columns,
    )
    checks["logical_trajectory_hash"] = v5_semantic == v6_semantic
    ordered_checks = (
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
    first = next((check for check in ordered_checks if not checks[check]), "")
    v5_scale = scale_median(strategy=v6_strategy, rounds=v5_rounds, selected=v5_selected)
    v6_scale = v6_scale_median(strategy=v6_strategy, rounds=v6_rounds, audit=v6_selected)
    if exact is None:
        frozen_v5_runner_raw_bytes_equal: object = "not_run_full_adapter_audit"
        frozen_v5_runner_checkpoint_semantics_equal: object = "not_run_full_adapter_audit"
        frozen_v5_runner_semantic_trajectory_equal: object = "not_run_full_adapter_audit"
        frozen_v5_runner_raw_logical_hash_equal: object = "not_run_full_adapter_audit"
    else:
        rerun = Path(exact.output_dir)
        rerun_rounds = active_rounds(pd.read_parquet(rerun / "rounds.parquet"))
        rerun_selected = pd.read_parquet(rerun / "selected.parquet").sort_values(
            ["round", "rank"], kind="stable"
        ).reset_index(drop=True)
        rerun_initial = json_id_list(rerun_rounds.iloc[0]["queried_ids_before"])
        rerun_metadata = checkpoint_metadata_semantics(rerun)
        rerun_binary = checkpoint_binary_hashes(rerun)
        rerun_models = checkpoint_model_semantics(rerun, canonical_X)
        rerun_endpoints = reference_endpoints(adapter, rerun)
        rerun_semantic = semantic_logical_hash(
            split_hashes=expected_split_hashes,
            initial_ids=rerun_initial,
            selected=rerun_selected,
            rounds=rerun_rounds,
            checkpoint_metadata=rerun_metadata,
            checkpoint_model_hashes=rerun_models,
            endpoints=rerun_endpoints,
            selected_columns=selected_columns,
        )
        frozen_v5_runner_raw_bytes_equal = v5_checkpoint_binary == rerun_binary
        frozen_v5_runner_checkpoint_semantics_equal = (
            v5_checkpoint_metadata == rerun_metadata and v5_checkpoint_models == rerun_models
        )
        # ``exact.passed`` retains frozen V5's historical raw-pickle logical
        # hash condition.  The explicit semantic control below demonstrates
        # whether every scientific field remains exact without that byte-level
        # serialization artifact.
        frozen_v5_runner_semantic_trajectory_equal = bool(
            all(bool(value) for name, value in exact.checks.items() if name != "logical_trajectory_hash")
            and frozen_v5_runner_checkpoint_semantics_equal
            and v5_semantic == rerun_semantic
        )
        frozen_v5_runner_raw_logical_hash_equal = bool(exact.checks.get("logical_trajectory_hash", False))
    return {
        "v5_job_id": str(v5_row.job_id),
        "v6_job_id": output_id,
        "task": task,
        "split": split,
        "model": model,
        "seed": SEED,
        "v5_strategy": v5_strategy,
        "v6_strategy": v6_strategy,
        "nominal_beta": float(beta),
        "v5_scale_median": v5_scale,
        "v6_scale_median": v6_scale,
        "v5_effective_beta_median": float(beta * v5_scale),
        "v6_effective_beta_median": float(beta * v6_scale),
        "v5_l1_campaign_mace": v5_endpoints[0],
        "v6_l1_campaign_mace": v6_endpoints[0],
        "v5_l4_top1pct_recall_nauc": v5_endpoints[1],
        "v6_l4_top1pct_recall_nauc": v6_endpoints[1],
        "frozen_v5_runner_exact_replay": "not_run_full_adapter_audit" if exact is None else bool(exact.passed),
        "frozen_v5_runner_raw_checkpoint_bytes_equal": frozen_v5_runner_raw_bytes_equal,
        "frozen_v5_runner_checkpoint_model_semantics_equal": frozen_v5_runner_checkpoint_semantics_equal,
        "frozen_v5_runner_semantic_trajectory_equal": frozen_v5_runner_semantic_trajectory_equal,
        "frozen_v5_runner_raw_logical_hash_equal": frozen_v5_runner_raw_logical_hash_equal,
        "v5_exact_logical_hash": adapter._logical_trajectory_hash(reference),
        "v5_rerun_exact_logical_hash": "" if exact is None else exact.replay_hashes["logical_trajectory_sha256"],
        "v5_v6_semantic_logical_hash": v5_semantic,
        "v6_semantic_logical_hash": v6_semantic,
        "v5_checkpoint_metadata": json.dumps(v5_checkpoint_metadata, sort_keys=True),
        "v6_checkpoint_metadata": json.dumps(v6_checkpoint_metadata, sort_keys=True),
        "v5_checkpoint_model_semantic_hashes": json.dumps(v5_checkpoint_models, sort_keys=True),
        "v6_checkpoint_model_semantic_hashes": json.dumps(v6_checkpoint_models, sort_keys=True),
        "v5_checkpoint_model_state_hashes": json.dumps(v5_checkpoint_binary, sort_keys=True),
        "v6_checkpoint_model_state_hashes": json.dumps(v6_checkpoint_binary, sort_keys=True),
        "v5_exact_replay_output": "" if exact is None else str(Path(exact.output_dir).relative_to(ROOT)),
        "v6_adapter_output": str(production.relative_to(ROOT)),
        "first_divergence": first,
        "passed": bool(all(checks[name] for name in ordered_checks)),
        **checks,
    }


def _run_case_in_isolated_process(
    case: tuple[pd.Series, str, str, float],
    output_root_text: str,
    run_frozen_v5_runner: bool,
) -> dict[str, object]:
    """Run one independent adapter comparison in its own Python process.

    Candidate-specific V5 strategy fitting is Python-heavy.  A process pool
    therefore avoids the interpreter lock while keeping all outputs confined
    to distinct V6-owned job directories.  The worker never writes under the
    frozen V5 root.
    """

    row, v6_strategy, v5_strategy, beta = case
    try:
        return compare_adapter(
            adapter=worker_adapter(),
            v5_row=row,
            v6_strategy=v6_strategy,
            v5_strategy=v5_strategy,
            beta=beta,
            output_root=Path(output_root_text),
            run_frozen_v5_runner=run_frozen_v5_runner,
        )
    except Exception as exc:  # Record failures in the audit rather than concealing a block.
        return {
            "v5_job_id": str(row.job_id),
            "v6_job_id": "",
            "task": str(row.task),
            "split": str(row.split_protocol),
            "model": str(row.model),
            "seed": SEED,
            "v5_strategy": v5_strategy,
            "v6_strategy": v6_strategy,
            "nominal_beta": beta,
            "first_divergence": f"{type(exc).__name__}: {exc}",
            "passed": False,
            "exception_traceback_sha256": canonical_hash(traceback.format_exc()),
        }


def write_table(path: Path, rows: list[dict[str, object]]) -> str:
    frame = pd.DataFrame(rows).sort_values(
        ["task", "split", "model", "v6_strategy"], kind="stable"
    ).reset_index(drop=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, float_format="%.17g", lineterminator="\n")
    os.replace(temporary, path)
    return sha256_file(path)


def main(
    *,
    workers: int = 1,
    smoke: bool = False,
    smoke_cases: int = 1,
    model_filter: str | None = None,
    run_frozen_v5_runner: bool = False,
) -> None:
    if SEED >= 7000:
        raise RuntimeError("historical audit must never use a confirmation seed")
    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority locks failed before historical compatibility audit")
    manifest = pd.read_csv(adapter.paths.v5_manifest)
    cases: list[tuple[pd.Series, str, str, float]] = []
    for task in TASKS:
        for split in SPLITS:
            for model in MODELS:
                for v6_strategy, v5_strategy, beta in STRATEGIES:
                    cases.append(
                        (
                            strategy_reference_row(manifest, task=task, split=split, model=model, v5_strategy=v5_strategy),
                            v6_strategy,
                            v5_strategy,
                            beta,
                        )
                    )
    if model_filter is not None:
        if model_filter not in MODELS:
            raise ValueError(f"unknown model filter: {model_filter}")
        cases = [case for case in cases if str(case[0].model) == model_filter]
        if not cases:
            raise RuntimeError("model filter selected no historical cases")
    if smoke:
        if smoke_cases < 1:
            raise ValueError("smoke case count must be positive")
        cases = cases[:smoke_cases]
    output_root = ROOT / "results" / "v6_v5_strategy_replay_audit"
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    if workers < 1:
        raise ValueError("workers must be positive")
    if workers == 1:
        for case in cases:
            rows.append(
                _run_case_in_isolated_process(
                    case,
                    str(output_root),
                    run_frozen_v5_runner or smoke,
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _run_case_in_isolated_process,
                    case,
                    str(output_root),
                    run_frozen_v5_runner or smoke,
                )
                for case in cases
            ]
            for future in as_completed(futures):
                rows.append(future.result())
    table_path = ROOT / "tables" / "v6_v5_strategy_replay_audit.csv"
    table_hash = write_table(table_path, rows)
    completed = int(sum(bool(row["passed"]) for row in rows))
    control_path = output_root / "checkpoint_serialization_control.json"
    control_rows = [
        row
        for row in rows
        if row.get("frozen_v5_runner_raw_checkpoint_bytes_equal") != "not_run_full_adapter_audit"
    ]
    if control_rows:
        existing_controls: dict[str, dict[str, object]] = {}
        if control_path.is_file():
            previous = json.loads(control_path.read_text(encoding="utf-8"))
            for item in previous.get("controls", []):
                if isinstance(item, dict) and "v5_job_id" in item:
                    existing_controls[str(item["v5_job_id"])] = item
        for row in control_rows:
            existing_controls[str(row["v5_job_id"])] = {
                "v5_job_id": str(row["v5_job_id"]),
                "model": str(row["model"]),
                "v5_strategy": str(row["v5_strategy"]),
                "raw_checkpoint_bytes_equal": bool(row["frozen_v5_runner_raw_checkpoint_bytes_equal"]),
                "raw_logical_hash_equal": bool(row["frozen_v5_runner_raw_logical_hash_equal"]),
                "checkpoint_model_semantics_equal": bool(row["frozen_v5_runner_checkpoint_model_semantics_equal"]),
                "semantic_trajectory_equal": bool(row["frozen_v5_runner_semantic_trajectory_equal"]),
            }
        control = {
            "schema_version": "v6-v5-checkpoint-serialization-control-v1",
            "purpose": (
                "Demonstrate whether raw checkpoint joblib bytes are reproducible under a frozen-V5 self-replay "
                "before excluding raw bytes from the required V5/V6 semantic trajectory comparison."
            ),
            "raw_binary_hash_is_required_semantic_criterion": False,
            "required_checkpoint_semantics": (
                "exact metadata plus canonical-domain model fingerprints: training arrays/IDs, hyperparameters, "
                "full-domain mean/std, and full-domain leaf/local representation"
            ),
            "controls": [existing_controls[key] for key in sorted(existing_controls)],
            "interpretation": (
                "A false raw-byte equality paired with true semantic equality is recorded as serializer byte volatility, "
                "not a V5/V6 scientific trajectory divergence."
            ),
        }
        temporary_control = control_path.with_suffix(control_path.suffix + ".tmp")
        temporary_control.write_text(
            json.dumps(control, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary_control, control_path)
    control_hash = sha256_file(control_path) if control_path.is_file() else "not_yet_created"
    summary = {
        "schema_version": "v6-v5-full-strategy-compatibility-audit-v1",
        "status": "SMOKE_PASS" if smoke and completed == len(rows) else ("PASS" if completed == len(rows) and len(rows) == 64 else "FAIL"),
        "evidence_class": EVIDENCE_CLASS,
        "historical_seed": SEED,
        "confirmation_seed_range_not_read_or_run": [7000, 7039],
        "coverage": {
            "tasks": list(TASKS),
            "splits": list(SPLITS),
            "models": list(MODELS),
            "strategies": [strategy for strategy, _, _ in STRATEGIES],
            "expected_jobs": 64,
            "audited_jobs": len(rows),
            "passed_jobs": completed,
            "failed_jobs": len(rows) - completed,
        },
        "frozen_v5_runner_replay_policy": (
            "all selected cases" if run_frozen_v5_runner else "serialization control only when explicitly requested or in smoke mode"
        ),
        "checkpoint_comparison_policy": {
            "required": [
                "checkpoint_values",
                "checkpoint_model_semantics",
                "logical_trajectory_hash",
            ],
            "reported_but_not_required": "checkpoint_model_state_hash_bytes",
            "reason": (
                "frozen V5 ExtraTrees checkpoint joblib bytes are not reproducible under a frozen-V5 self-replay; "
                "the serialization control records the distinction explicitly"
            ),
            "serialization_control": control_path.relative_to(ROOT).as_posix() if control_path.is_file() else "not_yet_created",
            "serialization_control_sha256": control_hash,
        },
        "audit_table": table_path.relative_to(ROOT).as_posix(),
        "audit_table_sha256": table_hash,
    "v5_authority": authority,
    }
    summary_path = output_root / "compatibility_summary.json"
    temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary["status"] not in {"PASS", "SMOKE_PASS"}:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--smoke", action="store_true", help="run only one environment/strategy case")
    parser.add_argument(
        "--smoke-cases",
        type=int,
        default=1,
        help="number of leading cases for a non-confirmatory worker smoke check",
    )
    parser.add_argument("--model", choices=MODELS, help="restrict a diagnostic audit invocation to one model")
    parser.add_argument("--run-frozen-v5-runner", action="store_true", help="also rerun the frozen V5 runner for every selected case")
    arguments = parser.parse_args()
    main(
        workers=arguments.workers,
        smoke=arguments.smoke,
        smoke_cases=arguments.smoke_cases,
        model_filter=arguments.model,
        run_frozen_v5_runner=arguments.run_frozen_v5_runner,
    )
