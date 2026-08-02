"""Prespecified calibration and discovery metrics for the independent P1 study."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, skew, spearmanr


def _vectors(*values: np.ndarray) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(v, dtype=float).reshape(-1) for v in values)
    if not arrays or len({len(v) for v in arrays}) != 1 or len(arrays[0]) == 0:
        raise ValueError("metric inputs must be aligned non-empty vectors")
    if not all(np.isfinite(v).all() for v in arrays):
        raise ValueError("metric inputs must be finite")
    return arrays


def empirical_coverage(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray, levels=(0.5, 0.8, 0.9, 0.95)) -> dict[float, float]:
    y, mean, sigma = _vectors(y, mean, sigma)
    if np.any(sigma <= 0):
        raise ValueError("sigma must be positive")
    return {
        float(level): float(np.mean(np.abs(y - mean) <= norm.ppf((1 + level) / 2) * sigma))
        for level in levels
    }


def mean_interval_width(sigma: np.ndarray, coverage: float = 0.9) -> float:
    (sigma,) = _vectors(sigma)
    if np.any(sigma <= 0):
        raise ValueError("sigma must be positive")
    return float(np.mean(2 * norm.ppf((1 + coverage) / 2) * sigma))


def interval_score(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray, coverage: float = 0.9) -> float:
    y, mean, sigma = _vectors(y, mean, sigma)
    alpha = 1 - float(coverage)
    if not 0 < alpha < 1 or np.any(sigma <= 0):
        raise ValueError("coverage and sigma are invalid")
    half = norm.ppf(1 - alpha / 2) * sigma
    lower, upper = mean - half, mean + half
    score = (upper - lower) + (2 / alpha) * (lower - y) * (y < lower) + (2 / alpha) * (y - upper) * (y > upper)
    return float(np.mean(score))


def gaussian_nll(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray) -> float:
    y, mean, sigma = _vectors(y, mean, sigma)
    if np.any(sigma <= 0):
        raise ValueError("sigma must be positive")
    return float(np.mean(0.5 * np.log(2 * np.pi * sigma**2) + 0.5 * ((y - mean) / sigma) ** 2))


def gaussian_crps(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray) -> float:
    y, mean, sigma = _vectors(y, mean, sigma)
    if np.any(sigma <= 0):
        raise ValueError("sigma must be positive")
    z = (y - mean) / sigma
    crps = sigma * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / math.sqrt(np.pi))
    return float(np.mean(crps))


def standardized_residual_summary(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray) -> dict[str, float]:
    y, mean, sigma = _vectors(y, mean, sigma)
    if np.any(sigma <= 0):
        raise ValueError("sigma must be positive")
    z = (y - mean) / sigma
    skewness = float(skew(z, bias=False))
    if not np.isfinite(skewness):
        skewness = 0.0
    return {
        "mean": float(z.mean()),
        "std": float(z.std(ddof=1)),
        "skewness": skewness,
        "median_abs": float(np.median(np.abs(z))),
        **{f"q{int(probability * 100):02d}": float(np.quantile(z, probability)) for probability in (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99)},
    }


def qq_points(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y, mean, sigma = _vectors(y, mean, sigma)
    z = np.sort((y - mean) / sigma)
    theoretical = norm.ppf((np.arange(len(z)) + 0.5) / len(z))
    return theoretical, z


def uncertainty_error_spearman(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray) -> float:
    y, mean, sigma = _vectors(y, mean, sigma)
    value = spearmanr(sigma, np.abs(y - mean)).statistic
    return float(value) if np.isfinite(value) else 0.0


def conditional_coverage(y: np.ndarray, mean: np.ndarray, sigma: np.ndarray, *, coverage: float = 0.9, bins: int = 5, by: str = "uncertainty") -> list[dict[str, float]]:
    y, mean, sigma = _vectors(y, mean, sigma)
    if bins < 2:
        raise ValueError("bins must be at least two")
    if by not in {"uncertainty", "predicted_mean"}:
        raise ValueError("by must be uncertainty or predicted_mean")
    stratifier = sigma if by == "uncertainty" else mean
    order = np.argsort(stratifier, kind="mergesort")
    half = norm.ppf((1 + coverage) / 2) * sigma
    rows = []
    for index, group in enumerate(np.array_split(order, bins)):
        rows.append({"bin": float(index), "n": float(len(group)), "mean_sigma": float(sigma[group].mean()), "mean_prediction": float(mean[group].mean()), "coverage": float(np.mean(np.abs(y[group] - mean[group]) <= half[group]))})
    return rows


def normalized_auc(x: np.ndarray, y: np.ndarray) -> float:
    x, y = _vectors(x, y)
    if len(x) < 2 or np.any(np.diff(x) < 0) or x[-1] <= x[0]:
        raise ValueError("x must be ordered and span a positive range")
    return float(np.trapezoid(y, x) / (x[-1] - x[0]))


def top_fraction_recall(y: np.ndarray, queried: np.ndarray, *, fraction: float = 0.01, maximize: bool = True) -> float:
    (y,) = _vectors(y)
    queried = np.asarray(queried, dtype=int).reshape(-1)
    count = max(1, int(np.ceil(float(fraction) * len(y))))
    order = np.argsort(y, kind="mergesort")
    top = order[-count:] if maximize else order[:count]
    return float(len(np.intersect1d(top, queried, assume_unique=False)) / count)


@dataclass(frozen=True)
class DiscoverySummary:
    recall_nauc: float
    best_so_far: float
    simple_regret: float
    enrichment: float
    time_to_first: float
    time_to_half: float
    gain_over_random: float
    segment_auc_early: float
    segment_auc_middle: float
    segment_auc_late: float


def discovery_summary(budget_fraction: np.ndarray, recall: np.ndarray, best: np.ndarray, *, optimum: float, random_recall: np.ndarray) -> DiscoverySummary:
    budget_fraction, recall, best, random_recall = _vectors(budget_fraction, recall, best, random_recall)
    if np.any(np.diff(budget_fraction) < 0):
        raise ValueError("budget must be ordered")
    def segment(low: float, high: float) -> float:
        inside = (budget_fraction > low) & (budget_fraction < high)
        x = np.concatenate(([low], budget_fraction[inside], [high]))
        values = np.interp(x, budget_fraction, recall)
        return normalized_auc(x, values)
    first = np.flatnonzero(recall > 0)
    half = np.flatnonzero(recall >= 0.5)
    expected = max(float(random_recall[-1]), np.finfo(float).eps)
    return DiscoverySummary(
        normalized_auc(budget_fraction, recall),
        float(best[-1]),
        float(optimum - best[-1]),
        float(recall[-1] / expected),
        float(budget_fraction[first[0]]) if len(first) else 1.0,
        float(budget_fraction[half[0]]) if len(half) else 1.0,
        normalized_auc(budget_fraction, recall - random_recall),
        segment(0.0, 0.25),
        segment(0.25, 0.75),
        segment(0.75, 1.0),
    )
