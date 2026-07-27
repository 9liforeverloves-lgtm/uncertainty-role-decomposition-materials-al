from __future__ import annotations

import numpy as np

from transportability_v6.diagnostics import nll_summary, nll_vectors


META = {
    "task": "synthetic",
    "split": "iid",
    "model": "test",
    "seed": 1,
    "strategy": "RAW",
    "round": 0,
    "environment": "synthetic__iid__test",
}


def test_nll_matches_direct_formula_and_is_finite_near_floor() -> None:
    y = np.array([0.0, 1.0, 100.0])
    mu = np.array([0.0, 0.0, 0.0])
    sigma = np.array([0.0, 1.0, 1e-30])
    frame = nll_vectors(
        y=y,
        mu=mu,
        sigma_raw=sigma,
        sigma_scaled=sigma,
        candidate_id=np.array(["a", "b", "c"]),
        metadata=META,
        floor=1e-8,
    )
    effective = np.maximum(sigma, 1e-8)
    expected = 0.5 * np.log(2 * np.pi * effective**2) + 0.5 * ((y - mu) / effective) ** 2
    np.testing.assert_allclose(frame["individual_nll"], expected)
    assert np.isfinite(frame["individual_nll"]).all()
    summary = nll_summary(frame)
    assert summary["fraction_at_floor"] == 2 / 3


def test_perfect_predictions_and_constant_sigma() -> None:
    y = np.arange(5.0)
    frame = nll_vectors(
        y=y,
        mu=y,
        sigma_raw=np.ones(5),
        sigma_scaled=np.ones(5),
        candidate_id=np.arange(5),
        metadata=META,
    )
    assert np.all(frame["gaussian_squared_residual_term"] == 0)
