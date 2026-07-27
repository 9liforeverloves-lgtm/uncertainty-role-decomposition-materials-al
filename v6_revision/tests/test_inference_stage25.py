from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transportability_v6.inference import (
    align_complete_pairs,
    bh_adjust,
    deterministic_child_seed,
    paired_bootstrap_interval,
    paired_inference,
    paired_sign_flip_pvalue,
    require_40_pair_completeness,
    versioned_paired_exclusion_sensitivity,
)


def test_zero_and_all_identical_pairs_are_analytically_stable() -> None:
    zero = np.zeros(8)
    assert paired_bootstrap_interval(zero, seed=1) == (0.0, 0.0)
    assert paired_sign_flip_pvalue(zero, seed=2) == 1.0
    identical = np.full(8, 2.0)
    lower, upper = paired_bootstrap_interval(identical, seed=3)
    assert (lower, upper) == (2.0, 2.0)
    p = paired_sign_flip_pvalue(identical, seed=4, alternative="greater")
    assert 1 / 10_001 <= p <= 1.0
    assert (p * 10_001).is_integer()  # mandatory add-one denominator


def test_child_seed_and_two_sided_definitions_are_deterministic() -> None:
    first = deterministic_child_seed(7, "family", "env", "contrast", "L1")
    assert first == deterministic_child_seed(7, "family", "env", "contrast", "L1")
    assert first != deterministic_child_seed(7, "family", "env", "contrast", "L4")
    values = np.array([1.0, 2.0, 3.0, 4.0])
    two = paired_sign_flip_pvalue(values, seed=9, alternative="two-sided")
    greater = paired_sign_flip_pvalue(values, seed=9, alternative="greater")
    less = paired_sign_flip_pvalue(values, seed=9, alternative="less")
    assert greater <= two <= 1.0
    assert less >= greater


def test_bh_and_pair_alignment_are_exact() -> None:
    np.testing.assert_allclose(bh_adjust([0.01, 0.04, 0.03]), [0.03, 0.04, 0.04])
    baseline = pd.DataFrame({"environment": ["a", "a"], "seed": [1, 2], "value": [1.0, 2.0]})
    test = pd.DataFrame({"environment": ["a", "a"], "seed": [1, 2], "value": [1.5, 1.0]})
    paired = align_complete_pairs(baseline, test, value_column="value")
    np.testing.assert_allclose(paired.paired_difference, [0.5, -1.0])
    with pytest.raises(ValueError, match="missing"):
        align_complete_pairs(baseline, test.iloc[:1], value_column="value")


def test_40_pair_gate_exclusions_and_complete_estimate() -> None:
    seeds = list(range(7000, 7040))
    require_40_pair_completeness(seeds, expected_seeds=seeds)
    with pytest.raises(ValueError, match="40"):
        require_40_pair_completeness(seeds[:-1])
    sensitivity = versioned_paired_exclusion_sensitivity(
        np.array([1.0, -2.0, 3.0]), excluded_positions=[1], version="v1", reason="predeclared check"
    )
    assert sensitivity["sensitivity_pair_count"] == 2
    estimate = paired_inference(
        np.array([1.0, -1.0, 2.0]),
        family="P0_L1_CALIBRATION_ONLY",
        environment="synthetic",
        contrast="test-vs-raw",
        endpoint="l1_campaign_mace",
    )
    assert estimate.n_pairs == 3
    assert estimate.bootstrap_ci_lower <= estimate.bootstrap_ci_upper
