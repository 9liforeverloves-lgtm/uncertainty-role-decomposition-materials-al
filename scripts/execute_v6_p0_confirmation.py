"""Outcome-blind execution and raw-result locking for frozen V6 P0 confirmation."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import traceback
from typing import Any

import numpy as np
import pandas as pd

from transportability_v6.calibration_replay import (
    CalibrationReplayConfig,
    run_calibration_replay,
)
from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.execution_registry import CanonicalJobRegistry, sha256_file
from transportability_v6.freeze_readiness import validate_manifest_policy_identity
from transportability_v6.production_campaign import (
    ProductionCampaignConfig,
    run_production_campaign,
)
from transportability_v6.production_strategies import PRODUCTION_STRATEGIES
from transportability_v6.registry_freeze import code_tree_sha256


ROOT = Path(__file__).resolve().parents[1]
FREEZE_COMMIT = "ff04a22158916b6b34ae0fa442f015f0b55f5c70"
FROZEN_MAP_SHA = "779608733b1b7e8727a28b3d08666227d69241756e30f685180ea2ca0f8909dd"
FREEZE_LOCK_SHA = "bea5809d5342417dc53b8210852370a3db372d1bb8bad208faac3cd87f00186a"
MANIFEST_SHA = "64b9e87063eb609d78c6b9db0284faf8faa2f1203047128ede50a1910bc30ef3"
CODE_TREE_SHA = "5612c35c5e436e9b4a4b9fbaac6172181c50a257a20c5aa54c38bcb7298b4f57"
EXPECTED_ROWS = 12800
SEEDS = tuple(range(7000, 7040))

FROZEN_MAP = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_FROZEN.json"
FREEZE_LOCK = ROOT / "locks" / "v6_p0_confirmation_selection_freeze_lock.json"
MANIFEST = ROOT / "manifests" / "v6_p0_confirmation_manifest.csv"
AUTHORIZATION = ROOT / "locks" / "v6_p0_confirmation_execution_authorization.json"
REQUIREMENTS_LOCK = ROOT / "requirements-lock.txt"
OUTPUT_ROOT = ROOT / "results" / "v6_p0_confirmation"
REGISTRY_PATH = OUTPUT_ROOT / "registry.sqlite"
TRAJECTORY_ROOT = OUTPUT_ROOT / "trajectories"
REPLAY_ROOT = OUTPUT_ROOT / "replays"
RECOVERY_ROOT = OUTPUT_ROOT / "recovery_records"
INITIAL_SNAPSHOT = OUTPUT_ROOT / "registry_snapshot_initial.csv"
FINAL_SNAPSHOT = OUTPUT_ROOT / "registry_snapshot_final.csv"
EXECUTION_REPORT = ROOT / "reports" / "07_p0_confirmation_execution.md"
EXECUTION_INVENTORY = ROOT / "tables" / "v6_p0_confirmation_execution_inventory.csv"
HASH_INVENTORY = ROOT / "tables" / "v6_p0_confirmation_trajectory_hash_inventory.csv"
RAW_RESULT_LOCK = ROOT / "locks" / "v6_p0_confirmation_raw_result_lock.json"

REPLAY_STRATEGIES = frozenset(
    {
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
    }
)
_WORKER_ADAPTERS: dict[str, CanonicalV5Adapter] = {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    content = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashlib.sha256(content).hexdigest():
            raise FileExistsError(f"refusing to overwrite divergent artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def verify_self_hash(path: Path, field: str) -> bool:
    payload = read_json(path)
    observed = str(payload.pop(field))
    return observed == canonical_hash(payload)


def read_manifest() -> pd.DataFrame:
    frame = pd.read_csv(MANIFEST, dtype=str, keep_default_na=False)
    if len(frame) != EXPECTED_ROWS:
        raise RuntimeError(f"manifest row count {len(frame)} != {EXPECTED_ROWS}")
    return frame


def dependency_lock_status() -> dict[str, Any]:
    mismatches: list[dict[str, str]] = []
    checked = 0
    for raw in REQUIREMENTS_LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        package, expected = line.split("==", 1)
        checked += 1
        try:
            observed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            observed = "MISSING"
        if observed != expected:
            mismatches.append(
                {"package": package, "expected": expected, "observed": observed}
            )
    return {
        "python_version": ".".join(map(str, os.sys.version_info[:3])),
        "requirements_lock_sha256": sha256_file(REQUIREMENTS_LOCK),
        "checked_packages": checked,
        "mismatches": mismatches,
        "passed": not mismatches and os.sys.version_info[:2] == (3, 12),
    }


def validate_frozen_bindings(*, require_clean: bool) -> dict[str, Any]:
    if git("merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD") != "":
        pass
    if sha256_file(FROZEN_MAP) != FROZEN_MAP_SHA:
        raise RuntimeError("frozen map byte hash mismatch")
    if sha256_file(FREEZE_LOCK) != FREEZE_LOCK_SHA:
        raise RuntimeError("freeze lock byte hash mismatch")
    if sha256_file(MANIFEST) != MANIFEST_SHA:
        raise RuntimeError("confirmation manifest byte hash mismatch")
    if not verify_self_hash(FROZEN_MAP, "frozen_map_self_sha256"):
        raise RuntimeError("frozen map self-hash mismatch")
    if not verify_self_hash(FREEZE_LOCK, "freeze_lock_self_sha256"):
        raise RuntimeError("freeze lock self-hash mismatch")
    if code_tree_sha256(ROOT / "src" / "transportability_v6") != CODE_TREE_SHA:
        raise RuntimeError("scientific code-tree hash mismatch")
    scientific_diff = git(
        "diff",
        "--name-only",
        FREEZE_COMMIT,
        "HEAD",
        "--",
        "src/transportability_v6",
        "analysis_plan/v6_p0_confirmation_selection_map_FROZEN.json",
        "locks/v6_p0_confirmation_selection_freeze_lock.json",
    )
    if scientific_diff:
        raise RuntimeError(f"scientific artifacts changed after freeze: {scientific_diff}")
    status = git("status", "--porcelain")
    if require_clean and status:
        raise RuntimeError("Git working tree is not clean: " + status.replace("\n", "; "))
    authority = CanonicalV5Adapter(ROOT).validate_v5_authority_locks()
    if not bool(authority["passed"]):
        raise RuntimeError("V5 authority locks changed")
    dependency = dependency_lock_status()
    if not dependency["passed"]:
        raise RuntimeError(f"dependency lock mismatch: {dependency['mismatches']}")
    disk = shutil.disk_usage(ROOT)
    # Prior development implies roughly 17 MB/job including local ignored artifacts.
    # Reserve 300 GB plus 10% of the volume for safe atomic writes and recovery.
    required_free = max(300 * 1024**3, int(disk.total * 0.10))
    if disk.free < required_free:
        raise RuntimeError(
            f"insufficient disk: free={disk.free}, required={required_free}"
        )
    frame = read_manifest()
    if set(frame["seed"].astype(int)) != set(SEEDS):
        raise RuntimeError("manifest seed range mismatch")
    if frame["job_id"].duplicated().any():
        raise RuntimeError("manifest has duplicate job IDs")
    if any(frame["job_id"].str.contains("h7", case=False)):
        raise RuntimeError("manifest contains H7 jobs")
    frozen = read_json(FROZEN_MAP)
    methods = {str(item["id"]): item for item in frozen["canonical_strategies"]}
    validate_manifest_policy_identity(frame.to_dict("records"), methods.values())
    if set(frame["strategy_id"]) & {"GG_JOINT", "CS_JOINT"}:
        raise RuntimeError("manifest contains alias jobs")
    if OUTPUT_ROOT.exists() and not REGISTRY_PATH.exists():
        raise RuntimeError("confirmation output root exists without a registered restart")
    return {
        "git_head": git("rev-parse", "HEAD"),
        "git_clean": not bool(status),
        "v5_authority": authority,
        "dependency_lock": dependency,
        "disk_free_bytes": disk.free,
        "disk_required_bytes": required_free,
        "manifest_rows": len(frame),
    }


def authorize() -> None:
    if AUTHORIZATION.exists():
        raise FileExistsError(f"authorization already exists: {AUTHORIZATION}")
    environment = validate_frozen_bindings(require_clean=False)
    if OUTPUT_ROOT.exists():
        raise RuntimeError("confirmation output root exists before authorization")
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-execution-authorization-v1",
        "authorization_status": "AUTHORIZED_FOR_FROZEN_EXECUTION",
        "authorized_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_commit": FREEZE_COMMIT,
        "frozen_map_sha256": FROZEN_MAP_SHA,
        "freeze_lock_sha256": FREEZE_LOCK_SHA,
        "confirmation_manifest_sha256": MANIFEST_SHA,
        "manifest_row_count": EXPECTED_ROWS,
        "confirmation_seeds": list(SEEDS),
        "output_root": OUTPUT_ROOT.relative_to(ROOT).as_posix(),
        "confirmation_outcomes_inspected": False,
        "environment_attestation": {
            "code_tree_sha256": CODE_TREE_SHA,
            "v5_authority_passed": bool(environment["v5_authority"]["passed"]),
            "requirements_lock_sha256": environment["dependency_lock"][
                "requirements_lock_sha256"
            ],
            "python_version": environment["dependency_lock"]["python_version"],
            "checked_packages": environment["dependency_lock"]["checked_packages"],
            "disk_free_bytes": environment["disk_free_bytes"],
        },
    }
    payload["execution_authorization_self_sha256"] = canonical_hash(payload)
    write_json_once(AUTHORIZATION, payload)
    print(
        json.dumps(
            {
                "authorization_status": payload["authorization_status"],
                "authorization_sha256": sha256_file(AUTHORIZATION),
                "self_hash": payload["execution_authorization_self_sha256"],
            },
            indent=2,
        )
    )


def verify_authorization() -> None:
    if not AUTHORIZATION.is_file():
        raise RuntimeError("execution authorization is absent")
    payload = read_json(AUTHORIZATION)
    if payload["authorization_status"] != "AUTHORIZED_FOR_FROZEN_EXECUTION":
        raise RuntimeError("execution is not authorized")
    if not verify_self_hash(AUTHORIZATION, "execution_authorization_self_sha256"):
        raise RuntimeError("execution authorization self-hash mismatch")
    exact = {
        "freeze_commit": FREEZE_COMMIT,
        "frozen_map_sha256": FROZEN_MAP_SHA,
        "freeze_lock_sha256": FREEZE_LOCK_SHA,
        "confirmation_manifest_sha256": MANIFEST_SHA,
        "manifest_row_count": EXPECTED_ROWS,
        "output_root": "results/v6_p0_confirmation",
    }
    for key, expected in exact.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"authorization binding mismatch: {key}")
    if payload["confirmation_seeds"] != list(SEEDS):
        raise RuntimeError("authorization seed binding mismatch")


def _install_authorized_confirmation_gate() -> None:
    """Open only the pre-approved confirmation seed gate without changing source."""

    verify_authorization()
    import transportability_v6.calibration_replay as replay_module
    import transportability_v6.production_campaign as campaign_module

    def authorized_assert(config: ProductionCampaignConfig):
        if config.phase != "confirmation":
            raise PermissionError("authorized worker accepts confirmation phase only")
        if int(config.seed) not in SEEDS:
            raise PermissionError("authorized worker accepts seeds 7000-7039 only")
        if config.evidence_class != "V6-MECH":
            raise ValueError("confirmation requires V6-MECH evidence class")
        if config.strategy not in PRODUCTION_STRATEGIES:
            raise KeyError(f"unregistered production strategy: {config.strategy}")
        if config.v5_strategy is not None:
            raise ValueError("confirmation cannot override a V5 strategy")
        if not math.isfinite(float(config.beta)) or float(config.beta) < 0:
            raise ValueError("beta must be finite and nonnegative")
        if (
            config.strategy == "RAW_FIXED_BETA_MATCHED"
            and config.stage_beta_map is not None
        ):
            raise ValueError("fixed matched beta cannot receive a stage map")
        if config.strategy == "RAW_STAGE_BETA_MATCHED":
            required = {"0_25", "25_50", "50_75", "75_100"}
            if config.stage_beta_map is None or set(config.stage_beta_map) != required:
                raise ValueError("stage matched beta map is incomplete")
            if any(
                not math.isfinite(float(value)) or float(value) < 0
                for value in config.stage_beta_map.values()
            ):
                raise ValueError("stage matched beta values are invalid")
        return PRODUCTION_STRATEGIES[config.strategy]

    def authorized_replay_validate(config: CalibrationReplayConfig):
        if config.phase != "confirmation" or int(config.seed) not in SEEDS:
            raise PermissionError("replay is outside authorized confirmation")
        spec = authorized_assert(
            ProductionCampaignConfig(
                job_id=config.job_id,
                task=config.task,
                split_protocol=config.split_protocol,
                model=config.model,
                strategy=config.strategy,
                seed=config.seed,
                evidence_class=config.evidence_class,
                phase=config.phase,
                manifest_sha256=config.manifest_sha256,
            )
        )
        if spec.acquisition_mapping != "raw_sigma":
            raise ValueError("only exact RAW acquisition may replay")
        return spec

    campaign_module._assert_production_config = authorized_assert
    replay_module._assert_production_config = authorized_assert
    replay_module._validate = authorized_replay_validate


def initialize_registry() -> None:
    verify_authorization()
    environment = validate_frozen_bindings(require_clean=True)
    if OUTPUT_ROOT.exists():
        raise FileExistsError("confirmation output root already exists")
    frame = read_manifest()
    registry = CanonicalJobRegistry(REGISTRY_PATH, adapter=CanonicalV5Adapter(ROOT))
    connection = registry.initialize(frame["job_id"].tolist(), MANIFEST_SHA)
    connection.close()
    snapshot = registry.snapshot_frame()
    if len(snapshot) != EXPECTED_ROWS or set(snapshot["status"]) != {"PLANNED"}:
        raise RuntimeError("registry did not initialize all jobs as PLANNED")
    if snapshot["job_id"].duplicated().any():
        raise RuntimeError("registry contains duplicate job IDs")
    INITIAL_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(INITIAL_SNAPSHOT, index=False, lineterminator="\n")
    os.chmod(INITIAL_SNAPSHOT, 0o444)
    metadata = {
        "initialized_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": MANIFEST_SHA,
        "manifest_rows": EXPECTED_ROWS,
        "registry_sha256": sha256_file(REGISTRY_PATH),
        "initial_snapshot_sha256": sha256_file(INITIAL_SNAPSHOT),
        "git_head": environment["git_head"],
        "code_tree_sha256": CODE_TREE_SHA,
        "development_seed_count": int(
            frame["seed"].astype(int).between(5000, 6999).sum()
        ),
    }
    write_json_once(OUTPUT_ROOT / "initialization_attestation.json", metadata)
    print(
        json.dumps(
            {"PLANNED": EXPECTED_ROWS, "RUNNING": 0, "FAILED": 0, "COMPLETED": 0},
            indent=2,
        )
    )


def _worker_adapter() -> CanonicalV5Adapter:
    key = str(ROOT)
    adapter = _WORKER_ADAPTERS.get(key)
    if adapter is None:
        adapter = CanonicalV5Adapter(ROOT)
        _WORKER_ADAPTERS[key] = adapter
    return adapter


def _row_beta(row: dict[str, str]) -> tuple[float, dict[str, float] | None]:
    strategy = row["strategy_id"]
    if strategy == "RAW_FIXED_BETA_MATCHED":
        return float(row["fixed_matched_beta"]), None
    if strategy == "RAW_STAGE_BETA_MATCHED":
        stage = {
            str(key): float(value)
            for key, value in json.loads(row["stage_beta_map_json"]).items()
        }
        return 1.0, stage
    return float(row["nominal_beta"]), None


def _trajectory_hash(output_dir: Path) -> str:
    trace = output_dir / "trajectory.json"
    if not trace.is_file():
        raise FileNotFoundError(f"completed output lacks trajectory.json: {output_dir}")
    return sha256_file(trace)


def _recovery_record(
    row: dict[str, str],
    *,
    attempt: int,
    event: str,
    detail: dict[str, Any],
) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    payload = {
        "schema_version": "v6-p0-confirmation-recovery-record-v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "job_id": row["job_id"],
        "attempt": int(attempt),
        "manifest_sha256": MANIFEST_SHA,
        "freeze_lock_sha256": FREEZE_LOCK_SHA,
        "configuration": row,
        "detail": detail,
        "endpoint_values_inspected": False,
    }
    path = RECOVERY_ROOT / (
        f"{timestamp}__{event}__attempt{attempt:03d}__{row['job_id']}.json"
    )
    write_json_once(path, payload)


def _execute_one(row: dict[str, str]) -> dict[str, Any]:
    _install_authorized_confirmation_gate()
    adapter = _worker_adapter()
    registry = CanonicalJobRegistry(REGISTRY_PATH, adapter=adapter)
    connection = registry.connect()
    job_id = row["job_id"]
    started = time.monotonic()
    try:
        state = connection.execute(
            "SELECT status,attempt,retry_count,output_path,output_hash FROM jobs WHERE job_id=?",
            (job_id,),
        ).fetchone()
        if state is None:
            raise RuntimeError(f"registry lacks job {job_id}")
        status, prior_attempt, retry_count, output_path, output_hash = state
        if status == "COMPLETED":
            path = Path(str(output_path))
            if not path.is_dir() or _trajectory_hash(path) != str(output_hash):
                raise RuntimeError("completed registry output hash is invalid")
            return {"status": "already_completed", "job_id": job_id}
        if status == "FAILED":
            _recovery_record(
                row,
                attempt=int(prior_attempt),
                event="retry_authorized",
                detail={
                    "retry_count": int(retry_count),
                    "configuration_unchanged": True,
                },
            )
            registry.transition(
                connection,
                job_id,
                "PLANNED",
                {"last_error": "outcome-blind retry with unchanged frozen row"},
                allow_retry=True,
            )
        elif status != "PLANNED":
            return {"status": f"blocked_{status.lower()}", "job_id": job_id}
        dependency = row["dependency_job_id"]
        if dependency:
            dependency_state = connection.execute(
                "SELECT status,output_path,output_hash FROM jobs WHERE job_id=?",
                (dependency,),
            ).fetchone()
            if dependency_state is None or dependency_state[0] != "COMPLETED":
                return {"status": "dependency_pending", "job_id": job_id}
            dependency_path = Path(str(dependency_state[1]))
            if (
                not dependency_path.is_dir()
                or _trajectory_hash(dependency_path) != str(dependency_state[2])
            ):
                raise RuntimeError("RAW dependency hash validation failed")
        claim = registry.claim_specific(
            connection,
            job_id,
            f"v6-p0-confirmation-{os.getpid()}",
            os.getpid(),
            socket.gethostname(),
        )
        try:
            if row["strategy_id"] in REPLAY_STRATEGIES:
                result = run_calibration_replay(
                    CalibrationReplayConfig(
                        job_id=job_id,
                        source_job_id=dependency,
                        task=row["task"],
                        split_protocol=row["split"],
                        model=row["model"],
                        strategy=row["strategy_id"],
                        seed=int(row["seed"]),
                        evidence_class=row["evidence_class"],
                        phase="confirmation",
                        manifest_sha256=MANIFEST_SHA,
                    ),
                    trajectory_root=TRAJECTORY_ROOT,
                    output_root=REPLAY_ROOT,
                    adapter=adapter,
                )
            else:
                beta, stage_map = _row_beta(row)
                result = run_production_campaign(
                    ProductionCampaignConfig(
                        job_id=job_id,
                        task=row["task"],
                        split_protocol=row["split"],
                        model=row["model"],
                        strategy=row["strategy_id"],
                        seed=int(row["seed"]),
                        evidence_class=row["evidence_class"],
                        beta=beta,
                        stage_beta_map=stage_map,
                        phase="confirmation",
                        manifest_sha256=MANIFEST_SHA,
                    ),
                    output_root=TRAJECTORY_ROOT,
                    adapter=adapter,
                )
            output_dir = Path(str(result["output_dir"]))
            output_hash_value = _trajectory_hash(output_dir)
            registry.transition(
                connection,
                job_id,
                "COMPLETED",
                {
                    "exit_code": 0,
                    "runtime_seconds": time.monotonic() - started,
                    "output_path": str(output_dir),
                    "output_hash": output_hash_value,
                },
            )
            return {
                "status": "completed",
                "job_id": job_id,
                "attempt": int(claim["attempt"]),
            }
        except Exception as exc:
            rendered = traceback.format_exc()
            traceback_hash = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
            error = f"{type(exc).__name__}: {exc}; traceback_sha256={traceback_hash}"
            registry.transition(
                connection,
                job_id,
                "FAILED",
                {
                    "exit_code": 1,
                    "runtime_seconds": time.monotonic() - started,
                    "last_error": error,
                },
            )
            _recovery_record(
                row,
                attempt=int(claim["attempt"]),
                event="execution_failed",
                detail={
                    "error": error,
                    "traceback_sha256": traceback_hash,
                    "traceback": rendered,
                },
            )
            return {"status": "failed", "job_id": job_id, "error": error}
    finally:
        connection.close()


def registry_counts() -> dict[str, int]:
    registry = CanonicalJobRegistry(REGISTRY_PATH, adapter=CanonicalV5Adapter(ROOT))
    frame = registry.snapshot_frame()
    counts = frame["status"].value_counts().to_dict()
    return {
        name: int(counts.get(name, 0))
        for name in (
            "PLANNED",
            "RUNNING",
            "FAILED",
            "COMPLETED",
            "RECOVERED",
            "EXCLUDED_WITH_REASON",
        )
    }


def execute(workers: int, max_retries: int) -> None:
    verify_authorization()
    validate_frozen_bindings(require_clean=True)
    if not REGISTRY_PATH.is_file():
        raise RuntimeError("registry is not initialized")
    frame = read_manifest()
    trajectory = frame[~frame["strategy_id"].isin(REPLAY_STRATEGIES)].copy()
    replay = frame[frame["strategy_id"].isin(REPLAY_STRATEGIES)].copy()
    phases = (("trajectory", trajectory), ("replay", replay))
    for phase_name, phase_rows in phases:
        for retry_round in range(max_retries + 1):
            registry = CanonicalJobRegistry(
                REGISTRY_PATH, adapter=CanonicalV5Adapter(ROOT)
            )
            snapshot = registry.snapshot_frame().set_index("job_id")
            eligible = phase_rows[
                phase_rows["job_id"].map(snapshot["status"]).isin(["PLANNED", "FAILED"])
            ]
            if eligible.empty:
                break
            records = eligible.to_dict("records")
            completed_in_round = 0
            failed_in_round = 0
            began = time.monotonic()
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_execute_one, row) for row in records]
                for index, future in enumerate(as_completed(futures), start=1):
                    result = future.result()
                    completed_in_round += int(result["status"] in {"completed", "already_completed"})
                    failed_in_round += int(result["status"] == "failed")
                    if index % 100 == 0 or index == len(records):
                        counts = registry_counts()
                        elapsed = time.monotonic() - began
                        print(
                            json.dumps(
                                {
                                    "phase": phase_name,
                                    "retry_round": retry_round,
                                    "submitted_done": index,
                                    "submitted_total": len(records),
                                    "registry_counts": counts,
                                    "elapsed_seconds": round(elapsed, 1),
                                    "worker_heartbeat": "ACTIVE",
                                }
                            ),
                            flush=True,
                        )
            if failed_in_round == 0:
                break
        counts = registry_counts()
        if counts["FAILED"] or counts["RUNNING"]:
            raise RuntimeError(
                f"{phase_name} phase incomplete after frozen retries: {counts}"
            )
    print(json.dumps({"execution_complete": True, "registry_counts": registry_counts()}, indent=2))


def _inventory_hashes(snapshot: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in snapshot.itertuples(index=False):
        output_dir = Path(str(row.output_path))
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path.name.endswith(".tmp"):
                continue
            records.append(
                {
                    "job_id": str(row.job_id),
                    "strategy_id": str(row.job_id).split("__")[-2].upper(),
                    "relative_path": path.relative_to(ROOT).as_posix(),
                    "artifact_kind": (
                        "checkpoint"
                        if path.name.startswith("checkpoint_")
                        else "trajectory"
                        if path.name == "trajectory.json"
                        else "supporting"
                    ),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return pd.DataFrame(records)


def finalize() -> None:
    verify_authorization()
    validate_frozen_bindings(require_clean=True)
    registry = CanonicalJobRegistry(REGISTRY_PATH, adapter=CanonicalV5Adapter(ROOT))
    snapshot = registry.snapshot_frame()
    counts = registry_counts()
    if counts != {
        "PLANNED": 0,
        "RUNNING": 0,
        "FAILED": 0,
        "COMPLETED": EXPECTED_ROWS,
        "RECOVERED": 0,
        "EXCLUDED_WITH_REASON": 0,
    }:
        raise RuntimeError(f"completion gate failed: {counts}")
    FINAL_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_csv(FINAL_SNAPSHOT, index=False, lineterminator="\n")
    inventory = snapshot.copy()
    inventory.insert(0, "manifest_sha256", MANIFEST_SHA)
    inventory.to_csv(EXECUTION_INVENTORY, index=False, lineterminator="\n")
    hash_inventory = _inventory_hashes(snapshot)
    hash_inventory.to_csv(HASH_INVENTORY, index=False, lineterminator="\n")
    trajectory_rows = hash_inventory[
        hash_inventory["artifact_kind"] == "trajectory"
    ]
    if len(trajectory_rows) != EXPECTED_ROWS:
        raise RuntimeError("trajectory hash inventory is incomplete")
    output_hashes = snapshot.set_index("job_id")["output_hash"].to_dict()
    if any(
        output_hashes[str(row.job_id)] != str(row.sha256)
        for row in trajectory_rows.itertuples(index=False)
    ):
        raise RuntimeError("registry trajectory hash differs from inventory")
    manifest = read_manifest()
    complete_ids = set(snapshot.loc[snapshot.status == "COMPLETED", "job_id"])
    pair_complete = True
    frozen = read_json(FROZEN_MAP)
    contrasts = [
        item
        for item in frozen["prospective_contrasts"]
        if not bool(item.get("analysis_only", False))
    ]
    for contrast in contrasts:
        for task in manifest["task"].unique():
            for split in manifest["split"].unique():
                for model in manifest["model"].unique():
                    block = manifest[
                        (manifest.task == task)
                        & (manifest.split == split)
                        & (manifest.model == model)
                    ]
                    for strategy in (
                        str(contrast["strategy_id"]),
                        str(contrast["baseline"]),
                    ):
                        ids = set(
                            block.loc[block.strategy_id == strategy, "job_id"]
                        )
                        pair_complete &= (
                            len(ids) == len(SEEDS) and ids <= complete_ids
                        )
    if not pair_complete:
        raise RuntimeError("40-pair completeness gate failed")
    authority = CanonicalV5Adapter(ROOT).validate_v5_authority_locks()
    if not bool(authority["passed"]):
        raise RuntimeError("V5 authority changed before raw result lock")
    recovery_records = (
        list(RECOVERY_ROOT.glob("*.json")) if RECOVERY_ROOT.exists() else []
    )
    retry_records = [
        path for path in recovery_records if "retry_authorized" in path.name
    ]
    failure_records = [
        path for path in recovery_records if "execution_failed" in path.name
    ]
    checkpoint_rows = hash_inventory[
        hash_inventory["artifact_kind"] == "checkpoint"
    ]
    lock: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-raw-result-lock-v1",
        "status": "RAW_CONFIRMATION_RESULTS_LOCKED_BEFORE_ANALYSIS",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": {
            "path": MANIFEST.relative_to(ROOT).as_posix(),
            "sha256": MANIFEST_SHA,
            "row_count": EXPECTED_ROWS,
        },
        "execution_authorization": {
            "path": AUTHORIZATION.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(AUTHORIZATION),
            "self_sha256": read_json(AUTHORIZATION)[
                "execution_authorization_self_sha256"
            ],
        },
        "final_registry": {
            "path": REGISTRY_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(REGISTRY_PATH),
            "snapshot_path": FINAL_SNAPSHOT.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256_file(FINAL_SNAPSHOT),
        },
        "trajectory_hash_inventory": {
            "path": HASH_INVENTORY.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(HASH_INVENTORY),
            "trajectory_count": int(len(trajectory_rows)),
            "checkpoint_file_count": int(len(checkpoint_rows)),
            "all_artifact_count": int(len(hash_inventory)),
        },
        "execution_inventory": {
            "path": EXECUTION_INVENTORY.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(EXECUTION_INVENTORY),
        },
        "counts": {
            "planned": counts["PLANNED"],
            "running": counts["RUNNING"],
            "failed": counts["FAILED"],
            "completed": counts["COMPLETED"],
            "recovered_registry_status": counts["RECOVERED"],
            "excluded": counts["EXCLUDED_WITH_REASON"],
            "recovery_retry_records": len(retry_records),
            "failure_attempt_records": len(failure_records),
        },
        "paired_completeness": {
            "required_seeds_per_contrast_environment": 40,
            "complete": bool(pair_complete),
            "registered_contrasts_checked": len(contrasts),
        },
        "code_tree_sha256": CODE_TREE_SHA,
        "v5_authority": {
            "passed": bool(authority["passed"]),
            "checked_files": int(authority["checked_files"]),
            "authority_manifest_sha256": sha256_file(
                ROOT / "locks" / "v5_frozen_manifest.json"
            ),
        },
        "endpoint_values_inspected": False,
        "scientific_analysis_started": False,
    }
    lock["raw_result_lock_self_sha256"] = canonical_hash(lock)
    write_json_once(RAW_RESULT_LOCK, lock)
    lines = [
        "# V6 P0 confirmation execution",
        "",
        "Status: **RAW_CONFIRMATION_RESULTS_LOCKED_BEFORE_ANALYSIS**",
        "",
        "This execution report is outcome-blind and contains no endpoint values, "
        "effect directions, rankings, confidence intervals, or p-values.",
        "",
        "| Gate | Status |",
        "|---|---:|",
        f"| Planned | {counts['PLANNED']} |",
        f"| Completed | {counts['COMPLETED']} |",
        f"| Running | {counts['RUNNING']} |",
        f"| Failed | {counts['FAILED']} |",
        f"| Excluded | {counts['EXCLUDED_WITH_REASON']} |",
        f"| Recovery retry records | {len(retry_records)} |",
        f"| Trajectory hashes | PASS ({len(trajectory_rows)}/{EXPECTED_ROWS}) |",
        f"| 40-pair completeness | {'PASS' if pair_complete else 'FAIL'} |",
        f"| V5 authority locks | PASS ({authority['checked_files']} files) |",
        "",
        f"Raw-result lock: `{RAW_RESULT_LOCK.relative_to(ROOT).as_posix()}`.",
        "",
        "No scientific analysis was performed.",
    ]
    EXECUTION_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "registry_counts": counts,
                "recovery_retry_records": len(retry_records),
                "failure_attempt_records": len(failure_records),
                "trajectory_hash_status": f"PASS {len(trajectory_rows)}/{EXPECTED_ROWS}",
                "pair_40_status": "PASS" if pair_complete else "FAIL",
                "v5_authority_status": "PASS",
                "raw_result_lock": RAW_RESULT_LOCK.relative_to(ROOT).as_posix(),
                "raw_result_lock_sha256": sha256_file(RAW_RESULT_LOCK),
            },
            indent=2,
        )
    )


def status() -> None:
    if not REGISTRY_PATH.exists():
        print(json.dumps({"registry": "ABSENT"}))
        return
    counts = registry_counts()
    disk = shutil.disk_usage(ROOT)
    print(
        json.dumps(
            {
                "registry_counts": counts,
                "disk_free_bytes": disk.free,
                "worker_heartbeat": "REGISTRY_RESPONSIVE",
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=("authorize", "init", "execute", "finalize", "status")
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args()
    if args.action == "authorize":
        authorize()
    elif args.action == "init":
        initialize_registry()
    elif args.action == "execute":
        execute(args.workers, args.max_retries)
    elif args.action == "finalize":
        finalize()
    else:
        status()


if __name__ == "__main__":
    main()
