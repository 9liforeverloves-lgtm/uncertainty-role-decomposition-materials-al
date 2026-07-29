from __future__ import annotations

import pytest

from transportability_v6.freeze_readiness import (
    effective_beta,
    validate_analysis_only_contrasts,
    validate_alias_registry,
    validate_contrast_endpoint_consistency,
    validate_gg_policy_identity,
    validate_manifest_policy_identity,
)


def _contrast(endpoint: str, *, baseline: str = "RAW") -> dict[str, str]:
    return {
        "id": "TEST",
        "strategy_id": "METHOD",
        "comparison": f"METHOD vs {baseline}",
        "baseline": baseline,
        "endpoint": endpoint,
    }


def test_l4_contrast_rejects_l1_only_strategy() -> None:
    registry = [
        {"id": "METHOD", "endpoint": "L1"},
        {"id": "RAW", "endpoint": "L1_and_L4"},
    ]
    with pytest.raises(ValueError, match="does not support L4"):
        validate_contrast_endpoint_consistency([_contrast("L4")], registry)


def test_l1_contrast_rejects_strategy_without_l1() -> None:
    registry = [
        {"id": "METHOD", "endpoint": "L4"},
        {"id": "RAW", "endpoint": "L1_and_L4"},
    ]
    with pytest.raises(ValueError, match="does not support L1"):
        validate_contrast_endpoint_consistency([_contrast("L1")], registry)


def test_contrast_rejects_absent_baseline() -> None:
    registry = [{"id": "METHOD", "endpoint": "L1_and_L4"}]
    with pytest.raises(ValueError, match="baseline .* is absent"):
        validate_contrast_endpoint_consistency(
            [_contrast("L1", baseline="MISSING")],
            registry,
        )


def test_aliases_are_not_independent_canonical_members() -> None:
    validate_alias_registry(
        {"GG_JOINT": "ORIGINAL_GG", "CS_JOINT": "SELECTED_CS"},
        {"RAW", "ORIGINAL_GG", "SELECTED_CS"},
    )
    with pytest.raises(ValueError, match="aliases also appear as canonical"):
        validate_alias_registry(
            {"GG_JOINT": "ORIGINAL_GG"},
            {"RAW", "ORIGINAL_GG", "GG_JOINT"},
        )


def _gg_policies() -> list[dict[str, object]]:
    return [
        {
            "id": "ORIGINAL_GG",
            "nominal_beta": 1.0,
            "policy_key": "ORIGINAL_GG__beta_1",
        },
        {
            "id": "SELECTED_GG",
            "nominal_beta": 0.5,
            "policy_key": "SELECTED_GG__beta_0p5",
            "policy_provenance": {"v5_strategy_id": "gg_ucb_beta_0p5"},
        },
    ]


def test_original_and_selected_gg_are_distinct_frozen_policies() -> None:
    policies = _gg_policies()
    validate_gg_policy_identity(policies)
    assert policies[0]["id"] != policies[1]["id"]
    assert policies[0]["nominal_beta"] == 1.0
    assert policies[1]["nominal_beta"] == 0.5
    assert effective_beta(1.0, 2.4) == pytest.approx(2.4)
    assert effective_beta(0.5, 2.4) == pytest.approx(1.2)


def test_manifest_cannot_substitute_original_and_selected_gg() -> None:
    policies = _gg_policies()
    validate_manifest_policy_identity(
        [
            {
                "strategy_id": "ORIGINAL_GG",
                "nominal_beta": 1.0,
                "policy_key": "ORIGINAL_GG__beta_1",
            },
            {
                "strategy_id": "SELECTED_GG",
                "nominal_beta": 0.5,
                "policy_key": "SELECTED_GG__beta_0p5",
            },
        ],
        policies,
    )
    with pytest.raises(ValueError, match="nominal beta"):
        validate_manifest_policy_identity(
            [
                {
                    "strategy_id": "SELECTED_GG",
                    "nominal_beta": 1.0,
                    "policy_key": "ORIGINAL_GG__beta_1",
                }
            ],
            policies,
        )
    with pytest.raises(ValueError, match="policy key"):
        validate_manifest_policy_identity(
            [
                {
                    "strategy_id": "ORIGINAL_GG",
                    "nominal_beta": 1.0,
                    "policy_key": "SELECTED_GG__beta_0p5",
                }
            ],
            policies,
        )


def test_analysis_only_hypothesis_cannot_generate_a_job() -> None:
    validate_analysis_only_contrasts(
        [
            {
                "id": "H7",
                "analysis_only": True,
                "generate_confirmation_job": False,
                "family": "NONE_DESCRIPTIVE",
                "binary_claim": False,
                "method_contrasts": ["GG_CALIBRATION_ONLY vs RAW"],
            }
        ]
    )
    with pytest.raises(ValueError, match="generates a job"):
        validate_analysis_only_contrasts(
            [
                {
                    "id": "H7",
                    "analysis_only": True,
                    "generate_confirmation_job": True,
                    "family": "NONE_DESCRIPTIVE",
                    "binary_claim": False,
                    "method_contrasts": ["GG_CALIBRATION_ONLY vs RAW"],
                }
            ]
        )
