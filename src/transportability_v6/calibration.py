from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, pi

import numpy as np
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge


def _vectors(residual: np.ndarray, sigma: np.ndarray, floor: float) -> tuple[np.ndarray, np.ndarray]:
    residual = np.asarray(residual, dtype=float)
    sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
    valid = np.isfinite(residual) & np.isfinite(sigma)
    if floor <= 0 or valid.sum() < 3:
        raise ValueError("at least three finite OOB residual/sigma pairs are required")
    return residual[valid], sigma[valid]


@dataclass(frozen=True)
class ScalarScale:
    method: str
    scale: float
    bounds: tuple[float, float]
    fit_count: int

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        return np.maximum(np.asarray(sigma, dtype=float), floor) * self.scale


def fit_scalar_nll(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds: tuple[float, float] = (0.05, 20.0),
) -> ScalarScale:
    residual, sigma = _vectors(residual, sigma, floor)
    unconstrained = float(np.sqrt(np.mean(np.square(residual / sigma))))
    scale = float(np.clip(unconstrained, *bounds))
    return ScalarScale("SCALAR_TEMPERATURE_NLL", scale, bounds, len(residual))


def fit_scalar_residual_ratio(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds: tuple[float, float] = (0.05, 20.0),
) -> ScalarScale:
    residual, sigma = _vectors(residual, sigma, floor)
    # Median absolute Gaussian residual is 0.67448975 sigma.
    unconstrained = float(np.median(np.abs(residual) / sigma) / 0.6744897501960817)
    scale = float(np.clip(unconstrained, *bounds))
    return ScalarScale("SCALAR_TEMPERATURE_RESIDUAL_RATIO", scale, bounds, len(residual))


@dataclass(frozen=True)
class PowerScale:
    log_a: float
    b: float
    bounds_log_a: tuple[float, float]
    bounds_b: tuple[float, float]
    fit_count: int
    converged: bool

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        base = np.maximum(np.asarray(sigma, dtype=float), floor)
        if not self.converged and self.log_a == 0.0 and self.b == 1.0:
            return base
        return np.exp(self.log_a + self.b * np.log(base))


def fit_power_nll(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
    bounds_log_a: tuple[float, float] = (-3.0, 3.0),
    bounds_b: tuple[float, float] = (0.25, 2.0),
) -> PowerScale:
    residual, sigma = _vectors(residual, sigma, floor)
    log_sigma = np.log(sigma)

    def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
        log_s = theta[0] + theta[1] * log_sigma
        inv_var_residual2 = np.square(residual) * np.exp(-2 * log_s)
        value = float(np.mean(log_s + 0.5 * inv_var_residual2))
        common = 1.0 - inv_var_residual2
        gradient = np.array([np.mean(common), np.mean(common * log_sigma)])
        return value, gradient

    try:
        fit = minimize(
            objective,
            x0=np.array([0.0, 1.0]),
            jac=True,
            bounds=(bounds_log_a, bounds_b),
            method="L-BFGS-B",
        )
        theta = fit.x if np.isfinite(fit.x).all() else np.array([0.0, 1.0])
        converged = bool(fit.success and np.isfinite(fit.fun))
    except Exception:
        theta = np.array([0.0, 1.0])
        converged = False
    return PowerScale(
        float(theta[0]),
        float(theta[1]),
        bounds_log_a,
        bounds_b,
        len(residual),
        converged,
    )


class IsotonicAbsResidualScale:
    method = "ISOTONIC_ABS_RESIDUAL"

    def __init__(self, model: IsotonicRegression, fit_count: int):
        self.model = model
        self.fit_count = fit_count

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
        expected_abs_residual = np.maximum(self.model.predict(sigma), floor)
        return expected_abs_residual * sqrt(pi / 2.0)


def fit_isotonic_abs_residual(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float = 1e-8,
) -> IsotonicAbsResidualScale:
    residual, sigma = _vectors(residual, sigma, floor)
    model = IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=floor)
    model.fit(sigma, np.abs(residual))
    return IsotonicAbsResidualScale(model, len(residual))


@dataclass(frozen=True)
class ConformalGlobal:
    method: str
    multiplier: float
    nominal_coverage: float
    fit_count: int

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        return np.maximum(np.asarray(sigma, dtype=float), floor) * self.multiplier


def fit_conformal_global(
    residual: np.ndarray,
    sigma: np.ndarray,
    *,
    nominal_coverage: float = 0.90,
    floor: float = 1e-8,
) -> ConformalGlobal:
    residual, sigma = _vectors(residual, sigma, floor)
    if not 0 < nominal_coverage < 1:
        raise ValueError("nominal_coverage must lie in (0, 1)")
    ratios = np.abs(residual) / sigma
    n = len(ratios)
    quantile_level = min(1.0, np.ceil((n + 1) * nominal_coverage) / n)
    multiplier = float(np.quantile(ratios, quantile_level, method="higher"))
    return ConformalGlobal("CONFORMAL_GLOBAL", multiplier, nominal_coverage, n)


