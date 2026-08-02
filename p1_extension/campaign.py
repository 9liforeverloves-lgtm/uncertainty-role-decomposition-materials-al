"""Checkpoint-ready P1 quantile-boosting active-learning campaign engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .metrics import (
    conditional_coverage,
    empirical_coverage,
    gaussian_crps,
    gaussian_nll,
    interval_score,
    mean_interval_width,
    normalized_auc,
    standardized_residual_summary,
    uncertainty_error_spearman,
)
from .models import (
    QuantileGradientBoostingSurrogate,
    crossfit_predictive_spread_aligned,
    fit_residual_ratio_aligned,
    stable_id_set_sha256,
)


Strategy = Literal["P1_QGB_RAW", "P1_QGB_CALIBRATION_ONLY_RR", "P1_QGB_ACQUISITION_ONLY_RR"]
COVERAGES = (0.50, 0.80, 0.90, 0.95)
CHECKPOINTS = {"initial": 0.0, "25pct": 0.25, "50pct": 0.50, "75pct": 0.75}


@dataclass(frozen=True)
class CampaignConfig:
    strategy: Strategy
    seed: int
    beta: float
    initial_count: int
    batch_size: int
    max_queries: int


def _stable_descending(values: np.ndarray, stable_ids: np.ndarray) -> np.ndarray:
    """Descending value with stable record ID as deterministic tie-break."""
    values = np.asarray(values, dtype=float).reshape(-1)
    stable_ids = np.asarray(stable_ids, dtype=str).reshape(-1)
    if len(values) != len(stable_ids) or not np.isfinite(values).all():
        raise ValueError("score and stable-ID vectors must be aligned and finite")
    return np.lexsort((stable_ids, -values))


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _atomic_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    pd.DataFrame(rows).to_parquet(temporary, index=False, compression="zstd")
    pd.read_parquet(temporary)
    os.replace(temporary, path)


def _stable_top_set(y: np.ndarray, pool: np.ndarray, ids: np.ndarray, fraction: float) -> np.ndarray:
    pool = np.asarray(pool, dtype=int)
    count = max(1, int(np.ceil(float(fraction) * len(pool))))
    order = np.lexsort((ids[pool].astype(str), -y[pool]))
    return pool[order[:count]]


def _recall(queried: list[int], target_set: np.ndarray) -> float:
    return float(len(set(map(int, queried)) & set(map(int, target_set))) / len(target_set))


def _mace(row: dict[str, object]) -> float:
    return float(np.mean([abs(float(row[f"coverage_{int(level * 100)}"]) - level) for level in COVERAGES]))


def _load_rows(path: Path) -> list[dict[str, object]]:
    return pd.read_parquet(path).to_dict("records") if path.is_file() else []


def run_qgb_campaign(
    X: np.ndarray,
    y: np.ndarray,
    *,
    material_ids: np.ndarray,
    source: np.ndarray,
    target: np.ndarray,
    diagnostic: np.ndarray,
    config: CampaignConfig,
    output_dir: Path,
    resume: bool = True,
) -> dict[str, object]:
    """Run one registered QGB environment with atomic job-level artifacts."""
    X, y = np.asarray(X, float), np.asarray(y, float).reshape(-1)
    ids = np.asarray(material_ids, dtype=str).reshape(-1)
    source, target, diagnostic = (np.asarray(v, dtype=int).reshape(-1) for v in (source, target, diagnostic))
    if X.ndim != 2 or len(X) != len(y) or len(ids) != len(y):
        raise ValueError("X/y/material_ids must be aligned")
    if not np.isfinite(X).all() or not np.isfinite(y).all() or len(np.unique(ids)) != len(ids):
        raise ValueError("finite inputs and globally unique material IDs are required")
    if set(source) & set(target) or set(source) & set(diagnostic) or set(target) & set(diagnostic):
        raise ValueError("source, target and diagnostic roles must be disjoint")
    if config.strategy not in {"P1_QGB_RAW", "P1_QGB_CALIBRATION_ONLY_RR", "P1_QGB_ACQUISITION_ONLY_RR"}:
        raise ValueError("unregistered strategy")
    if config.initial_count < 5 or config.initial_count > len(source):
        raise ValueError("initial_count must permit five-fold cross-fitting")
    if config.batch_size < 1 or config.max_queries < 1 or config.max_queries > len(target):
        raise ValueError("invalid campaign geometry")

    output_dir = Path(output_dir)
    state_path = output_dir / "state.json"
    rounds_path = output_dir / "rounds.parquet"
    diagnostic_metrics_path = output_dir / "diagnostic_metrics.parquet"
    diagnostic_predictions_path = output_dir / "diagnostic_predictions.parquet"
    state: dict[str, object] | None = None
    if resume and state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["config"] != asdict(config):
            raise RuntimeError("checkpoint configuration mismatch")
        if state.get("complete"):
            return state

    if state is None:
        initial = np.sort(np.random.default_rng(config.seed).choice(source, size=config.initial_count, replace=False)).tolist()
        queried: list[int] = []
        next_round = 0
        checkpoint_rows: dict[str, int] = {}
        round_rows: list[dict[str, object]] = []
        diagnostic_rows: list[dict[str, object]] = []
        prediction_rows: list[dict[str, object]] = []
    else:
        initial = list(map(int, state["initial_indices"]))
        queried = list(map(int, state["queried_indices"]))
        next_round = int(state["next_round"])
        checkpoint_rows = {str(k): int(v) for k, v in dict(state["checkpoint_rows"]).items()}
        round_rows = _load_rows(rounds_path)
        diagnostic_rows = _load_rows(diagnostic_metrics_path)
        prediction_rows = _load_rows(diagnostic_predictions_path)

    top_sets = {fraction: _stable_top_set(y, target, ids, fraction) for fraction in (0.01, 0.05, 0.10)}
    pool_reference = np.concatenate((source, target))
    source_set, diagnostic_set = set(map(int, source)), set(map(int, diagnostic))

    while len(queried) < config.max_queries:
        labelled = np.asarray(initial + queried, dtype=int)
        labelled_ids = ids[labelled]
        if set(labelled) & diagnostic_set or not set(initial) <= source_set:
            raise RuntimeError("diagnostic leakage or invalid initial role")
        model_seed = int(np.random.SeedSequence([config.seed, next_round, 43]).generate_state(1)[0])
        model = QuantileGradientBoostingSurrogate(random_state=model_seed).fit(X[labelled], y[labelled])
        ratio = 1.0
        scalar_ids_hash = stable_id_set_sha256(labelled_ids)
        if config.strategy != "P1_QGB_RAW":
            aligned = crossfit_predictive_spread_aligned(
                X[labelled], y[labelled], labelled_ids, random_state=model_seed, n_splits=5
            )
            labelled_y_by_id = {
                str(ids[index]): float(y[index]) for index in labelled
            }
            ratio = fit_residual_ratio_aligned(labelled_ids, labelled_y_by_id, aligned)

        budget = len(queried) / config.max_queries
        diagnostic_pred = model.predict(X[diagnostic])
        evaluation_sigma = diagnostic_pred.sigma * ratio if config.strategy == "P1_QGB_CALIBRATION_ONLY_RR" else diagnostic_pred.sigma
        evaluation_sigma = np.maximum(evaluation_sigma, model.floor)
        coverage = empirical_coverage(y[diagnostic], diagnostic_pred.mean, evaluation_sigma, COVERAGES)
        residual_summary = standardized_residual_summary(y[diagnostic], diagnostic_pred.mean, evaluation_sigma)
        diagnostic_row: dict[str, object] = {
            "round": next_round,
            "budget_fraction": budget,
            "strategy": config.strategy,
            "seed": config.seed,
            "diagnostic_count": len(diagnostic),
            "diagnostic_targets_used_in_scalar": False,
            "scalar_fit_count": len(labelled),
            "scalar_fit_ids_sha256": scalar_ids_hash,
            "residual_ratio": ratio,
            "quantile_crossings": diagnostic_pred.crossing_count,
            **{f"coverage_{int(level * 100)}": value for level, value in coverage.items()},
            "mean_absolute_coverage_error": float(np.mean([abs(coverage[level] - level) for level in COVERAGES])),
            "mean_interval_width_50": mean_interval_width(evaluation_sigma, 0.50),
            "mean_interval_width_80": mean_interval_width(evaluation_sigma, 0.80),
            "mean_interval_width_90": mean_interval_width(evaluation_sigma, 0.90),
            "mean_interval_width_95": mean_interval_width(evaluation_sigma, 0.95),
            "interval_score_90": interval_score(y[diagnostic], diagnostic_pred.mean, evaluation_sigma, 0.90),
            "gaussian_nll": gaussian_nll(y[diagnostic], diagnostic_pred.mean, evaluation_sigma),
            "gaussian_crps": gaussian_crps(y[diagnostic], diagnostic_pred.mean, evaluation_sigma),
            "standardized_residual_mean": residual_summary["mean"],
            "standardized_residual_std": residual_summary["std"],
            "standardized_residual_skewness": residual_summary["skewness"],
            "standardized_residual_median_abs": residual_summary["median_abs"],
            **{f"standardized_residual_{key}": value for key, value in residual_summary.items() if key.startswith("q")},
            "uncertainty_error_spearman": uncertainty_error_spearman(y[diagnostic], diagnostic_pred.mean, evaluation_sigma),
        }
        diagnostic_index = len(diagnostic_rows)
        diagnostic_rows.append(diagnostic_row)
        for label, threshold in CHECKPOINTS.items():
            if label not in checkpoint_rows and budget + 1e-12 >= threshold:
                checkpoint_rows[label] = diagnostic_index
        for local, global_index in enumerate(diagnostic):
            prediction_rows.append({
                "round": next_round,
                "budget_fraction": budget,
                "material_id": ids[global_index],
                "target": y[global_index],
                "predicted_mean": diagnostic_pred.mean[local],
                "q0_16": diagnostic_pred.q_low[local],
                "q0_84": diagnostic_pred.q_high[local],
                "raw_sigma": diagnostic_pred.sigma[local],
                "evaluation_sigma": evaluation_sigma[local],
            })

        observed = np.asarray(initial + queried, dtype=int)
        best = float(np.max(y[observed]))
        target_optimum = float(np.max(y[pool_reference]))
        row: dict[str, object] = {
            "round": next_round,
            "budget_fraction": budget,
            "queried_count": len(queried),
            "queried_ids_sha256": stable_id_set_sha256(ids[np.asarray(queried, dtype=int)]),
            "residual_ratio": ratio,
            "top1_recall": _recall(queried, top_sets[0.01]),
            "top5_recall": _recall(queried, top_sets[0.05]),
            "top10_recall": _recall(queried, top_sets[0.10]),
            "best_so_far": best,
            "simple_regret": target_optimum - best,
            "enrichment_top1": float("nan") if not queried else _recall(queried, top_sets[0.01]) * len(top_sets[0.01]) / len(queried) / (len(top_sets[0.01]) / len(target)),
            "selected_batch_ids_json": "[]",
        }

        remaining = np.asarray(sorted(set(map(int, target)) - set(queried)), dtype=int)
        if set(remaining) & set(queried):
            raise RuntimeError("queried records remained in candidate set")
        candidate_pred = model.predict(X[remaining])
        acquisition_sigma = candidate_pred.sigma * ratio if config.strategy == "P1_QGB_ACQUISITION_ONLY_RR" else candidate_pred.sigma
        score = candidate_pred.mean + float(config.beta) * acquisition_sigma
        order = _stable_descending(score, ids[remaining])
        count = min(config.batch_size, config.max_queries - len(queried), len(remaining))
        selected = remaining[order[:count]].tolist()
        row["selected_batch_ids_json"] = json.dumps(ids[np.asarray(selected, dtype=int)].tolist())
        row["candidate_count"] = len(remaining)
        row["candidate_quantile_crossings"] = candidate_pred.crossing_count
        row["acquisition_order_sha256"] = hashlib.sha256("\n".join(ids[remaining[order]].tolist()).encode("utf-8")).hexdigest()
        round_rows.append(row)
        queried.extend(map(int, selected))
        next_round += 1

        partial = {
            "schema_version": 2,
            "config": asdict(config),
            "initial_indices": initial,
            "queried_indices": queried,
            "next_round": next_round,
            "checkpoint_rows": checkpoint_rows,
            "complete": False,
        }
        _atomic_parquet(rounds_path, round_rows)
        _atomic_parquet(diagnostic_metrics_path, diagnostic_rows)
        _atomic_parquet(diagnostic_predictions_path, prediction_rows)
        _atomic_json(state_path, partial)

    # Query-complete state: no model fit is needed to record final discovery.
    observed = np.asarray(initial + queried, dtype=int)
    final_best = float(np.max(y[observed]))
    target_optimum = float(np.max(y[pool_reference]))
    round_rows.append({
        "round": next_round,
        "budget_fraction": 1.0,
        "queried_count": len(queried),
        "queried_ids_sha256": stable_id_set_sha256(ids[np.asarray(queried, dtype=int)]),
        "residual_ratio": float("nan"),
        "top1_recall": _recall(queried, top_sets[0.01]),
        "top5_recall": _recall(queried, top_sets[0.05]),
        "top10_recall": _recall(queried, top_sets[0.10]),
        "best_so_far": final_best,
        "simple_regret": target_optimum - final_best,
        "enrichment_top1": _recall(queried, top_sets[0.01]) * len(top_sets[0.01]) / len(queried) / (len(top_sets[0.01]) / len(target)),
        "selected_batch_ids_json": "[]",
        "candidate_count": len(target) - len(queried),
        "candidate_quantile_crossings": 0,
        "acquisition_order_sha256": "NOT_APPLICABLE_FINAL_STATE",
    })
    if set(checkpoint_rows) != set(CHECKPOINTS):
        raise RuntimeError(f"campaign lacks registered checkpoint rows: {checkpoint_rows}")
    budgets = np.asarray([float(row["budget_fraction"]) for row in round_rows])
    endpoints = {
        "l1_campaign_mace": float(np.mean([_mace(diagnostic_rows[checkpoint_rows[label]]) for label in CHECKPOINTS])),
        "l4_top1pct_recall_nauc": normalized_auc(budgets, np.asarray([float(row["top1_recall"]) for row in round_rows])),
        "top5pct_recall_nauc": normalized_auc(budgets, np.asarray([float(row["top5_recall"]) for row in round_rows])),
        "top10pct_recall_nauc": normalized_auc(budgets, np.asarray([float(row["top10_recall"]) for row in round_rows])),
    }
    if not np.isfinite(list(endpoints.values())).all():
        raise RuntimeError("non-finite registered endpoint")
    final_state = {
        "schema_version": 2,
        "config": asdict(config),
        "initial_indices": initial,
        "queried_indices": queried,
        "next_round": next_round,
        "checkpoint_rows": checkpoint_rows,
        "endpoints": endpoints,
        "complete": True,
    }
    _atomic_parquet(rounds_path, round_rows)
    _atomic_parquet(diagnostic_metrics_path, diagnostic_rows)
    _atomic_parquet(diagnostic_predictions_path, prediction_rows)
    _atomic_json(state_path, final_state)
    _atomic_json(output_dir / "trajectory.json", final_state)
    return final_state
