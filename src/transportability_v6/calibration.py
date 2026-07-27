"""Validated OOB-only uncertainty calibration objects.

All fitters receive residuals and uncertainties from already-labelled OOB
records only.  Production code must filter unavailable OOB predictions before
calling a fitter; NaN is never silently converted into usable uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
import warnings

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge


COVERAGE_LEVELS = (0.50, 0.80, 0.90, 0.95)


def validate_sigma(
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    name: str = "sigma",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate raw uncertainty and record strict floor activations.

    Zero and positive values below ``floor`` are valid but are not silently
    treated as raw values in any likelihood calculation.  The returned tuple
    is ``(raw, effective, floor_event_mask)``.
    """

    raw = np.asarray(sigma, dtype=float)
    if raw.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(floor) or floor <= 0:
        raise ValueError("floor must be finite and positive")
    if not np.isfinite(raw).all():
        raise ValueError(f"{name} must be finite")
    if np.any(raw < 0):
        raise ValueError(f"{name} must be non-negative")
    floor_event = raw < float(floor)
    return raw, np.maximum(raw, float(floor)), floor_event


def _vectors(
    residual: np.ndarray,
    sigma: np.ndarray,
    floor: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual = np.asarray(residual, dtype=float)
    if residual.ndim != 1:
        raise ValueError("residual must be one-dimensional")
    _, effective, events = validate_sigma(sigma, floor=floor, name="OOB sigma")
    if residual.shape != effective.shape:
        raise ValueError("OOB residual and sigma vectors must align")
    if not np.isfinite(residual).all():
        raise ValueError("OOB residual must be finite")
    if len(residual) < 3:
        raise ValueError("at least three finite OOB residual/sigma pairs are required")
    return residual, effective, events


def _positive_bounds(bounds: tuple[float, float], name: str = "bounds") -> tuple[float, float]:
    low, high = map(float, bounds)
    if not np.isfinite((low, high)).all() or low <= 0 or high < low:
        raise ValueError(f"{name} must be finite positive ordered values")
    return low, high


@dataclass(frozen=True)
class ScalarScale:
    method: str
    scale: float
    bounds: tuple[float, float]
    fit_count: int
    oob_floor_event_count: int = 0

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, effective, _ = validate_sigma(sigma, floor=floor)
        if not np.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale must be finite and positive")
        return effective * self.scale


def fit_scalar_nll(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds: tuple[float, float] = (0.05, 20.0),
) -> ScalarScale:
    residual, sigma, events = _vectors(residual, sigma, floor)
    bounds = _positive_bounds(bounds)
    unconstrained = float(np.sqrt(np.mean(np.square(residual / sigma))))
    scale = float(np.clip(unconstrained, *bounds))
    return ScalarScale("SCALAR_TEMPERATURE_NLL", scale, bounds, len(residual), int(events.sum()))


def fit_scalar_residual_ratio(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds: tuple[float, float] = (0.05, 20.0),
) -> ScalarScale:
    residual, sigma, events = _vectors(residual, sigma, floor)
    bounds = _positive_bounds(bounds)
    unconstrained = float(np.median(np.abs(residual) / sigma) / 0.6744897501960817)
    scale = float(np.clip(unconstrained, *bounds))
    return ScalarScale(
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO", scale, bounds, len(residual), int(events.sum())
    )


@dataclass(frozen=True)
class PowerScale:
    log_a: float
    b: float
    bounds_log_a: tuple[float, float]
    bounds_b: tuple[float, float]
    fit_count: int
    converged: bool
    oob_floor_event_count: int = 0

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, base, _ = validate_sigma(sigma, floor=floor)
        if not self.converged:
            return base
        values = np.exp(self.log_a + self.b * np.log(base))
        if not np.isfinite(values).all() or np.any(values <= 0):
            raise ValueError("power-scaled sigma must be finite and positive")
        return values


def fit_power_nll(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds_log_a: tuple[float, float] = (-3.0, 3.0),
    bounds_b: tuple[float, float] = (0.25, 2.0),
) -> PowerScale:
    residual, sigma, events = _vectors(residual, sigma, floor)
    low_b, high_b = map(float, bounds_b)
    if not np.isfinite((low_b, high_b)).all() or low_b <= 0 or high_b < low_b:
        raise ValueError("power exponent bounds must be finite, positive, and ordered")
    log_sigma = np.log(sigma)

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        log_s = theta[0] + theta[1] * log_sigma
        inv_var_residual2 = np.square(residual) * np.exp(-2 * log_s)
        value = float(np.mean(log_s + 0.5 * inv_var_residual2))
        common = 1.0 - inv_var_residual2
        return value, np.array([np.mean(common), np.mean(common * log_sigma)])

    try:
        fit = minimize(
            objective,
            x0=np.array([0.0, 1.0]),
            jac=True,
            bounds=(bounds_log_a, bounds_b),
            method="L-BFGS-B",
        )
        if not bool(fit.success and np.isfinite(fit.fun) and np.isfinite(fit.x).all()):
            raise RuntimeError("power optimizer did not converge")
        theta = np.asarray(fit.x, float)
        converged = True
    except Exception:
        theta = np.array([0.0, 1.0])
        converged = False
    return PowerScale(
        float(theta[0]),
        float(theta[1]),
        tuple(map(float, bounds_log_a)),
        (low_b, high_b),
        len(residual),
        converged,
        int(events.sum()),
    )


class IsotonicAbsResidualScale:
    method = "ISOTONIC_ABS_RESIDUAL"

    def __init__(self, model: IsotonicRegression, fit_count: int, oob_floor_event_count: int = 0):
        self.model = model
        self.fit_count = int(fit_count)
        self.oob_floor_event_count = int(oob_floor_event_count)

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, sigma, _ = validate_sigma(sigma, floor=floor)
        expected_abs_residual = np.maximum(self.model.predict(sigma), floor)
        result = expected_abs_residual * sqrt(pi / 2.0)
        if not np.isfinite(result).all() or np.any(result <= 0):
            raise ValueError("isotonic-scaled sigma must be finite and positive")
        return result


def fit_isotonic_abs_residual(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
) -> IsotonicAbsResidualScale:
    residual, sigma, events = _vectors(residual, sigma, floor)
    model = IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=floor)
    model.fit(sigma, np.abs(residual))
    return IsotonicAbsResidualScale(model, len(residual), int(events.sum()))


