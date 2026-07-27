from __future__ import annotations

import numpy as np

from transportability_v6.calibration import (
    IdentityScale,
    fit_conformal_global,
    fit_equivalent_dof_ridge,
    fit_isotonic_abs_residual,
    fit_power_nll,
    fit_scalar_nll,
    fit_scalar_residual_ratio,
)


def test_scalar_nll_recovers_known_multiplier() -> None:
    sigma = np.ones(1000)
    z = np.tile(np.array([-2.0, -1.0, 1.0, 2.0]), 250)
    residual = 2.0 * z / np.sqrt(np.mean(z**2))
    fit = fit_scalar_nll(residual, sigma)
    assert abs(fit.scale - 2.0) < 1e-12


def test_all_simple_scalers_are_positive_and_finite() -> None:
    sigma = np.linspace(0.1, 2.0, 200)
    residual = 1.7 * sigma * np.sin(np.arange(200))
    fits = (
        fit_scalar_nll(residual, sigma),
        fit_scalar_residual_ratio(residual, sigma),
        fit_power_nll(residual, sigma),
        fit_isotonic_abs_residual(residual, sigma),
        fit_conformal_global(residual, sigma),
        IdentityScale(),
    )
    for fit in fits:
        transformed = fit.transform(sigma)
        assert np.isfinite(transformed).all()
        assert np.all(transformed > 0)


def test_isotonic_endpoint_behavior_is_clipped() -> None:
    sigma = np.array([1.0, 2.0, 3.0, 4.0])
    residual = np.array([1.0, 2.0, 3.0, 4.0])
    fit = fit_isotonic_abs_residual(residual, sigma)
    transformed = fit.transform(np.array([0.01, 10.0]))
    assert np.isfinite(transformed).all()
    assert transformed[0] <= transformed[1]


def test_equivalent_dof_control_has_seven_parameters() -> None:
    rng = np.random.default_rng(3)
    sigma = np.linspace(0.2, 2.0, 100)
    features = rng.normal(size=(100, 6))
    residual = sigma * np.exp(0.2 * features[:, 0])
    fit = fit_equivalent_dof_ridge(residual, sigma, features)
    assert fit.free_parameter_count == 7
    transformed = fit.transform(sigma, features)
    assert np.isfinite(transformed).all()
    assert np.all(transformed > 0)
