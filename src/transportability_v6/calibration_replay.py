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
    PRODUCTION_EVIDENCE_CLASSES,
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
    if config.phase != "development" or int(config.seed) not in range(6000, 6010):
        raise PermissionError("calibration replay is restricted to P0 development seeds 6000-6009")
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
        config.task, config.split_protocol, config.seed, "raw_ucb_beta_1"
    )
    floor = float(canonical["oob"]["uncertainty_floor"])
    y = frame.target.to_numpy(float)
    target = np.asarray(split.target, int)
    diagnostic = np.asarray(split.diagnostic, int)
    rows: list[dict[str, object]] = []
    checkpoint_rows: dict[str, int] = {}
    source_checkpoints: dict[str, str] = {}
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
            seed=int(np.random.SeedSequence([config.seed, index, 71]).generate_state(1)[0]),
            floor=floor,
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
