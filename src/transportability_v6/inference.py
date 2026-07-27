"""Deterministic paired inference for prospectively registered V6 families."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Literal, Sequence

import numpy as np
import pandas as pd


Alternative = Literal["two-sided", "greater", "less"]


@dataclass(frozen=True)
class PairedEstimate:
    n_pairs: int
    mean_effect: float
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    sign_flip_p_value: float
    alternative: Alternative
    bootstrap_seed: int
    sign_flip_seed: int


def deterministic_child_seed(
    root_seed: int,
    family: str,
    environment: str,
    contrast: str,
    endpoint: str,
) -> int:
    """Derive the registered first-32-bit SHA-256 child seed."""

    if int(root_seed) < 0:
        raise ValueError("root seed must be non-negative")
    payload = f"{int(root_seed)}|{family}|{environment}|{contrast}|{endpoint}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big", signed=False)


def _differences(differences: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(differences, dtype=float)
    if values.ndim != 1 or not len(values):
        raise ValueError("paired differences must be a non-empty one-dimensional vector")
    if not np.isfinite(values).all():
        raise ValueError("paired differences must be finite")
    return values


def paired_mean_effect(differences: Sequence[float] | np.ndarray) -> float:
    return float(np.mean(_differences(differences)))


def paired_bootstrap_interval(
    differences: Sequence[float] | np.ndarray,
    *,
    seed: int,
    n_resamples: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    values = _differences(differences)
    if n_resamples != 10_000:
        raise ValueError("registered paired bootstrap requires exactly 10,000 resamples")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie in (0, 1)")
    rng = np.random.default_rng(int(seed))
    indices = rng.integers(0, len(values), size=(n_resamples, len(values)), endpoint=False)
    means = values[indices].mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    return float(np.quantile(means, alpha)), float(np.quantile(means, 1.0 - alpha))


def paired_sign_flip_pvalue(
    differences: Sequence[float] | np.ndarray,
    *,
    seed: int,
    alternative: Alternative = "two-sided",
    n_resamples: int = 10_000,
) -> float:
    """Paired randomization p value with the mandatory add-one correction."""

    values = _differences(differences)
    if n_resamples != 10_000:
        raise ValueError("registered paired sign-flip test requires exactly 10,000 resamples")
    if alternative not in {"two-sided", "greater", "less"}:
        raise ValueError("alternative must be two-sided, greater, or less")
    observed = float(np.mean(values))
    rng = np.random.default_rng(int(seed))
    signs = rng.integers(0, 2, size=(n_resamples, len(values)), endpoint=False) * 2 - 1
    simulated = (signs * values).mean(axis=1)
    tolerance = np.finfo(float).eps * max(1.0, abs(observed)) * 8.0
    if alternative == "two-sided":
        extreme = np.abs(simulated) >= abs(observed) - tolerance
    elif alternative == "greater":
        extreme = simulated >= observed - tolerance
    else:
        extreme = simulated <= observed + tolerance
    return float((1 + int(np.count_nonzero(extreme))) / (n_resamples + 1))


def align_complete_pairs(
    baseline: pd.DataFrame,
    test: pd.DataFrame,
    *,
    value_column: str,
    key_columns: tuple[str, ...] = ("environment", "seed"),
) -> pd.DataFrame:
    """Return one-to-one paired differences or reject missing/duplicate pairs."""

    required = set(key_columns) | {value_column}
    if not required <= set(baseline) or not required <= set(test):
        raise ValueError("paired inference frames lack required columns")
    if baseline.duplicated(list(key_columns)).any() or test.duplicated(list(key_columns)).any():
        raise ValueError("duplicate execution prevents one-to-one paired inference")
    merged = baseline[list(key_columns) + [value_column]].merge(
        test[list(key_columns) + [value_column]],
        how="outer",
        on=list(key_columns),
        validate="one_to_one",
        indicator=True,
        suffixes=("_baseline", "_test"),
    )
    if not merged["_merge"].eq("both").all():
        missing = merged.loc[~merged["_merge"].eq("both"), list(key_columns) + ["_merge"]]
        raise ValueError(f"missing paired endpoint rows: {missing.to_dict(orient='records')}")
    values = merged[[f"{value_column}_baseline", f"{value_column}_test"]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("paired endpoint values must be finite")
    merged["paired_difference"] = values[:, 1] - values[:, 0]
    return merged.drop(columns="_merge").sort_values(list(key_columns), kind="stable").reset_index(drop=True)


def require_40_pair_completeness(
    paired: pd.DataFrame | Iterable[int],
    *,
    seed_column: str = "seed",
    expected_seeds: Iterable[int] | None = None,
) -> None:
    """Enforce the confirmation 40-pair gate; no implicit exclusion is allowed."""

    if isinstance(paired, pd.DataFrame):
        if seed_column not in paired:
            raise ValueError(f"paired frame lacks {seed_column}")
        seeds = [int(value) for value in paired[seed_column].tolist()]
    else:
        seeds = [int(value) for value in paired]
    if len(seeds) != 40 or len(set(seeds)) != 40:
        raise ValueError("confirmation inference requires exactly 40 complete unique paired seeds")
    if expected_seeds is not None and set(seeds) != {int(value) for value in expected_seeds}:
        raise ValueError("paired seed set differs from the registered confirmation seed set")


def bh_adjust(p_values: Sequence[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("BH requires a non-empty vector of finite p values in [0, 1]")
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    adjusted = ordered * len(values) / np.arange(1, len(values) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0.0, 1.0)
    return result


def paired_inference(
    differences: Sequence[float] | np.ndarray,
    *,
    family: str,
    environment: str,
    contrast: str,
    endpoint: str,
    bootstrap_root_seed: int = 610001,
    sign_flip_root_seed: int = 610002,
    alternative: Alternative = "two-sided",
) -> PairedEstimate:
    values = _differences(differences)
    bootstrap_seed = deterministic_child_seed(
        bootstrap_root_seed, family, environment, contrast, endpoint
    )
    sign_seed = deterministic_child_seed(sign_flip_root_seed, family, environment, contrast, endpoint)
    lower, upper = paired_bootstrap_interval(values, seed=bootstrap_seed)
    return PairedEstimate(
        n_pairs=len(values),
        mean_effect=paired_mean_effect(values),
        bootstrap_ci_lower=lower,
        bootstrap_ci_upper=upper,
        sign_flip_p_value=paired_sign_flip_pvalue(values, seed=sign_seed, alternative=alternative),
        alternative=alternative,
        bootstrap_seed=bootstrap_seed,
        sign_flip_seed=sign_seed,
    )


def versioned_paired_exclusion_sensitivity(
    differences: Sequence[float] | np.ndarray,
    *,
    excluded_positions: Iterable[int],
    version: str,
    reason: str,
) -> dict[str, object]:
    """Report a fully versioned sensitivity analysis without mutating the primary set."""

    values = _differences(differences)
    positions = sorted({int(position) for position in excluded_positions})
    if any(position < 0 or position >= len(values) for position in positions):
        raise ValueError("excluded paired position is out of range")
    kept = np.ones(len(values), dtype=bool)
    kept[positions] = False
    if not kept.any():
        raise ValueError("sensitivity analysis cannot exclude every pair")
    return {
        "schema_version": "v6-paired-exclusion-sensitivity-v1",
        "version": str(version),
        "reason": str(reason),
        "primary_pair_count": int(len(values)),
        "excluded_positions": positions,
        "sensitivity_pair_count": int(kept.sum()),
        "primary_mean_effect": float(np.mean(values)),
        "sensitivity_mean_effect": float(np.mean(values[kept])),
        "direction_changed": bool(np.sign(np.mean(values)) != np.sign(np.mean(values[kept]))),
    }

