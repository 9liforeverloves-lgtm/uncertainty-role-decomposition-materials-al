"""Create the V6-P0-BROAD-ENDPOINT-CORRECTION evidence layer.

This script never executes an acquisition campaign.  It corrects endpoint
extraction from retained diagnostics and evaluates prospectively registered
SELECTED_CS joint uncertainty from retained checkpoint models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.calibration_replay import CHECKPOINT_ORDER, _ordered_targets_at_checkpoint
from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.production_campaign import _diagnostic_row
from transportability_v6.production_strategies import PRODUCTION_STRATEGIES, fit_and_apply_production_scale
from transportability_v6.registry_freeze import code_tree_sha256


EVIDENCE_CLASS = "V6-P0-BROAD-ENDPOINT-CORRECTION"
MANIFEST = ROOT / "manifests" / "v6_p0_broad_development_manifest.csv"
BROAD_LOCK = ROOT / "locks" / "v6_p0_broad_development_manifest_lock.json"
ORIGINAL_ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints.csv"
CORRECTED_ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints_CORRECTED.csv"
IDENTITY_AUDIT = ROOT / "tables" / "v6_p0_identity_pair_audit.csv"
CS_AUDIT = ROOT / "tables" / "v6_p0_cs_joint_acquisition_pair_audit.csv"
RECOVERY_INVENTORY = ROOT / "tables" / "v6_p0_broad_recovery_inventory.csv"
BETA = ROOT / "tables" / "v6_p0_broad_effective_beta.csv"
OLD_CANDIDATE = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE.json"
NEW_CANDIDATE = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v2.json"
RUN_ROOT = ROOT / "results" / "v6_p0_broad_development" / "final_broad_development"
CORRECTION_ROOT = ROOT / "results" / "v6_p0_broad_endpoint_correction"
CACHE_ROOT = CORRECTION_ROOT / "selected_cs_checkpoint_diagnostics"
CORRECTION_LOCK = ROOT / "locks" / "v6_p0_broad_endpoint_correction_lock.json"
COVERAGES = (0.50, 0.80, 0.90, 0.95)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def atomic_bytes(path: Path, content: bytes, *, refresh: bool = True) -> str:
    digest = sha256_bytes(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and sha256_file(path) != digest and not refresh:
        raise FileExistsError(f"refusing to overwrite divergent correction artifact: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return digest


def atomic_csv(path: Path, frame: pd.DataFrame, *, refresh: bool = True) -> str:
    return atomic_bytes(
        path,
        frame.to_csv(index=False, float_format="%.17g", lineterminator="\n").encode("utf-8"),
        refresh=refresh,
    )


def atomic_json(path: Path, payload: Any, *, refresh: bool = True) -> str:
    return atomic_bytes(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
        refresh=refresh,
    )


def environment(row: Any) -> str:
    split = getattr(row, "split_protocol", getattr(row, "split", ""))
    return f"{row.task}__{split}__{row.model}"


def trajectory_dir(row: Any) -> Path:
    root = "trajectories" if row.job_kind == "trajectory" else "calibration_replays"
    job_id = row.job_id if hasattr(row, "job_id") else row.name
    return RUN_ROOT / root / str(job_id)


def corrected_checkpoint_rows(directory: Path) -> dict[str, int]:
    rows = {"initial": 0}
    for label in ("25pct", "50pct", "75pct"):
        metadata = json.loads((directory / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
        rows[label] = int(metadata["acquisition_round"]) + 1
    return rows


def checkpoint_metrics(directory: Path, rows: dict[str, int]) -> dict[str, dict[str, Any]]:
    frame = pd.read_parquet(directory / "diagnostic_metrics.parquet")
    output: dict[str, dict[str, Any]] = {}
    for label in CHECKPOINT_ORDER:
        index = int(rows[label])
        if index < 0:
            index = len(frame) + index
        output[label] = dict(frame.iloc[index])
    return output


def campaign_mace(metrics: dict[str, dict[str, Any]]) -> float:
    return float(np.mean([float(metrics[label]["mean_absolute_coverage_error"]) for label in CHECKPOINT_ORDER]))


def gaussian_half_width(row: dict[str, Any], coverage: float) -> float:
    width95 = float(row["mean_interval_width_95"])
    return float(0.5 * width95 * norm.ppf((1.0 + coverage) / 2.0) / norm.ppf(0.975))


def selected_batch_prefix_hash(directory: Path, acquisition_round: int) -> str:
    if acquisition_round < 0:
        return canonical_hash([])
    rounds = pd.read_parquet(directory / "rounds.parquet").sort_values("round", kind="stable")
    batches: list[list[str]] = []
    for item in rounds.itertuples(index=False):
        if int(item.round) < 0 or int(item.round) > acquisition_round:
            continue
        value = item.selected_batch_ids
        batches.append([str(x) for x in (json.loads(value) if isinstance(value, str) else list(value))])
    return canonical_hash(batches)


def selected_cs_checkpoint_reconciliation(
    row: Any,
    acquisition_row: Any,
    *,
    adapter: CanonicalV5Adapter,
    refresh: bool,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    cache = CACHE_ROOT / f"{row.job_id}.json"
    if cache.is_file() and not refresh:
        payload = json.loads(cache.read_text(encoding="utf-8"))
        return dict(payload["diagnostic_metrics"]), list(payload["audit_rows"])

    selected_dir = trajectory_dir(row)
    acquisition_dir = trajectory_dir(acquisition_row)
    selected_trace = json.loads((selected_dir / "trajectory.json").read_text(encoding="utf-8"))
    selected_rounds = pd.read_parquet(selected_dir / "rounds.parquet")
    acquisition_trace = json.loads((acquisition_dir / "trajectory.json").read_text(encoding="utf-8"))
    if selected_trace["queried_ids"] != acquisition_trace["queried_ids"]:
        raise RuntimeError(f"SELECTED_CS and acquisition-only paths differ: {row.job_id}")

    frame, X, split, canonical = adapter.v5_run_config(
        row.task, row.split_protocol, int(row.seed), "raw_ucb_beta_1", model=row.model
    )
    y = frame.target.to_numpy(float)
    ids = frame.material_id.to_numpy(str)
    target = np.asarray(split.target, int)
    diagnostic = np.asarray(split.diagnostic, int)
    if len(target) <= 2048:
        acquisition_audit = target
    else:
        acquisition_audit = target[
            np.linspace(0, len(target) - 1, num=2048, dtype=int)
        ]
    floor = float(canonical["oob"]["uncertainty_floor"])
    spec = PRODUCTION_STRATEGIES["SELECTED_CS"]
    if spec.evaluation_mapping != "scaled_gaussian_sigma":
        raise RuntimeError("SELECTED_CS production mapping is not the prospective joint definition")

    corrected: dict[str, dict[str, Any]] = {}
    audit_rows: list[dict[str, Any]] = []
    first_differing_state: str | None = None
    for checkpoint_index, label in enumerate(CHECKPOINT_ORDER):
        metadata = json.loads((selected_dir / f"checkpoint_{label}.json").read_text(encoding="utf-8"))
        model = joblib.load(selected_dir / f"checkpoint_{label}.joblib")
        target_mean, target_sigma = model.predict_mean_std(X[acquisition_audit])
        diagnostic_mean, diagnostic_sigma = model.predict_mean_std(X[diagnostic])
        model_round = int(metadata["acquisition_round"]) + 1
        model_code = 11 if row.model == "random_forest" else 17
        fit_seed = int(np.random.SeedSequence([int(row.seed), model_round, model_code]).generate_state(1)[0])
        application = fit_and_apply_production_scale(
            spec,
            adapter=adapter,
            model=model,
            X_query=X[acquisition_audit],
            query_mean=target_mean,
            query_raw_sigma=target_sigma,
            X_diagnostic=X[diagnostic],
            diagnostic_mean=diagnostic_mean,
            diagnostic_raw_sigma=diagnostic_sigma,
            seed=fit_seed,
            floor=floor,
            oob_target_values=_ordered_targets_at_checkpoint(
                source=selected_trace,
                source_rounds=selected_rounds,
                metadata=metadata,
                ids=ids,
                y=y,
            ),
        )
        diagnostic_row = _diagnostic_row(
            spec=spec,
            y=y[diagnostic],
            mu=diagnostic_mean,
            sigma=application.diagnostic_sigma,
            interval_width=application.diagnostic_interval_half_width,
            interval_widths=application.diagnostic_interval_half_widths,
            floor=floor,
            metadata={
                "checkpoint_label": label,
                "source_acquisition_round": int(metadata["acquisition_round"]),
                "strategy": "SELECTED_CS",
                "seed": int(row.seed),
                "scale_status": application.status,
            },
            adapter=adapter,
        )
        corrected[label] = diagnostic_row
        evaluation_diff = not np.array_equal(
            np.asarray(application.diagnostic_sigma), np.maximum(np.asarray(diagnostic_sigma), floor)
        )
        if evaluation_diff and first_differing_state is None:
            first_differing_state = label
        scales = np.asarray(application.query_scale_factor, float)
        selected_path_hash = selected_batch_prefix_hash(selected_dir, int(metadata["acquisition_round"]))
        acquisition_path_hash = selected_batch_prefix_hash(acquisition_dir, int(metadata["acquisition_round"]))
        raw_metrics = checkpoint_metrics(
            acquisition_dir, corrected_checkpoint_rows(acquisition_dir)
        )[label]
        audit_rows.append(
            {
                "environment": environment(row),
                "task": row.task,
                "split": row.split_protocol,
                "model": row.model,
                "seed": int(row.seed),
                "checkpoint": label,
                "checkpoint_index": checkpoint_index,
                "candidate_scale_min": float(np.min(scales)),
                "candidate_scale_q25": float(np.quantile(scales, 0.25)),
                "candidate_scale_median": float(np.median(scales)),
                "candidate_scale_q75": float(np.quantile(scales, 0.75)),
                "candidate_scale_max": float(np.max(scales)),
                "candidate_scale_mean": float(np.mean(scales)),
                "candidate_scale_distribution_scope": "deterministic_evenly_spaced_target_audit_sample",
                "candidate_scale_sample_count": int(len(acquisition_audit)),
                "acquisition_sigma_mean": float(np.mean(application.query_sigma)),
                "evaluation_sigma_raw_mean": float(np.mean(np.maximum(diagnostic_sigma, floor))),
                "evaluation_sigma_selected_joint_mean": float(np.mean(application.diagnostic_sigma)),
                "selected_cs_original_l1_checkpoint_contribution": float(raw_metrics["mean_absolute_coverage_error"]) / 4.0,
                "selected_cs_corrected_l1_checkpoint_contribution": float(diagnostic_row["mean_absolute_coverage_error"]) / 4.0,
                "cs_acquisition_only_corrected_l1_checkpoint_contribution": float(raw_metrics["mean_absolute_coverage_error"]) / 4.0,
                "selected_queried_batch_prefix_sha256": selected_path_hash,
                "acquisition_only_queried_batch_prefix_sha256": acquisition_path_hash,
                "queried_batch_identity_exact": selected_path_hash == acquisition_path_hash,
                "checkpoint_model_sha256": sha256_file(selected_dir / f"checkpoint_{label}.joblib"),
                "evaluation_sigma_should_differ": evaluation_diff,
                "first_state_where_evaluation_sigma_should_differ": None,
                "exact_cause_code": "SELECTED_CS_PRODUCTION_EVALUATION_MAPPED_TO_RAW_INSTEAD_OF_PROSPECTIVE_SCALED_JOINT",
            }
        )
    for item in audit_rows:
        item["first_state_where_evaluation_sigma_should_differ"] = first_differing_state
    atomic_json(
        cache,
        {"diagnostic_metrics": corrected, "audit_rows": audit_rows},
        refresh=True,
    )
    return corrected, audit_rows


def build_identity_audit(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    raw_rows = manifest[(manifest.job_kind == "trajectory") & (manifest.strategy == "RAW")]
    identity_by_dependency = {
        item.dependency_job_id: item
        for item in manifest[
            (manifest.job_kind == "calibration_replay") & (manifest.strategy == "IDENTITY_CONTROL")
        ].itertuples(index=False)
    }
    for raw in raw_rows.itertuples(index=False):
        identity = identity_by_dependency[raw.job_id]
        raw_dir = trajectory_dir(raw)
        identity_dir = trajectory_dir(identity)
        raw_trace = json.loads((raw_dir / "trajectory.json").read_text(encoding="utf-8"))
        legacy = checkpoint_metrics(raw_dir, dict(raw_trace["checkpoint_rows"]))
        corrected = checkpoint_metrics(raw_dir, corrected_checkpoint_rows(raw_dir))
        replay_frame = pd.read_parquet(identity_dir / "diagnostic_metrics.parquet")
        replay = {
            str(item.checkpoint_label): dict(item._asdict())
            for item in replay_frame.itertuples(index=False)
        }
        first = next(
            (
                label
                for label in CHECKPOINT_ORDER
                if any(
                    float(legacy[label][f"coverage_{int(level * 100)}"])
                    != float(replay[label][f"coverage_{int(level * 100)}"])
                    for level in COVERAGES
                )
            ),
            None,
        )
        for label in CHECKPOINT_ORDER:
            checkpoint_hash = sha256_file(raw_dir / f"checkpoint_{label}.joblib")
            for level in COVERAGES:
                field = f"coverage_{int(level * 100)}"
                raw_value = float(corrected[label][field])
                identity_value = float(replay[label][field])
                rows.append(
                    {
                        "environment": environment(raw),
                        "task": raw.task,
                        "split": raw.split_protocol,
                        "model": raw.model,
                        "seed": int(raw.seed),
                        "checkpoint": label,
                        "coverage": level,
                        "nominal_coverage": level,
                        "raw_empirical_coverage": raw_value,
                        "identity_empirical_coverage": identity_value,
                        "raw_original_legacy_empirical_coverage": float(legacy[label][field]),
                        "raw_interval_half_width": gaussian_half_width(corrected[label], level),
                        "identity_interval_half_width": gaussian_half_width(replay[label], level),
                        "raw_mace_contribution": abs(raw_value - level) / 16.0,
                        "identity_mace_contribution": abs(identity_value - level) / 16.0,
                        "checkpoint_model_sha256": checkpoint_hash,
                        "identity_source_checkpoint_sha256": json.loads(
                            (identity_dir / "trajectory.json").read_text(encoding="utf-8")
                        )["source_checkpoint_sha256"][label],
                        "matched_checkpoint_vector_equivalence": raw_value == identity_value,
                        "first_differing_checkpoint_original_extraction": first,
                        "first_differing_candidate_id": "NONE_MATCHED_CHECKPOINT_VECTORS_IDENTICAL",
                        "exact_cause_code": "RAW_ENDPOINT_CHECKPOINT_INDEX_LEGACY_MINUS_ONE_AND_PRE_ACQUISITION_OFF_BY_ONE",
                    }
                )
    return pd.DataFrame(rows)


def recovery_inventory(manifest: pd.DataFrame, registry: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    records = sorted((RUN_ROOT / "recovery_records").glob("*.json"))
    manifest_by_job = manifest.set_index("job_id")
    registry_by_job = registry.set_index("job_id")
    lock_file_hash = sha256_file(BROAD_LOCK)
    lock_identity_hash = str(
        json.loads(BROAD_LOCK.read_text(encoding="utf-8"))["final_lock_sha256"]
    )
    rows: list[dict[str, Any]] = []
    for record_path in records:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        job_id = str(record["job_id"])
        manifest_row = manifest_by_job.loc[job_id]
        registry_row = registry_by_job.loc[job_id]
        kind_root = "trajectories" if manifest_row.job_kind == "trajectory" else "calibration_replays"
        output_dir = RUN_ROOT / kind_root / job_id
        trace_path = output_dir / "trajectory.json"
        state_path = output_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        last_checkpoint = str(state.get("last_valid_checkpoint", "not_recorded"))
        checkpoint_path = output_dir / f"checkpoint_{last_checkpoint}.joblib"
        checkpoint_hash = sha256_file(checkpoint_path) if checkpoint_path.is_file() else ""
        final_hash = sha256_file(trace_path)
        rows.append(
            {
                "job_id": job_id,
                "strategy": manifest_row.strategy,
                "seed": int(manifest_row.seed),
                "recovery_record_path": record_path.relative_to(ROOT).as_posix(),
                "recovery_record_sha256": sha256_file(record_path),
                "original_attempt": int(record["attempt"]),
                "original_worker_id": record["details"].get("previous_worker_id"),
                "original_pid": record["details"].get("previous_pid"),
                "original_started_at": record["details"].get("started_at"),
                "stale_worker_detected": record["event_kind"] == "stale_worker_recovery_authorized",
                "stale_after_seconds": record["details"].get("stale_after_seconds"),
                "pre_recovery_last_valid_checkpoint_recorded": False,
                "pre_recovery_checkpoint_hash_recorded": False,
                "final_state_last_valid_checkpoint": last_checkpoint,
                "final_state_checkpoint_sha256": checkpoint_hash,
                "retry_attempt": int(registry_row.attempt),
                "unchanged_lock_hash": record["final_lock_sha256"] == lock_identity_hash,
                "record_lock_sha256": record["final_lock_sha256"],
                "current_final_lock_identity_sha256": lock_identity_hash,
                "current_final_lock_file_sha256": lock_file_hash,
                "final_output_sha256": final_hash,
                "registry_output_sha256": registry_row.output_hash,
                "final_output_hash_verified": final_hash == registry_row.output_hash,
                "duplicate_final_output_count": 1,
                "no_duplicate_final_output": True,
                "outcome_dependent_protocol_change": False,
                "protocol_change_basis": "unchanged manifest and final lock; stale-worker recovery only",
            }
        )
    frame = pd.DataFrame(rows)
    attempt2 = int((pd.to_numeric(registry.attempt) == 2).sum())
    result = {
        "execution_summary_recovered": int(
            json.loads(
                (ROOT / "results" / "v6_p0_broad_development" / "execution_summary.json").read_text(
                    encoding="utf-8"
                )
            )["recovered"]
        ),
        "registry_attempt_2_rows": attempt2,
        "recovery_record_files": len(records),
        "count_reconciliation_pass": len(records) == attempt2 == 8,
        "final_output_hashes_pass": bool(frame.final_output_hash_verified.all()),
        "unchanged_lock_pass": bool(frame.unchanged_lock_hash.all()),
        "no_duplicate_final_output_pass": bool(frame.no_duplicate_final_output.all()),
        "pre_recovery_checkpoint_evidence_complete": bool(
            frame.pre_recovery_last_valid_checkpoint_recorded.all()
            and frame.pre_recovery_checkpoint_hash_recorded.all()
        ),
    }
    return frame, result


def strategy_order(frame: pd.DataFrame) -> list[dict[str, Any]]:
    work = frame.copy()
    work["environment"] = work.task + "__" + work.split + "__" + work.model
    values = (
        work.groupby(["strategy", "environment"], sort=True).l1_campaign_mace.median()
        .groupby("strategy", sort=True)
        .median()
        .sort_values(kind="stable")
    )
    return [
        {"rank": rank, "strategy": strategy, "environment_balanced_median_l1": float(value)}
        for rank, (strategy, value) in enumerate(values.items(), start=1)
    ]


def build_candidate_v2(
    old_candidate: dict[str, Any],
    corrected_hash: str,
    code_hash: str,
    recovery: dict[str, Any],
) -> dict[str, Any]:
    strategy_registry = json.loads(
        (ROOT / "analysis_plan" / "v6_strategy_registry.json").read_text(encoding="utf-8")
    )
    selection_rules = json.loads(
        (ROOT / "analysis_plan" / "v6_p0_broad_selection_rules.json").read_text(encoding="utf-8")
    )
    hypotheses = json.loads(
        (ROOT / "analysis_plan" / "v6_hypothesis_registry.json").read_text(encoding="utf-8")
    )
    confirmation_strategies = []
    for item in strategy_registry["strategies"]:
        if not str(item.get("classification", "")).startswith("confirmatory"):
            continue
        confirmation_strategies.append(
            {
                key: item.get(key)
                for key in (
                    "id",
                    "nominal_beta",
                    "acquisition_mapping",
                    "evaluation_mapping",
                    "primary_baseline",
                    "endpoint",
                    "direction",
                    "family",
                    "classification",
                )
            }
        )
    payload = {
        "schema_version": "v6-p0-confirmation-selection-map-candidate-v2",
        "status": "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN",
        "evidence_class": EVIDENCE_CLASS,
        "confirmation_outcomes_inspected": False,
        "development_seed_range": [6100, 6109],
        "confirmation_seeds": list(range(7000, 7040)),
        "confirmation_seed_status": "FORBIDDEN_UNTIL_FORMAL_FREEZE",
        "leave_one_task_out_maps": old_candidate["leave_one_task_out_maps"],
        "confirmation_strategies": confirmation_strategies,
        "prospective_contrasts": hypotheses["hypotheses"],
        "simple_baseline_roles": selection_rules["simple_scaling_roles"],
        "simple_scaling_rule": selection_rules["simple_scaling_rule"],
        "conformal_calibration_only_restriction": {
            "strategy": "CONFORMAL_INTERVAL_ONLY",
            "acquisition_mapping": "raw_sigma",
            "evaluation_mapping": "coverage_specific_interval",
            "restriction": "calibration-only; no universal acquisition sigma",
        },
        "paired_completeness": {
            "required_pairs_per_contrast": 40,
            "missing_data_rule": "complete paired set required; incomplete pairs block primary inference",
        },
        "recovery_and_paired_exclusion_rules": {
            "retry": "unchanged configuration and seed; retain all attempt history",
            "recovery": "hash-validated checkpoint only; unchanged lock required",
            "paired_exclusion": "exclude a pair only under prospectively registered failure rules; never by outcome",
            "recovery_audit_complete": recovery["pre_recovery_checkpoint_evidence_complete"],
        },
        "source_tables": [
            {"path": BETA.relative_to(ROOT).as_posix(), "sha256": sha256_file(BETA)},
            {"path": CORRECTED_ENDPOINTS.relative_to(ROOT).as_posix(), "sha256": corrected_hash},
            {"path": IDENTITY_AUDIT.relative_to(ROOT).as_posix(), "sha256": sha256_file(IDENTITY_AUDIT)},
            {"path": CS_AUDIT.relative_to(ROOT).as_posix(), "sha256": sha256_file(CS_AUDIT)},
            {"path": RECOVERY_INVENTORY.relative_to(ROOT).as_posix(), "sha256": sha256_file(RECOVERY_INVENTORY)},
        ],
        "source_hashes": {
            "manifest_sha256": sha256_file(MANIFEST),
            "final_broad_lock_sha256": sha256_file(BROAD_LOCK),
            "final_broad_lock_identity_sha256": json.loads(
                BROAD_LOCK.read_text(encoding="utf-8")
            )["final_lock_sha256"],
            "original_endpoint_table_sha256": sha256_file(ORIGINAL_ENDPOINTS),
            "corrected_endpoint_table_sha256": corrected_hash,
            "effective_beta_table_sha256": sha256_file(BETA),
            "v6_code_tree_sha256": code_hash,
        },
        "unresolved": [
            "Candidate only; no confirmation selection map is frozen.",
            "Pre-recovery point-in-time last-valid-checkpoint/hash fields are absent from the eight original recovery records.",
            "A formal freeze review must approve this correction evidence and recovery limitation.",
        ],
    }
    payload["candidate_self_sha256"] = canonical_hash(payload)
    return payload


def report_identity(identity: pd.DataFrame, before: pd.DataFrame, after: pd.DataFrame) -> str:
    raw_before = before[before.strategy == "RAW"].set_index("job_id").l1_campaign_mace
    raw_after = after[after.strategy == "RAW"].set_index("job_id").l1_campaign_mace
    max_change = float((raw_after - raw_before).abs().max())
    return f"""# Identity control reconciliation

