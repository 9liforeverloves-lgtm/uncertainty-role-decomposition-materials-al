"""Canonical V5-engine-backed V6 production campaign runner.

Unlike ``smoke_only.campaigns``, this runner is restricted to V6 evidence
classes and calls the frozen V5 loader, featurizer, split, surrogate, tie
breaking, metrics, checkpoint definitions, and registry facade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .calibration import COVERAGE_LEVELS
from .canonical_adapter import CanonicalV5Adapter
from .execution_registry import DurableCheckpointStore, atomic_write_json_no_overwrite
from .production_endpoints import campaign_mace
from .production_strategies import (
    PRODUCTION_STRATEGIES,
    ProductionStrategySpec,
    fit_and_apply_production_scale,
    score_production_round,
)


PRODUCTION_EVIDENCE_CLASSES = frozenset({"V6-MECH", "V6-EXT", "V6-SENS", "V6-REP"})
CHECKPOINT_LABELS = ("initial", "25pct", "50pct", "75pct")


@dataclass(frozen=True)
class ProductionCampaignConfig:
    job_id: str
    task: str
    split_protocol: str
    model: str
    strategy: str
    seed: int
    evidence_class: str = "V6-MECH"
    beta: float = 1.0
    stage_beta_map: dict[str, float] | None = None
    phase: str = "development"
    manifest_sha256: str = ""


def _sha(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _atomic_parquet_replace(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    pd.read_parquet(temporary)
    os.replace(temporary, path)


def _atomic_state(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _model_payload(model: Any) -> bytes:
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


def _assert_production_config(config: ProductionCampaignConfig) -> ProductionStrategySpec:
    if config.evidence_class not in PRODUCTION_EVIDENCE_CLASSES:
        raise ValueError("production runner requires a registered V6 evidence class")
    if config.strategy not in PRODUCTION_STRATEGIES:
        raise KeyError(f"unregistered production strategy: {config.strategy}")
    if config.phase not in {"development", "confirmation"}:
        raise ValueError("production phase must be development or confirmation")
    if config.phase == "confirmation" or 7000 <= int(config.seed) <= 7039:
        raise PermissionError("V6 confirmation is blocked by the Stage-2.5 stop condition")
    if config.phase == "development" and int(config.seed) not in range(6000, 6010):
        raise ValueError("production development requires registered seeds 6000-6009")
    if not np.isfinite(config.beta) or float(config.beta) < 0:
        raise ValueError("beta must be finite and nonnegative")
    if config.strategy == "RAW_FIXED_BETA_MATCHED" and config.stage_beta_map is not None:
        raise ValueError("fixed-beta strategy cannot receive a stage beta map")
    if config.strategy == "RAW_STAGE_BETA_MATCHED":
        required = {"0_25", "25_50", "50_75", "75_100"}
        if config.stage_beta_map is None or set(config.stage_beta_map) != required:
            raise ValueError("stage-matched beta strategy requires all four frozen stages")
        if not np.isfinite(list(config.stage_beta_map.values())).all() or any(
            float(value) < 0 for value in config.stage_beta_map.values()
        ):
            raise ValueError("stage beta values must be finite and nonnegative")
    return PRODUCTION_STRATEGIES[config.strategy]


def _beta_for_round(config: ProductionCampaignConfig, budget_fraction: float) -> float:
    """Return the frozen fixed or stage-matched beta without fitting in-run."""

    if config.stage_beta_map is None:
        return float(config.beta)
    budget = float(budget_fraction)
    if not 0.0 <= budget <= 1.0:
        raise ValueError("campaign budget must lie in [0, 1]")
    if budget < 0.25:
        return float(config.stage_beta_map["0_25"])
    if budget < 0.50:
        return float(config.stage_beta_map["25_50"])
    if budget < 0.75:
        return float(config.stage_beta_map["50_75"])
    return float(config.stage_beta_map["75_100"])


def _diagnostic_row(
    *,
    spec: ProductionStrategySpec,
    y: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray | None,
    interval_width: np.ndarray | None,
    interval_widths: dict[float, np.ndarray] | None,
    floor: float,
    metadata: dict[str, Any],
    adapter: CanonicalV5Adapter,
) -> dict[str, Any]:
    if interval_width is not None or interval_widths is not None:
        if interval_widths is None:
            raise ValueError("production conformal evaluation requires every registered coverage")
        if set(interval_widths) != set(COVERAGE_LEVELS):
            raise ValueError("conformal interval widths lack a registered coverage")
        coverage: dict[str, float] = {}
        widths_by_level: dict[float, np.ndarray] = {}
        for level in COVERAGE_LEVELS:
            widths = np.asarray(interval_widths[level], float)
            if widths.shape != y.shape or not np.isfinite(widths).all() or np.any(widths < 0):
                raise ValueError("conformal interval half-width is invalid")
            widths_by_level[level] = widths
            coverage[f"coverage_{int(level * 100)}"] = float(np.mean(np.abs(y - mu) <= widths))
        reference = float(spec.conformal_reference_coverage or 0.90)
        mace = float(abs(coverage[f"coverage_{int(reference * 100)}"] - reference))
        return {
            **metadata,
            "mean_absolute_coverage_error": mace,
            **coverage,
            "evaluation_kind": "conformal_interval_only",
            "mean_interval_width": float(np.mean(2.0 * widths_by_level[reference])),
            "gaussian_nll_mean": np.nan,
        }
    if sigma is None:
        raise ValueError("Gaussian diagnostic requires a sigma vector")
    quality = adapter.modules["layers"].uncertainty_quality(y, mu, sigma, floor)
    return {**metadata, **quality, "evaluation_kind": "gaussian_sigma"}


def _checkpoint_payload(identity: dict[str, Any], round_index: int, queried_count: int) -> bytes:
    return json.dumps(
        {"identity": identity, "round": int(round_index), "queried_count": int(queried_count)},
        sort_keys=True,
    ).encode("utf-8")


def run_production_campaign(
    config: ProductionCampaignConfig,
    *,
    output_root: str | Path,
    adapter: CanonicalV5Adapter | None = None,
    crash_at: str | None = None,
) -> dict[str, Any]:
    """Execute one restartable canonical V6 development job.

    The runner does not make a confirmation path available.  All outputs are
    caller-owned V6 artifacts; V5 files are loaded only read-only.
    """

    spec = _assert_production_config(config)
    adapter = adapter or CanonicalV5Adapter()
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    frame, X, split, canonical_config = adapter.v5_run_config(
        config.task, config.split_protocol, config.seed, "raw_ucb_beta_1"
    )
    geometry = canonical_config["campaign"]
    y = frame.target.to_numpy(float)
    ids = frame.material_id.to_numpy(str)
    formulas = frame.formula.to_numpy(str)
    stable = np.arange(len(frame), dtype=np.int64)
    identity = {
        "schema_version": "v6-production-trajectory-v1",
        "job_id": config.job_id,
        "manifest_sha256": config.manifest_sha256,
        "config_sha256": _sha({"campaign": asdict(config), "canonical_geometry": canonical_config}),
        "v5_source_lock": adapter.source_lock_status()["expected_overall_sha256"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    output_dir = Path(output_root).resolve() / config.job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"
    rounds_path = output_dir / "rounds.parquet"
    diagnostic_path = output_dir / "diagnostic_metrics.parquet"
    trace_path = output_dir / "trajectory.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("config_sha256") != identity["config_sha256"]:
            raise RuntimeError("existing production output has a different immutable configuration")
        if state.get("complete"):
            endpoints = dict(state["endpoints"])
            return {"job_id": config.job_id, "status": "COMPLETED", "output_dir": str(output_dir), **endpoints}
        queried = list(map(int, state["queried_indices"]))
        initial = list(map(int, state["initial_indices"]))
        next_round = int(state["next_round"])
        round_rows = pd.read_parquet(rounds_path).to_dict("records") if rounds_path.exists() else []
        diagnostic_rows = pd.read_parquet(diagnostic_path).to_dict("records") if diagnostic_path.exists() else []
        checkpoint_rows = dict(state.get("checkpoint_rows", {}))
    else:
        initial = list(
            map(
                int,
                np.sort(
                    np.random.default_rng(config.seed).choice(
                        split.source, size=int(geometry["initial_count"]), replace=False
                    )
                ),
            )
        )
        queried = list(initial)
        next_round = 0
        round_rows = []
        diagnostic_rows = []
        checkpoint_rows: dict[str, int] = {}
    durable = DurableCheckpointStore(output_dir, adapter=adapter)
    durable.recover(identity)
    queried_selectable = set(queried) & set(map(int, split.target))
    floor = float(canonical_config["oob"]["uncertainty_floor"])
    max_queries = int(geometry["max_queries"])
    batch_size = int(geometry["batch_size"])

    def fit_model(round_index: int, labelled: list[int]):
        code = 11 if config.model == "random_forest" else 17
        model_seed = int(np.random.SeedSequence([config.seed, round_index, code]).generate_state(1)[0])
        model = adapter.modules["surrogates"].make_surrogate(
            config.model,
            n_estimators=int(canonical_config["model"]["n_estimators"]),
            min_samples_leaf=int(canonical_config["model"]["min_samples_leaf"]),
            n_jobs=1,
        )
        return model.fit(X[labelled], y[labelled], model_seed, stable[labelled])

    if "initial" not in checkpoint_rows:
        initial_model = fit_model(-1, queried)
        durable.write_payload(
            "initial",
            _model_payload(initial_model),
            identity,
            realized_progress=0.0,
            acquisition_round=-1,
            queried_count=len(queried),
            crash_at=crash_at,
        )
        checkpoint_rows["initial"] = 0
        diagnostic_mean, diagnostic_raw_sigma = initial_model.predict_mean_std(X[split.diagnostic])
        application = fit_and_apply_production_scale(
            spec,
            adapter=adapter,
            model=initial_model,
            X_query=X[np.asarray(split.target, int)],
            query_mean=initial_model.predict_mean_std(X[np.asarray(split.target, int)])[0],
            query_raw_sigma=initial_model.predict_mean_std(X[np.asarray(split.target, int)])[1],
            X_diagnostic=X[split.diagnostic],
            diagnostic_mean=diagnostic_mean,
            diagnostic_raw_sigma=diagnostic_raw_sigma,
            seed=int(np.random.SeedSequence([config.seed, -1, 31]).generate_state(1)[0]),
            floor=floor,
        )
        diagnostic_rows.append(
            _diagnostic_row(
                spec=spec,
                y=y[split.diagnostic],
                mu=diagnostic_mean,
                sigma=application.diagnostic_sigma,
                interval_width=application.diagnostic_interval_half_width,
                interval_widths=application.diagnostic_interval_half_widths,
                floor=floor,
                metadata={"round": -1, "budget_fraction": 0.0, "strategy": spec.id, "seed": config.seed},
                adapter=adapter,
            )
        )
        round_rows.append(
            {
                "round": -1,
                "budget_fraction": 0.0,
                "top1_recall": adapter.modules["metrics"].recall(y, queried, split.target, stable, 0.01),
                "selected_batch_ids": [],
                "strategy": spec.id,
                "seed": config.seed,
                "scale_status": application.status,
                "effective_beta_median": float(
                    np.median(float(config.beta) * application.query_scale_factor)
                ),
            }
        )

    thresholds = {"25pct": 0.25, "50pct": 0.50, "75pct": 0.75}
    while len(queried_selectable) < max_queries:
        candidates = np.array(sorted(set(map(int, split.target)) - queried_selectable), dtype=int)
        if not len(candidates):
            break
        model = fit_model(next_round, queried)
        mean, raw_sigma = model.predict_mean_std(X[candidates])
        diagnostic_mean, diagnostic_raw_sigma = model.predict_mean_std(X[split.diagnostic])
        fit_seed = int(np.random.SeedSequence([config.seed, next_round, 31]).generate_state(1)[0])
        application = fit_and_apply_production_scale(
            spec,
            adapter=adapter,
            model=model,
            X_query=X[candidates],
            query_mean=mean,
            query_raw_sigma=raw_sigma,
            X_diagnostic=X[split.diagnostic],
            diagnostic_mean=diagnostic_mean,
            diagnostic_raw_sigma=diagnostic_raw_sigma,
            seed=fit_seed,
            floor=floor,
        )
        round_beta = _beta_for_round(config, len(queried_selectable) / max_queries)
        scores, stable_order = score_production_round(
            spec, application, mean, stable[candidates], beta=round_beta, adapter=adapter
        )
        number = min(batch_size, max_queries - len(queried_selectable), len(candidates))
        positions = np.asarray(stable_order[:number], int)
        selected = candidates[positions]
        diagnostic_rows.append(
            _diagnostic_row(
                spec=spec,
                y=y[split.diagnostic],
                mu=diagnostic_mean,
                sigma=application.diagnostic_sigma,
                interval_width=application.diagnostic_interval_half_width,
                interval_widths=application.diagnostic_interval_half_widths,
                floor=floor,
                metadata={"round": next_round, "budget_fraction": len(queried_selectable) / max_queries, "strategy": spec.id, "seed": config.seed},
                adapter=adapter,
            )
        )
        queried.extend(map(int, selected))
        queried_selectable.update(map(int, selected))
        budget = len(queried_selectable) / max_queries
        round_rows.append(
            {
                "round": next_round,
                "budget_fraction": budget,
                "top1_recall": adapter.modules["metrics"].recall(y, queried, split.target, stable, 0.01),
                "selected_batch_ids": ids[selected].tolist(),
                "candidate_count": int(len(candidates)),
                "strategy": spec.id,
                "seed": config.seed,
                "scale_status": application.status,
                "beta_used": round_beta,
                "effective_beta_median": float(
                    np.median(round_beta * application.query_scale_factor)
                ),
                "effective_beta_minimum": float(
                    np.min(round_beta * application.query_scale_factor)
                ),
                "effective_beta_maximum": float(
                    np.max(round_beta * application.query_scale_factor)
                ),
                "acquisition_score_hash": _sha(np.asarray(scores, float).round(14).tolist()),
                "stable_order_ids": ids[candidates[stable_order]].tolist(),
                "raw_sigma_floor_events": int(np.count_nonzero(raw_sigma < floor)),
            }
        )
        for label, threshold in thresholds.items():
            if label not in checkpoint_rows and budget + 1e-12 >= threshold:
                post_model = fit_model(next_round + 1, queried)
                durable.write_payload(
                    label,
                    _model_payload(post_model),
                    identity,
                    realized_progress=budget,
                    acquisition_round=next_round,
                    queried_count=len(queried),
                    crash_at=None,
                )
                checkpoint_rows[label] = len(diagnostic_rows) - 1
        _atomic_parquet_replace(pd.DataFrame(round_rows), rounds_path)
        _atomic_parquet_replace(pd.DataFrame(diagnostic_rows), diagnostic_path)
        _atomic_state(
            state_path,
            {
                **identity,
                "initial_indices": initial,
                "queried_indices": queried,
                "next_round": next_round + 1,
                "complete": False,
                "checkpoint_rows": checkpoint_rows,
                "last_valid_checkpoint": durable.last_valid_checkpoint(),
            },
        )
        next_round += 1

    for label in ("25pct", "50pct", "75pct"):
        if label not in checkpoint_rows:
            raise RuntimeError(f"campaign finished without canonical checkpoint {label}")
    endpoints = {
        "l1_campaign_mace": campaign_mace(pd.DataFrame(diagnostic_rows), checkpoint_rows),
        "l4_top1pct_recall_nauc": float(
            adapter.modules["metrics"].normalized_auc(
                np.asarray([row["budget_fraction"] for row in round_rows], float),
                np.asarray([row["top1_recall"] for row in round_rows], float),
            )
        ),
    }
    if not np.isfinite(list(endpoints.values())).all():
        raise RuntimeError("production endpoint is non-finite")
    _atomic_parquet_replace(pd.DataFrame(round_rows), rounds_path)
    _atomic_parquet_replace(pd.DataFrame(diagnostic_rows), diagnostic_path)
    final_state = {
        **identity,
        "initial_indices": initial,
        "queried_indices": queried,
        "next_round": next_round,
        "complete": True,
        "checkpoint_rows": checkpoint_rows,
        "last_valid_checkpoint": durable.last_valid_checkpoint(),
        "endpoints": endpoints,
        "primary_nauc": endpoints["l4_top1pct_recall_nauc"],
    }
    _atomic_state(state_path, final_state)
    atomic_write_json_no_overwrite(
        {
            "schema_version": "v6-production-trajectory-summary-v1",
            "job": asdict(config),
            "identity": identity,
            "source_ids_hash": _sha(ids[split.source].tolist()),
            "target_ids_hash": _sha(ids[split.target].tolist()),
            "diagnostic_ids_hash": _sha(ids[split.diagnostic].tolist()),
            "initial_labeled_ids": ids[np.asarray(initial, int)].tolist(),
            "queried_ids": ids[np.asarray(queried, int)].tolist(),
            "checkpoint_rows": checkpoint_rows,
            "endpoints": endpoints,
        },
        trace_path,
    )
    return {"job_id": config.job_id, "status": "COMPLETED", "output_dir": str(output_dir), **endpoints}