@dataclass(frozen=True)
class IdentityScale:
    method: str = "IDENTITY_CONTROL"

    def transform(self, sigma: np.ndarray, floor: float = 1e-8) -> np.ndarray:
        return np.maximum(np.asarray(sigma, dtype=float), floor)


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
        return np.maximum(np.asarray(sigma, dtype=float), floor)


class SelectedCsEquivalentDofControl:
    """Nominal 2-parameter control: intercept plus standardized log raw sigma."""

    method = "SELECTED_CS_EQUIVALENT_DOF_CONTROL"
    nominal_parameter_count = 2
    fitted_parameter_count = 2
    used_fallback = False

    def __init__(
        self,
        model: Ridge,
        center: float,
        spread: float,
        fit_count: int,
        effective_degrees_of_freedom: float,
    ):
        self.model = model
        self.center = center
        self.spread = spread
        self.fit_count = fit_count
        self.effective_degrees_of_freedom = effective_degrees_of_freedom

    def transform(
        self,
        sigma: np.ndarray,
        floor: float = 1e-8,
        bounds: tuple[float, float] = (0.25, 4.0),
    ) -> np.ndarray:
        sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
        z = ((np.log(sigma) - self.center) / self.spread).reshape(-1, 1)
        log_scale = self.model.predict(z)
        scale = np.exp(np.clip(log_scale, np.log(bounds[0]), np.log(bounds[1])))
        return sigma * scale


class HistoricalCsEquivalentDofControl:
    """Nominal 7-parameter control: intercept plus six standardized OOB features."""

    method = "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL"
    nominal_parameter_count = 7
    fitted_parameter_count = 7
    used_fallback = False

    def __init__(
        self,
        model: Ridge,
        center: np.ndarray,
        spread: np.ndarray,
        fit_count: int,
        effective_degrees_of_freedom: float,
    ):
        self.model = model
        self.center = center
        self.spread = spread
        self.fit_count = fit_count
        self.effective_degrees_of_freedom = effective_degrees_of_freedom

    def transform(
        self,
        sigma: np.ndarray,
        features: np.ndarray,
        floor: float = 1e-8,
        bounds: tuple[float, float] = (0.25, 4.0),
    ) -> np.ndarray:
        sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
        features = np.asarray(features, dtype=float)
        if features.shape != (len(sigma), 6):
            raise ValueError("historical equivalent-DoF control requires six candidate features")
        z = (features - self.center) / self.spread
        log_scale = self.model.predict(z)
        scale = np.exp(np.clip(log_scale, np.log(bounds[0]), np.log(bounds[1])))
        return sigma * scale


def _ridge_effective_df(design: np.ndarray, alpha: float) -> float:
    singular_values = np.linalg.svd(np.asarray(design, float), compute_uv=False)
    return float(1.0 + np.sum(singular_values**2 / (singular_values**2 + alpha)))


def _oob_arrays(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    floor: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual = np.asarray(residual_oob, dtype=float)
    sigma = np.asarray(sigma_oob, dtype=float)
    if residual.shape != sigma.shape or residual.ndim != 1:
        raise ValueError("OOB residual and sigma vectors must align")
    valid = np.isfinite(residual) & np.isfinite(sigma) & (sigma >= 0)
    return residual[valid], np.maximum(sigma[valid], floor), valid


def fit_selected_cs_equivalent_dof(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    *,
    floor: float = 1e-8,
    alpha: float = 1.0,
    min_samples: int = 20,
) -> SelectedCsEquivalentDofControl | EquivalentDofFallback:
    residual, sigma, _ = _oob_arrays(residual_oob, sigma_oob, floor)
    if len(residual) < min_samples:
        return EquivalentDofFallback(
            "SELECTED_CS_EQUIVALENT_DOF_CONTROL",
            "insufficient_oob_samples",
            2,
            len(residual),
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
    return SelectedCsEquivalentDofControl(
        model,
        center,
        spread,
        len(residual),
        _ridge_effective_df(z, float(alpha)),
    )


def fit_historical_cs_equivalent_dof(
    residual_oob: np.ndarray,
    sigma_oob: np.ndarray,
    features_oob: np.ndarray,
    *,
    floor: float = 1e-8,
    alpha: float = 1.0,
    min_samples: int = 20,
) -> HistoricalCsEquivalentDofControl | EquivalentDofFallback:
    residual, sigma, valid = _oob_arrays(residual_oob, sigma_oob, floor)
    features = np.asarray(features_oob, dtype=float)
    if features.shape != (len(valid), 6):
        raise ValueError("six aligned OOB features are required")
    features = features[valid]
    finite = np.isfinite(features).all(axis=1)
    residual, sigma, features = residual[finite], sigma[finite], features[finite]
    if len(residual) < min_samples:
        return EquivalentDofFallback(
            "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL",
            "insufficient_oob_samples",
            7,
            len(residual),
        )
    center = features.mean(axis=0)
    spread = features.std(axis=0)
    spread[spread < 1e-12] = 1.0
    z = (features - center) / spread
    target = np.log(np.maximum(np.abs(residual) / sigma, floor))
    model = Ridge(alpha=float(alpha), fit_intercept=True)
    model.fit(z, target)
    return HistoricalCsEquivalentDofControl(
        model,
        center,
        spread,
        len(residual),
        _ridge_effective_df(z, float(alpha)),
    )
