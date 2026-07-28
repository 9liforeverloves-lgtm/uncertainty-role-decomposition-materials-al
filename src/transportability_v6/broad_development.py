"""Prospective, non-confirmatory V6 P0 broad-development workflow.

This module is deliberately separate from the accepted expt-gap sentinel
cohort.  It accepts only seeds 6100--6109, covers the 16 V5 environments, and
never creates confirmation jobs or reads confirmation outputs.
"""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import traceback
from typing import Any, Iterable

import pandas as pd

from .calibration_replay import CalibrationReplayConfig, run_calibration_replay
from .canonical_adapter import CanonicalV5Adapter
from .execution_registry import CanonicalJobRegistry, sha256_file
from .production_campaign import ProductionCampaignConfig, run_production_campaign
from .registry_freeze import code_tree_sha256, current_git_commit
from .selection import fit_matched_beta_map


WORKSPACE = Path(__file__).resolve().parents[2]
BROAD_SEEDS = tuple(range(6100, 6110))
CANARY_SEED = 6099
EVIDENCE_CLASS = "V6-P0-BROAD-DEVELOPMENT"
CANARY_EVIDENCE_CLASS = "V6-CANARY"

TASKS = (
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
)
SPLITS = ("iid_record", "chemical_system_ood")
MODELS = ("random_forest", "extra_randomized_bagging")
ENVIRONMENTS = tuple(
    {"task": task, "split_protocol": split, "model": model}
    for task in TASKS
    for split in SPLITS
    for model in MODELS
)

# Full campaigns can alter the acquisition path.  Calibration-only rows have
# an explicit RAW dependency and are evaluated at immutable RAW checkpoints.
FULL_BASE_STRATEGIES = (
    "RAW",
    "ORIGINAL_GG",
    "HISTORICAL_CS",
    "SELECTED_GG",
    "SELECTED_CS",
    "GG_ACQUISITION_ONLY",
    "CS_ACQUISITION_ONLY",
)
CALIBRATION_REPLAY_STRATEGIES = (
    "IDENTITY_CONTROL",
    "GG_CALIBRATION_ONLY",
    "CS_CALIBRATION_ONLY",
    "SCALAR_TEMPERATURE_NLL",
    "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
    "POWER_SCALING",
    "ISOTONIC_ABS_RESIDUAL",
    "CONFORMAL_INTERVAL_ONLY",
)
POST_SELECTION_FULL_STRATEGIES = (
    "RAW_FIXED_BETA_MATCHED",
    "RAW_STAGE_BETA_MATCHED",
)

SIMPLE_SCALER_ROLES = {
    "IDENTITY_CONTROL": "negative_implementation_control_not_scaling_winner",
    "SCALAR_TEMPERATURE_RESIDUAL_RATIO": "candidate_simple_nonidentity_scalar_baseline",
    "SCALAR_TEMPERATURE_NLL": "prespecified_mechanistic_scalar_baseline",
    "POWER_SCALING": "flexible_parametric_secondary_baseline",
    "ISOTONIC_ABS_RESIDUAL": "monotonic_nonparametric_secondary_baseline",
    "CONFORMAL_INTERVAL_ONLY": "L1_calibration_only_secondary_no_universal_acquisition_sigma",
}


# Process workers keep one adapter so immutable task descriptors can be reused
# safely within a worker without sharing V5 module globals across processes.
_BROAD_WORKER_ADAPTERS: dict[str, CanonicalV5Adapter] = {}


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    return _sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _environment_id(environment: dict[str, str]) -> str:
    return "__".join((environment["task"], environment["split_protocol"], environment["model"]))


def _job_id(environment: dict[str, str], strategy: str, seed: int, *, prefix: str = "v6_p0_broad") -> str:
    return f"{prefix}__{_environment_id(environment)}__{strategy.lower()}__seed{int(seed)}"


def _write_bytes_once(path: Path, content: bytes) -> str:
    digest = _sha256_bytes(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if sha256_file(path) != digest:
            raise FileExistsError(f"refusing to overwrite divergent prospective artifact: {path}")
        return digest
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return digest


def _write_csv_once(rows: list[dict[str, object]], path: Path) -> str:
    if not rows:
        raise ValueError("broad-development manifest must contain jobs")
    columns = list(rows[0])
    if any(list(row) != columns for row in rows):
        raise ValueError("manifest rows have inconsistent columns")
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return _write_bytes_once(path, buffer.getvalue().encode("utf-8"))


def _write_json_once(path: Path, payload: dict[str, Any]) -> str:
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return _write_bytes_once(path, content)


def _manifest_rows(*, seeds: Iterable[int] = BROAD_SEEDS, evidence_class: str = EVIDENCE_CLASS, prefix: str = "v6_p0_broad") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for environment in ENVIRONMENTS:
        held_out = str(environment["task"])
        sources = "|".join(task for task in TASKS if task != held_out)
        for seed in seeds:
            raw_id = _job_id(environment, "RAW", int(seed), prefix=prefix)
            for strategy in FULL_BASE_STRATEGIES:
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, int(seed), prefix=prefix),
                        "job_kind": "trajectory",
                        "execution_phase": "base",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": int(seed),
                        "evidence_class": evidence_class,
                        "dependency_job_id": "",
                        "dependency_kind": "independent_full_trajectory",
                        "beta_rule": (
                            "historical_selected_gg_nominal_beta_0p5"
                            if strategy == "SELECTED_GG"
                            else "raw_beta_1"
                        ),
                        "held_out_task": held_out,
                        "selection_source_tasks": sources,
                        "strategy_role": "historical_or_mechanistic_full_trajectory",
                    }
                )
            for strategy in CALIBRATION_REPLAY_STRATEGIES:
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, int(seed), prefix=prefix),
                        "job_kind": "calibration_replay",
                        "execution_phase": "base",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": int(seed),
                        "evidence_class": evidence_class,
                        "dependency_job_id": raw_id,
                        "dependency_kind": "exact_RAW_acquisition_replay",
                        "beta_rule": "exact_RAW_acquisition",
                        "held_out_task": held_out,
                        "selection_source_tasks": sources,
                        "strategy_role": SIMPLE_SCALER_ROLES.get(strategy, "calibration_only"),
                    }
                )
            for strategy in POST_SELECTION_FULL_STRATEGIES:
                beta_rule = {
                    "RAW_FIXED_BETA_MATCHED": "leave_one_task_out_fixed_matched_beta",
                    "RAW_STAGE_BETA_MATCHED": "leave_one_task_out_stage_matched_beta",
                }[strategy]
                rows.append(
                    {
                        "job_id": _job_id(environment, strategy, int(seed), prefix=prefix),
                        "job_kind": "trajectory",
                        "execution_phase": "post_selection",
                        "task": environment["task"],
                        "split_protocol": environment["split_protocol"],
                        "model": environment["model"],
                        "strategy": strategy,
                        "seed": int(seed),
                        "evidence_class": evidence_class,
                        "dependency_job_id": "",
                        "dependency_kind": "independent_full_trajectory_after_prospective_LOTO_rule",
                        "beta_rule": beta_rule,
                        "held_out_task": held_out,
                        "selection_source_tasks": sources,
                        "strategy_role": "matched_beta_mechanism_full_trajectory",
                    }
                )
    return rows