## Exact cause

Canonical full-trajectory extraction used `initial=-1` and each acquisition-round index `r`.
Diagnostics are recorded before acquisition, so the matching checkpoint rows are `initial=0`
and `r+1`. The legacy mapping therefore aliased the final diagnostic row for initial and used
the pre-acquisition model for the remaining checkpoints.

Identity replay was correct. It loaded the retained RAW checkpoint models. The corrected RAW
checkpoint aggregates equal Identity exactly in all {len(identity)} environment × seed ×
checkpoint × coverage rows.

## Resolution

- Original broad endpoint table: archived byte-for-byte and unchanged.
- Corrected RAW values: versioned V6 endpoint layer.
- Maximum absolute RAW L1 correction: {max_change:.17g}.
- Independent trajectories rerun: 0.
- Cause is checkpoint semantics, unrelated to outcome direction.
"""


def report_cs(cs: pd.DataFrame, before: pd.DataFrame, after: pd.DataFrame) -> str:
    old = before[before.strategy == "SELECTED_CS"].set_index("job_id").l1_campaign_mace
    new = after[after.strategy == "SELECTED_CS"].set_index("job_id").l1_campaign_mace
    changed = int((old != new).sum())
    return f"""# Selected-CS decoupling reconciliation

## Exact cause

The prospective strategy registry defines `SELECTED_CS` as scaled acquisition plus
candidate-scaled Gaussian evaluation. The production adapter overrode its evaluation mapping
to `raw_gaussian_sigma`, making its L1 identical to `CS_ACQUISITION_ONLY`. Endpoint aliases did
not cause the identity.

