from __future__ import annotations

import numpy as np
import pytest

from transportability_v6.records import build_round_records


META = {
    "task": "t", "split": "s", "model": "m", "seed": 6000,
    "strategy": "RAW", "round": 0, "budget_fraction": 0.1,
}


def _kwargs():
    return {
        "candidate_id": np.array(["a", "b"]),
        "predictive_mean": np.array([1.0, 2.0]),
        "raw_sigma": np.array([0.1, 0.2]),
        "scaled_sigma": np.array([0.1, 0.2]),
        "scale_factor": np.ones(2),
        "raw_beta": 1.0,
        "effective_beta": np.ones(2),
        "acquisition_score": np.array([1.1, 2.2]),
        "stable_rank": np.array([2, 1]),
        "queried": np.array([False, True]),
        "target": np.array([np.nan, 3.0]),
        "target_revealed": np.array([False, True]),
        "calibration_role": np.array([False, False]),
        "selectable_role": np.array([True, True]),
        "diagnostic_role": np.array([False, False]),
        "metadata": META,
    }


def test_unrevealed_targets_are_missing() -> None:
    frame = build_round_records(**_kwargs())
    assert np.isnan(frame.loc[0, "target"])


def test_unrevealed_target_value_is_rejected() -> None:
    kwargs = _kwargs()
    kwargs["target"] = np.array([99.0, 3.0])
    with pytest.raises(ValueError, match="unrevealed"):
        build_round_records(**kwargs)