@dataclass(frozen=True)
class ConformalIntervalOnly:
    """Coverage-specific split-conformal intervals, not a universal sigma."""

    method: str
    nominal_coverage: float
    alpha: float
    residual_ratio_quantile: float
    fit_count: int
    oob_floor_event_count: int = 0

    def half_width(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, effective, _ = validate_sigma(sigma, floor=floor)
        return effective * self.residual_ratio_quantile

    def interval(
        self,
        mu: np.ndarray,
        sigma: np.ndarray,
        floor: float = 1e-8,
    ) -> tuple[np.ndarray, np.ndarray]:
        mean = np.asarray(mu, dtype=float)
        if mean.ndim != 1 or not np.isfinite(mean).all():
            raise ValueError("mean must be a finite one-dimensional vector")
        width = self.half_width(sigma, floor)
        if mean.shape != width.shape:
            raise ValueError("mean and sigma must align")
        return mean - width, mean + width

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        """Compatibility alias returning interval half-width, never a sigma."""

        return self.half_width(sigma, floor)


def _coverage(coverage: float) -> float:
    coverage = float(coverage)
    if not any(np.isclose(coverage, level, rtol=0.0, atol=1e-12) for level in COVERAGE_LEVELS):
        raise ValueError(f"nominal coverage must be one of {COVERAGE_LEVELS}")
    return coverage


def fit_conformal_interval_only(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    nominal_coverage: float = 0.90,
    floor: float = 1e-8,
) -> ConformalIntervalOnly:
    residual, sigma, events = _vectors(residual, sigma, floor)
    coverage = _coverage(nominal_coverage)
    ratios = np.abs(residual) / sigma
    n = len(ratios)
    # The finite-sample split-conformal order statistic is k=ceil((n+1)c),
    # capped at n.  Passing k/n to NumPy's ``higher`` interpolation would
    # select k+1 for most interior values, so select the order statistic
    # directly instead.
    order_index = min(n, int(np.ceil((n + 1) * coverage))) - 1
    multiplier = float(np.partition(ratios, order_index)[order_index])
    if not np.isfinite(multiplier) or multiplier < 0:
        raise ValueError("conformal residual-ratio quantile is invalid")
    return ConformalIntervalOnly(
        "CONFORMAL_INTERVAL_ONLY",
        coverage,
        1.0 - coverage,
        multiplier,
        n,
        int(events.sum()),
    )


@dataclass(frozen=True)
class ConformalGaussianEquivalent:
    """A single prospectively named coverage-specific Gaussian-equivalent sigma."""

    method: str
    reference_coverage: float
    alpha: float
    residual_ratio_quantile: float
    gaussian_z: float
    fit_count: int
    oob_floor_event_count: int = 0

    def sigma_equivalent(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, effective, _ = validate_sigma(sigma, floor=floor)
        return effective * self.residual_ratio_quantile / self.gaussian_z

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        return self.sigma_equivalent(sigma, floor)


def fit_conformal_gaussian_equivalent(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    reference_coverage: float = 0.90,
    floor: float = 1e-8,
) -> ConformalGaussianEquivalent:
    interval = fit_conformal_interval_only(
        residual, sigma, nominal_coverage=reference_coverage, floor=floor
    )
    z = float(norm.ppf((1.0 + interval.nominal_coverage) / 2.0))
    if not np.isfinite(z) or z <= 0:
        raise ValueError("Gaussian reference quantile must be finite and positive")
    return ConformalGaussianEquivalent(
        "CONFORMAL_GAUSSIAN_EQUIVALENT",
        interval.nominal_coverage,
        interval.alpha,
        interval.residual_ratio_quantile,
        z,
        interval.fit_count,
        interval.oob_floor_event_count,
    )


def fit_conformal_global(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    nominal_coverage: float = 0.90,
    floor: float = 1e-8,
) -> ConformalIntervalOnly:
    """Deprecated name retained only for old smoke callers.

    Its return value is an interval object.  In particular, it no longer
    represents ``q * sigma`` as a Gaussian standard deviation.
    """

    warnings.warn(
        "fit_conformal_global is deprecated; use fit_conformal_interval_only",
        DeprecationWarning,
        stacklevel=2,
    )
    return fit_conformal_interval_only(
        residual, sigma, nominal_coverage=nominal_coverage, floor=floor
    )


@dataclass(frozen=True)
class IdentityScale:
    method: str = "IDENTITY_CONTROL"

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        _, effective, _ = validate_sigma(sigma, floor=floor)
        return effective


@dataclass(frozen=True)
class EquivalentDofFallback:
    method: str
    fallback_reason: str
    nominal_parameter_count: int
    fit_count: int
    fitted_parameter_count: int = 0
    effective_degrees_of_freedom: float = 0.0
    used_fallback: bool = True

    def transform(
        self,
        sigma: np.ndarray,
        features: np.ndarray | None = None,
        floor: float = 1e-8,
        bounds: tuple[float, float] = (0.25, 4.0),
    ) -> np.ndarray:
        del features, bounds
        _, effective, _ = validate_sigma(sigma, floor=floor)
        return effective


class SelectedCsEquivalentDofControl:
    """Two-parameter control: intercept plus standardized log raw sigma."""

    method = "SELECTED_CS_EQUIVALENT_DOF_CONTROL"
    nominal_parameter_count = 2
    fitted_parameter_count = 2
    used_fallback = False

    def __init__(self, model: Ridge, center: float, spread: float, fit_count: int, effective_degrees_of_freedom: float):
        self.model = model
        self.center = float(center)
        self.spread = float(spread)
        self.fit_count = int(fit_count)
        self.effective_degrees_of_freedom = float(effective_degrees_of_freedom)

    def transform(
        self,
        sigma: np.ndarray,
        floor: float = 1e-8,
        bounds: tuple[float, float] = (0.25, 4.0),
    ) -> np.ndarray:
        _, sigma, _ = validate_sigma(sigma, floor=floor)
        low, high = _positive_bounds(bounds, "scale bounds")
        z = ((np.log(sigma) - self.center) / self.spread).reshape(-1, 1)
        log_scale = self.model.predict(z)
        return sigma * np.exp(np.clip(log_scale, np.log(low), np.log(high)))


class HistoricalCsEquivalentDofControl:
    """Seven-parameter control: intercept plus six standardized OOB features."""

    method = "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL"
    nominal_parameter_count = 7
    fitted_parameter_count = 7
    used_fallback = False

    def __init__(self, model: Ridge, center: np.ndarray, spread: np.ndarray, fit_count: int, effective_degrees_of_freedom: float):
        self.model = model
        self.center = np.asarray(center, dtype=float)
        self.spread = np.asarray(spread, dtype=float)
        self.fit_count = int(fit_count)
        self.effective_degrees_of_freedom = float(effective_degrees_of_freedom)

    def transform(
        self,
        sigma: np.ndarray,
        features: np.ndarray,
        floor: float = 1e-8,
        bounds: tuple[float, float] = (0.25, 4.0),
    ) -> np.ndarray:
        _, sigma, _ = validate_sigma(sigma, floor=floor)
        features = np.asarray(features, dtype=float)
        if features.shape != (len(sigma), 6):
            raise ValueError("historical equivalent-DoF control requires six candidate features")
        if not np.isfinite(features).all():
            raise ValueError("candidate features must be finite")
        low, high = _positive_bounds(bounds, "scale bounds")
        z = (features - self.center) / self.spread
        log_scale = self.model.predict(z)
        return sigma * np.exp(np.clip(log_scale, np.log(low), np.log(high)))


def _ridge_effective_df(design: np.ndarray, alpha: float) -> float:
    if not np.isfinite(alpha) or alpha < 0:
        raise ValueError("ridge alpha must be finite and non-negative")
    singular_values = np.linalg.svd(np.asarray(design, float), compute_uv=False)
    return float(1.0 + np.sum(singular_values**2 / (singular_values**2 + alpha)))


def _oob_arrays(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    floor: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual = np.asarray(residual_oob, dtype=float)
    if residual.ndim != 1:
        raise ValueError("OOB residual and sigma vectors must align")
    residual, sigma, events = _vectors(residual, sigma_oob, floor)
    return residual, sigma, events


def fit_selected_cs_equivalent_dof(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    *,
    floor: float = 1e-8,
    alpha: float = 1.0,
    min_samples: int = 20,
) -> SelectedCsEquivalentDofControl | EquivalentDofFallback:
    residual, sigma, _ = _oob_arrays(residual_oob, sigma_oob, floor)
    if min_samples < 3:
        raise ValueError("minimum OOB sample count must be at least three")
    if len(residual) < min_samples:
        return EquivalentDofFallback(
            "SELECTED_CS_EQUIVALENT_DOF_CONTROL", "insufficient_oob_samples", 2, len(residual)
        )
    log_sigma = np.log(sigma)
    center = float(log_sigma.mean())
    spread = float(log_sigma.std())
    if spread < 1e-12:
        spread = 1.0
    z = ((log_sigma - center) / spread).reshape(-1, 1)
    target = np.log(np.maximum(np.abs(residual) / sigma, floor))
    model = Ridge(alpha=float(alpha), fit_intercept=True)
    model.fit(z, target)
    return SelectedCsEquivalentDofControl(model, center, spread, len(residual), _ridge_effective_df(z, float(alpha)))


def fit_historical_cs_equivalent_dof(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    features_oob: np.ndarray,
    *,
    floor: float = 1e-8,
    alpha: float = 1.0,
    min_samples: int = 20,
) -> HistoricalCsEquivalentDofControl | EquivalentDofFallback:
    residual, sigma, _ = _oob_arrays(residual_oob, sigma_oob, floor)
    features = np.asarray(features_oob, dtype=float)
    if features.shape != (len(residual), 6):
        raise ValueError("six aligned OOB features are required")
    if not np.isfinite(features).all():
        raise ValueError("OOB features must be finite")
    if min_samples < 3:
        raise ValueError("minimum OOB sample count must be at least three")
    if len(residual) < min_samples:
        return EquivalentDofFallback(
            "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL", "insufficient_oob_samples", 7, len(residual)
        )
    center = features.mean(axis=0)
    spread = features.std(axis=0)
    spread[spread < 1e-12] = 1.0
    z = (features - center) / spread
    target = np.log(np.maximum(np.abs(residual) / sigma, floor))
    model = Ridge(alpha=float(alpha), fit_intercept=True)
    model.fit(z, target)
    return HistoricalCsEquivalentDofControl(model, center, spread, len(residual), _ridge_effective_df(z, float(alpha)))