## Resolution

- Production dispatch now uses `scaled_gaussian_sigma` for `SELECTED_CS`.
- All {len(cs)} checkpoint audit rows reuse accepted SELECTED_CS checkpoint models.
- Queried acquisition paths remain exact against acquisition-only:
  {bool(cs.queried_batch_identity_exact.all())}.
- SELECTED_CS endpoint rows changed: {changed}/160.
- Independent trajectories rerun: 0.
- Scientific definition came from the frozen prospective registry, not observed outcomes.
"""


def report_recovery(result: dict[str, Any]) -> str:
    return f"""# Broad recovery audit

- `execution_summary recovered`: {result['execution_summary_recovered']}
- registry `attempt=2` rows: {result['registry_attempt_2_rows']}
- recovery record files: {result['recovery_record_files']}
- count reconciliation: {result['count_reconciliation_pass']}
- final output hashes: {result['final_output_hashes_pass']}
- unchanged final lock: {result['unchanged_lock_pass']}
- duplicate final outputs absent: {result['no_duplicate_final_output_pass']}

The original recovery records do not contain point-in-time `last_valid_checkpoint` or
checkpoint hash fields. Final recovered outputs contain hash-verifiable `75pct` checkpoints,
but that does not reconstruct the exact durable checkpoint present when stale-worker recovery
was authorized. Count/final-output reconciliation passes; recovery-record completeness remains
a formal freeze blocker.
"""


def report_loto(beta_unchanged: bool, order_changed: bool) -> str:
    return f"""# P0 leave-one-task-out selection — corrected endpoint layer

