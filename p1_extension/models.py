"""Frozen P1 quantile-gradient-boosting surrogate.

The returned scale is an interval-derived conditional predictive-spread proxy.
It must not be described as epistemic uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold


Q_LOW = 0.16
Q_HIGH = 0.84
SIGMA_DENOMINATOR = 1.9889157664195078
DEFAULT_FLOOR = 1e-8
SHARED_PARAMETERS = {
    "n_estimators": 200,
    "learning_rate": 0.05,
    "max_depth": 3,
    "min_samples_leaf": 5,
    "subsample": 1.0,
}


@dataclass(frozen=True)
class PredictiveSpread:
    mean: np.ndarray
    sigma: np.ndarray
    q_low: np.ndarray
    q_high: np.ndarray
    crossing_count: int


@dataclass(frozen=True)
class AlignedPredictiveSpread:
    """Cross-fitted predictions explicitly keyed by immutable record ID."""

    record_ids: np.ndarray
    prediction: PredictiveSpread

    def validate(self) -> None:
        ids = np.asarray(self.record_ids, dtype=str).reshape(-1)
        if len(ids) != len(self.prediction.mean) or len(np.unique(ids)) != len(ids):
            raise ValueError("cross-fit record IDs must be unique and aligned")


class QuantileGradientBoostingSurrogate:
    """Central and conditional-quantile regressors with shared parameters."""

    def __init__(self, *, random_state: int, floor: float = DEFAULT_FLOOR) -> None:
        if not np.isfinite(floor) or floor <= 0:
            raise ValueError("floor must be finite and positive")
        self.random_state = int(random_state)
        self.floor = float(floor)
        common = dict(SHARED_PARAMETERS, random_state=self.random_state)
        self.central = GradientBoostingRegressor(loss="squared_error", **common)
        self.lower = GradientBoostingRegressor(loss="quantile", alpha=Q_LOW, **common)
        self.upper = GradientBoostingRegressor(loss="quantile", alpha=Q_HIGH, **common)
        self._is_fitted = False

    @staticmethod
    def _validated_xy(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).reshape(-1)
        if X.ndim != 2 or len(X) != len(y) or len(y) < 2:
            raise ValueError("X/y must be aligned with at least two rows")
        if not np.isfinite(X).all() or not np.isfinite(y).all():
            raise ValueError("X/y must be finite")
        return X, y

    def fit(self, X: np.ndarray, y: np.ndarray) -> "QuantileGradientBoostingSurrogate":
        X, y = self._validated_xy(X, y)
        self.central.fit(X, y)
        self.lower.fit(X, y)
        self.upper.fit(X, y)
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> PredictiveSpread:
        if not self._is_fitted:
            raise RuntimeError("fit must be called before predict")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or not np.isfinite(X).all():
            raise ValueError("X must be a finite matrix")
        mean = self.central.predict(X)
        q_low = self.lower.predict(X)
        q_high = self.upper.predict(X)
        crossing = q_high < q_low
        sigma = np.maximum((q_high - q_low) / SIGMA_DENOMINATOR, self.floor)
        if not all(np.isfinite(v).all() for v in (mean, q_low, q_high, sigma)):
            raise FloatingPointError("non-finite predictive output")
        return PredictiveSpread(mean, sigma, q_low, q_high, int(crossing.sum()))


def crossfit_predictive_spread(
    X: np.ndarray,
    y: np.ndarray,
    *,
    random_state: int,
    n_splits: int = 5,
    floor: float = DEFAULT_FLOOR,
) -> PredictiveSpread:
    """Deterministic labelled-only out-of-fold predictions for calibration."""
    X, y = QuantileGradientBoostingSurrogate._validated_xy(X, y)
    if n_splits < 2 or n_splits > len(y):
        raise ValueError("invalid n_splits")
    mean = np.empty(len(y), dtype=float)
    sigma = np.empty(len(y), dtype=float)
    q_low = np.empty(len(y), dtype=float)
    q_high = np.empty(len(y), dtype=float)
    crossings = 0
    folds = KFold(n_splits=n_splits, shuffle=True, random_state=int(random_state))
    for fold, (train, valid) in enumerate(folds.split(X)):
        model = QuantileGradientBoostingSurrogate(
            random_state=int(random_state) + fold, floor=floor
        ).fit(X[train], y[train])
        pred = model.predict(X[valid])
        mean[valid], sigma[valid] = pred.mean, pred.sigma
        q_low[valid], q_high[valid] = pred.q_low, pred.q_high
        crossings += pred.crossing_count
    return PredictiveSpread(mean, sigma, q_low, q_high, crossings)


def crossfit_predictive_spread_aligned(
    X: np.ndarray,
    y: np.ndarray,
    record_ids: np.ndarray,
    *,
    random_state: int,
    n_splits: int = 5,
    floor: float = DEFAULT_FLOOR,
) -> AlignedPredictiveSpread:
    """Return deterministic OOF predictions keyed by stable record IDs."""
    ids = np.asarray(record_ids, dtype=str).reshape(-1)
    X_checked, y_checked = QuantileGradientBoostingSurrogate._validated_xy(X, y)
    if len(ids) != len(y_checked) or len(np.unique(ids)) != len(ids):
        raise ValueError("record_ids must be unique and aligned with X/y")
    prediction = crossfit_predictive_spread(
        X_checked,
        y_checked,
        random_state=random_state,
        n_splits=n_splits,
        floor=floor,
    )
    aligned = AlignedPredictiveSpread(ids.copy(), prediction)
    aligned.validate()
    return aligned


def fit_residual_ratio(y: np.ndarray, prediction: PredictiveSpread, *, floor: float = DEFAULT_FLOOR) -> float:
    """Fit the frozen robust scalar from labelled residuals only."""
    y = np.asarray(y, dtype=float).reshape(-1)
    if len(y) != len(prediction.mean) or not np.isfinite(y).all():
        raise ValueError("y and prediction must be aligned and finite")
    ratio = np.abs(y - prediction.mean) / np.maximum(prediction.sigma, floor)
    value = float(np.median(ratio))
    if not np.isfinite(value) or value < 0:
        raise FloatingPointError("invalid residual-ratio fit")
    return value


def fit_residual_ratio_aligned(
    record_ids: np.ndarray,
    y_by_id: dict[str, float],
    aligned: AlignedPredictiveSpread,
    *,
    floor: float = DEFAULT_FLOOR,
) -> float:
    """Fit the scalar only after exact ID-set validation and ID lookup."""
    ids = np.asarray(record_ids, dtype=str).reshape(-1)
    aligned.validate()
    if len(np.unique(ids)) != len(ids):
        raise ValueError("requested scalar-fit IDs are duplicated")
    if set(ids) != set(aligned.record_ids):
        missing = sorted(set(ids) - set(aligned.record_ids))[:3]
        extra = sorted(set(aligned.record_ids) - set(ids))[:3]
        raise ValueError(f"cross-fit ID mismatch: missing={missing}, extra={extra}")
    if set(ids) - set(y_by_id):
        raise ValueError("target lookup lacks registered scalar-fit IDs")
    position = {value: index for index, value in enumerate(aligned.record_ids.tolist())}
    ordered_y = np.asarray([float(y_by_id[value]) for value in ids], dtype=float)
    ordered_mean = np.asarray([aligned.prediction.mean[position[value]] for value in ids], dtype=float)
    ordered_sigma = np.asarray([aligned.prediction.sigma[position[value]] for value in ids], dtype=float)
    reordered = PredictiveSpread(ordered_mean, ordered_sigma, ordered_mean, ordered_mean, aligned.prediction.crossing_count)
    return fit_residual_ratio(ordered_y, reordered, floor=floor)


def stable_id_set_sha256(record_ids: np.ndarray) -> str:
    """Hash an ordered ID sequence for leakage/provenance audits."""
    payload = "\n".join(np.asarray(record_ids, dtype=str).reshape(-1).tolist()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
