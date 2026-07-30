"""Frozen V6 P0 confirmation endpoint extraction, inference, and result locking.

This module is deliberately limited to the contrasts and methods bound by the
accepted raw-result lock and frozen selection map.  It does not mutate raw
confirmation outputs or any frozen analysis-plan input.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.inference import (
    bh_adjust,
    deterministic_child_seed,
    paired_bootstrap_interval,
    paired_inference,
)


EXPECTED_RAW_LOCK_SELF_HASH = (
    "b5e0caae9573fd0e7b70fc175898765477b30215fb2c1349d1deb867531ab0b2"
)
EXPECTED_SEEDS = tuple(range(7000, 7040))
EXPECTED_JOBS = 12_800
EXPECTED_TRAJECTORIES = 12_800
EXPECTED_CHECKPOINT_FILES = 46_080
EXPECTED_ARTIFACTS = 58_880
EXPECTED_ENVIRONMENTS = 16
EXPECTED_CONTRASTS = 11
BOOTSTRAP_ROOT_SEED = 610001
SIGN_FLIP_ROOT_SEED = 610002
N_RESAMPLES = 10_000
ALPHA = 0.05

RAW_LOCK = ROOT / "locks" / "v6_p0_confirmation_raw_result_lock.json"
FROZEN_MAP = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_FROZEN.json"
HYPOTHESIS_REGISTRY = ROOT / "analysis_plan" / "v6_hypothesis_registry.json"
MULTIPLICITY_REGISTRY = ROOT / "analysis_plan" / "v6_multiplicity_families.json"
ENDPOINT_REGISTRY = ROOT / "analysis_plan" / "v6_endpoint_registry.json"

VALIDATION_REPORT = ROOT / "reports" / "08_p0_raw_result_lock_validation.md"
INFERENCE_REPORT = ROOT / "reports" / "09_p0_confirmation_inference.md"
ENDPOINT_TABLE = ROOT / "tables" / "v6_p0_confirmation_seed_level_endpoints.csv"
ENDPOINT_LOCK = ROOT / "locks" / "v6_p0_confirmation_seed_level_endpoints_lock.json"
PAIR_TABLE = ROOT / "tables" / "v6_p0_confirmation_pair_completeness.csv"
PRIMARY_TABLE = ROOT / "tables" / "v6_p0_confirmation_primary_contrasts.csv"
EFFECTS_TABLE = ROOT / "tables" / "v6_p0_confirmation_environment_effects.csv"
MULTIPLICITY_TABLE = ROOT / "tables" / "v6_p0_confirmation_multiplicity.csv"
H7_TABLE = ROOT / "tables" / "v6_p0_confirmation_h7_direction_table.csv"
SEED_TABLE = ROOT / "tables" / "v6_p0_confirmation_resampling_seeds.csv"
INFERENCE_LOCK = ROOT / "locks" / "v6_p0_confirmation_inference_result_lock.json"

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
CHECKPOINT_LABELS = ("initial", "25pct", "50pct", "75pct")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, content: bytes, *, refresh: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = hashlib.sha256(content).hexdigest()
    if path.exists():
        observed = sha256_file(path)
        if observed == expected:
            return
        if not refresh:
            raise FileExistsError(f"refusing to overwrite divergent artifact: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, Any], *, refresh: bool = False) -> None:
    content = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    atomic_write(path, content, refresh=refresh)


def write_csv(path: Path, frame: pd.DataFrame, *, refresh: bool = False) -> None:
    content = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
        na_rep="",
    ).encode("utf-8")
    atomic_write(path, content, refresh=refresh)


def write_text(path: Path, text: str, *, refresh: bool = False) -> None:
    atomic_write(path, text.encode("utf-8"), refresh=refresh)


def validate_raw_lock() -> dict[str, Any]:
    lock = read_json(RAW_LOCK)
    canonical = dict(lock)
    claimed_self_hash = str(canonical.pop("raw_result_lock_self_sha256"))
    observed_self_hash = canonical_hash(canonical)
    if claimed_self_hash != EXPECTED_RAW_LOCK_SELF_HASH or observed_self_hash != claimed_self_hash:
        raise RuntimeError("raw-result-lock self-hash mismatch")

    bindings = (
        ("manifest", "path", "sha256"),
        ("execution_authorization", "path", "sha256"),
        ("final_registry", "path", "sha256"),
        ("final_registry", "snapshot_path", "snapshot_sha256"),
        ("execution_inventory", "path", "sha256"),
        ("trajectory_hash_inventory", "path", "sha256"),
    )
    checked: list[dict[str, str]] = []
    for section, path_key, hash_key in bindings:
        path = ROOT / str(lock[section][path_key])
        observed = sha256_file(path)
        expected = str(lock[section][hash_key])
        if observed != expected:
            raise RuntimeError(f"raw-result binding mismatch: {section}.{path_key}")
        checked.append(
            {
                "binding": f"{section}.{path_key}",
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": observed,
            }
        )

    registry_path = ROOT / str(lock["final_registry"]["path"])
    with sqlite3.connect(registry_path) as connection:
        registry_counts = dict(
            connection.execute(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY status"
            ).fetchall()
        )
    if registry_counts != {"COMPLETED": EXPECTED_JOBS}:
        raise RuntimeError(f"final registry completion mismatch: {registry_counts}")
    if (
        int(lock["counts"]["completed"]) != EXPECTED_JOBS
        or int(lock["counts"]["failed"]) != 0
        or int(lock["counts"]["excluded"]) != 0
    ):
        raise RuntimeError("locked completion/failure/exclusion counts mismatch")

    inventory_path = ROOT / str(lock["trajectory_hash_inventory"]["path"])
    inventory = pd.read_csv(inventory_path, dtype=str, keep_default_na=False)
    artifact_count = len(inventory)
    trajectory_count = int(inventory["artifact_kind"].eq("trajectory").sum())
    checkpoint_count = int(inventory["artifact_kind"].eq("checkpoint").sum())
    if (
        trajectory_count != EXPECTED_TRAJECTORIES
        or checkpoint_count != EXPECTED_CHECKPOINT_FILES
        or artifact_count != EXPECTED_ARTIFACTS
    ):
        raise RuntimeError("trajectory/checkpoint/artifact inventory count mismatch")
    locked_inventory = lock["trajectory_hash_inventory"]
    if (
        int(locked_inventory["trajectory_count"]) != EXPECTED_TRAJECTORIES
        or int(locked_inventory["checkpoint_file_count"]) != EXPECTED_CHECKPOINT_FILES
        or int(locked_inventory["all_artifact_count"]) != EXPECTED_ARTIFACTS
    ):
        raise RuntimeError("raw lock contains incorrect artifact counts")

    pair = lock["paired_completeness"]
    if (
        not bool(pair["complete"])
        or int(pair["registered_contrasts_checked"]) != EXPECTED_CONTRASTS
        or int(pair["required_seeds_per_contrast_environment"]) != len(EXPECTED_SEEDS)
    ):
        raise RuntimeError("locked paired-completeness declaration mismatch")

    authority = CanonicalV5Adapter(ROOT).validate_v5_authority_locks()
    authority_manifest = ROOT / "locks" / "v5_frozen_manifest.json"
    if (
        not bool(authority["passed"])
        or int(authority["checked_files"]) != 18
        or sha256_file(authority_manifest)
        != str(lock["v5_authority"]["authority_manifest_sha256"])
    ):
        raise RuntimeError("V5 authority 18/18 changed")

    frozen = read_json(FROZEN_MAP)
    contrasts = [
        item
        for item in frozen["prospective_contrasts"]
        if not bool(item.get("analysis_only", False))
    ]
    if len(contrasts) != EXPECTED_CONTRASTS:
        raise RuntimeError("frozen contrast count mismatch")
    return {
        "lock": lock,
        "checked_bindings": checked,
        "registry_counts": registry_counts,
        "trajectory_count": trajectory_count,
        "checkpoint_count": checkpoint_count,
        "artifact_count": artifact_count,
        "contrast_count": len(contrasts),
        "v5_checked_files": int(authority["checked_files"]),
    }


def validation_report_text() -> str:
    return """# V6 P0 raw-result lock validation

