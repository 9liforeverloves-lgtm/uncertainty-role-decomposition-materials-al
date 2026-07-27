from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from transportability_v6.calibration import (
    COVERAGE_LEVELS,
    fit_conformal_gaussian_equivalent,
    fit_conformal_interval_only,
)


def test_interval_only_is_coverage_specific_and_uses_finite_sample_quantiles() -> None:
    residual = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sigma = np.ones_like(residual)
    expected = {0.50: 3.0, 0.80: 5.0, 0.90: 5.0, 0.95: 5.0}
    for coverage in COVERAGE_LEVELS:
        fit = fit_conformal_interval_only(residual, sigma, nominal_coverage=coverage)
        assert fit.method == "CONFORMAL_INTERVAL_ONLY"
        assert fit.residual_ratio_quantile == expected[coverage]
        np.testing.assert_allclose(fit.half_width(np.array([2.0])), [2.0 * expected[coverage]])
        lower, upper = fit.interval(np.array([10.0]), np.array([2.0]))
        np.testing.assert_allclose(lower, [10.0 - 2.0 * expected[coverage]])
        np.testing.assert_allclose(upper, [10.0 + 2.0 * expected[coverage]])


def test_gaussian_equivalent_is_not_the_conformal_half_width_or_raw_multiplier() -> None:
    residual = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sigma = np.ones_like(residual)
    interval = fit_conformal_interval_only(residual, sigma, nominal_coverage=0.90)
    equivalent = fit_conformal_gaussian_equivalent(residual, sigma, reference_coverage=0.90)
    raw_sigma = np.array([2.0])
    half_width = interval.half_width(raw_sigma)
    sigma_equiv = equivalent.sigma_equivalent(raw_sigma)
    z = norm.ppf(0.95)
    np.testing.assert_allclose(half_width, sigma_equiv * z)
    # The old incorrect implementation used q*sigma as a universal Gaussian
    # sigma, whose 90% Gaussian interval would be q*sigma*z, not q*sigma.
    incorrect_gaussian_half_width = interval.residual_ratio_quantile * raw_sigma * z
    assert not np.allclose(half_width, sigma_equiv)
    assert not np.allclose(half_width, incorrect_gaussian_half_width)
    assert equivalent.reference_coverage == pytest.approx(0.90)


@pytest.mark.parametrize("coverage", [0.49, 0.75, 0.99])
def test_conformal_rejects_unregistered_coverages(coverage: float) -> None:
    with pytest.raises(ValueError, match="nominal coverage"):
        fit_conformal_interval_only(np.ones(4), np.ones(4), nominal_coverage=coverage)
