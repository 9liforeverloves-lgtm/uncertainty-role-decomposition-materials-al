from __future__ import annotations

import numpy as np
import pytest

from p1_extension.metrics import (
    conditional_coverage,
    discovery_summary,
    empirical_coverage,
    gaussian_crps,
    gaussian_nll,
    interval_score,
    mean_interval_width,
    qq_points,
    standardized_residual_summary,
    top_fraction_recall,
    uncertainty_error_spearman,
)


def test_calibration_metrics_are_finite_and_well_formed() -> None:
    y = np.array([-1.0, -0.2, 0.1, 1.2, 2.0])
    mean = np.array([-0.8, -0.1, 0.0, 0.9, 1.8])
    sigma = np.array([0.3, 0.2, 0.2, 0.4, 0.3])
    coverage = empirical_coverage(y, mean, sigma)
    assert set(coverage) == {0.5, 0.8, 0.9, 0.95}
    assert all(0 <= value <= 1 for value in coverage.values())
    for value in (mean_interval_width(sigma), interval_score(y, mean, sigma), gaussian_nll(y, mean, sigma), gaussian_crps(y, mean, sigma)):
        assert np.isfinite(value)
    summary = standardized_residual_summary(y, mean, sigma)
    assert set(summary) == {"mean", "std", "skewness", "median_abs", "q01", "q05", "q25", "q50", "q75", "q95", "q99"}
    theoretical, observed = qq_points(y, mean, sigma)
    assert len(theoretical) == len(observed) == len(y)
    assert -1 <= uncertainty_error_spearman(y, mean, sigma) <= 1
    assert len(conditional_coverage(y, mean, sigma, bins=2, by="uncertainty")) == 2
    assert len(conditional_coverage(y, mean, sigma, bins=2, by="predicted_mean")) == 2


def test_discovery_metrics_include_initial_state_and_stable_top_ties() -> None:
    y = np.array([1.0, 5.0, 5.0, 2.0])
    assert top_fraction_recall(y, np.array([2]), fraction=0.25) == 1.0
    budget = np.array([0.0, 0.5, 1.0])
    recall = np.array([0.0, 0.5, 1.0])
    best = np.array([1.0, 4.0, 5.0])
    random = np.array([0.0, 0.25, 0.5])
    result = discovery_summary(budget, recall, best, optimum=5.0, random_recall=random)
    assert result.recall_nauc == pytest.approx(0.5)
    assert result.simple_regret == 0
    assert result.time_to_first == 0.5
    assert result.time_to_half == 0.5
    assert np.isfinite(result.segment_auc_middle)


def test_unreached_time_metrics_are_censored_at_one() -> None:
    budget = np.array([0.0, 0.5, 1.0])
    result = discovery_summary(budget, np.zeros(3), np.ones(3), optimum=2.0, random_recall=np.array([0.0, 0.25, 0.5]))
    assert result.time_to_first == 1.0
    assert result.time_to_half == 1.0


def test_nonpositive_sigma_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        gaussian_nll(np.ones(2), np.ones(2), np.array([1.0, 0.0]))
