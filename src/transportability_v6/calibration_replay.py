"""Calibration-only V6 evaluation on immutable canonical RAW checkpoints.

Strategies with an exact RAW acquisition map must not spend a second campaign
to reproduce the same path.  This module loads the V6 RAW checkpoint models,
fits the registered OOB-only calibration rule, and evaluates the four frozen
V5 checkpoint definitions.  It never writes to V5-RC1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .canonical_adapter import CanonicalV5Adapter
from .diagnostics import atomic_parquet
from .execution_registry import atomic_write_json_no_overwrite, sha256_file
from .production_campaign import (
    BROAD_DEVELOPMENT_SEEDS,
    CANARY_SEEDS,
    PRODUCTION_EVIDENCE_CLASSES,
    SENTINEL_DEVELOPMENT_SEEDS,
    _assert_production_config,
    _diagnostic_row,
)
from .production_endpoints import campaign_mace
from .production_strategies import fit_and_apply_production_scale


CHECKPOINT_ORDER = ("initial", "25pct", "50pct", "75pct")


@dataclass(frozen=True)
class CalibrationReplayConfig:
    job_id: str
    source_job_id: str
    task: str
    split_protocol: str
    model: str
    strategy: str
    seed: int
    evidence_class: str = "V6-MECH"
    phase: str = "development"
    manifest_sha256: str = ""


def _hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _validate(config: CalibrationReplayConfig):
    if config.evidence_class not in PRODUCTION_EVIDENCE_CLASSES:
        raise ValueError("calibration replay requires a registered V6 evidence class")
    permitted = {
        "development": SENTINEL_DEVELOPMENT_SEEDS,
        "broad_development": BROAD_DEVELOPMENT_SEEDS,
        "canary": CANARY_SEEDS,
    }
    if config.phase not in permitted or int(config.seed) not in permitted[config.phase]:
        raise PermissionError("calibration replay uses an unregistered non-confirmation development seed")
    # Reuse production configuration guards, including registered strategies.
    from .production_campaign import ProductionCampaignConfig

    spec = _assert_production_config(
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
        raise ValueError("only exact-RAW-acquisition strategies may use calibration replay")
    return spec


def _as_id_list(value: object) -> list[str]:
    if isinstance(value, str):
        parsed = json.loads(value)
    else:
        parsed = np.asarray(value, dtype=object).tolist()
    return [str(item) for item in parsed]


def _ordered_targets_at_checkpoint(
    *,
    source: dict[str, Any],
    source_rounds: pd.DataFrame,
    metadata: dict[str, Any],
    ids: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """Reconstruct the V5-legacy queried order for a RAW checkpoint."""

    initial = [str(value) for value in source["initial_labeled_ids"]]
    ordered = list(initial)
    count = int(metadata["queried_count"])
    if len(ordered) > count:
        raise ValueError("RAW initial labels exceed the checkpoint queried count")
    if len(ordered) < count:
        for row in source_rounds.sort_values("round", kind="stable").itertuples(index=False):
            if int(row.round) < 0:
                continue
            ordered.extend(_as_id_list(getattr(row, "selected_batch_ids")))
            if len(ordered) >= count:
                break
    if len(ordered) != count:
        raise ValueError("RAW trajectory cannot reconstruct the checkpoint queried order")
    lookup = {str(value): index for index, value in enumerate(ids)}
    if len(set(ordered)) != len(ordered) or any(value not in lookup for value in ordered):
        raise ValueError("RAW trajectory checkpoint contains invalid material IDs")
    return y[np.asarray([lookup[value] for value in ordered], int)]


def run_calibration_replay(
    config: CalibrationReplayConfig,
    *,
    trajectory_root: str | Path,
    output_root: str | Path,
    adapter: CanonicalV5Adapter | None = None,
) -> dict[str, object]:
    """Evaluate a calibration-only strategy at RAW's canonical checkpoints."""

    spec = _validate(config)
    adapter = adapter or CanonicalV5Adapter()
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    source_dir = Path(trajectory_root).resolve() / config.source_job_id
    source_trace = source_dir / "trajectory.json"
    if not source_trace.is_file():
        raise FileNotFoundError(f"RAW source trajectory is unavailable: {source_trace}")
    source = json.loads(source_trace.read_text(encoding="utf-8"))
    if source.get("job", {}).get("strategy") != "RAW":
        raise ValueError("calibration replay source must be an immutable V6 RAW trajectory")
    if int(source["job"].get("seed")) != int(config.seed):
        raise ValueError("calibration replay source seed differs from registered job seed")
    output_dir = Path(output_root).resolve() / config.job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / "trajectory.json"
    expected_config_hash = _hash(asdict(config))
    if trace_path.exists():
        existing = json.loads(trace_path.read_text(encoding="utf-8"))
        if existing.get("config_sha256") != expected_config_hash:
            raise FileExistsError("refusing to overwrite a divergent calibration replay")
        return {
            "job_id": config.job_id,
            "status": "COMPLETED",
            "output_dir": str(output_dir),
            **existing["endpoints"],
        }

    frame, X, split, canonical = adapter.v5_run_config(
        config.task,
        config.split_protocol,
        config.seed,
        "raw_ucb_beta_1",
        model=config.model,
    )
    floor = float(canonical["oob"]["uncertainty_floor"])
    y = frame.target.to_numpy(float)
    ids = frame.material_id.to_numpy(str)
    target = np.asarray(split.target, int)
    diagnostic = np.asarray(split.diagnostic, int)
    rows: list[dict[str, object]] = []
    checkpoint_rows: dict[str, int] = {}
    source_checkpoints: dict[str, str] = {}
    source_rounds_path = source_dir / "rounds.parquet"
    if not source_rounds_path.is_file():
        raise FileNotFoundError("RAW source trajectory lacks its canonical round ledger")
    source_rounds = pd.read_parquet(source_rounds_path)
    for index, label in enumerate(CHECKPOINT_ORDER):
        checkpoint_path = source_dir / f"checkpoint_{label}.joblib"
        metadata_path = source_dir / f"checkpoint_{label}.json"
        if not checkpoint_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"source trajectory lacks V5 checkpoint {label}")
        checkpoint_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source_checkpoints[label] = sha256_file(checkpoint_path)
        model = joblib.load(checkpoint_path)
        target_mean, target_sigma = model.predict_mean_std(X[target])
        diagnostic_mean, diagnostic_sigma = model.predict_mean_std(X[diagnostic])
        # V5 saves an initial model trained with round key 0 and later
        # checkpoints with the post-acquisition model key r + 1.  Its
        # candidate-specific optimizer consumes that same surrogate seed.
        # Do not substitute an evaluation-only RNG stream here.
        checkpoint_model_round = int(checkpoint_metadata["acquisition_round"]) + 1
        model_code = 11 if config.model == "random_forest" else 17
        fit_seed = int(
            np.random.SeedSequence([config.seed, checkpoint_model_round, model_code]).generate_state(1)[0]
        )
        application = fit_and_apply_production_scale(
            spec,
            adapter=adapter,
            model=model,
            X_query=X[target],
            query_mean=target_mean,
            query_raw_sigma=target_sigma,
            X_diagnostic=X[diagnostic],
            diagnostic_mean=diagnostic_mean,
            diagnostic_raw_sigma=diagnostic_sigma,
            seed=fit_seed,
            floor=floor,
            oob_target_values=_ordered_targets_at_checkpoint(
                source=source,
                source_rounds=source_rounds,
                metadata=checkpoint_metadata,
                ids=ids,
                y=y,
            ),
        )
        row = _diagnostic_row(
            spec=spec,
            y=y[diagnostic],
            mu=diagnostic_mean,
            sigma=application.diagnostic_sigma,
            interval_width=application.diagnostic_interval_half_width,
            interval_widths=application.diagnostic_interval_half_widths,
            floor=floor,
            metadata={
                "checkpoint_label": label,
                "source_acquisition_round": int(checkpoint_metadata["acquisition_round"]),
                "round": index,
                "budget_fraction": float(checkpoint_metadata["realized_campaign_progress"]),
                "strategy": spec.id,
                "seed": config.seed,
                "scale_status": application.status,
            },
            adapter=adapter,
        )
        rows.append(row)
        checkpoint_rows[label] = index
    diagnostic_frame = pd.DataFrame(rows)
    endpoints = {"l1_campaign_mace": campaign_mace(diagnostic_frame, checkpoint_rows)}
    atomic_parquet(diagnostic_frame, output_dir / "diagnostic_metrics.parquet")
    atomic_write_json_no_overwrite(
        {
            "schema_version": "v6-calibration-replay-v1",
            "config_sha256": expected_config_hash,
            "job": asdict(config),
            "source_job_id": config.source_job_id,
            "source_trajectory_sha256": sha256_file(source_trace),
            "source_checkpoint_sha256": source_checkpoints,
            "checkpoint_rows": checkpoint_rows,
            "endpoints": endpoints,
            "v5_source_lock": adapter.source_lock_status()["expected_overall_sha256"],
        },
        trace_path,
    )
    return {"job_id": config.job_id, "status": "COMPLETED", "output_dir": str(output_dir), **endpoints}
