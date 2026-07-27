from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


ScaleSource = Literal["raw", "global", "candidate"]
BetaMode = Literal["raw", "fixed_matched", "stage_matched", "normalized_global"]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    acquisition_scale: ScaleSource
    evaluation_scale: ScaleSource
    beta_mode: BetaMode = "raw"
    must_match_raw_path: bool = False
    replay_only: bool = False


STRATEGIES = {
    item.name: item
    for item in (
        StrategySpec("RAW", "raw", "raw"),
        StrategySpec("GG_JOINT", "global", "global"),
        StrategySpec("GG_CALIBRATION_ONLY", "raw", "global", must_match_raw_path=True),
        StrategySpec("GG_ACQUISITION_ONLY", "global", "raw"),
        StrategySpec("RAW_FIXED_BETA_MATCHED", "raw", "raw", "fixed_matched"),
        StrategySpec("RAW_STAGE_BETA_MATCHED", "raw", "raw", "stage_matched"),
        StrategySpec(
            "GG_NORMALIZED_ACQUISITION",
            "global",
            "global",
            "normalized_global",
            must_match_raw_path=True,
        ),
        StrategySpec("CS_JOINT", "candidate", "candidate"),
        StrategySpec("CS_CALIBRATION_ONLY", "raw", "candidate", must_match_raw_path=True),
        StrategySpec("CS_ACQUISITION_ONLY", "candidate", "raw"),
        StrategySpec("REPLAY_EVALUATION", "raw", "raw", replay_only=True),
    )
}


def _positive_vector(value: float | np.ndarray, n: int, name: str) -> np.ndarray:
    vector = np.broadcast_to(np.asarray(value, dtype=float), (n,)).copy()
    if not np.isfinite(vector).all() or np.any(vector <= 0):
        raise ValueError(f"{name} must be finite and positive")
    return vector


def stable_order(scores: np.ndarray, stable_ids: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    stable_ids = np.asarray(stable_ids)
    if scores.ndim != 1 or stable_ids.shape != scores.shape:
        raise ValueError("scores and stable_ids must be aligned one-dimensional vectors")
    if not np.isfinite(scores).all():
        raise ValueError("scores must be finite")
    return np.lexsort((stable_ids, -scores))


def score_round(
    spec: StrategySpec,
    mean: np.ndarray,
    raw_sigma: np.ndarray,
    stable_ids: np.ndarray,
    *,
    beta_raw: float,
    global_scale: float = 1.0,
    candidate_scale: np.ndarray | None = None,
    fixed_matched_beta: float | None = None,
    stage_matched_beta: float | None = None,
    sigma_floor: float = 1e-8,
) -> dict[str, np.ndarray | float]:
    mean = np.asarray(mean, dtype=float)
    raw_sigma = np.asarray(raw_sigma, dtype=float)
    stable_ids = np.asarray(stable_ids)
    if mean.shape != raw_sigma.shape or mean.shape != stable_ids.shape:
        raise ValueError("mean, raw_sigma, and stable_ids must align")
    if not np.isfinite(mean).all() or not np.isfinite(raw_sigma).all():
        raise ValueError("predictions must be finite")
    if sigma_floor <= 0:
        raise ValueError("sigma_floor must be positive")
    floored = np.maximum(raw_sigma, sigma_floor)
    n = len(mean)
    global_vector = _positive_vector(global_scale, n, "global_scale")
    candidate_vector = (
        _positive_vector(candidate_scale, n, "candidate_scale")
        if candidate_scale is not None
        else None
    )

    def scale(source: ScaleSource) -> np.ndarray:
        if source == "raw":
            return np.ones(n)
        if source == "global":
            return global_vector
        if candidate_vector is None:
            raise ValueError(f"{spec.name} requires candidate_scale")
        return candidate_vector

    acquisition_scale = scale(spec.acquisition_scale)
    evaluation_scale = scale(spec.evaluation_scale)
    if spec.beta_mode == "raw":
        beta = float(beta_raw)
    elif spec.beta_mode == "fixed_matched":
        if fixed_matched_beta is None:
            raise ValueError("fixed matched beta was not frozen")
        beta = float(fixed_matched_beta)
    elif spec.beta_mode == "stage_matched":
        if stage_matched_beta is None:
            raise ValueError("stage matched beta was not frozen")
        beta = float(stage_matched_beta)
    elif spec.beta_mode == "normalized_global":
        if not np.allclose(global_vector, global_vector[0]):
            raise ValueError("normalized global acquisition requires a scalar global scale")
        beta = float(beta_raw) / float(global_vector[0])
    else:  # pragma: no cover
        raise ValueError(spec.beta_mode)
    if not np.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    acquisition_sigma = floored * acquisition_scale
    evaluation_sigma = floored * evaluation_scale
    scores = mean + beta * acquisition_sigma
    order = stable_order(scores, stable_ids)
    return {
        "scores": scores,
        "stable_order": order,
        "raw_sigma_floored": floored,
        "acquisition_sigma": acquisition_sigma,
        "evaluation_sigma": evaluation_sigma,
        "acquisition_scale": acquisition_scale,
        "evaluation_scale": evaluation_scale,
        "beta_used": beta,
        "effective_beta": beta * acquisition_scale,
    }
