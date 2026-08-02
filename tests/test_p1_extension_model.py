from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from p1_extension.models import (
    Q_HIGH,
    Q_LOW,
    SHARED_PARAMETERS,
    QuantileGradientBoostingSurrogate,
    crossfit_predictive_spread,
    crossfit_predictive_spread_aligned,
    fit_residual_ratio,
    fit_residual_ratio_aligned,
)


def test_all_three_regressors_share_frozen_hyperparameters() -> None:
    first = QuantileGradientBoostingSurrogate(random_state=17)
    second = QuantileGradientBoostingSurrogate(random_state=17)
    shared = ("n_estimators", "learning_rate", "max_depth", "min_samples_leaf", "subsample", "random_state")
    for name in shared:
        values = [getattr(model, name) for model in (first.central, first.lower, first.upper, second.central, second.lower, second.upper)]
        assert len(set(values)) == 1


ROOT = Path(__file__).resolve().parents[1]


def toy_data(seed: int = 11, n: int = 54) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 5))
    y = X[:, 0] - 0.7 * X[:, 1] ** 2 + rng.normal(scale=0.2 + 0.1 * np.abs(X[:, 2]), size=n)
    return X, y


def test_contract_matches_implementation() -> None:
    contract = json.loads((ROOT / "p1_extension/implementation_contract.json").read_text(encoding="utf-8"))
    assert contract["quantile_levels"] == [Q_LOW, Q_HIGH]
    assert contract["shared_parameters"] == SHARED_PARAMETERS
    assert contract["sentinel_seeds"] == list(range(8000, 8005))
    assert contract["confirmation_seeds_sealed"] == [8200, 8239]


def test_model_is_deterministic_positive_and_finite() -> None:
    X, y = toy_data()
    first = QuantileGradientBoostingSurrogate(random_state=17).fit(X, y).predict(X)
    second = QuantileGradientBoostingSurrogate(random_state=17).fit(X, y).predict(X)
    np.testing.assert_array_equal(first.mean, second.mean)
    np.testing.assert_array_equal(first.sigma, second.sigma)
    assert first.mean.shape == first.sigma.shape == y.shape
    assert np.isfinite(first.mean).all() and np.isfinite(first.sigma).all()
    assert np.all(first.sigma > 0)


def test_crossfit_is_complete_and_labelled_only_ratio_is_valid() -> None:
    X, y = toy_data(n=40)
    pred = crossfit_predictive_spread(X, y, random_state=23, n_splits=5)
    assert pred.mean.shape == y.shape
    assert np.isfinite(pred.mean).all() and np.isfinite(pred.sigma).all()
    ratio = fit_residual_ratio(y, pred)
    assert np.isfinite(ratio) and ratio >= 0


def test_crossfit_residual_ratio_requires_exact_record_id_alignment() -> None:
    X, y = toy_data(n=40)
    ids = np.asarray([f"id-{index}" for index in range(len(y))])
    aligned = crossfit_predictive_spread_aligned(X, y, ids, random_state=23)
    lookup = dict(zip(ids, y))
    assert np.isfinite(fit_residual_ratio_aligned(ids[::-1], lookup, aligned))
    with np.testing.assert_raises_regex(ValueError, "mismatch"):
        fit_residual_ratio_aligned(np.asarray([*ids[:-1], "unknown"]), lookup, aligned)


def test_invalid_inputs_fail_closed() -> None:
    X, y = toy_data(n=10)
    X[0, 0] = np.nan
    try:
        QuantileGradientBoostingSurrogate(random_state=1).fit(X, y)
    except ValueError as error:
        assert "finite" in str(error)
    else:
        raise AssertionError("non-finite model input was accepted")