def _validate_manifest_rows(
    rows: Iterable[dict[str, object]],
    *,
    seeds: set[int],
    evidence_class: str,
    require_all_environments: bool = True,
) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("broad-development manifest is empty")
    jobs = [str(row["job_id"]) for row in materialized]
    if len(jobs) != len(set(jobs)):
        raise ValueError("broad-development manifest has duplicate job IDs")
    observed_seeds = {int(row["seed"]) for row in materialized}
    if observed_seeds != seeds or observed_seeds & set(range(7000, 7040)):
        raise ValueError("broad-development manifest has a seed collision")
    expected_environment_ids = {_environment_id(item) for item in ENVIRONMENTS}
    actual_environment_ids = {
        _environment_id({"task": str(row["task"]), "split_protocol": str(row["split_protocol"]), "model": str(row["model"])})
        for row in materialized
    }
    if require_all_environments and actual_environment_ids != expected_environment_ids:
        raise ValueError("broad-development manifest does not cover all 16 environments")
    if not require_all_environments and not actual_environment_ids <= expected_environment_ids:
        raise ValueError("canary manifest contains an unregistered environment")
    if not all(str(row["evidence_class"]) == evidence_class for row in materialized):
        raise ValueError("broad-development manifest has an invalid evidence class")
    if not all(str(row["execution_phase"]) in {"base", "post_selection"} for row in materialized):
        raise ValueError("broad-development manifest has an invalid phase")
    expected_per_environment_seed = (
        len(FULL_BASE_STRATEGIES) + len(CALIBRATION_REPLAY_STRATEGIES) + len(POST_SELECTION_FULL_STRATEGIES)
    )
    expected_count = (
        len(ENVIRONMENTS) if require_all_environments else len(actual_environment_ids)
    ) * len(seeds) * expected_per_environment_seed
    if len(materialized) != expected_count:
        raise ValueError("broad-development manifest has an unexpected job count")


def _selection_rules_payload(workspace: Path) -> dict[str, Any]:
    return {
        "schema_version": "v6-p0-broad-selection-rules-v1",
        "status": "PROSPECTIVE_BROAD_DEVELOPMENT_RULES_FROZEN_BEFORE_ENDPOINT_READ",
        "evidence_class": EVIDENCE_CLASS,
        "broad_seed_range": [min(BROAD_SEEDS), max(BROAD_SEEDS)],
        "confirmation_seed_range_forbidden": [7000, 7039],
        "matched_beta_selection": {
            "unit": "Original-GG effective beta at active-learning rounds >= 0",
            "held_out_task_rule": "one map per held-out task; use only the other three tasks",
            "balancing_rule": "median within each source task/split/model environment, then median across environments",
            "fixed_beta_rule": "environment-balanced median",
            "stage_boundaries": [0.0, 0.25, 0.50, 0.75, 1.0],
            "stage_rule": "same environment-balanced median within the stage",
            "fallback_rule": "fixed_matched_beta when a stage has no valid source rows",
            "tie_rule": "deterministic lexical ordering before every grouped reduction",
        },
        "simple_scaling_roles": SIMPLE_SCALER_ROLES,
        "simple_scaling_rule": "no outcome-driven simple-scaler winner is selected from sentinel or broad outcomes",
        "reuse_rules": {
            "calibration_replay": list(CALIBRATION_REPLAY_STRATEGIES),
            "full_trajectory": list(FULL_BASE_STRATEGIES + POST_SELECTION_FULL_STRATEGIES),
            "GG_NORMALIZED_ACQUISITION": "not registered for broad reuse; no RAW identity is assumed",
        },
        "source_hashes": {
            "v6_code_tree_sha256": code_tree_sha256(workspace / "src" / "transportability_v6"),
            "v5_authority_lock_sha256": sha256_file(workspace / "locks" / "v5_frozen_manifest.json"),
        },
        "git_commit": current_git_commit(workspace),
    }


