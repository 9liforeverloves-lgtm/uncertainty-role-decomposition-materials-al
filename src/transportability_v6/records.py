from __future__ import annotations

import numpy as np
import pandas as pd

from .calibration import validate_sigma


REQUIRED_ROUND_COLUMNS = (
    "task", "split", "model", "seed", "strategy", "round", "budget_fraction",
    "candidate_id", "predictive_mean", "raw_sigma", "scaled_sigma",
    "raw_sigma_floor_event", "scaled_sigma_floor_event",
    "scale_factor", "raw_beta", "effective_beta", "acquisition_score",
    "stable_rank", "queried", "target", "target_revealed",
    "calibration_role", "selectable_role", "diagnostic_role",
)


def build_round_records(
    *,
    candidate_id: np.ndarray,
    predictive_mean: np.ndarray,
    raw_sigma: np.ndarray,
    scaled_sigma: np.ndarray,
    scale_factor: np.ndarray,
    raw_beta: float,
    effective_beta: np.ndarray,
    acquisition_score: np.ndarray,
    stable_rank: np.ndarray,
    queried: np.ndarray,
    target: np.ndarray,
    target_revealed: np.ndarray,
    calibration_role: np.ndarray,
    selectable_role: np.ndarray,
    diagnostic_role: np.ndarray,
    metadata: dict[str, object],
) -> pd.DataFrame:
    vectors = [
        candidate_id, predictive_mean, raw_sigma, scaled_sigma, scale_factor,
        effective_beta, acquisition_score, stable_rank, queried, target,
        target_revealed, calibration_role, selectable_role, diagnostic_role,
    ]
    arrays = [np.asarray(value) for value in vectors]
    n = len(arrays[0])
    if any(value.shape != (n,) for value in arrays):
        raise ValueError("round record vectors must be aligned")
    candidate_values = arrays[0].astype(str)
    if len(np.unique(candidate_values)) != len(candidate_values):
        raise ValueError("duplicate candidate IDs")
    mean = arrays[1].astype(float)
    if not np.isfinite(mean).all():
        raise ValueError("predictive_mean must be finite")
    raw_sigma, _, raw_floor_event = validate_sigma(arrays[2].astype(float), name="raw_sigma")
    scaled_sigma, _, scaled_floor_event = validate_sigma(arrays[3].astype(float), name="scaled_sigma")
    scale_factor = arrays[4].astype(float)
    if not np.isfinite(scale_factor).all() or np.any(scale_factor <= 0):
        raise ValueError("scale_factor must be finite and positive")
    if not np.isfinite(raw_beta) or float(raw_beta) < 0:
        raise ValueError("raw_beta must be finite and nonnegative")
    effective_beta_values = arrays[5].astype(float)
    if not np.isfinite(effective_beta_values).all() or np.any(effective_beta_values < 0):
        raise ValueError("effective_beta must be finite and nonnegative")
    scores = arrays[6].astype(float)
    if not np.isfinite(scores).all():
        raise ValueError("acquisition_score must be finite")
    ranks = arrays[7].astype(int)
    zero_based = np.array_equal(np.sort(ranks), np.arange(n))
    one_based = np.array_equal(np.sort(ranks), np.arange(1, n + 1))
    if not (zero_based or one_based):
        raise ValueError("stable_rank must be a complete permutation")
    queried_values = arrays[8].astype(bool)
    target_values = arrays[9].astype(float)
    revealed = arrays[10].astype(bool)
    calibration = arrays[11].astype(bool)
    selectable = arrays[12].astype(bool)
    diagnostic = arrays[13].astype(bool)
    roles = np.column_stack([calibration, selectable, diagnostic])
    if np.any(roles.sum(axis=1) != 1):
        raise ValueError("each row must have exactly one production role")
    if np.any(revealed & ~np.isfinite(target_values)):
        raise ValueError("revealed targets must be finite")
    if np.any(~revealed & ~np.isnan(target_values)):
        raise ValueError("unrevealed targets must be missing")
    if np.any(calibration & (~queried_values | ~revealed)):
        raise ValueError("calibration-role records must be queried with revealed targets")
    if np.any(selectable & (queried_values != revealed)):
        raise ValueError("selectable-role target revelation must equal queried status")
    if np.any(diagnostic & (queried_values | revealed)):
        raise ValueError("diagnostic-role records must remain unrevealed during production acquisition")
    frame = pd.DataFrame(
        {
            "candidate_id": candidate_values,
            "predictive_mean": mean,
            "raw_sigma": raw_sigma,
            "scaled_sigma": scaled_sigma,
            "raw_sigma_floor_event": raw_floor_event,
            "scaled_sigma_floor_event": scaled_floor_event,
            "scale_factor": scale_factor,
            "raw_beta": float(raw_beta),
            "effective_beta": effective_beta_values,
            "acquisition_score": scores,
            "stable_rank": ranks,
            "queried": queried_values,
            "target": target_values,
            "target_revealed": revealed,
            "calibration_role": calibration,
            "selectable_role": selectable,
            "diagnostic_role": diagnostic,
        }
    )
    for key in ("task", "split", "model", "seed", "strategy", "round", "budget_fraction"):
        if key not in metadata:
            raise ValueError(f"missing metadata: {key}")
        frame[key] = metadata[key]
    return frame.loc[:, REQUIRED_ROUND_COLUMNS]
