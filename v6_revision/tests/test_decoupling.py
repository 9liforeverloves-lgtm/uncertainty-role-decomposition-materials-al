from __future__ import annotations

import numpy as np
import pytest

from transportability_v6.strategies import STRATEGIES, score_round


MEAN = np.array([0.2, 0.5, 0.1, 0.7])
SIGMA = np.array([0.3, 0.1, 0.8, 0.05])
IDS = np.array([10, 11, 12, 13])
CSCALE = np.array([0.5, 2.0, 1.5, 0.75])


@pytest.mark.parametrize(
    "name",
    ["GG_CALIBRATION_ONLY", "GG_NORMALIZED_ACQUISITION", "CS_CALIBRATION_ONLY"],
)
def test_calibration_only_or_normalized_path_matches_raw(name: str) -> None:
    raw = score_round(STRATEGIES["RAW"], MEAN, SIGMA, IDS, beta_raw=1.2)
    test = score_round(
        STRATEGIES[name],
        MEAN,
        SIGMA,
        IDS,
        beta_raw=1.2,
        global_scale=2.7,
        candidate_scale=CSCALE,
    )
    np.testing.assert_array_equal(test["stable_order"], raw["stable_order"])
    np.testing.assert_allclose(test["scores"], raw["scores"], rtol=0, atol=1e-15)


def test_acquisition_only_keeps_raw_evaluation_sigma() -> None:
    result = score_round(
        STRATEGIES["GG_ACQUISITION_ONLY"],
        MEAN,
        SIGMA,
        IDS,
        beta_raw=1.0,
        global_scale=3.0,
    )
    np.testing.assert_allclose(result["evaluation_sigma"], SIGMA)
    np.testing.assert_allclose(result["acquisition_sigma"], 3.0 * SIGMA)


def test_joint_global_scaling_equals_effective_beta() -> None:
    joint = score_round(
        STRATEGIES["GG_JOINT"], MEAN, SIGMA, IDS, beta_raw=0.5, global_scale=3.0
    )
    matched = score_round(
        STRATEGIES["RAW_FIXED_BETA_MATCHED"],
        MEAN,
        SIGMA,
        IDS,
        beta_raw=0.5,
        fixed_matched_beta=1.5,
    )
    np.testing.assert_allclose(joint["scores"], matched["scores"])
    np.testing.assert_array_equal(joint["stable_order"], matched["stable_order"])
