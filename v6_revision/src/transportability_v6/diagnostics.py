from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


VECTOR_COLUMNS = (
    "candidate_id", "task", "split", "model", "seed", "strategy", "round",
    "environment", "y", "mu", "sigma_raw", "sigma_scaled",
    "uncertainty_floor_before", "uncertainty_floor_after",
    "standardized_residual", "gaussian_log_term",
    "gaussian_squared_residual_term", "individual_nll",
)


def nll_vectors(
    *,
    y: np.ndarray,
    mu: np.ndarray,
    sigma_raw: np.ndarray,
    sigma_scaled: np.ndarray,
    candidate_id: np.ndarray,
    metadata: dict[str, object],
    floor: float = 1e-8,
) -> pd.DataFrame:
    y = np.asarray(y, dtype=float)
    mu = np.asarray(mu, dtype=float)
    raw = np.asarray(sigma_raw, dtype=float)
    scaled = np.asarray(sigma_scaled, dtype=float)
    candidate_id = np.asarray(candidate_id)
    if not (y.shape == mu.shape == raw.shape == scaled.shape == candidate_id.shape):
        raise ValueError("diagnostic vectors must align")
    if floor <= 0 or not np.isfinite(y).all() or not np.isfinite(mu).all():
        raise ValueError("finite y/mu and positive floor required")
    effective = np.maximum(scaled, floor)
    z = (y - mu) / effective
    log_term = 0.5 * np.log(2 * np.pi * np.square(effective))
    squared_term = 0.5 * np.square(z)
    frame = pd.DataFrame(
        {
            "candidate_id": candidate_id.astype(str),
            "y": y,
            "mu": mu,
            "sigma_raw": raw,
            "sigma_scaled": scaled,
            "uncertainty_floor_before": raw < floor,
            "uncertainty_floor_after": scaled < floor,
            "standardized_residual": z,
            "gaussian_log_term": log_term,
            "gaussian_squared_residual_term": squared_term,
            "individual_nll": log_term + squared_term,
        }
    )
    for key in ("task", "split", "model", "seed", "strategy", "round", "environment"):
        if key not in metadata:
            raise ValueError(f"missing metadata: {key}")
        frame[key] = metadata[key]
    frame = frame.loc[:, VECTOR_COLUMNS]
    if not np.isfinite(frame["individual_nll"]).all():
        raise FloatingPointError("non-finite individual NLL")
    return frame


def nll_summary(frame: pd.DataFrame, trim_fraction: float = 0.01) -> dict[str, float]:
    nll = frame["individual_nll"].to_numpy(float)
    sigma = np.maximum(frame["sigma_scaled"].to_numpy(float), 0)
    z = np.abs(frame["standardized_residual"].to_numpy(float))
    if not len(nll):
        raise ValueError("empty diagnostic frame")
    ordered = np.sort(nll)
    trim = min(int(len(ordered) * trim_fraction), max(0, (len(ordered) - 1) // 2))
    trimmed = ordered[trim : len(ordered) - trim] if trim else ordered
    total_abs = np.sum(np.abs(nll))
    return {
        "n": float(len(nll)),
        "mean": float(np.mean(nll)),
        "median": float(np.median(nll)),
        "trimmed_mean_descriptive": float(np.mean(trimmed)),
        "maximum": float(np.max(nll)),
        "p95": float(np.quantile(nll, 0.95)),
        "p99": float(np.quantile(nll, 0.99)),
        "p99p9": float(np.quantile(nll, 0.999)),
        "sigma_minimum": float(np.min(sigma)),
        "sigma_p01": float(np.quantile(sigma, 0.01)),
        "sigma_median": float(np.median(sigma)),
        "fraction_at_floor": float(np.mean(frame["uncertainty_floor_after"])),
        "maximum_abs_standardized_residual": float(np.max(z)),
        "largest_observation_contribution_share": (
            float(np.max(np.abs(nll)) / total_abs) if total_abs else 0.0
        ),
    }


def atomic_parquet(frame: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)
