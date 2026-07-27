from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import validate_sigma


VECTOR_COLUMNS = (
    "candidate_id", "task", "split", "model", "seed", "strategy", "round",
    "environment", "y", "mu", "sigma_raw", "sigma_scaled", "sigma_effective",
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
    if not np.isfinite(y).all() or not np.isfinite(mu).all():
        raise ValueError("finite y/mu/sigma vectors and positive floor required")
    raw, _, raw_floor = validate_sigma(raw, floor=floor, name="sigma_raw")
    scaled, effective, scaled_floor = validate_sigma(scaled, floor=floor, name="sigma_scaled")
    if len(np.unique(candidate_id.astype(str))) != len(candidate_id):
        raise ValueError("duplicate diagnostic candidate_id")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        z_unbounded = (y - mu) / effective
    z_limit = np.sqrt(np.finfo(float).max / 4.0)
    z = np.clip(z_unbounded, -z_limit, z_limit)
    log_term = 0.5 * np.log(2 * np.pi * np.square(effective))
    squared_term = 0.5 * np.square(z)
    frame = pd.DataFrame(
        {
            "candidate_id": candidate_id.astype(str),
            "y": y,
            "mu": mu,
            "sigma_raw": raw,
            "sigma_scaled": scaled,
            "sigma_effective": effective,
            "uncertainty_floor_before": raw_floor,
            "uncertainty_floor_after": scaled_floor,
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
    raw_sigma = frame["sigma_raw"].to_numpy(float)
    if "sigma_effective" in frame:
        effective_sigma = frame["sigma_effective"].to_numpy(float)
    else:  # Compatibility with immutable Stage-2 diagnostic artifacts.
        effective_sigma = np.maximum(frame["sigma_scaled"].to_numpy(float), 1e-8)
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
        "raw_sigma_minimum": float(np.min(raw_sigma)),
        "raw_sigma_p01": float(np.quantile(raw_sigma, 0.01)),
        "raw_sigma_p05": float(np.quantile(raw_sigma, 0.05)),
        "raw_sigma_median": float(np.median(raw_sigma)),
        "raw_sigma_p95": float(np.quantile(raw_sigma, 0.95)),
        "raw_sigma_p99": float(np.quantile(raw_sigma, 0.99)),
        "effective_sigma_minimum": float(np.min(effective_sigma)),
        "effective_sigma_p01": float(np.quantile(effective_sigma, 0.01)),
        "effective_sigma_p05": float(np.quantile(effective_sigma, 0.05)),
        "effective_sigma_median": float(np.median(effective_sigma)),
        "effective_sigma_p95": float(np.quantile(effective_sigma, 0.95)),
        "effective_sigma_p99": float(np.quantile(effective_sigma, 0.99)),
        # Legacy aliases retained for Stage-2 report compatibility.
        "sigma_minimum": float(np.min(effective_sigma)),
        "sigma_p01": float(np.quantile(effective_sigma, 0.01)),
        "sigma_median": float(np.median(effective_sigma)),
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
    if path.exists():
        existing = pd.read_parquet(path)
        if not existing.equals(frame):
            raise FileExistsError(f"refusing to overwrite a different committed artifact: {path}")
        return
    try:
        frame.to_parquet(temporary, index=False, compression="zstd")
        pd.read_parquet(temporary)
        os.replace(temporary, path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def recover_atomic_parquet(path: str | Path) -> str:
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.is_file():
        if temporary.exists():
            temporary.unlink()
        pd.read_parquet(path)
        return "committed_file_kept"
    if temporary.is_file():
        pd.read_parquet(temporary)
        os.replace(temporary, path)
        return "validated_temporary_promoted"
    return "no_artifact"


def _trimmed_mean(values: np.ndarray, fraction: float = 0.01) -> float:
    ordered = np.sort(np.asarray(values, float))
    trim = min(int(len(ordered) * fraction), max(0, (len(ordered) - 1) // 2))
    selected = ordered[trim : len(ordered) - trim] if trim else ordered
    return float(np.mean(selected))


def nll_contrast_stability(
    baseline: pd.DataFrame,
    test: pd.DataFrame,
    *,
    key_columns: tuple[str, ...] = ("environment", "seed", "candidate_id", "round"),
) -> dict[str, object]:
    required = set(key_columns) | {"individual_nll"}
    if not required <= set(baseline) or not required <= set(test):
        raise ValueError("NLL contrast frames lack required columns")
    if baseline.duplicated(list(key_columns)).any() or test.duplicated(list(key_columns)).any():
        raise ValueError("duplicate NLL contrast rows")
    if not np.isfinite(baseline["individual_nll"].to_numpy(float)).all() or not np.isfinite(
        test["individual_nll"].to_numpy(float)
    ).all():
        raise ValueError("NLL contrast contains non-finite individual NLL values")
    paired = baseline[list(key_columns) + ["individual_nll"]].merge(
        test[list(key_columns) + ["individual_nll"]],
        on=list(key_columns),
        how="inner",
        validate="one_to_one",
        suffixes=("_baseline", "_test"),
    )
    if len(paired) != len(baseline) or len(paired) != len(test):
        raise ValueError("NLL contrast is not fully paired")
    diff = paired["individual_nll_test"].to_numpy(float) - paired[
        "individual_nll_baseline"
    ].to_numpy(float)
    mean_diff = float(np.mean(diff))
    trimmed_diff = _trimmed_mean(diff)
    seed_contribution = paired.assign(abs_diff=np.abs(diff)).groupby("seed")[
        "abs_diff"
    ].sum()
    total = float(seed_contribution.sum())
    largest_seed_share = float(seed_contribution.max() / total) if total else 0.0
    full_sign = int(np.sign(mean_diff))
    loo_signs = []
    for environment in sorted(paired["environment"].unique()):
        remaining = diff[paired["environment"].to_numpy() != environment]
        loo_signs.append(int(np.sign(np.mean(remaining))) if len(remaining) else full_sign)
    direction_agreement = int(np.sign(trimmed_diff)) == full_sign
    loo_stable = all(sign == full_sign for sign in loo_signs)
    return {
        "paired_rows": len(paired),
        "mean_difference": mean_diff,
        "trimmed_mean_difference": trimmed_diff,
        "trimmed_mean_direction_agreement": direction_agreement,
        "largest_seed_contribution_share": largest_seed_share,
        "leave_one_environment_out_direction_stable": loo_stable,
        "passes_seed_dominance_gate": largest_seed_share <= 0.20,
        "passes_trimmed_mean_direction_gate": direction_agreement,
        "passes_leave_one_environment_out_gate": loo_stable,
    }


def nll_stability_gate(
    baseline: pd.DataFrame,
    test: pd.DataFrame,
    *,
    floor_rate_maximum: float = 0.01,
    observation_dominance_maximum: float = 0.10,
    seed_dominance_maximum: float = 0.20,
) -> dict[str, object]:
    """Apply every registered NLL interpretability gate in one auditable result."""

    if not 0 <= floor_rate_maximum <= 1 or not 0 < observation_dominance_maximum <= 1 or not 0 < seed_dominance_maximum <= 1:
        raise ValueError("NLL stability thresholds are invalid")
    required = {"individual_nll", "uncertainty_floor_after", "sigma_raw", "sigma_scaled"}
    if not required <= set(baseline) or not required <= set(test):
        raise ValueError("NLL stability gate requires complete NLL vectors")
    baseline_summary = nll_summary(baseline)
    test_summary = nll_summary(test)
    contrast = nll_contrast_stability(baseline, test)
    checks = {
        "individual_nll_finite": bool(
            np.isfinite(baseline["individual_nll"].to_numpy(float)).all()
            and np.isfinite(test["individual_nll"].to_numpy(float)).all()
        ),
        "floor_rate": bool(
            baseline_summary["fraction_at_floor"] <= floor_rate_maximum
            and test_summary["fraction_at_floor"] <= floor_rate_maximum
        ),
        "observation_dominance": bool(
            baseline_summary["largest_observation_contribution_share"] <= observation_dominance_maximum
            and test_summary["largest_observation_contribution_share"] <= observation_dominance_maximum
        ),
        "seed_dominance": bool(contrast["largest_seed_contribution_share"] <= seed_dominance_maximum),
        "trimmed_mean_direction": bool(contrast["passes_trimmed_mean_direction_gate"]),
        "leave_one_environment_out": bool(contrast["passes_leave_one_environment_out_gate"]),
    }
    return {
        "status": "stable" if all(checks.values()) else "numerically_unstable_descriptive_only",
        "passes": all(checks.values()),
        "checks": checks,
        "baseline_summary": baseline_summary,
        "test_summary": test_summary,
        "contrast": contrast,
        "thresholds": {
            "floor_rate_maximum": floor_rate_maximum,
            "observation_dominance_maximum": observation_dominance_maximum,
            "seed_dominance_maximum": seed_dominance_maximum,
        },
    }