def _plan_text(manifest_hash: str, selection_rules_hash: str) -> str:
    return f"""# V6 P0 broad development plan

Evidence class: `V6-P0-BROAD-DEVELOPMENT`.

Scope: all four frozen Matbench tasks, IID-record and chemical-system group-disjoint splits, Random Forest and ExtraTrees-compatible (`extra_randomized_bagging`) ensembles, and seeds 6100--6109 only. This is development-only and excludes all confirmation seeds.

The manifest contains 16 environments × 10 seeds × 17 registered jobs = 2720 jobs. Eight calibration-only strategies are exact RAW-acquisition replays and declare their RAW dependency. Nine strategies are independent full trajectories because acquisition can change.

Matched-beta maps use leave-one-task-out source tasks, an environment-balanced median rule, four fixed stages, lexical deterministic reductions, and a fixed-beta missing-stage fallback. No simple-scaling method is selected by observed sentinel outcomes: identity is a negative control; residual-ratio is the candidate non-identity scalar baseline; NLL, power, isotonic, and conformal retain their prespecified roles.

Prospective manifest SHA-256: `{manifest_hash}`.
Prospective selection-rules SHA-256: `{selection_rules_hash}`.
"""


def create_broad_development_design(*, workspace: str | Path = WORKSPACE) -> dict[str, object]:
    """Create the broad plan, manifest, and prospective selection rules only."""

    workspace = Path(workspace).resolve()
    adapter = CanonicalV5Adapter(workspace)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority locks failed before broad-development design")
    rows = _manifest_rows()
    _validate_manifest_rows(rows, seeds=set(BROAD_SEEDS), evidence_class=EVIDENCE_CLASS)
    manifest_path = workspace / "manifests" / "v6_p0_broad_development_manifest.csv"
    manifest_hash = _write_csv_once(rows, manifest_path)
    rules_path = workspace / "analysis_plan" / "v6_p0_broad_selection_rules.json"
    rules = _selection_rules_payload(workspace)
    rules_hash = _write_json_once(rules_path, rules)
    plan_path = workspace / "analysis_plan" / "v6_p0_broad_development_plan.md"
    plan_hash = _write_bytes_once(plan_path, _plan_text(manifest_hash, rules_hash).encode("utf-8"))
    return {
        "manifest_path": manifest_path.relative_to(workspace).as_posix(),
        "manifest_sha256": manifest_hash,
        "selection_rules_path": rules_path.relative_to(workspace).as_posix(),
        "selection_rules_sha256": rules_hash,
        "plan_path": plan_path.relative_to(workspace).as_posix(),
        "plan_sha256": plan_hash,
        "manifest_job_count": len(rows),
    }


