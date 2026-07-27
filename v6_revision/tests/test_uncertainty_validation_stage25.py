from __future__ import annotations

import numpy as np
import pytest

from transportability_v6.calibration import fit_scalar_nll, validate_sigma
from transportability_v6.diagnostics import nll_stability_gate, nll_summary, nll_vectors
from transportability_v6.records import build_round_records
from transportability_v6.strategies import STRATEGIES, score_round


META = {
    "task": "synthetic",
    "split": "iid",
    "model": "random_forest",
    "seed": 91000,
    "strategy": "RAW",
    "round": 0,
    "budget_fraction": 0.0,
    "environment": "synthetic__iid__random_forest",
}


def _record_kwargs() -> dict[str, object]:
    return {
        "candidate_id": np.array(["source", "target", "diagnostic"]),
        "predictive_mean": np.array([0.0, 0.0, 0.0]),
        "raw_sigma": np.array([0.0, 1.0, 1.0]),
        "scaled_sigma": np.array([0.0, 1.0, 1.0]),
        "scale_factor": np.ones(3),
        "raw_beta": 1.0,
        "effective_beta": np.ones(3),
        "acquisition_score": np.zeros(3),
        "stable_rank": np.array([0, 1, 2]),
        "queried": np.array([True, False, False]),
        "target": np.array([1.0, np.nan, np.nan]),
        "target_revealed": np.array([True, False, False]),
        "calibration_role": np.array([True, False, False]),
        "selectable_role": np.array([False, True, False]),
        "diagnostic_role": np.array([False, False, True]),
        "metadata": {key: META[key] for key in META if key != "environment"},
    }


@pytest.mark.parametrize("bad", [np.array([-1.0]), np.array([np.nan]), np.array([np.inf])])
def test_sigma_rejects_negative_nan_and_inf(bad: np.ndarray) -> None:
    with pytest.raises(ValueError):
        validate_sigma(bad)
    with pytest.raises(ValueError):
        fit_scalar_nll(np.ones(len(bad)), bad)


def test_subfloor_sigma_is_allowed_and_audited() -> None:
    raw, effective, events = validate_sigma(np.array([0.0, 1e-12, 1.0]), floor=1e-8)
    np.testing.assert_array_equal(raw, [0.0, 1e-12, 1.0])
    np.testing.assert_array_equal(effective, [1e-8, 1e-8, 1.0])
    np.testing.assert_array_equal(events, [True, True, False])


def test_strategy_rejects_bad_scale_beta_and_duplicate_ids() -> None:
    args = dict(
        spec=STRATEGIES["GG_JOINT"],
        mean=np.array([0.0, 1.0]),
        raw_sigma=np.array([1.0, 1.0]),
        stable_ids=np.array(["a", "b"]),
        beta_raw=1.0,
    )
    with pytest.raises(ValueError, match="positive"):
        score_round(**args, global_scale=0.0)
    with pytest.raises(ValueError, match="finite"):
        score_round(**{**args, "beta_raw": np.nan})
    with pytest.raises(ValueError, match="unique"):
        score_round(**{**args, "stable_ids": np.array(["a", "a"])})


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("candidate_id", np.array(["x", "x", "z"]), "duplicate"),
        ("effective_beta", np.array([1.0, -1.0, 1.0]), "effective_beta"),
        ("stable_rank", np.array([0, 0, 2]), "permutation"),
        ("target", np.array([np.nan, np.nan, np.nan]), "revealed"),
        ("target", np.array([1.0, 2.0, np.nan]), "unrevealed"),
        ("diagnostic_role", np.array([True, False, True]), "exactly one"),
    ],
)
def test_records_reject_malformed_production_schema(field: str, value: np.ndarray, message: str) -> None:
    kwargs = _record_kwargs()
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        build_round_records(**kwargs)


def _nll_frame(seed: int, multiplier: float = 1.0):
    return nll_vectors(
        y=np.array([0.0, 0.0]),
        mu=np.array([0.0, 0.0]),
        sigma_raw=np.array([0.0, 2.0]),
        sigma_scaled=np.array([0.0, 2.0]),
        candidate_id=np.array([f"{seed}-a", f"{seed}-b"]),
        metadata={**META, "seed": seed, "environment": "e"},
    ).assign(individual_nll=lambda frame: frame.individual_nll * multiplier)


def test_nll_reports_raw_and_effective_quantiles_and_combined_gate() -> None:
    baseline = _nll_frame(91000)
    test = _nll_frame(91000, multiplier=1.01)
    summary = nll_summary(baseline)
    assert summary["raw_sigma_minimum"] == 0.0
    assert summary["effective_sigma_minimum"] == pytest.approx(1e-8)
    gate = nll_stability_gate(baseline, test, floor_rate_maximum=1.0)
    assert {"observation_dominance", "seed_dominance", "floor_rate"} <= set(gate["checks"])
    assert isinstance(gate["passes"], bool)
