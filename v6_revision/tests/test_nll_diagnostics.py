from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transportability_v6.diagnostics import (
    atomic_parquet,
    nll_contrast_stability,
    nll_summary,
    nll_vectors,
    recover_atomic_parquet,
)


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


def test_nll_overflow_is_clipped_to_finite() -> None:
    frame = nll_vectors(
        y=np.array([1e308]),
        mu=np.array([-1e308]),
        sigma_raw=np.array([1e-300]),
        sigma_scaled=np.array([1e-300]),
        candidate_id=np.array(["x"]),
        metadata=META,
    )
    assert np.isfinite(frame["individual_nll"]).all()


@pytest.mark.parametrize(
    "field,bad",
    [
        ("y", np.nan),
        ("mu", np.inf),
        ("sigma_raw", np.nan),
        ("sigma_scaled", np.inf),
    ],
)
def test_nll_rejects_nan_and_inf(field, bad) -> None:
    values = {
        "y": np.array([1.0]),
        "mu": np.array([1.0]),
        "sigma_raw": np.array([1.0]),
        "sigma_scaled": np.array([1.0]),
    }
    values[field][0] = bad
    with pytest.raises(ValueError, match="finite"):
        nll_vectors(
            **values,
            candidate_id=np.array(["x"]),
            metadata=META,
        )


def test_raw_and_scaled_floor_flags_are_separate() -> None:
    frame = nll_vectors(
        y=np.array([0.0, 0.0]),
        mu=np.array([0.0, 0.0]),
        sigma_raw=np.array([1e-12, 1.0]),
        sigma_scaled=np.array([1.0, 1e-12]),
        candidate_id=np.array(["a", "b"]),
        metadata=META,
    )
    assert frame["uncertainty_floor_before"].tolist() == [True, False]
    assert frame["uncertainty_floor_after"].tolist() == [False, True]


def test_duplicate_nll_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        nll_vectors(
            y=np.array([0.0, 1.0]),
            mu=np.array([0.0, 1.0]),
            sigma_raw=np.ones(2),
            sigma_scaled=np.ones(2),
            candidate_id=np.array(["same", "same"]),
            metadata=META,
        )


def _contrast_frame(scale_by_seed=None, flip_environment=None):
    rows = []
    scale_by_seed = scale_by_seed or {}
    for environment in ("a", "b", "c"):
        for seed in range(10):
            value = scale_by_seed.get(seed, 1.0)
            if environment == flip_environment:
                value *= -5
            rows.append(
                {
                    "environment": environment,
                    "seed": seed,
                    "candidate_id": f"{environment}-{seed}",
                    "round": 0,
                    "individual_nll": value,
                }
            )
    return pd.DataFrame(rows)


def test_observation_seed_and_direction_stability_gates() -> None:
    baseline = _contrast_frame()
    baseline["individual_nll"] = 0.0
    stable = nll_contrast_stability(baseline, _contrast_frame())
    assert stable["passes_seed_dominance_gate"]
    assert stable["passes_trimmed_mean_direction_gate"]
    assert stable["passes_leave_one_environment_out_gate"]
    dominant = nll_contrast_stability(
        baseline, _contrast_frame(scale_by_seed={0: 1000.0})
    )
    assert not dominant["passes_seed_dominance_gate"]
    loo_unstable = nll_contrast_stability(
        baseline, _contrast_frame(flip_environment="c")
    )
    assert not loo_unstable["passes_leave_one_environment_out_gate"]


def test_observation_dominance_and_trimmed_direction_failure() -> None:
    frame = nll_vectors(
        y=np.array([0.0, 0.0, 0.0, 1000.0]),
        mu=np.zeros(4),
        sigma_raw=np.ones(4),
        sigma_scaled=np.ones(4),
        candidate_id=np.array(["a", "b", "c", "d"]),
        metadata=META,
    )
    assert nll_summary(frame)["largest_observation_contribution_share"] > 0.9
    baseline = _contrast_frame()
    baseline["individual_nll"] = 0.0
    test = _contrast_frame()
    test["individual_nll"] = -1.0
    # One extreme positive row reverses the ordinary mean but is removed by 1% trimming.
    repeated = pd.concat([test] * 10, ignore_index=True)
    baseline_repeated = pd.concat([baseline] * 10, ignore_index=True)
    repeated["candidate_id"] = [f"row-{index}" for index in range(len(repeated))]
    baseline_repeated["candidate_id"] = repeated["candidate_id"]
    repeated.loc[0, "individual_nll"] = 1000.0
    gate = nll_contrast_stability(baseline_repeated, repeated)
    assert not gate["passes_trimmed_mean_direction_gate"]


def test_parquet_round_trip_and_interrupted_write_recovery(tmp_path) -> None:
    frame = nll_vectors(
        y=np.array([0.0, 1.0]),
        mu=np.array([0.0, 0.0]),
        sigma_raw=np.ones(2),
        sigma_scaled=np.ones(2),
        candidate_id=np.array(["a", "b"]),
        metadata=META,
    )
    path = tmp_path / "vectors.parquet"
    atomic_parquet(frame, path)
    pd.testing.assert_frame_equal(pd.read_parquet(path), frame)
    temporary = path.with_suffix(".parquet.tmp")
    frame.to_parquet(temporary, index=False)
    assert recover_atomic_parquet(path) == "committed_file_kept"
    assert not temporary.exists()
    path.unlink()
    frame.to_parquet(temporary, index=False)
    assert recover_atomic_parquet(path) == "validated_temporary_promoted"
    pd.testing.assert_frame_equal(pd.read_parquet(path), frame)