def _read_manifest(workspace: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = workspace / "manifests" / "v6_p0_broad_development_manifest.csv"
    lock_path = workspace / "locks" / "v6_p0_broad_development_manifest_lock.json"
    if not manifest_path.is_file() or not lock_path.is_file():
        raise FileNotFoundError("final broad-development manifest lock is required before execution")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if sha256_file(manifest_path) != str(lock.get("manifest_sha256")):
        raise RuntimeError("broad-development manifest hash does not match its final lock")
    rows = pd.read_csv(manifest_path, dtype={"seed": int}).fillna("")
    _validate_manifest_rows(rows.to_dict("records"), seeds=set(BROAD_SEEDS), evidence_class=EVIDENCE_CLASS)
    return rows, lock


def _snapshot(registry: CanonicalJobRegistry, output_root: Path, run_root: Path) -> pd.DataFrame:
    frame = registry.snapshot_frame()
    for path in (run_root / "registry_snapshot.csv", output_root / "registry_snapshot.csv"):
        temporary = path.with_suffix(path.suffix + ".tmp")
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    return frame


def _result_hash(result: dict[str, object]) -> str:
    path = Path(str(result["output_dir"])) / "trajectory.json"
    return sha256_file(path) if path.is_file() else _canonical_hash(result)


def _run_row(
    row: pd.Series,
    *,
    manifest_sha256: str,
    trajectory_root: Path,
    evaluation_root: Path,
    adapter: CanonicalV5Adapter,
    phase: str,
    selection_maps: dict[str, dict[str, object]] | None,
) -> dict[str, object]:
    common = {
        "job_id": str(row.job_id),
        "task": str(row.task),
        "split_protocol": str(row.split_protocol),
        "model": str(row.model),
        "strategy": str(row.strategy),
        "seed": int(row.seed),
        "evidence_class": str(row.evidence_class),
        "phase": phase,
        "manifest_sha256": manifest_sha256,
    }
    if str(row.job_kind) == "calibration_replay":
        return run_calibration_replay(
            CalibrationReplayConfig(source_job_id=str(row.dependency_job_id), **common),
            trajectory_root=trajectory_root,
            output_root=evaluation_root,
            adapter=adapter,
        )
    # ``SELECTED_GG`` is the historical selected-beta comparator, whose
    # scientific identity includes nominal beta=0.5.  Leave-one-task-out maps
    # are reserved for the two explicitly matched RAW mechanisms below.
    beta = 0.5 if str(row.strategy) == "SELECTED_GG" else 1.0
    stage_beta_map = None
    if str(row.execution_phase) == "post_selection":
        if selection_maps is None or str(row.held_out_task) not in selection_maps:
            raise RuntimeError("post-selection job lacks its frozen leave-one-task-out map")
        selection = selection_maps[str(row.held_out_task)]
        beta = float(selection["fixed_matched_beta"])
        if str(row.strategy) == "RAW_STAGE_BETA_MATCHED":
            stage_beta_map = dict(selection["stage_matched_beta"])
    return run_production_campaign(
        ProductionCampaignConfig(beta=beta, stage_beta_map=stage_beta_map, **common),
        output_root=trajectory_root,
        adapter=adapter,
    )


def _record_recovery_event(
    *,
    run_root: Path,
    final_lock_sha256: str,
    manifest_sha256: str,
    recovery_run_id: str,
    event_kind: str,
    row: dict[str, object],
    attempt: int,
    prior_status: str,
    details: dict[str, object],
) -> str:
    """Create an append-only, lock-addressed execution/recovery record."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    job_id = str(row["job_id"])
    payload = {
        "schema_version": "v6-p0-broad-development-recovery-record-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "event_kind": event_kind,
        "recovery_run_id": recovery_run_id,
        "final_lock_sha256": final_lock_sha256,
        "manifest_sha256": manifest_sha256,
        "job_id": job_id,
        "attempt": int(attempt),
        "prior_status": prior_status,
        "job": row,
        "details": details,
    }
    path = run_root / "recovery_records" / f"{timestamp}__{event_kind}__attempt{int(attempt):03d}__{job_id}.json"
    _write_json_once(path, payload)
    return path.as_posix()


def _execute_one_row(
    row: dict[str, object],
    *,
    registry: CanonicalJobRegistry,
    manifest_sha256: str,
    trajectory_root: Path,
    evaluation_root: Path,
    adapter: CanonicalV5Adapter,
    phase: str,
    selection_maps: dict[str, dict[str, object]] | None,
    run_root: Path,
    final_lock_sha256: str,
    recovery_run_id: str,
    worker_id: str,
) -> dict[str, object]:
    """Claim, execute, and ledger one row without rewriting the final lock."""

    job_id = str(row["job_id"])
    connection = registry.connect()
    try:
        existing = connection.execute(
            "SELECT status,attempt,retry_count,last_error,output_path,output_hash FROM jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if existing is None:
            raise RuntimeError(f"registry has no broad job {job_id}")
        status, attempt, retry_count, prior_error, prior_output_path, prior_output_hash = existing
        status = str(status)
        if status == "COMPLETED":
            return {"job_id": job_id, "outcome": "already_completed"}
        if status == "EXCLUDED_WITH_REASON":
            return {"job_id": job_id, "outcome": "already_excluded"}
        if status == "RUNNING":
            return {
                "job_id": job_id,
                "outcome": "blocked_running",
                "error": "job is RUNNING; use explicit stale recovery only after confirming the worker is gone",
            }
        dependency = str(row.get("dependency_job_id", "") or "")
        if dependency:
            source = connection.execute("SELECT status,output_hash FROM jobs WHERE job_id=?", (dependency,)).fetchone()
            if source is None or str(source[0]) != "COMPLETED":
                registry.transition(
                    connection,
                    job_id,
                    "EXCLUDED_WITH_REASON",
                    {"last_error": "exact RAW dependency did not complete"},
                )
                _record_recovery_event(
                    run_root=run_root,
                    final_lock_sha256=final_lock_sha256,
                    manifest_sha256=manifest_sha256,
                    recovery_run_id=recovery_run_id,
                    event_kind="dependency_excluded",
                    row=row,
                    attempt=int(attempt),
                    prior_status=status,
                    details={"dependency_job_id": dependency, "dependency_status": None if source is None else str(source[0])},
                )
                return {"job_id": job_id, "outcome": "excluded_dependency"}
        if status == "FAILED":
            _record_recovery_event(
                run_root=run_root,
                final_lock_sha256=final_lock_sha256,
                manifest_sha256=manifest_sha256,
                recovery_run_id=recovery_run_id,
                event_kind="retry_authorized",
                row=row,
                attempt=int(attempt),
                prior_status=status,
                details={
                    "prior_retry_count": int(retry_count),
                    "prior_last_error": prior_error,
                    "prior_output_path": prior_output_path,
                    "prior_output_hash": prior_output_hash,
                    "rule": "unchanged final lock; retry only through a versioned recovery record",
                },
            )
            registry.transition(
                connection,
                job_id,
                "PLANNED",
                {"last_error": "versioned recovery retry with unchanged final lock"},
                allow_retry=True,
            )
        claim = registry.claim_specific(connection, job_id, worker_id, os.getpid(), socket.gethostname())
        try:
            result = _run_row(
                pd.Series(row),
                manifest_sha256=manifest_sha256,
                trajectory_root=trajectory_root,
                evaluation_root=evaluation_root,
                adapter=adapter,
                phase=phase,
                selection_maps=selection_maps,
            )
            registry.transition(
                connection,
                job_id,
                "COMPLETED",
                {"output_path": str(result["output_dir"]), "output_hash": _result_hash(result)},
            )
            return {"job_id": job_id, "outcome": "completed", "attempt": int(claim["attempt"])}
        except Exception as exc:
            failure = traceback.format_exc()
            error = f"{type(exc).__name__}: {exc}; traceback_sha256=" + _sha256_bytes(failure.encode("utf-8"))
            registry.transition(connection, job_id, "FAILED", {"last_error": error})
            _record_recovery_event(
                run_root=run_root,
                final_lock_sha256=final_lock_sha256,
                manifest_sha256=manifest_sha256,
                recovery_run_id=recovery_run_id,
                event_kind="execution_failed",
                row=row,
                attempt=int(claim["attempt"]),
                prior_status="RUNNING",
                details={"last_error": error, "traceback_sha256": _sha256_bytes(failure.encode("utf-8"))},
            )
            return {"job_id": job_id, "outcome": "failed", "error": error}
    finally:
        connection.close()


def _worker_adapter(workspace: str) -> CanonicalV5Adapter:
    adapter = _BROAD_WORKER_ADAPTERS.get(workspace)
    if adapter is None:
        adapter = CanonicalV5Adapter(workspace)
        _BROAD_WORKER_ADAPTERS[workspace] = adapter
    return adapter


def _execute_one_row_in_process(
    row: dict[str, object],
    *,
    workspace: str,
    registry_path: str,
    manifest_sha256: str,
    trajectory_root: str,
    evaluation_root: str,
    phase: str,
    selection_maps: dict[str, dict[str, object]] | None,
    run_root: str,
    final_lock_sha256: str,
    recovery_run_id: str,
) -> dict[str, object]:
    adapter = _worker_adapter(workspace)
    registry = CanonicalJobRegistry(registry_path, adapter=adapter)
    return _execute_one_row(
        row,
        registry=registry,
        manifest_sha256=manifest_sha256,
        trajectory_root=Path(trajectory_root),
        evaluation_root=Path(evaluation_root),
        adapter=adapter,
        phase=phase,
        selection_maps=selection_maps,
        run_root=Path(run_root),
        final_lock_sha256=final_lock_sha256,
        recovery_run_id=recovery_run_id,
        worker_id=f"v6-broad-process-{os.getpid()}",
    )


def _execute_rows(
    rows: pd.DataFrame,
    *,
    registry: CanonicalJobRegistry,
    manifest_sha256: str,
    trajectory_root: Path,
    evaluation_root: Path,
    adapter: CanonicalV5Adapter,
    phase: str,
    selection_maps: dict[str, dict[str, object]] | None,
    workspace: Path,
    run_root: Path,
    final_lock_sha256: str,
    recovery_run_id: str,
    workers: int = 1,
) -> list[dict[str, object]]:
    """Execute phase-eligible rows, with process isolation when requested."""

    if workers < 1:
        raise ValueError("broad-development worker count must be positive")
    records = [dict(row._asdict()) for row in rows.itertuples(index=False)]
    outcomes: list[dict[str, object]] = []
    if workers == 1:
        for row in records:
            outcomes.append(
                _execute_one_row(
                    row,
                    registry=registry,
                    manifest_sha256=manifest_sha256,
                    trajectory_root=trajectory_root,
                    evaluation_root=evaluation_root,
                    adapter=adapter,
                    phase=phase,
                    selection_maps=selection_maps,
                    run_root=run_root,
                    final_lock_sha256=final_lock_sha256,
                    recovery_run_id=recovery_run_id,
                    worker_id="v6-broad-sequential-worker",
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _execute_one_row_in_process,
                    row,
                    workspace=str(workspace),
                    registry_path=str(registry.path),
                    manifest_sha256=manifest_sha256,
                    trajectory_root=str(trajectory_root),
                    evaluation_root=str(evaluation_root),
                    phase=phase,
                    selection_maps=selection_maps,
                    run_root=str(run_root),
                    final_lock_sha256=final_lock_sha256,
                    recovery_run_id=recovery_run_id,
                )
                for row in records
            ]
            for future in as_completed(futures):
                outcomes.append(future.result())
    blocked = [item for item in outcomes if str(item.get("outcome")) == "blocked_running"]
    if blocked:
        raise RuntimeError(f"broad execution is blocked by active registry rows: {[item['job_id'] for item in blocked]}")
    return outcomes


def _collect_original_gg_effective_beta(rows: pd.DataFrame, trajectory_root: Path) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    subset = rows[(rows.strategy == "ORIGINAL_GG") & (rows.execution_phase == "base")]
    for row in subset.itertuples(index=False):
        path = trajectory_root / str(row.job_id) / "rounds.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Original GG output unavailable: {path}")
        frame = pd.read_parquet(path)
        required = (
            "round",
            "budget_fraction",
            "fitted_scale_median",
            "effective_beta_median",
            "valid_oob_observation_count",
            "scale_status",
        )
        if not set(required) <= set(frame):
            raise ValueError("Original GG trajectory lacks required effective-beta fields")
        frame = frame.loc[frame["round"] >= 0, list(required)].copy()
        frame["environment"] = _environment_id(row._asdict())
        frame["task"] = str(row.task)
        frame["split"] = str(row.split_protocol)
        frame["model"] = str(row.model)
        frame["strategy"] = str(row.strategy)
        frame["seed"] = int(row.seed)
        frame["nominal_beta"] = 1.0
        frame = frame.rename(
            columns={
                "fitted_scale_median": "fitted_scale",
                "effective_beta_median": "effective_beta",
                "valid_oob_observation_count": "valid_oob_observation_count",
                "scale_status": "fallback_status",
            }
        )
        records.append(frame)
    if not records:
        raise ValueError("no broad Original GG outputs are available")
    return pd.concat(records, ignore_index=True).sort_values(
        ["task", "split", "model", "seed", "round"], kind="stable"
    )


def _write_effective_beta_table_once(workspace: Path, beta: pd.DataFrame) -> str:
    path = workspace / "tables" / "v6_p0_broad_effective_beta.csv"
    csv_bytes = beta.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    return _write_bytes_once(path, csv_bytes)


def _candidate_selection_payload(
    *,
    workspace: Path,
    manifest_hash: str,
    beta_table_hash: str,
    beta: pd.DataFrame,
) -> dict[str, Any]:
    maps: dict[str, dict[str, object]] = {}
    for held_out in TASKS:
        source = beta.loc[beta["task"].astype(str) != held_out].copy()
        selection = fit_matched_beta_map(source, allowed_seeds=set(BROAD_SEEDS))
        maps[held_out] = {
            **selection,
            "held_out_task": held_out,
            "source_tasks": sorted(set(source["task"].astype(str))),
            "source_environments": sorted(set(source["environment"].astype(str))),
            "source_seeds": sorted(set(source["seed"].astype(int))),
            "source_table_sha256": beta_table_hash,
        }
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-selection-map-candidate-v1",
        "status": "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN",
        "evidence_class": EVIDENCE_CLASS,
        "confirmation_outcomes_inspected": False,
        "manifest_sha256": manifest_hash,
        "broad_seed_range": [min(BROAD_SEEDS), max(BROAD_SEEDS)],
        "source_tables": [{"path": "tables/v6_p0_broad_effective_beta.csv", "sha256": beta_table_hash}],
        "leave_one_task_out_maps": maps,
        "unresolved": [
            "Candidate only; no confirmation selection map is frozen.",
            "No confirmation seeds or outputs were created or read.",
        ],
        "source_hashes": {
            "v6_code_tree_sha256": code_tree_sha256(workspace / "src" / "transportability_v6"),
            "v5_authority_lock_sha256": sha256_file(workspace / "locks" / "v5_frozen_manifest.json"),
        },
    }
    payload["candidate_selection_map_sha256"] = _canonical_hash(payload)
    return payload


def _selection_maps_from_candidate(payload: dict[str, Any]) -> dict[str, dict[str, object]]:
    maps = dict(payload["leave_one_task_out_maps"])
    required = set(TASKS)
    if set(maps) != required:
        raise ValueError("candidate map does not contain one leave-one-task-out map per task")
    return {task: dict(maps[task]) for task in TASKS}


def run_broad_canary(*, workspace: str | Path = WORKSPACE) -> dict[str, object]:
    """Exercise every broad execution path once using seed 6099 only."""

    workspace = Path(workspace).resolve()
    # Freeze the prospective broad rules/manifest before the engineering
    # canary produces any endpoint.  The final broad lock subsequently binds
    # these exact artifacts after the canary passes.
    design = create_broad_development_design(workspace=workspace)
    adapter = CanonicalV5Adapter(workspace)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    environment = {"task": "matbench_expt_gap", "split_protocol": "iid_record", "model": "random_forest"}
    rows = [
        row
        for row in _manifest_rows(seeds=(CANARY_SEED,), evidence_class=CANARY_EVIDENCE_CLASS, prefix="v6_p0_broad_canary")
        if _environment_id({"task": str(row["task"]), "split_protocol": str(row["split_protocol"]), "model": str(row["model"])})
        == _environment_id(environment)
    ]
    _validate_manifest_rows(
        rows,
        seeds={CANARY_SEED},
        evidence_class=CANARY_EVIDENCE_CLASS,
        require_all_environments=False,
    )
    root = workspace / "results" / "v6_p0_broad_development_canary"
    manifest_path = root / "canary_manifest.csv"
    manifest_hash = _write_csv_once(rows, manifest_path)
    registry = CanonicalJobRegistry(root / "job_registry.sqlite", adapter=adapter)
    connection = registry.initialize([str(row["job_id"]) for row in rows], manifest_hash)
    connection.close()
    frame = pd.DataFrame(rows)
    trajectory_root = root / "trajectories"
    evaluation_root = root / "calibration_replays"
    trajectory_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    _execute_rows(
        frame[(frame.execution_phase == "base") & (frame.job_kind == "trajectory")],
        registry=registry,
        manifest_sha256=manifest_hash,
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="canary",
        selection_maps=None,
        workspace=workspace,
        run_root=root,
        final_lock_sha256="CANARY_ENGINEERING_ONLY_NO_FINAL_LOCK",
        recovery_run_id=f"canary_seed_{CANARY_SEED}",
    )
    _execute_rows(
        frame[(frame.execution_phase == "base") & (frame.job_kind == "calibration_replay")],
        registry=registry,
        manifest_sha256=manifest_hash,
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="canary",
        selection_maps=None,
        workspace=workspace,
        run_root=root,
        final_lock_sha256="CANARY_ENGINEERING_ONLY_NO_FINAL_LOCK",
        recovery_run_id=f"canary_seed_{CANARY_SEED}",
    )
    static_map = {
        task: {
            "fixed_matched_beta": 1.0,
            "stage_matched_beta": {"0_25": 1.0, "25_50": 1.0, "50_75": 1.0, "75_100": 1.0},
        }
        for task in TASKS
    }
    _execute_rows(
        frame[frame.execution_phase == "post_selection"],
        registry=registry,
        manifest_sha256=manifest_hash,
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="canary",
        selection_maps=static_map,
        workspace=workspace,
        run_root=root,
        final_lock_sha256="CANARY_ENGINEERING_ONLY_NO_FINAL_LOCK",
        recovery_run_id=f"canary_seed_{CANARY_SEED}",
    )
    snapshot = _snapshot(registry, root, root)
    summary = {
        "schema_version": "v6-p0-broad-canary-v1",
        "status": "PASSED" if set(snapshot.status) == {"COMPLETED"} else "FAILED",
        "canary_seed": CANARY_SEED,
        "prospective_design": design,
        "manifest_sha256": manifest_hash,
        "planned": int(len(frame)),
        "completed": int((snapshot.status == "COMPLETED").sum()),
        "failed": int((snapshot.status == "FAILED").sum()),
        "excluded": int((snapshot.status == "EXCLUDED_WITH_REASON").sum()),
        "source_code_tree_sha256": code_tree_sha256(workspace / "src" / "transportability_v6"),
        "confirmation_outcomes_inspected": False,
    }
    _write_json_once(root / "canary_summary.json", summary)
    if summary["status"] != "PASSED":
        raise RuntimeError("broad-development canary failed; final lock must not be issued")
    return summary


def issue_final_broad_lock(*, workspace: str | Path = WORKSPACE) -> dict[str, object]:
    """Issue the one final prospective broad-development lock after canary success."""

    workspace = Path(workspace).resolve()
    design = create_broad_development_design(workspace=workspace)
    canary_path = workspace / "results" / "v6_p0_broad_development_canary" / "canary_summary.json"
    if not canary_path.is_file():
        raise RuntimeError("broad canary must pass before issuing the final broad lock")
    canary = json.loads(canary_path.read_text(encoding="utf-8"))
    current_code = code_tree_sha256(workspace / "src" / "transportability_v6")
    if canary.get("status") != "PASSED" or canary.get("source_code_tree_sha256") != current_code:
        raise RuntimeError("canary did not pass against the current code tree")
    adapter = CanonicalV5Adapter(workspace)
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority locks failed before final broad lock")
    lock_path = workspace / "locks" / "v6_p0_broad_development_manifest_lock.json"
    if lock_path.exists():
        existing = json.loads(lock_path.read_text(encoding="utf-8"))
        if existing.get("manifest_sha256") != design["manifest_sha256"] or existing.get("v6_code_tree_sha256") != current_code:
            raise RuntimeError("final broad lock exists but does not match the prospective design")
        return existing
    lock: dict[str, Any] = {
        "schema_version": "v6-p0-broad-development-manifest-lock-v1",
        "status": "FINAL_PROSPECTIVE_BROAD_DEVELOPMENT_LOCK",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": current_git_commit(workspace),
        "manifest_path": design["manifest_path"],
        "manifest_sha256": design["manifest_sha256"],
        "manifest_job_count": design["manifest_job_count"],
        "selection_rules_path": design["selection_rules_path"],
        "selection_rules_sha256": design["selection_rules_sha256"],
        "plan_path": design["plan_path"],
        "plan_sha256": design["plan_sha256"],
        "evidence_class": EVIDENCE_CLASS,
        "development_seed_range": [min(BROAD_SEEDS), max(BROAD_SEEDS)],
        "seed_collision_audit": "passed_exactly_6100_6109_and_no_5000_5039_or_7000_7039",
        "environment_count": len(ENVIRONMENTS),
        "environment_scope": [_environment_id(item) for item in ENVIRONMENTS],
        "strategy_list": list(FULL_BASE_STRATEGIES + CALIBRATION_REPLAY_STRATEGIES + POST_SELECTION_FULL_STRATEGIES),
        "canary_summary_path": canary_path.relative_to(workspace).as_posix(),
        "canary_summary_sha256": sha256_file(canary_path),
        "canary_seed": CANARY_SEED,
        "v6_code_tree_sha256": current_code,
        "v5_source_lock": adapter.source_lock_status(),
        "v5_authority_lock": authority,
        "execution_run_id": "final_broad_development",
        "execution_policy": {
            "isolated_process_workers_default": 2,
            "registry": "canonical V5 SQLite registry with atomic named claims",
            "retry_rule": "FAILED rows may return to PLANNED only with a versioned retry_authorized record linked to this final lock",
            "stale_rule": "RUNNING rows block a new executor unless explicit age-threshold stale recovery emits a versioned record",
            "records_directory": "results/v6_p0_broad_development/final_broad_development/recovery_records",
        },
        "recovery_rule": "Preserve this final lock. Any execution failure creates a versioned recovery record and never reissues or overwrites the lock.",
        "confirmation_boundary": "No confirmation jobs, seeds, outputs, or inference are permitted.",
    }
    lock["final_lock_sha256"] = _canonical_hash(lock)
    _write_json_once(lock_path, lock)
    return lock


def _recover_stale_jobs(
    *,
    registry: CanonicalJobRegistry,
    rows: pd.DataFrame,
    run_root: Path,
    lock: dict[str, Any],
    stale_after_seconds: int,
    recovery_run_id: str,
) -> list[str]:
    """Explicitly return abandoned RUNNING rows to PLANNED with records.

    This is intentionally opt-in.  A normal resume never assumes a RUNNING
    job is stale, so two users cannot silently execute the same locked row.
    """

    if stale_after_seconds <= 0:
        raise ValueError("stale recovery threshold must be positive")
    snapshot = registry.snapshot_frame()
    cutoff = datetime.now(timezone.utc).timestamp() - int(stale_after_seconds)
    by_job = {str(row.job_id): dict(row._asdict()) for row in rows.itertuples(index=False)}
    recovered: list[str] = []
    connection = registry.connect()
    try:
        for item in snapshot.loc[snapshot.status.astype(str) == "RUNNING"].itertuples(index=False):
            started = str(item.started_at or "")
            try:
                started_epoch = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
            except ValueError as exc:
                raise RuntimeError(f"RUNNING job has malformed started_at: {item.job_id}") from exc
            if started_epoch >= cutoff:
                continue
            job_id = str(item.job_id)
            _record_recovery_event(
                run_root=run_root,
                final_lock_sha256=str(lock["final_lock_sha256"]),
                manifest_sha256=str(lock["manifest_sha256"]),
                recovery_run_id=recovery_run_id,
                event_kind="stale_worker_recovery_authorized",
                row=by_job[job_id],
                attempt=int(item.attempt),
                prior_status="RUNNING",
                details={
                    "started_at": started,
                    "stale_after_seconds": int(stale_after_seconds),
                    "previous_worker_id": item.worker_id,
                    "previous_pid": item.pid,
                    "previous_output_path": item.output_path,
                    "previous_output_hash": item.output_hash,
                },
            )
            registry.transition(
                connection,
                job_id,
                "PLANNED",
                {"last_error": "versioned stale-worker recovery with unchanged final lock"},
                allow_stale_recovery=True,
            )
            recovered.append(job_id)
    finally:
        connection.close()
    return recovered


def execute_broad_development(
    *,
    workspace: str | Path = WORKSPACE,
    workers: int = 2,
    recover_stale_after_seconds: int | None = None,
) -> dict[str, object]:
    """Execute only the final locked broad-development manifest."""

    workspace = Path(workspace).resolve()
    rows, lock = _read_manifest(workspace)
    if code_tree_sha256(workspace / "src" / "transportability_v6") != str(lock["v6_code_tree_sha256"]):
        raise RuntimeError("V6 code tree changed after final broad lock; execution is blocked")
    adapter = CanonicalV5Adapter(workspace)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority locks failed before broad execution")
    output_root = workspace / "results" / "v6_p0_broad_development"
    run_root = output_root / str(lock["execution_run_id"])
    trajectory_root = run_root / "trajectories"
    evaluation_root = run_root / "calibration_replays"
    trajectory_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    registry = CanonicalJobRegistry(run_root / "job_registry.sqlite", adapter=adapter)
    connection = registry.initialize(rows.job_id.astype(str).tolist(), str(lock["manifest_sha256"]))
    connection.close()
    if workers < 1:
        raise ValueError("broad-development worker count must be positive")
    recovery_run_id = datetime.now(timezone.utc).strftime("broad_resume_%Y%m%dT%H%M%SZ")
    if recover_stale_after_seconds is not None:
        _recover_stale_jobs(
            registry=registry,
            rows=rows,
            run_root=run_root,
            lock=lock,
            stale_after_seconds=int(recover_stale_after_seconds),
            recovery_run_id=recovery_run_id,
        )
    active = registry.snapshot_frame()
    running = active.loc[active.status.astype(str) == "RUNNING", "job_id"].astype(str).tolist()
    if running:
        raise RuntimeError(
            "broad execution has active RUNNING jobs; do not start a second executor. "
            "Use explicit stale recovery only after the worker is confirmed absent: " + ", ".join(running)
        )
    base = rows[rows.execution_phase == "base"]
    _execute_rows(
        base[base.job_kind == "trajectory"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="broad_development",
        selection_maps=None,
        workspace=workspace,
        run_root=run_root,
        final_lock_sha256=str(lock["final_lock_sha256"]),
        recovery_run_id=recovery_run_id,
        workers=workers,
    )
    _execute_rows(
        base[base.job_kind == "calibration_replay"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="broad_development",
        selection_maps=None,
        workspace=workspace,
        run_root=run_root,
        final_lock_sha256=str(lock["final_lock_sha256"]),
        recovery_run_id=recovery_run_id,
        workers=workers,
    )
    snapshot = _snapshot(registry, output_root, run_root)
    if (snapshot.status == "FAILED").any() or (snapshot.status == "EXCLUDED_WITH_REASON").any():
        return _write_execution_summary(workspace, output_root, run_root, lock, snapshot, status="FAILED_BASE")
    beta = _collect_original_gg_effective_beta(rows, trajectory_root)
    beta_table_hash = _write_effective_beta_table_once(workspace, beta)
    candidate = _candidate_selection_payload(
        workspace=workspace,
        manifest_hash=str(lock["manifest_sha256"]),
        beta_table_hash=beta_table_hash,
        beta=beta,
    )
    candidate_path = workspace / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE.json"
    _write_json_once(candidate_path, candidate)
    _execute_rows(
        rows[rows.execution_phase == "post_selection"],
        registry=registry,
        manifest_sha256=str(lock["manifest_sha256"]),
        trajectory_root=trajectory_root,
        evaluation_root=evaluation_root,
        adapter=adapter,
        phase="broad_development",
        selection_maps=_selection_maps_from_candidate(candidate),
        workspace=workspace,
        run_root=run_root,
        final_lock_sha256=str(lock["final_lock_sha256"]),
        recovery_run_id=recovery_run_id,
        workers=workers,
    )
    snapshot = _snapshot(registry, output_root, run_root)
    status = "COMPLETED" if set(snapshot.status) == {"COMPLETED"} else "COMPLETED_WITH_FAILURES"
    return _write_execution_summary(workspace, output_root, run_root, lock, snapshot, status=status)


def _write_execution_summary(
    workspace: Path,
    output_root: Path,
    run_root: Path,
    lock: dict[str, Any],
    snapshot: pd.DataFrame,
    *,
    status: str,
) -> dict[str, object]:
    recovery_records = sorted((run_root / "recovery_records").glob("*.json")) if (run_root / "recovery_records").is_dir() else []
    payload: dict[str, object] = {
        "schema_version": "v6-p0-broad-development-execution-summary-v1",
        "status": status,
        "evidence_class": EVIDENCE_CLASS,
        "planned": int(len(snapshot)),
        "completed": int((snapshot.status == "COMPLETED").sum()),
        "failed": int((snapshot.status == "FAILED").sum()),
        "excluded": int((snapshot.status == "EXCLUDED_WITH_REASON").sum()),
        "recovered": int(snapshot.last_error.fillna("").astype(str).str.contains("recovery", case=False).sum()),
        "recovery_record_count": len(recovery_records),
        "recovery_records_directory": (run_root / "recovery_records").relative_to(workspace).as_posix(),
        "manifest_sha256": str(lock["manifest_sha256"]),
        "final_lock_sha256": str(lock["final_lock_sha256"]),
        "execution_run_root": run_root.relative_to(workspace).as_posix(),
        "registry_snapshot": (output_root / "registry_snapshot.csv").relative_to(workspace).as_posix(),
        "candidate_selection_map": "analysis_plan/v6_p0_confirmation_selection_map_CANDIDATE.json",
        "confirmation_outcomes_inspected": False,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = output_root / "execution_summary.json"
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if path.exists():
        # A retry after a failure is a separate recovery record; do not
        # silently replace prior evidence.
        attempt = output_root / f"execution_summary_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        _write_bytes_once(attempt, content)
    else:
        _write_bytes_once(path, content)
    return payload