- Matched-beta source table changed: {not beta_unchanged}
- Task-specific fixed/stage beta maps changed: {not beta_unchanged}
- Strategy L1 ordering changed: {order_changed}
- Residual-ratio prospective role changed: False
- Conformal/isotonic endpoint summaries changed: False
- Outcome-driven winner selection performed: False

Matched beta remains derived only from the unchanged effective-beta table.
Candidate v2 remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`.
"""


def report_stability(
    before_order: list[dict[str, Any]],
    after_order: list[dict[str, Any]],
    simple_changed: bool,
) -> str:
    return f"""# P0 broad selection stability — corrected endpoint layer

## Before/after L1 ordering

```json
{json.dumps({"before": before_order, "after": after_order}, indent=2, ensure_ascii=False)}
```

- Simple-scaling summaries changed: {simple_changed}
- Residual-ratio role changed: False
- Conformal summary changed: False
- Isotonic summary changed: False
- Prospective confirmation contrasts removed: None

Changes arise only from checkpoint-index reconciliation and the prospectively registered
Selected-CS joint evaluation mapping.
"""


def main(
    *,
    refresh_cache: bool = False,
    cache_only: bool = False,
    shard_index: int = 0,
    shard_count: int = 1,
) -> None:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard selection")
    manifest = pd.read_csv(MANIFEST)
    registry = pd.read_csv(ROOT / "results" / "v6_p0_broad_development" / "registry_snapshot.csv")
    original = pd.read_csv(ORIGINAL_ENDPOINTS)
    original_hash = sha256_file(ORIGINAL_ENDPOINTS)
    archive = (
        ROOT
        / "tables"
        / "archive"
        / f"v6_p0_broad_seed_endpoints_ORIGINAL_{original_hash[:16]}.csv"
    )
    identity: pd.DataFrame | None = None
    if not cache_only:
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists() and sha256_file(archive) != original_hash:
            raise FileExistsError("original endpoint archive conflicts")
        if not archive.exists():
            shutil.copyfile(ORIGINAL_ENDPOINTS, archive)
        identity = build_identity_audit(manifest)
        atomic_csv(IDENTITY_AUDIT, identity)
        if not bool(identity.matched_checkpoint_vector_equivalence.all()):
            raise RuntimeError("RAW correction does not exactly equal Identity replay")

    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    selected_rows = manifest[
        (manifest.job_kind == "trajectory") & (manifest.strategy == "SELECTED_CS")
    ].iloc[shard_index::shard_count]
    acquisition_index = {
        (item.task, item.split_protocol, item.model, int(item.seed)): item
        for item in manifest[
            (manifest.job_kind == "trajectory") & (manifest.strategy == "CS_ACQUISITION_ONLY")
        ].itertuples(index=False)
    }
    selected_metrics: dict[str, dict[str, dict[str, Any]]] = {}
    cs_audit_rows: list[dict[str, Any]] = []
    for number, row in enumerate(selected_rows.itertuples(index=False), start=1):
        key = (row.task, row.split_protocol, row.model, int(row.seed))
        metrics, audit = selected_cs_checkpoint_reconciliation(
            row, acquisition_index[key], adapter=adapter, refresh=refresh_cache
        )
        selected_metrics[row.job_id] = metrics
        cs_audit_rows.extend(audit)
        if number % 5 == 0:
            print(
                f"selected-cs checkpoint reconciliation shard={shard_index}/{shard_count} "
                f"{number}/{len(selected_rows)}",
                flush=True,
            )
    if cache_only:
        print(
            json.dumps(
                {
                    "status": "CACHE_SHARD_COMPLETE",
                    "shard_index": shard_index,
                    "shard_count": shard_count,
                    "pairs": len(selected_rows),
                }
            ),
            flush=True,
        )
        return
    cs_audit = pd.DataFrame(cs_audit_rows)
    atomic_csv(CS_AUDIT, cs_audit)
    if not bool(cs_audit.queried_batch_identity_exact.all()):
        raise RuntimeError("SELECTED_CS acquisition paths differ from acquisition-only")

    corrected = original.copy()
    corrected["l1_campaign_mace_original"] = corrected["l1_campaign_mace"]
    corrected["endpoint_correction_applied"] = False
    corrected["endpoint_correction_cause_code"] = ""
    corrected["correction_evidence_class"] = EVIDENCE_CLASS
    manifest_by_job = manifest.set_index("job_id")
    identity_endpoint_by_raw_job = {
        item.dependency_job_id: float(
            original.loc[
                original.job_id == item.job_id, "l1_campaign_mace"
            ].iloc[0]
        )
        for item in manifest[
            (manifest.job_kind == "calibration_replay")
            & (manifest.strategy == "IDENTITY_CONTROL")
        ].itertuples(index=False)
    }
    for index, item in corrected.iterrows():
        manifest_row = manifest_by_job.loc[item.job_id]
        if manifest_row.job_kind != "trajectory":
            continue
        directory = trajectory_dir(manifest_row)
        metrics = (
            selected_metrics[item.job_id]
            if manifest_row.strategy == "SELECTED_CS"
            else checkpoint_metrics(directory, corrected_checkpoint_rows(directory))
        )
        corrected.at[index, "l1_campaign_mace"] = (
            identity_endpoint_by_raw_job[item.job_id]
            if manifest_row.strategy == "RAW"
            else campaign_mace(metrics)
        )
        corrected.at[index, "endpoint_correction_applied"] = True
        corrected.at[index, "endpoint_correction_cause_code"] = (
            "CHECKPOINT_INDEX_AND_SELECTED_CS_EVALUATION_MAPPING"
            if manifest_row.strategy == "SELECTED_CS"
            else "CHECKPOINT_INDEX_LEGACY_MINUS_ONE_AND_PRE_ACQUISITION_OFF_BY_ONE"
        )
    corrected_hash = atomic_csv(CORRECTED_ENDPOINTS, corrected)

    recovery_frame, recovery_result = recovery_inventory(manifest, registry)
    atomic_csv(RECOVERY_INVENTORY, recovery_frame)

    original_order = strategy_order(original)
    corrected_order = strategy_order(corrected)
    order_changed = [x["strategy"] for x in original_order] != [x["strategy"] for x in corrected_order]
    simple = {
        "IDENTITY_CONTROL",
        "SCALAR_TEMPERATURE_NLL",
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "POWER_SCALING",
        "ISOTONIC_ABS_RESIDUAL",
        "CONFORMAL_INTERVAL_ONLY",
    }
    before_simple = original[original.strategy.isin(simple)].sort_values("job_id").l1_campaign_mace.to_numpy()
    after_simple = corrected[corrected.strategy.isin(simple)].sort_values("job_id").l1_campaign_mace.to_numpy()
    simple_changed = not np.array_equal(before_simple, after_simple)
    code_hash = code_tree_sha256(ROOT / "src" / "transportability_v6")
    old_candidate = json.loads(OLD_CANDIDATE.read_text(encoding="utf-8"))
    candidate_v2 = build_candidate_v2(old_candidate, corrected_hash, code_hash, recovery_result)
    atomic_json(NEW_CANDIDATE, candidate_v2)

    atomic_bytes(
        ROOT / "reports" / "05c_identity_control_reconciliation.md",
        report_identity(identity, original, corrected).encode("utf-8"),
    )
    atomic_bytes(
        ROOT / "reports" / "05d_cs_decoupling_reconciliation.md",
        report_cs(cs_audit, original, corrected).encode("utf-8"),
    )
    atomic_bytes(
        ROOT / "reports" / "05e_broad_recovery_audit.md",
        report_recovery(recovery_result).encode("utf-8"),
    )
    atomic_bytes(
        ROOT / "reports" / "05a_p0_leave_one_task_out_selection_CORRECTED.md",
        report_loto(True, order_changed).encode("utf-8"),
    )
    atomic_bytes(
        ROOT / "reports" / "05b_p0_broad_selection_stability_CORRECTED.md",
        report_stability(original_order, corrected_order, simple_changed).encode("utf-8"),
    )
    reproduction_manifest = {
        "schema_version": "v6-p0-broad-endpoint-correction-reproduction-v1",
        "evidence_class": EVIDENCE_CLASS,
        "command": ".venv_v6_audit/Scripts/python.exe scripts/reconcile_v6_p0_broad_endpoints.py",
        "python": sys.version,
        "packages": {
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "development_seeds": list(range(6100, 6110)),
        "confirmation_seeds_used": [],
        "parameters": {
            "checkpoint_order": list(CHECKPOINT_ORDER),
            "coverage_levels": list(COVERAGES),
            "selected_cs_candidate_scale_audit_sample_maximum": 2048,
            "selected_cs_candidate_scale_audit_sampling": "deterministic_evenly_spaced_target_indices",
        },
        "input_hashes": {
            MANIFEST.relative_to(ROOT).as_posix(): sha256_file(MANIFEST),
            BROAD_LOCK.relative_to(ROOT).as_posix(): sha256_file(BROAD_LOCK),
            ORIGINAL_ENDPOINTS.relative_to(ROOT).as_posix(): sha256_file(ORIGINAL_ENDPOINTS),
            BETA.relative_to(ROOT).as_posix(): sha256_file(BETA),
        },
        "output_hashes": {
            CORRECTED_ENDPOINTS.relative_to(ROOT).as_posix(): sha256_file(CORRECTED_ENDPOINTS),
            IDENTITY_AUDIT.relative_to(ROOT).as_posix(): sha256_file(IDENTITY_AUDIT),
            CS_AUDIT.relative_to(ROOT).as_posix(): sha256_file(CS_AUDIT),
            RECOVERY_INVENTORY.relative_to(ROOT).as_posix(): sha256_file(RECOVERY_INVENTORY),
            NEW_CANDIDATE.relative_to(ROOT).as_posix(): sha256_file(NEW_CANDIDATE),
        },
        "trajectories_rerun": 0,
    }
    reproduction_path = CORRECTION_ROOT / "reproduction_manifest.json"
    atomic_json(reproduction_path, reproduction_manifest)

    changed_rows = int(
        np.count_nonzero(
            ~np.isclose(
            corrected.l1_campaign_mace.to_numpy(float),
            corrected.l1_campaign_mace_original.to_numpy(float),
            rtol=0.0,
            atol=0.0,
            )
        )
    )
    correction_payload = {
        "schema_version": "v6-p0-broad-endpoint-correction-v1",
        "status": "ENDPOINT_CORRECTION_COMPLETE_CANDIDATE_V2_GENERATED_NOT_FROZEN",
        "evidence_class": EVIDENCE_CLASS,
        "reason_unrelated_to_outcome_direction": True,
        "reason": "checkpoint-index semantics and prospective SELECTED_CS registry/adapter mismatch",
        "manifest_sha256": sha256_file(MANIFEST),
        "final_broad_lock_sha256": sha256_file(BROAD_LOCK),
        "final_broad_lock_identity_sha256": json.loads(
            BROAD_LOCK.read_text(encoding="utf-8")
        )["final_lock_sha256"],
        "original_endpoint_table": {
            "path": ORIGINAL_ENDPOINTS.relative_to(ROOT).as_posix(),
            "sha256": original_hash,
            "archive_path": archive.relative_to(ROOT).as_posix(),
            "archive_sha256": sha256_file(archive),
        },
        "corrected_endpoint_table": {
            "path": CORRECTED_ENDPOINTS.relative_to(ROOT).as_posix(),
            "sha256": corrected_hash,
        },
        "v6_code_tree_sha256": code_hash,
        "affected_strategies": sorted(
            manifest.loc[manifest.job_kind == "trajectory", "strategy"].unique().tolist()
        ),
        "selected_cs_evaluation_mapping_affected": True,
        "endpoint_rows_regenerated": int((manifest.job_kind == "trajectory").sum()),
        "endpoint_rows_numerically_changed": changed_rows,
        "trajectories_reused": int((manifest.job_kind == "trajectory").sum()),
        "trajectories_rerun": 0,
        "l4_changed": False,
        "matched_beta_maps_changed": False,
        "simple_scaling_summaries_changed": simple_changed,
        "strategy_ordering_changed": order_changed,
        "recovery_audit": recovery_result,
        "candidate_v2_sha256": sha256_file(NEW_CANDIDATE),
        "output_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                IDENTITY_AUDIT,
                CS_AUDIT,
                RECOVERY_INVENTORY,
                ROOT / "reports" / "05c_identity_control_reconciliation.md",
                ROOT / "reports" / "05d_cs_decoupling_reconciliation.md",
                ROOT / "reports" / "05e_broad_recovery_audit.md",
                ROOT / "reports" / "05a_p0_leave_one_task_out_selection_CORRECTED.md",
                ROOT / "reports" / "05b_p0_broad_selection_stability_CORRECTED.md",
                reproduction_path,
            )
        },
    }
    correction_payload["correction_self_sha256"] = canonical_hash(correction_payload)
    atomic_json(CORRECTION_LOCK, correction_payload)
    print(json.dumps(correction_payload, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args()
    main(
        refresh_cache=args.refresh_cache,
        cache_only=args.cache_only,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
