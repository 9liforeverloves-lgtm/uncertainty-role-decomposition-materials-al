from __future__ import annotations

import numpy as np
import pytest

import transportability_v6.calibration as calibration_module

from transportability_v6.calibration import (
    IdentityScale,
    fit_conformal_global,
    fit_historical_cs_equivalent_dof,
    fit_isotonic_abs_residual,
    fit_power_nll,
    fit_selected_cs_equivalent_dof,
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


def test_selected_and_historical_equivalent_dof_parameter_counts() -> None:
    rng = np.random.default_rng(3)
    sigma = np.linspace(0.2, 2.0, 100)
    features = rng.normal(size=(100, 6))
    residual = sigma * np.exp(0.2 * features[:, 0])
    selected = fit_selected_cs_equivalent_dof(residual, sigma)
    historical = fit_historical_cs_equivalent_dof(residual, sigma, features)
    assert selected.nominal_parameter_count == selected.fitted_parameter_count == 2
    assert historical.nominal_parameter_count == historical.fitted_parameter_count == 7
    assert 1.0 <= selected.effective_degrees_of_freedom <= 2.0
    assert 1.0 <= historical.effective_degrees_of_freedom <= 7.0
    assert np.all(np.isfinite(selected.transform(sigma)))
    assert np.all(np.isfinite(historical.transform(sigma, features)))
    assert np.all(selected.transform(sigma) > 0)
    assert np.all(historical.transform(sigma, features) > 0)


def test_equivalent_dof_fits_are_deterministic_and_oob_only() -> None:
    rng = np.random.default_rng(11)
    sigma_oob = np.linspace(0.1, 1.5, 80)
    residual_oob = rng.normal(size=80) * sigma_oob
    features_oob = rng.normal(size=(80, 6))
    first = fit_selected_cs_equivalent_dof(residual_oob, sigma_oob)
    second = fit_selected_cs_equivalent_dof(residual_oob, sigma_oob)
    np.testing.assert_array_equal(first.transform(sigma_oob), second.transform(sigma_oob))
    hist_first = fit_historical_cs_equivalent_dof(
        residual_oob, sigma_oob, features_oob
    )
    hist_second = fit_historical_cs_equivalent_dof(
        residual_oob, sigma_oob, features_oob
    )
    np.testing.assert_array_equal(
        hist_first.transform(sigma_oob, features_oob),
        hist_second.transform(sigma_oob, features_oob),
    )


def test_equivalent_dof_constant_sigma_and_insufficient_fallback() -> None:
    residual = np.linspace(-2, 2, 30)
    sigma = np.ones(30)
    features = np.ones((30, 6))
    selected = fit_selected_cs_equivalent_dof(residual, sigma)
    historical = fit_historical_cs_equivalent_dof(residual, sigma, features)
    assert np.isfinite(selected.transform(sigma)).all()
    assert np.isfinite(historical.transform(sigma, features)).all()
    selected_fallback = fit_selected_cs_equivalent_dof(residual[:5], sigma[:5])
    historical_fallback = fit_historical_cs_equivalent_dof(
        residual[:5], sigma[:5], features[:5]
    )
    assert selected_fallback.used_fallback
    assert historical_fallback.used_fallback
    np.testing.assert_array_equal(selected_fallback.transform(sigma[:5]), sigma[:5])
    np.testing.assert_array_equal(
        historical_fallback.transform(sigma[:5], features[:5]), sigma[:5]
    )


def test_constant_residuals_and_duplicate_sigma_isotonic() -> None:
    sigma = np.repeat(np.array([0.2, 0.5, 1.0, 2.0]), 10)
    residual = np.ones_like(sigma)
    fits = (
        fit_scalar_nll(residual, sigma),
        fit_scalar_residual_ratio(residual, sigma),
        fit_power_nll(residual, sigma),
        fit_isotonic_abs_residual(residual, sigma),
    )
    for fit in fits:
        transformed = fit.transform(sigma)
        assert np.isfinite(transformed).all()
        assert np.all(transformed > 0)


def test_power_optimizer_failure_uses_deterministic_identity_parameters(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic optimizer failure")

    monkeypatch.setattr(calibration_module, "minimize", fail)
    sigma = np.linspace(0.2, 2.0, 30)
    fit = fit_power_nll(np.ones(30), sigma)
    assert not fit.converged
    np.testing.assert_array_equal(fit.transform(sigma), sigma)


def test_transform_scale_bounds_limit_extrapolation() -> None:
    sigma = np.geomspace(1e-8, 1e8, 60)
    residual = np.linspace(-2.0, 2.0, 60)
    fit = fit_selected_cs_equivalent_dof(residual, sigma)
    transformed = fit.transform(np.array([1e-30, 1e30]))
    base = np.maximum(np.array([1e-30, 1e30]), 1e-8)
    ratio = transformed / base
    assert np.all(ratio >= 0.25)
    assert np.all(ratio <= 4.0)


def test_equivalent_dof_rejects_non_oob_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="aligned OOB"):
        fit_historical_cs_equivalent_dof(
            np.ones(30), np.ones(30), np.ones((29, 6))
        )