Status: **PASS - FROZEN INFERENCE MAY PROCEED**

Validation was completed before any confirmation endpoint value was read.

| Validation gate | Result |
|---|---:|
| Raw-result-lock canonical self-hash | PASS |
| Expected self-hash `b5e0caae9573fd0e7b70fc175898765477b30215fb2c1349d1deb867531ab0b2` | MATCH |
| Manifest hash | PASS |
| Execution-authorization hash | PASS |
| Final-registry hash | PASS |
| Final registry-snapshot hash | PASS |
| Execution-inventory hash | PASS |
| Trajectory-hash-inventory hash | PASS |
| Completed jobs | PASS (12,800) |
| Final failed jobs | PASS (0) |
| Final excluded jobs | PASS (0) |
| Trajectory hashes | PASS (12,800) |
| Checkpoint-file hashes | PASS (46,080) |
| Total artifact hashes | PASS (58,880) |
| Registered pair gate | PASS (11 contrasts x 16 environments x 40 seeds) |
| Registered seed set | PASS (7000-7039) |
| V5 authority | PASS (18/18 unchanged) |

No frozen map, manifest, hypothesis, contrast direction, multiplicity family,
endpoint definition, beta map, exclusion rule, or raw-result file was modified.
"""


def validate_and_report(*, refresh: bool = False) -> None:
    validate_raw_lock()
    write_text(VALIDATION_REPORT, validation_report_text(), refresh=refresh)


def registry_frame(lock: dict[str, Any]) -> pd.DataFrame:
    with sqlite3.connect(ROOT / str(lock["final_registry"]["path"])) as connection:
        return pd.read_sql_query("SELECT * FROM jobs ORDER BY job_id", connection)


def recovery_events() -> dict[str, list[dict[str, Any]]]:
    root = ROOT / "results" / "v6_p0_confirmation" / "recovery_records"
    events: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(root.glob("*.json")):
        record = read_json(path)
        item = {
            "event": str(record["event"]),
            "attempt": int(record["attempt"]),
            "recorded_utc": str(record["recorded_utc"]),
            "record_sha256": sha256_file(path),
        }
        events.setdefault(str(record["job_id"]), []).append(item)
    return events


def _fallback_status(status: str) -> bool:
    lowered = status.lower()
    return "fallback" in lowered or "insufficient" in lowered


def materialize_endpoints(*, refresh: bool = False) -> dict[str, Any]:
    validation = validate_raw_lock()
    lock = validation["lock"]
    manifest_path = ROOT / str(lock["manifest"]["path"])
    manifest = pd.read_csv(manifest_path, dtype={"seed": int}, keep_default_na=False)
    registry = registry_frame(lock)
    joined = manifest.merge(
        registry[
            [
                "job_id",
                "status",
                "attempt",
                "retry_count",
                "last_error",
                "output_path",
                "output_hash",
            ]
        ],
        on="job_id",
        how="left",
        validate="one_to_one",
    )
    if len(joined) != EXPECTED_JOBS or not joined["status"].eq("COMPLETED").all():
        raise RuntimeError("endpoint extraction requires 12,800 completed manifest rows")

    trajectory_inventory = pd.read_csv(
        ROOT / str(lock["trajectory_hash_inventory"]["path"]),
        dtype=str,
        keep_default_na=False,
    )
    trajectory_inventory = trajectory_inventory.loc[
        trajectory_inventory["artifact_kind"].eq("trajectory")
    ].copy()
    if trajectory_inventory["job_id"].duplicated().any():
        raise RuntimeError("trajectory inventory has duplicate job IDs")
    inventory_by_job = trajectory_inventory.set_index("job_id")
    event_by_job = recovery_events()

    records: list[dict[str, Any]] = []
    for row in joined.itertuples(index=False):
        output_dir = Path(str(row.output_path))
        trajectory_path = output_dir / "trajectory.json"
        if str(row.job_id) not in inventory_by_job.index:
            raise RuntimeError(f"trajectory inventory lacks {row.job_id}")
        inventory_row = inventory_by_job.loc[str(row.job_id)]
        observed_trajectory_hash = sha256_file(trajectory_path)
        if (
            observed_trajectory_hash != str(row.output_hash)
            or observed_trajectory_hash != str(inventory_row["sha256"])
        ):
            raise RuntimeError(f"trajectory hash mismatch during extraction: {row.job_id}")

        trace = read_json(trajectory_path)
        endpoints = dict(trace.get("endpoints", {}))
        diagnostic_path = output_dir / "diagnostic_metrics.parquet"
        diagnostic = pd.read_parquet(diagnostic_path)
        diagnostic = diagnostic[
            [
                column
                for column in (
                    "mean_absolute_coverage_error",
                    "scale_status",
                    "checkpoint_label",
                )
                if column in diagnostic.columns
            ]
        ]
        checkpoint_rows = dict(trace["checkpoint_rows"])
        checkpoint_values: dict[str, float] = {}
        for label in CHECKPOINT_LABELS:
            if label not in checkpoint_rows:
                raise RuntimeError(f"missing checkpoint row {label}: {row.job_id}")
            position = int(checkpoint_rows[label])
            if position < 0 or position >= len(diagnostic):
                raise RuntimeError(f"invalid checkpoint row {label}: {row.job_id}")
            checkpoint_values[label] = float(
                diagnostic.iloc[position]["mean_absolute_coverage_error"]
            )

        l1 = float(endpoints.get("l1_campaign_mace", np.nan))
        requires_l4 = "L4" in str(row.endpoint_requirements)
        l4 = float(endpoints.get("l4_top1pct_recall_nauc", np.nan))
        checkpoint_mean = float(np.mean(list(checkpoint_values.values())))
        components_match = bool(np.isclose(checkpoint_mean, l1, rtol=0.0, atol=1e-12))

        if str(row.strategy_id) in REPLAY_STRATEGIES:
            status_values = (
                diagnostic["scale_status"].astype(str).tolist()
                if "scale_status" in diagnostic
                else []
            )
            job_kind = "calibration_replay"
        else:
            rounds = pd.read_parquet(output_dir / "rounds.parquet", columns=["scale_status"])
            status_values = rounds["scale_status"].astype(str).tolist()
            job_kind = "production_campaign"
        unique_statuses = sorted(set(status_values))
        fallback_counts = {
            status: status_values.count(status)
            for status in unique_statuses
            if _fallback_status(status)
        }
        fallback_payload: list[Any] | dict[str, int] = (
            fallback_counts if fallback_counts else []
        )
        finite_components = bool(np.isfinite(list(checkpoint_values.values())).all())
        endpoint_valid = bool(
            np.isfinite(l1)
            and finite_components
            and components_match
            and ((not requires_l4 and np.isnan(l4)) or (requires_l4 and np.isfinite(l4)))
        )
        if not endpoint_valid:
            raise RuntimeError(f"invalid registered endpoint: {row.job_id}")

        recovery = event_by_job.get(str(row.job_id), [])
        records.append(
            {
                "manifest_job_id": str(row.job_id),
                "task": str(row.task),
                "split": str(row.split),
                "model": str(row.model),
                "environment": "__".join((str(row.task), str(row.split), str(row.model))),
                "seed": int(row.seed),
                "canonical_strategy": str(row.strategy_id),
                "endpoint_requirements": str(row.endpoint_requirements),
                "job_kind": job_kind,
                "completion_status": str(row.status),
                "endpoint_validity_status": "VALID",
                "l1_campaign_mace": l1,
                "l4_top1pct_recall_nauc": l4 if requires_l4 else np.nan,
                "l1_mace_initial": checkpoint_values["initial"],
                "l1_mace_25pct": checkpoint_values["25pct"],
                "l1_mace_50pct": checkpoint_values["50pct"],
                "l1_mace_75pct": checkpoint_values["75pct"],
                "checkpoint_l1_mean_matches": components_match,
                "fallback_event_count": int(sum(fallback_counts.values())),
                "fallback_events_json": json.dumps(
                    fallback_payload, sort_keys=True, separators=(",", ":")
                ),
                "scale_statuses_json": json.dumps(
                    unique_statuses, sort_keys=True, separators=(",", ":")
                ),
                "recovery_attempt": int(row.attempt),
                "recovery_retry_count": int(row.retry_count),
                "recovery_event_count": len(recovery),
                "recovery_events_json": json.dumps(
                    recovery, sort_keys=True, separators=(",", ":")
                ),
                "trajectory_path": trajectory_path.relative_to(ROOT).as_posix(),
                "trajectory_sha256": observed_trajectory_hash,
            }
        )

    endpoints = pd.DataFrame(records).sort_values(
        ["task", "split", "model", "seed", "canonical_strategy"],
        kind="stable",
    )
    key = ["task", "split", "model", "seed", "canonical_strategy"]
    if len(endpoints) != EXPECTED_JOBS or endpoints.duplicated(key).any():
        raise RuntimeError("seed-level endpoint table cardinality/uniqueness failure")
    if set(endpoints["seed"].astype(int)) != set(EXPECTED_SEEDS):
        raise RuntimeError("seed-level endpoint table contains an unregistered seed set")
    write_csv(ENDPOINT_TABLE, endpoints, refresh=refresh)

    endpoint_lock: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-seed-level-endpoints-lock-v1",
        "status": "ENDPOINT_TABLE_LOCKED_BEFORE_INFERENCE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "raw_result_lock": {
            "path": RAW_LOCK.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(RAW_LOCK),
            "self_sha256": EXPECTED_RAW_LOCK_SELF_HASH,
        },
        "endpoint_table": {
            "path": ENDPOINT_TABLE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(ENDPOINT_TABLE),
            "row_count": int(len(endpoints)),
            "unique_job_count": int(endpoints["manifest_job_id"].nunique()),
            "unique_environment_count": int(endpoints["environment"].nunique()),
            "seed_first": min(EXPECTED_SEEDS),
            "seed_last": max(EXPECTED_SEEDS),
        },
        "endpoint_values_read_only_from_locked_outputs": True,
        "aggregation_or_ranking_performed_during_extraction": False,
    }
    endpoint_lock["endpoint_table_lock_self_sha256"] = canonical_hash(endpoint_lock)
    write_json(ENDPOINT_LOCK, endpoint_lock, refresh=refresh)
    verify_endpoint_lock()
    return endpoint_lock


def verify_endpoint_lock() -> dict[str, Any]:
    validate_raw_lock()
    lock = read_json(ENDPOINT_LOCK)
    canonical = dict(lock)
    claimed = str(canonical.pop("endpoint_table_lock_self_sha256"))
    if canonical_hash(canonical) != claimed:
        raise RuntimeError("endpoint-table lock self-hash mismatch")
    if (
        str(lock["raw_result_lock"]["self_sha256"]) != EXPECTED_RAW_LOCK_SELF_HASH
        or sha256_file(RAW_LOCK) != str(lock["raw_result_lock"]["sha256"])
        or sha256_file(ENDPOINT_TABLE) != str(lock["endpoint_table"]["sha256"])
        or int(lock["endpoint_table"]["row_count"]) != EXPECTED_JOBS
    ):
        raise RuntimeError("endpoint-table lock binding mismatch")
    return lock


def frozen_contrasts() -> list[dict[str, Any]]:
    frozen = read_json(FROZEN_MAP)
    contrasts = [
        dict(item)
        for item in frozen["prospective_contrasts"]
        if not bool(item.get("analysis_only", False))
    ]
    if [item["id"] for item in contrasts] != [
        "H1",
        "H5A",
        "H2A",
        "H2B",
        "H5B",
        "H5C",
        "H3",
        "H4",
        "H6A",
        "H6B",
        "H6",
    ]:
        raise RuntimeError("frozen contrast order/content changed")
    return contrasts


def endpoint_column(endpoint: str) -> str:
    if endpoint == "L1":
        return "l1_campaign_mace"
    if endpoint == "L4":
        return "l4_top1pct_recall_nauc"
    raise ValueError(f"unsupported registered endpoint: {endpoint}")


def paired_difference_frame(
    endpoints: pd.DataFrame, contrast: dict[str, Any]
) -> pd.DataFrame:
    value = endpoint_column(str(contrast["endpoint"]))
    key = ["task", "split", "model", "environment", "seed"]
    strategy = endpoints.loc[
        endpoints["canonical_strategy"].eq(str(contrast["strategy_id"])),
        key + [value, "endpoint_validity_status"],
    ].copy()
    baseline = endpoints.loc[
        endpoints["canonical_strategy"].eq(str(contrast["baseline"])),
        key + [value, "endpoint_validity_status"],
    ].copy()
    if strategy.duplicated(key).any() or baseline.duplicated(key).any():
        raise RuntimeError(f"duplicate registered seed rows for {contrast['id']}")
    paired = baseline.merge(
        strategy,
        on=key,
        how="outer",
        validate="one_to_one",
        indicator=True,
        suffixes=("_baseline", "_strategy"),
    )
    paired["endpoint_missing"] = (
        ~paired["_merge"].eq("both")
        | ~paired["endpoint_validity_status_baseline"].eq("VALID")
        | ~paired["endpoint_validity_status_strategy"].eq("VALID")
        | ~np.isfinite(pd.to_numeric(paired[f"{value}_baseline"], errors="coerce"))
        | ~np.isfinite(pd.to_numeric(paired[f"{value}_strategy"], errors="coerce"))
    )
    paired["paired_difference"] = (
        pd.to_numeric(paired[f"{value}_strategy"], errors="coerce")
        - pd.to_numeric(paired[f"{value}_baseline"], errors="coerce")
    )
    return paired.sort_values(key, kind="stable").reset_index(drop=True)


def pair_completeness(endpoints: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    expected = set(EXPECTED_SEEDS)
    for contrast in frozen_contrasts():
        paired = paired_difference_frame(endpoints, contrast)
        for environment, block in paired.groupby("environment", sort=True):
            task = str(block["task"].iloc[0])
            split = str(block["split"].iloc[0])
            model = str(block["model"].iloc[0])
            strategy_seeds = set(
                block.loc[
                    block["_merge"].isin(["both", "right_only"]), "seed"
                ].dropna().astype(int)
            )
            baseline_seeds = set(
                block.loc[
                    block["_merge"].isin(["both", "left_only"]), "seed"
                ].dropna().astype(int)
            )
            complete = block.loc[~block["endpoint_missing"]]
            complete_seeds = set(complete["seed"].astype(int))
            missing_strategy = sorted(expected - strategy_seeds)
            missing_baseline = sorted(expected - baseline_seeds)
            invalid_count = int(block["endpoint_missing"].sum())
            gate = bool(
                len(block) == 40
                and strategy_seeds == expected
                and baseline_seeds == expected
                and complete_seeds == expected
                and invalid_count == 0
            )
            rows.append(
                {
                    "hypothesis_id": str(contrast["id"]),
                    "family": str(contrast["family"]),
                    "endpoint": str(contrast["endpoint"]),
                    "strategy_id": str(contrast["strategy_id"]),
                    "baseline": str(contrast["baseline"]),
                    "task": task,
                    "split": split,
                    "model": model,
                    "environment": str(environment),
                    "required_seed_first": min(EXPECTED_SEEDS),
                    "required_seed_last": max(EXPECTED_SEEDS),
                    "expected_pair_count": len(EXPECTED_SEEDS),
                    "strategy_row_count": len(strategy_seeds),
                    "baseline_row_count": len(baseline_seeds),
                    "complete_pair_count": len(complete_seeds),
                    "duplicate_strategy_seed_count": 0,
                    "duplicate_baseline_seed_count": 0,
                    "missing_strategy_seeds": "|".join(map(str, missing_strategy)),
                    "missing_baseline_seeds": "|".join(map(str, missing_baseline)),
                    "endpoint_missing_pair_count": invalid_count,
                    "unregistered_exclusion_count": 0,
                    "gate_status": "PASS" if gate else "FAIL",
                    "blocked_primary_inference": not gate,
                }
            )
    result = pd.DataFrame(rows).sort_values(
        ["hypothesis_id", "task", "split", "model"], kind="stable"
    )
    if len(result) != EXPECTED_CONTRASTS * EXPECTED_ENVIRONMENTS:
        raise RuntimeError("pair-completeness table does not cover 11 x 16 environments")
    return result


def aggregate_seed_effects(
    paired: pd.DataFrame,
    *,
    level: str,
    label: str,
) -> np.ndarray:
    if level == "pooled":
        block = paired
    elif level == "task":
        block = paired.loc[paired["task"].eq(label)]
    elif level == "split":
        block = paired.loc[paired["split"].eq(label)]
    elif level == "model":
        block = paired.loc[paired["model"].eq(label)]
    elif level == "environment":
        block = paired.loc[paired["environment"].eq(label)]
    else:
        raise ValueError(level)
    if bool(block["endpoint_missing"].any()):
        raise RuntimeError(f"endpoint missingness in {level}:{label}")
    means = (
        block.groupby("seed", sort=True)["paired_difference"]
        .mean()
        .reindex(EXPECTED_SEEDS)
    )
    if means.isna().any() or len(means) != 40:
        raise RuntimeError(f"40-seed aggregation failed for {level}:{label}")
    return means.to_numpy(float)


def stratum_specs(paired: pd.DataFrame) -> Iterable[tuple[str, str, str]]:
    yield ("pooled", "POOLED", "POOLED")
    for value in sorted(paired["task"].unique()):
        yield ("task", str(value), f"TASK:{value}")
    for value in sorted(paired["split"].unique()):
        yield ("split", str(value), f"SPLIT:{value}")
    for value in sorted(paired["model"].unique()):
        yield ("model", str(value), f"MODEL:{value}")
    for value in sorted(paired["environment"].unique()):
        yield ("environment", str(value), f"ENVIRONMENT:{value}")


def analyze_contrasts(
    endpoints: pd.DataFrame, pairs: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not pairs["gate_status"].eq("PASS").all():
        failed = sorted(pairs.loc[pairs["gate_status"].eq("FAIL"), "hypothesis_id"].unique())
        raise RuntimeError(f"primary inference blocked by completeness gates: {failed}")

    effects: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []
    for contrast in frozen_contrasts():
        paired = paired_difference_frame(endpoints, contrast)
        is_descriptive = str(contrast["id"]) == "H6"
        for level, label, seed_label in stratum_specs(paired):
            differences = aggregate_seed_effects(paired, level=level, label=label)
            bootstrap_seed = deterministic_child_seed(
                BOOTSTRAP_ROOT_SEED,
                str(contrast["family"]),
                seed_label,
                str(contrast["id"]),
                str(contrast["endpoint"]),
            )
            if level == "pooled" and not is_descriptive:
                estimate = paired_inference(
                    differences,
                    family=str(contrast["family"]),
                    environment=seed_label,
                    contrast=str(contrast["id"]),
                    endpoint=str(contrast["endpoint"]),
                    bootstrap_root_seed=BOOTSTRAP_ROOT_SEED,
                    sign_flip_root_seed=SIGN_FLIP_ROOT_SEED,
                    alternative=str(contrast["alternative"]),
                )
                lower = estimate.bootstrap_ci_lower
                upper = estimate.bootstrap_ci_upper
                raw_p = estimate.sign_flip_p_value
                sign_seed: float | int = estimate.sign_flip_seed
                seed_records.append(
                    {
                        "hypothesis_id": str(contrast["id"]),
                        "endpoint": str(contrast["endpoint"]),
                        "family": str(contrast["family"]),
                        "aggregation_level": level,
                        "aggregation_label": label,
                        "resampling_method": "paired_sign_flip",
                        "root_seed": SIGN_FLIP_ROOT_SEED,
                        "child_seed": int(sign_seed),
                        "resample_count": N_RESAMPLES,
                    }
                )
            else:
                lower, upper = paired_bootstrap_interval(
                    differences,
                    seed=bootstrap_seed,
                    n_resamples=N_RESAMPLES,
                )
                raw_p = np.nan
                sign_seed = np.nan
            seed_records.append(
                {
                    "hypothesis_id": str(contrast["id"]),
                    "endpoint": str(contrast["endpoint"]),
                    "family": str(contrast["family"]),
                    "aggregation_level": level,
                    "aggregation_label": label,
                    "resampling_method": "paired_bootstrap",
                    "root_seed": BOOTSTRAP_ROOT_SEED,
                    "child_seed": int(bootstrap_seed),
                    "resample_count": N_RESAMPLES,
                }
            )
            effects.append(
                {
                    "hypothesis_id": str(contrast["id"]),
                    "classification": str(contrast["classification"]),
                    "family": str(contrast["family"]),
                    "endpoint": str(contrast["endpoint"]),
                    "strategy_id": str(contrast["strategy_id"]),
                    "baseline": str(contrast["baseline"]),
                    "alternative": str(contrast["alternative"]),
                    "aggregation_level": level,
                    "aggregation_label": label,
                    "seed_pairing_rule": "mean within registered stratum for each shared seed",
                    "n_pairs": len(differences),
                    "underlying_environment_seed_pairs": (
                        640
                        if level == "pooled"
                        else 160
                        if level == "task"
                        else 320
                        if level in {"split", "model"}
                        else 40
                    ),
                    "mean_paired_effect": float(np.mean(differences)),
                    "bootstrap_ci_lower": float(lower),
                    "bootstrap_ci_upper": float(upper),
                    "raw_p_value": raw_p,
                    "adjusted_p_value": np.nan,
                    "bootstrap_seed": int(bootstrap_seed),
                    "sign_flip_seed": sign_seed,
                    "resample_count": N_RESAMPLES,
                    "multiplicity_scope": (
                        "registered pooled inference"
                        if level == "pooled" and not is_descriptive
                        else "descriptive heterogeneity diagnostic"
                        if level != "pooled"
                        else "descriptive estimate only"
                    ),
                }
            )

    effects_frame = pd.DataFrame(effects).sort_values(
        ["hypothesis_id", "aggregation_level", "aggregation_label"], kind="stable"
    )
    primary = effects_frame.loc[effects_frame["aggregation_level"].eq("pooled")].copy()
    environment = effects_frame.loc[
        ~effects_frame["aggregation_level"].eq("pooled")
    ].copy()

    env_only = environment.loc[environment["aggregation_level"].eq("environment")]
    sign_summary: dict[str, dict[str, Any]] = {}
    for hypothesis_id, group in env_only.groupby("hypothesis_id", sort=False):
        pooled_effect = float(
            primary.loc[
                primary["hypothesis_id"].eq(hypothesis_id), "mean_paired_effect"
            ].iloc[0]
        )
        values = group["mean_paired_effect"].to_numpy(float)
        pooled_sign = int(np.sign(pooled_effect))
        same = int(np.count_nonzero(np.sign(values) == pooled_sign))
        sign_summary[str(hypothesis_id)] = {
            "environment_same_direction_count": same,
            "environment_opposite_direction_count": int(len(values) - same),
            "environment_same_direction_fraction": float(same / len(values)),
            "environment_effect_minimum": float(np.min(values)),
            "environment_effect_maximum": float(np.max(values)),
        }
    for column in (
        "environment_same_direction_count",
        "environment_opposite_direction_count",
        "environment_same_direction_fraction",
        "environment_effect_minimum",
        "environment_effect_maximum",
    ):
        primary[column] = primary["hypothesis_id"].map(
            lambda value: sign_summary[str(value)][column]
        )
    primary["complete_environment_count"] = EXPECTED_ENVIRONMENTS
    primary["completeness_gate_status"] = "PASS"
    primary["confirmatory_binary_claim"] = ~primary["hypothesis_id"].eq("H6")
    primary["inference_role"] = np.where(
        primary["hypothesis_id"].eq("H6"),
        "descriptive_estimate_only_no_binary_or_noninferiority_claim",
        "multiplicity_adjusted_confirmatory",
    )
    return (
        primary.reset_index(drop=True),
        environment.reset_index(drop=True),
        pd.DataFrame(seed_records).sort_values(
            [
                "hypothesis_id",
                "aggregation_level",
                "aggregation_label",
                "resampling_method",
            ],
            kind="stable",
        ),
    )


def apply_multiplicity(
    primary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    registry = read_json(MULTIPLICITY_REGISTRY)
    registered_families = {
        str(item["id"]): list(map(str, item.get("members", [])))
        for item in registry["families"]
        if str(item["id"]).startswith("P0_")
    }
    rows: list[dict[str, Any]] = []
    adjusted_by_hypothesis: dict[str, float] = {}
    for family, members in registered_families.items():
        block = primary.set_index("hypothesis_id").loc[members]
        p_values = block["raw_p_value"].to_numpy(float)
        adjusted = bh_adjust(p_values)
        order = np.argsort(p_values, kind="stable")
        ranks = np.empty(len(members), dtype=int)
        ranks[order] = np.arange(1, len(members) + 1)
        for index, hypothesis_id in enumerate(members):
            adjusted_by_hypothesis[hypothesis_id] = float(adjusted[index])
            rows.append(
                {
                    "family": family,
                    "family_size": len(members),
                    "hypothesis_id": hypothesis_id,
                    "raw_p_value": float(p_values[index]),
                    "bh_rank": int(ranks[index]),
                    "adjusted_p_value": float(adjusted[index]),
                    "alpha": ALPHA,
                    "reject_adjusted": bool(adjusted[index] <= ALPHA),
                    "method": "Benjamini-Hochberg within exact registered family",
                }
            )
    multiplicity = pd.DataFrame(rows).sort_values(
        ["family", "bh_rank", "hypothesis_id"], kind="stable"
    )
    if len(multiplicity) != 10 or set(multiplicity["hypothesis_id"]) != {
        "H1",
        "H5A",
        "H2A",
        "H2B",
        "H5B",
        "H5C",
        "H3",
        "H4",
        "H6A",
        "H6B",
    }:
        raise RuntimeError("multiplicity membership changed")
    output = primary.copy()
    output["adjusted_p_value"] = output["hypothesis_id"].map(adjusted_by_hypothesis)
    output["reject_adjusted_alpha_0_05"] = output["adjusted_p_value"].map(
        lambda value: bool(value <= ALPHA) if pd.notna(value) else np.nan
    )
    return output, multiplicity


def h7_direction_table(primary: pd.DataFrame) -> pd.DataFrame:
    frozen = read_json(FROZEN_MAP)
    h7 = next(item for item in frozen["prospective_contrasts"] if item["id"] == "H7")
    by_hypothesis = primary.set_index("hypothesis_id")
    rows: list[dict[str, Any]] = []
    for item in h7["method_contrasts"]:
        hypothesis_id = str(item["hypothesis_id"])
        source = by_hypothesis.loc[hypothesis_id]
        effect = float(source["mean_paired_effect"])
        endpoint = str(item["endpoint"])
        favorable = effect < 0 if endpoint == "L1" else effect > 0
        rows.append(
            {
                "h7_row_id": f"H7__{hypothesis_id}",
                "source_hypothesis_id": hypothesis_id,
                "strategy_id": str(item["strategy_id"]),
                "baseline": str(item["baseline"]),
                "endpoint": endpoint,
                "endpoint_direction": (
                    "lower_is_better" if endpoint == "L1" else "higher_is_better"
                ),
                "pooled_mean_paired_effect": effect,
                "bootstrap_ci_lower": float(source["bootstrap_ci_lower"]),
                "bootstrap_ci_upper": float(source["bootstrap_ci_upper"]),
                "observed_direction": (
                    "strategy_minus_baseline_negative"
                    if effect < 0
                    else "strategy_minus_baseline_positive"
                    if effect > 0
                    else "zero"
                ),
                "direction_relative_to_endpoint": (
                    "favorable" if favorable else "unfavorable" if effect != 0 else "neutral"
                ),
                "binary_claim": False,
                "multiplicity_family": "NONE_DESCRIPTIVE",
                "interpretation": "registered analysis-only descriptive direction row",
            }
        )
    if len(rows) != 11:
        raise RuntimeError("H7 frozen direction table must contain exactly 11 rows")
    return pd.DataFrame(rows)


def format_number(value: float) -> str:
    return f"{float(value):.8g}"


def format_p(value: float) -> str:
    return f"{float(value):.6g}"


def inference_report_text(
    primary: pd.DataFrame,
    effects: pd.DataFrame,
    multiplicity: pd.DataFrame,
    h7: pd.DataFrame,
    pairs: pd.DataFrame,
) -> str:
    lines = [
        "# V6 P0 frozen confirmation inference",
        "",
        "Status: **FROZEN INFERENTIAL ANALYSIS COMPLETE AND LOCK-READY**",
        "",
        "The independent paired unit for pooled inference is the registered seed. "
        "For each seed, the paired strategy-minus-baseline effect is averaged equally "
        "over all 16 task x split x model environments before the registered paired "
        "bootstrap and sign-flip procedures are applied (40 paired seed blocks). "
        "Environment, task, split, and model results are prespecified heterogeneity "
        "diagnostics and do not replace the pooled inference.",
        "",
        "## Multiplicity-adjusted confirmatory conclusions",
        "",
        "| ID | Endpoint | Effect (strategy - baseline) | 95% paired bootstrap CI | Raw p | BH-adjusted p | Conclusion |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    confirmatory = primary.loc[~primary["hypothesis_id"].eq("H6")]
    for row in confirmatory.itertuples(index=False):
        conclusion = (
            "reject registered null after BH correction"
            if bool(row.reject_adjusted_alpha_0_05)
            else "do not reject registered null after BH correction"
        )
        lines.append(
            f"| {row.hypothesis_id} | {row.endpoint} | {format_number(row.mean_paired_effect)} "
            f"| [{format_number(row.bootstrap_ci_lower)}, {format_number(row.bootstrap_ci_upper)}] "
            f"| {format_p(row.raw_p_value)} | {format_p(row.adjusted_p_value)} | {conclusion} |"
        )

    h6 = primary.loc[primary["hypothesis_id"].eq("H6")].iloc[0]
    lines.extend(
        [
            "",
            "## Descriptive H6 and H7 results",
            "",
            f"H6 (SCALAR_TEMPERATURE_RESIDUAL_RATIO - SELECTED_CS, L1) had a pooled "
            f"paired effect of {format_number(h6['mean_paired_effect'])} "
            f"(95% paired bootstrap CI "
            f"[{format_number(h6['bootstrap_ci_lower'])}, "
            f"{format_number(h6['bootstrap_ci_upper'])}]; 40 paired seed blocks). "
            "No p-value, binary conclusion, or noninferiority claim was generated.",
            "",
            "| H7 row | Endpoint | Strategy - baseline | Effect | Direction relative to endpoint |",
            "|---|---|---|---:|---|",
        ]
    )
    for row in h7.itertuples(index=False):
        lines.append(
            f"| {row.source_hypothesis_id} | {row.endpoint} | "
            f"{row.strategy_id} - {row.baseline} | "
            f"{format_number(row.pooled_mean_paired_effect)} | "
            f"{row.direction_relative_to_endpoint} |"
        )

    lines.extend(
        [
            "",
            "## Prespecified heterogeneity diagnostics",
            "",
            "| ID | Same pooled direction across environments | Environment-effect range | Pair count per environment |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in primary.itertuples(index=False):
        lines.append(
            f"| {row.hypothesis_id} | "
            f"{row.environment_same_direction_count}/16 | "
            f"[{format_number(row.environment_effect_minimum)}, "
            f"{format_number(row.environment_effect_maximum)}] | 40 |"
        )
    lines.extend(
        [
            "",
            "All task-level (4 per contrast), split-level (2), model-level (2), and "
            "environment-level (16) paired estimates and intervals are reported in "
            "`tables/v6_p0_confirmation_environment_effects.csv`. These diagnostics "
            "were not substituted for the pooled confirmatory analyses.",
            "",
            "## Completeness gates",
            "",
            f"- Passed environments: {int(pairs['gate_status'].eq('PASS').sum())}/"
            f"{len(pairs)}.",
            f"- Failed completeness gates: {int(pairs['gate_status'].eq('FAIL').sum())}.",
            "- Each registered contrast/environment contains exactly seeds 7000-7039, "
            "both strategy and baseline, no duplicate seed, no unregistered exclusion, "
            "and no endpoint missingness.",
            "",
            "No post-hoc contrast, exclusion, endpoint, multiplicity family, method "
            "change, environment selection, or exploratory analysis was introduced.",
            "",
        ]
    )
    return "\n".join(lines)


def run_inference(*, refresh: bool = False) -> None:
    verify_endpoint_lock()
    endpoints = pd.read_csv(
        ENDPOINT_TABLE,
        dtype={"seed": int},
        keep_default_na=False,
        na_values=[""],
    )
    pairs = pair_completeness(endpoints)
    write_csv(PAIR_TABLE, pairs, refresh=refresh)
    if not pairs["gate_status"].eq("PASS").all():
        raise RuntimeError("one or more registered 40-pair gates failed")

    primary, effects, seeds = analyze_contrasts(endpoints, pairs)
    primary, multiplicity = apply_multiplicity(primary)
    h7 = h7_direction_table(primary)
    write_csv(PRIMARY_TABLE, primary, refresh=refresh)
    write_csv(EFFECTS_TABLE, effects, refresh=refresh)
    write_csv(MULTIPLICITY_TABLE, multiplicity, refresh=refresh)
    write_csv(H7_TABLE, h7, refresh=refresh)
    write_csv(SEED_TABLE, seeds, refresh=refresh)
    write_text(
        INFERENCE_REPORT,
        inference_report_text(primary, effects, multiplicity, h7, pairs),
        refresh=refresh,
    )


def analysis_code_tree() -> dict[str, Any]:
    paths = [
        ROOT / "scripts" / "analyze_v6_p0_confirmation.py",
        ROOT / "src" / "transportability_v6" / "inference.py",
    ]
    files = [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
        for path in paths
    ]
    return {"files": files, "sha256": canonical_hash(files)}


def create_inference_lock(*, refresh: bool = False) -> dict[str, Any]:
    validate_raw_lock()
    endpoint_lock = verify_endpoint_lock()
    required = [
        PAIR_TABLE,
        PRIMARY_TABLE,
        EFFECTS_TABLE,
        MULTIPLICITY_TABLE,
        H7_TABLE,
        SEED_TABLE,
        VALIDATION_REPORT,
        INFERENCE_REPORT,
    ]
    if any(not path.is_file() for path in required):
        raise FileNotFoundError("inference result package is incomplete")
    pairs = pd.read_csv(PAIR_TABLE)
    primary = pd.read_csv(PRIMARY_TABLE)
    effects = pd.read_csv(EFFECTS_TABLE)
    multiplicity = pd.read_csv(MULTIPLICITY_TABLE)
    h7 = pd.read_csv(H7_TABLE)
    seeds = pd.read_csv(SEED_TABLE)
    if (
        len(pairs) != 176
        or not pairs["gate_status"].eq("PASS").all()
        or len(primary) != 11
        or len(effects) != 11 * (4 + 2 + 2 + 16)
        or len(multiplicity) != 10
        or len(h7) != 11
    ):
        raise RuntimeError("inference result cardinality validation failed")

    files = {
        "raw_lock_validation_report": VALIDATION_REPORT,
        "endpoint_table": ENDPOINT_TABLE,
        "endpoint_table_lock": ENDPOINT_LOCK,
        "pair_completeness": PAIR_TABLE,
        "primary_contrasts": PRIMARY_TABLE,
        "environment_effects": EFFECTS_TABLE,
        "multiplicity": MULTIPLICITY_TABLE,
        "h7_direction_table": H7_TABLE,
        "resampling_seeds": SEED_TABLE,
        "inference_report": INFERENCE_REPORT,
    }
    file_bindings = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(path),
        }
        for name, path in files.items()
    }
    lock: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-inference-result-lock-v1",
        "status": "FROZEN_INFERENCE_RESULTS_LOCKED_BEFORE_MANUSCRIPT_INTERPRETATION",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "raw_result_lock": {
            "path": RAW_LOCK.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(RAW_LOCK),
            "self_sha256": EXPECTED_RAW_LOCK_SELF_HASH,
        },
        "endpoint_table_lock_self_sha256": str(
            endpoint_lock["endpoint_table_lock_self_sha256"]
        ),
        "files": file_bindings,
        "analysis_code_tree": analysis_code_tree(),
        "frozen_analysis_inputs": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                FROZEN_MAP,
                HYPOTHESIS_REGISTRY,
                MULTIPLICITY_REGISTRY,
                ENDPOINT_REGISTRY,
            )
        },
        "resampling": {
            "bootstrap_root_seed": BOOTSTRAP_ROOT_SEED,
            "sign_flip_root_seed": SIGN_FLIP_ROOT_SEED,
            "resample_count_per_analysis": N_RESAMPLES,
            "seed_inventory_path": SEED_TABLE.relative_to(ROOT).as_posix(),
            "seed_inventory_sha256": sha256_file(SEED_TABLE),
            "seed_record_count": int(len(seeds)),
            "child_seed_derivation": (
                "first 32 bits of SHA-256(root_seed|family|stratum|contrast|endpoint)"
            ),
        },
        "cardinality": {
            "endpoint_rows": EXPECTED_JOBS,
            "pair_gate_rows": int(len(pairs)),
            "primary_contrast_rows": int(len(primary)),
            "heterogeneity_rows": int(len(effects)),
            "multiplicity_rows": int(len(multiplicity)),
            "h7_rows": int(len(h7)),
            "failed_completeness_gates": int(pairs["gate_status"].eq("FAIL").sum()),
        },
        "scope_guards": {
            "registered_contrasts_only": True,
            "registered_multiplicity_families_only": True,
            "h6_descriptive_only": True,
            "h7_analysis_only_no_binary_claim": True,
            "post_hoc_exploration_performed": False,
            "manuscript_interpretation_started": False,
        },
    }
    lock["inference_result_lock_self_sha256"] = canonical_hash(lock)
    write_json(INFERENCE_LOCK, lock, refresh=refresh)
    verify_inference_lock()
    return lock


def verify_inference_lock() -> dict[str, Any]:
    lock = read_json(INFERENCE_LOCK)
    canonical = dict(lock)
    claimed = str(canonical.pop("inference_result_lock_self_sha256"))
    if canonical_hash(canonical) != claimed:
        raise RuntimeError("inference-result-lock self-hash mismatch")
    if (
        str(lock["raw_result_lock"]["self_sha256"]) != EXPECTED_RAW_LOCK_SELF_HASH
        or sha256_file(RAW_LOCK) != str(lock["raw_result_lock"]["sha256"])
    ):
        raise RuntimeError("inference lock does not bind the accepted raw-result lock")
    for binding in lock["files"].values():
        if sha256_file(ROOT / str(binding["path"])) != str(binding["sha256"]):
            raise RuntimeError(f"inference file binding changed: {binding['path']}")
    if analysis_code_tree()["sha256"] != str(lock["analysis_code_tree"]["sha256"]):
        raise RuntimeError("analysis code tree changed after inference lock")
    return lock


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("validate", "extract", "infer", "lock", "all", "verify"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.action in {"validate", "all"}:
        validate_and_report(refresh=args.refresh)
    if args.action in {"extract", "all"}:
        materialize_endpoints(refresh=args.refresh)
    if args.action in {"infer", "all"}:
        run_inference(refresh=args.refresh)
    if args.action in {"lock", "all"}:
        lock = create_inference_lock(refresh=args.refresh)
        print(
            json.dumps(
                {
                    "status": lock["status"],
                    "inference_result_lock": INFERENCE_LOCK.relative_to(ROOT).as_posix(),
                    "inference_result_lock_sha256": sha256_file(INFERENCE_LOCK),
                    "inference_result_lock_self_sha256": lock[
                        "inference_result_lock_self_sha256"
                    ],
                    "failed_completeness_gates": lock["cardinality"][
                        "failed_completeness_gates"
                    ],
                },
                indent=2,
            )
        )
    if args.action == "verify":
        validate_raw_lock()
        verify_endpoint_lock()
        lock = verify_inference_lock()
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "inference_result_lock_self_sha256": lock[
                        "inference_result_lock_self_sha256"
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
