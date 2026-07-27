"""P0 development manifest, execution, and descriptive selection analysis.

The module has an intentionally narrow boundary: it only accepts seeds
6000--6009 and only creates V6-owned development outputs.  It provides no
confirmation manifest or confirmation execution code.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .calibration_replay import CalibrationReplayConfig, run_calibration_replay
from .canonical_adapter import CanonicalV5Adapter
from .execution_registry import CanonicalJobRegistry, atomic_write_json_no_overwrite, sha256_file
from .production_campaign import ProductionCampaignConfig, run_production_campaign
from .registry_freeze import code_tree_sha256, current_git_commit
from .selection import fit_matched_beta_map


WORKSPACE = Path(__file__).resolve().parents[2]
P0_SEEDS = tuple(range(6000, 6010))
P0_ENVIRONMENTS = (
    {"task": "matbench_expt_gap", "split_protocol": "iid_record", "model": "random_forest"},
    {"task": "matbench_expt_gap", "split_protocol": "chemical_system_ood", "model": "random_forest"},
)
BASE_TRAJECTORY_STRATEGIES = ("RAW", "ORIGINAL_GG", "HISTORICAL_CS", "SELECTED_CS")
CALIBRATION_REPLAY_STRATEGIES = (
    "IDENTITY_CONTROL",
    "GG_CALIBRATION_ONLY",
    "CS_CALIBRATION_ONLY",
    "SCALAR_TEMPERATURE_NLL",
    "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
    "POWER_SCALING",
    "ISOTONIC_ABS_RESIDUAL",
    "CONFORMAL_INTERVAL_ONLY",
    "CONFORMAL_GAUSSIAN_EQUIVALENT",
    "SELECTED_CS_EQUIVALENT_DOF_CONTROL",
    "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL",
)
POST_SELECTION_TRAJECTORY_STRATEGIES = (
    "SELECTED_GG",
    "RAW_FIXED_BETA_MATCHED",
    "RAW_STAGE_BETA_MATCHED",
)


def _environment_id(row: dict[str, str]) -> str:
    return "__".join((row["task"], row["split_protocol"], row["model"]))


def _job_id(environment: dict[str, str], strategy: str, seed: int) -> str:
    return f"v6_p0__{_environment_id(environment)}__{strategy.lower()}__seed{int(seed)}"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_csv_once(rows: list[dict[str, object]], path: Path) -> str:
    if not rows:
        raise ValueError("P0 manifest must contain jobs")
    columns = list(rows[0])
    if any(list(row) != columns for row in rows):
        raise ValueError("manifest rows use inconsistent columns")
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode("utf-8")
    digest = _sha256_bytes(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if sha256_file(path) != digest:
            raise FileExistsError(f"refusing to overwrite divergent P0 manifest: {path}")
        return digest
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return digest


def _manifest_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for environment in P0_ENVIRONMENTS:
        for seed in P0_SEEDS:
            raw_id = _job_id(environment, "RAW", seed)
            for strategy in BASE_TRAJECTORY_STRATEGIES:
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, seed),
                        "job_kind": "trajectory",
                        "execution_phase": "base",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": seed,
                        "evidence_class": "V6-MECH",
                        "dependency_job_id": "",
                        "beta_rule": "raw_beta_1",
                    }
                )
            for strategy in CALIBRATION_REPLAY_STRATEGIES:
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, seed),
                        "job_kind": "calibration_replay",
                        "execution_phase": "base",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": seed,
                        "evidence_class": "V6-MECH",
                        "dependency_job_id": raw_id,
                        "beta_rule": "exact_RAW_acquisition",
                    }
                )
            for strategy in POST_SELECTION_TRAJECTORY_STRATEGIES:
                beta_rule = {
                    "SELECTED_GG": "fixed_beta_from_DRAFT_selection_map",
                    "RAW_FIXED_BETA_MATCHED": "fixed_matched_beta_from_DRAFT_selection_map",
                    "RAW_STAGE_BETA_MATCHED": "stage_matched_beta_from_DRAFT_selection_map",
                }[strategy]
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, seed),
                        "job_kind": "trajectory",
                        "execution_phase": "post_selection",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": seed,
                        "evidence_class": "V6-MECH",
                        "dependency_job_id": "",
                        "beta_rule": beta_rule,
                    }
                )
    return rows


def _validate_manifest_rows(rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    job_ids = [str(row["job_id"]) for row in rows]
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("P0 manifest has duplicate job IDs")
    seeds = {int(row["seed"]) for row in rows}
    if seeds != set(P0_SEEDS):
        raise ValueError("P0 manifest does not use exactly the registered development seeds")
    if any(int(row["seed"]) not in P0_SEEDS for row in rows):
        raise ValueError("P0 manifest leaked a non-development seed")
    if not all(row["execution_phase"] in {"base", "post_selection"} for row in rows):
        raise ValueError("P0 manifest contains an unregistered execution phase")
    if not all(str(row["evidence_class"]) == "V6-MECH" for row in rows):
        raise ValueError("P0 manifest contains a non-mechanistic evidence class")


def generate_p0_manifest(
    *,
    workspace: str | Path = WORKSPACE,
    adapter: CanonicalV5Adapter | None = None,
) -> dict[str, object]:
    """Generate the immutable P0 design manifest without executing a job."""

    workspace = Path(workspace).resolve()
    rows = _manifest_rows()
    _validate_manifest_rows(rows)
    manifest_path = workspace / "manifests" / "v6_p0_development_manifest.csv"
    manifest_hash = _write_csv_once(rows, manifest_path)
    adapter = adapter or CanonicalV5Adapter(workspace)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    v5_lock = adapter.validate_v5_authority_locks()
    if not v5_lock["passed"]:
        raise RuntimeError("V5 authority locks failed; P0 manifest cannot be released")
    lock = {
        "schema_version": "v6-p0-development-manifest-lock-v1",
        "status": "PRE_DEVELOPMENT_LOCKED_NOT_EXECUTED",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_before_stage_2_5_commit": current_git_commit(workspace),
        "manifest_path": manifest_path.relative_to(workspace).as_posix(),
        "manifest_sha256": manifest_hash,
        "manifest_job_count": len(rows),
        "development_seed_range": [min(P0_SEEDS), max(P0_SEEDS)],
        "seed_collision_check": "passed_exactly_6000_6009",
        "v6_code_tree_sha256": code_tree_sha256(workspace / "src" / "transportability_v6"),
        "v5_source_lock": adapter.source_lock_status(),
        "v5_authority_lock": v5_lock,
        "p0_environment_scope": [_environment_id(item) for item in P0_ENVIRONMENTS],
        "execution_boundary": "development only; no confirmation execution capability",
    }
    payload = dict(lock)
    lock["immutable_lock_sha256"] = _sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    lock_path = workspace / "locks" / "v6_p0_development_manifest_lock.json"
    if lock_path.exists():
        existing = json.loads(lock_path.read_text(encoding="utf-8"))
        if existing.get("immutable_lock_sha256") != lock["immutable_lock_sha256"]:
            raise FileExistsError(f"refusing to overwrite divergent P0 lock: {lock_path}")
    else:
        temporary = lock_path.with_suffix(lock_path.suffix + ".tmp")
        temporary.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, lock_path)
    return {"manifest_path": str(manifest_path), "lock_path": str(lock_path), **lock}


def _read_manifest(workspace: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    manifest_path = workspace / "manifests" / "v6_p0_development_manifest.csv"
    lock_path = workspace / "locks" / "v6_p0_development_manifest_lock.json"
    if not manifest_path.is_file() or not lock_path.is_file():
        raise FileNotFoundError("P0 manifest and lock must be generated before execution")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if sha256_file(manifest_path) != lock.get("manifest_sha256"):
        raise RuntimeError("P0 manifest hash does not match its lock")
    frame = pd.read_csv(manifest_path, dtype={"seed": int}).fillna("")
    _validate_manifest_rows(frame.to_dict("records"))
    return frame, lock


def _write_registry_snapshot(registry: CanonicalJobRegistry, output_root: Path) -> pd.DataFrame:
    snapshot = registry.snapshot_frame()
    path = output_root / "registry_snapshot.csv"
    temporary = path.with_suffix(path.suffix + ".tmp")
    snapshot.to_csv(temporary, index=False)
    os.replace(temporary, path)
    return snapshot


def _run_row(
    row: pd.Series,
    *,
    manifest_sha256: str,
    trajectory_root: Path,
    evaluation_root: Path,
    adapter: CanonicalV5Adapter,
    selection: dict[str, object] | None,
) -> dict[str, object]:
    common = {
        "job_id": str(row.job_id),
        "task": str(row.task),
        "split_protocol": str(row.split_protocol),
        "model": str(row.model),
        "strategy": str(row.strategy),
        "seed": int(row.seed),
        "evidence_class": str(row.evidence_class),
        "phase": "development",
        "manifest_sha256": manifest_sha256,
    }
    if row.job_kind == "calibration_replay":
        return run_calibration_replay(
            CalibrationReplayConfig(source_job_id=str(row.dependency_job_id), **common),
            trajectory_root=trajectory_root,
            output_root=evaluation_root,
            adapter=adapter,
        )
    beta = 1.0
    stage_beta_map = None
    if row.execution_phase == "post_selection":
        if selection is None:
            raise RuntimeError("post-selection job was scheduled without a DRAFT selection map")
        if row.strategy == "RAW_STAGE_BETA_MATCHED":
            stage_beta_map = dict(selection["stage_matched_beta"])
            beta = float(selection["fixed_matched_beta"])
        else:
            beta = float(selection["fixed_matched_beta"])
    return run_production_campaign(
        ProductionCampaignConfig(beta=beta, stage_beta_map=stage_beta_map, **common),
        output_root=trajectory_root,
        adapter=adapter,
    )


def _result_hash(result: dict[str, object]) -> str:
    directory = Path(str(result["output_dir"]))
    trace = directory / "trajectory.json"
    return sha256_file(trace) if trace.is_file() else _sha256_bytes(json.dumps(result, sort_keys=True).encode())


def _execute_phase(
    rows: pd.DataFrame,
    *,
    registry: CanonicalJobRegistry,
    manifest_sha256: str,
    trajectory_root: Path,
    evaluation_root: Path,
    adapter: CanonicalV5Adapter,
    selection: dict[str, object] | None,
    max_retries: int = 2,
) -> None:
    for row in rows.itertuples(index=False):
        connection = registry.connect()
        try:
            source = str(getattr(row, "dependency_job_id", ""))
            if source:
                source_row = connection.execute("SELECT status FROM jobs WHERE job_id=?", (source,)).fetchone()
                if source_row is None or source_row[0] != "COMPLETED":
                    registry.transition(
                        connection,
                        row.job_id,
                        "EXCLUDED_WITH_REASON",
                        {"last_error": "required RAW source job did not complete"},
                    )
                    continue
            claimed = registry.claim_specific(connection, row.job_id, "p0-sequential-worker", os.getpid(), "localhost")
            del claimed
            for attempt in range(max_retries + 1):
                try:
                    result = _run_row(
                        pd.Series(row._asdict()),
                        manifest_sha256=manifest_sha256,
                        trajectory_root=trajectory_root,
                        evaluation_root=evaluation_root,
                        adapter=adapter,
                        selection=selection,
                    )
                    registry.transition(
                        connection,
                        row.job_id,
                        "COMPLETED",
                        {"output_path": str(result["output_dir"]), "output_hash": _result_hash(result)},
                    )
                    break
                except Exception as exc:
                    failure = traceback.format_exc()
                    registry.transition(
                        connection,
                        row.job_id,
                        "FAILED",
                        {
                            "last_error": f"{type(exc).__name__}: {exc}; traceback_sha256="
                            + _sha256_bytes(failure.encode("utf-8")),
                        },
                    )
                    if attempt >= max_retries:
                        break
                    registry.transition(
                        connection,
                        row.job_id,
                        "PLANNED",
                        {"last_error": "unchanged automatic retry"},
                        allow_retry=True,
                    )
                    registry.claim_specific(connection, row.job_id, "p0-sequential-worker", os.getpid(), "localhost")
        finally:
            connection.close()


def _collect_original_gg_beta(rows: pd.DataFrame, trajectory_root: Path) -> pd.DataFrame:
    extracted: list[pd.DataFrame] = []
    selected = rows[(rows.strategy == "ORIGINAL_GG") & (rows.execution_phase == "base")]
    for row in selected.itertuples(index=False):
        path = trajectory_root / row.job_id / "rounds.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"original GG output unavailable for beta selection: {path}")
        frame = pd.read_parquet(path)
        required = {"round", "budget_fraction", "effective_beta_median"}
        if not required <= set(frame):
            raise ValueError("original GG rounds lack registered effective beta summaries")
        frame = frame.loc[frame["round"] >= 0, ["budget_fraction", "effective_beta_median"]].copy()
        frame["environment"] = _environment_id(row._asdict())
        frame["seed"] = int(row.seed)
        frame = frame.rename(columns={"effective_beta_median": "effective_beta"})
        extracted.append(frame)
    if not extracted:
        raise ValueError("no completed Original GG rows available for beta selection")
    return pd.concat(extracted, ignore_index=True)


def _balanced_winner(frame: pd.DataFrame, strategy_column: str, value_column: str) -> tuple[str, dict[str, float]]:
    summaries: dict[str, float] = {}
    for strategy, group in frame.groupby(strategy_column, sort=True):
        summaries[str(strategy)] = float(group.groupby("environment", sort=True)[value_column].median().median())
    if not summaries:
        return "", {}
    return min(summaries, key=lambda key: (summaries[key], key)), summaries


def _collect_simple_l1(rows: pd.DataFrame, evaluation_root: Path) -> pd.DataFrame:
    subset = rows[
        (rows.job_kind == "calibration_replay")
        & rows.strategy.isin(["IDENTITY_CONTROL", "SCALAR_TEMPERATURE_NLL", "SCALAR_TEMPERATURE_RESIDUAL_RATIO"])
    ]
    records: list[dict[str, object]] = []
    for row in subset.itertuples(index=False):
        trace = evaluation_root / row.job_id / "trajectory.json"
        if not trace.is_file():
            continue
        payload = json.loads(trace.read_text(encoding="utf-8"))
        records.append(
            {
                "environment": _environment_id(row._asdict()),
                "seed": int(row.seed),
                "strategy": str(row.strategy),
                "l1_campaign_mace": float(payload["endpoints"]["l1_campaign_mace"]),
            }
        )
    return pd.DataFrame(records)


def _write_draft_selection_map(
    *,
    workspace: Path,
    manifest_sha256: str,
    beta_selection: dict[str, object],
    simple_l1: pd.DataFrame,
    status: str,
) -> dict[str, object]:
    winner, scores = _balanced_winner(simple_l1, "strategy", "l1_campaign_mace")
    payload: dict[str, object] = {
        "schema_version": "v6-selection-map-draft-v2",
        "status": status,
        "confirmation_outcomes_inspected": False,
        "development_seed_range": [min(P0_SEEDS), max(P0_SEEDS)],
        "manifest_sha256": manifest_sha256,
        "selection": beta_selection,
        "simple_scaling_development_summary": {
            "criterion": "minimum environment-balanced median L1 MACE; development only",
            "selected_strategy_draft": winner or None,
            "environment_balanced_median_l1": scores,
        },
        "source_hashes": {
            "v6_code_tree_sha256": code_tree_sha256(workspace / "src" / "transportability_v6"),
            "v5_authority_lock_sha256": sha256_file(workspace / "locks" / "v5_frozen_manifest.json"),
        },
        "unresolved": [
            "DRAFT only: no confirmation selection map has been frozen.",
            "P0 sentinel coverage does not establish transfer to the remaining V5 task/model universe.",
        ],
    }
    payload["draft_selection_map_sha256"] = _sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    path = workspace / "analysis_plan" / "v6_selection_map_DRAFT.json"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload


def execute_p0_development(*, workspace: str | Path = WORKSPACE) -> dict[str, object]:
    """Run the already locked P0 development manifest and nothing beyond it."""

    workspace = Path(workspace).resolve()
    rows, lock = _read_manifest(workspace)
    if code_tree_sha256(workspace / "src" / "transportability_v6") != lock["v6_code_tree_sha256"]:
        raise RuntimeError("V6 code tree changed after the P0 lock; regenerate and recommit before execution")
    adapter = CanonicalV5Adapter(workspace)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority lock failed before P0 execution")
    output_root = workspace / "results" / "v6_development"
    trajectory_root = output_root / "trajectories"
    evaluation_root = output_root / "calibration_replays"
    trajectory_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    registry = CanonicalJobRegistry(output_root / "job_registry.sqlite", adapter=adapter)
    connection = registry.initialize(rows.job_id.astype(str).tolist(), str(lock["manifest_sha256"]))
    connection.close()
    base = rows[rows.execution_phase == "base"]
    _execute_phase(
        base[base.job_kind == "trajectory"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        selection=None,
    )
    _execute_phase(
        base[base.job_kind == "calibration_replay"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        selection=None,
    )
    snapshot = _write_registry_snapshot(registry, output_root)
    failures = snapshot[snapshot.status == "FAILED"]
    if len(failures):
        return {
            "status": "FAILED_BASE_P0_DEVELOPMENT",
            "planned": len(rows),
            "completed": int((snapshot.status == "COMPLETED").sum()),
            "failed": int(len(failures)),
            "registry_snapshot": str(output_root / "registry_snapshot.csv"),
        }
    beta_frame = _collect_original_gg_beta(rows, trajectory_root)
    beta_selection = fit_matched_beta_map(beta_frame)
    preliminary = _write_draft_selection_map(
        workspace=workspace,
        manifest_sha256=str(lock["manifest_sha256"]),
        beta_selection=beta_selection,
        simple_l1=_collect_simple_l1(rows, evaluation_root),
        status="DRAFT_BETA_MAP_READY_P0_POST_SELECTION_PENDING",
    )
    _execute_phase(
        rows[rows.execution_phase == "post_selection"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        selection=dict(preliminary["selection"]),
    )
    snapshot = _write_registry_snapshot(registry, output_root)
    final = _write_draft_selection_map(
        workspace=workspace,
        manifest_sha256=str(lock["manifest_sha256"]),
        beta_selection=beta_selection,
        simple_l1=_collect_simple_l1(rows, evaluation_root),
        status="DRAFT_P0_DEVELOPMENT_ANALYSIS_COMPLETE_NOT_CONFIRMATION_FROZEN",
    )
    summary = {
        "schema_version": "v6-p0-development-execution-summary-v1",
        "status": "COMPLETED" if not (snapshot.status == "FAILED").any() else "COMPLETED_WITH_FAILURES",
        "planned": int(len(rows)),
        "completed": int((snapshot.status == "COMPLETED").sum()),
        "failed": int((snapshot.status == "FAILED").sum()),
        "excluded": int((snapshot.status == "EXCLUDED_WITH_REASON").sum()),
        "manifest_sha256": lock["manifest_sha256"],
        "registry_snapshot": (output_root / "registry_snapshot.csv").relative_to(workspace).as_posix(),
        "selection_map": (workspace / "analysis_plan" / "v6_selection_map_DRAFT.json").relative_to(workspace).as_posix(),
        "selection_map_sha256": final["draft_selection_map_sha256"],
        "completed_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json_no_overwrite(summary, output_root / "execution_summary.json")
    return summary


def selection_stability_summary(*, workspace: str | Path = WORKSPACE) -> dict[str, object]:
    """Produce a descriptive P0 stability summary; no confirmatory p values."""

    workspace = Path(workspace).resolve()
    output_root = workspace / "results" / "v6_development"
    trajectory_root = output_root / "trajectories"
    evaluation_root = output_root / "calibration_replays"
    rows, lock = _read_manifest(workspace)
    beta = _collect_original_gg_beta(rows, trajectory_root)
    leave_one_seed_out: dict[str, dict[str, float]] = {}
    for seed in P0_SEEDS:
        fit = fit_matched_beta_map(beta.loc[beta.seed != seed])
        leave_one_seed_out[str(seed)] = {
            "fixed_matched_beta": float(fit["fixed_matched_beta"]),
            **{f"stage_{name}": float(value) for name, value in fit["stage_matched_beta"].items()},
        }
    simple = _collect_simple_l1(rows, evaluation_root)
    winner, scores = _balanced_winner(simple, "strategy", "l1_campaign_mace")
    winner_counts: dict[str, int] = {}
    for seed in P0_SEEDS:
        candidate, _ = _balanced_winner(simple.loc[simple.seed != seed], "strategy", "l1_campaign_mace")
        if candidate:
            winner_counts[candidate] = winner_counts.get(candidate, 0) + 1
    payload = {
        "schema_version": "v6-p0-selection-stability-v1",
        "status": "DESCRIPTIVE_DEVELOPMENT_ONLY",
        "manifest_sha256": lock["manifest_sha256"],
        "environment_scope": [_environment_id(item) for item in P0_ENVIRONMENTS],
        "seed_count": len(P0_SEEDS),
        "matched_beta_leave_one_seed_out": leave_one_seed_out,
        "simple_scaler_selected_draft": winner or None,
        "simple_scaler_environment_balanced_median_l1": scores,
        "simple_scaler_leave_one_seed_out_winner_count": winner_counts,
        "limitations": [
            "P0 uses development data and is descriptive for selection only.",
            "The future 40-pair confirmation completeness gate is not invoked here.",
            "Only the two declared expt-gap sentinel environments are covered.",
        ],
    }
    path = output_root / "p0_selection_stability.json"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload
