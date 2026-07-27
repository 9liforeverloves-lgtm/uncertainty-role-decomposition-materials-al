from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_ROUND_COLUMNS = (
    "task", "split", "model", "seed", "strategy", "round", "budget_fraction",
    "candidate_id", "predictive_mean", "raw_sigma", "scaled_sigma",
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
    roles = np.column_stack(
        [arrays[-3].astype(bool), arrays[-2].astype(bool), arrays[-1].astype(bool)]
    )
    if np.any(roles.sum(axis=1) > 1):
        raise ValueError("calibration/selectable/diagnostic roles overlap")
    revealed = arrays[-4].astype(bool)
    target_values = arrays[-5].astype(float)
    if np.any(~revealed & np.isfinite(target_values)):
        raise ValueError("unrevealed targets must be missing")
    frame = pd.DataFrame(
        {
            "candidate_id": arrays[0].astype(str),
            "predictive_mean": arrays[1].astype(float),
            "raw_sigma": arrays[2].astype(float),
            "scaled_sigma": arrays[3].astype(float),
            "scale_factor": arrays[4].astype(float),
            "raw_beta": float(raw_beta),
            "effective_beta": arrays[5].astype(float),
            "acquisition_score": arrays[6].astype(float),
            "stable_rank": arrays[7].astype(int),
            "queried": arrays[8].astype(bool),
            "target": target_values,
            "target_revealed": revealed,
            "calibration_role": arrays[11].astype(bool),
            "selectable_role": arrays[12].astype(bool),
            "diagnostic_role": arrays[13].astype(bool),
        }
    )
    for key in ("task", "split", "model", "seed", "strategy", "round", "budget_fraction"):
        if key not in metadata:
            raise ValueError(f"missing metadata: {key}")
        frame[key] = metadata[key]
    return frame.loc[:, REQUIRED_ROUND_COLUMNS]
