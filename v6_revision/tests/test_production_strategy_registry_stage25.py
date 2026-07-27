from __future__ import annotations

from transportability_v6.development import CALIBRATION_REPLAY_STRATEGIES
from transportability_v6.production_campaign import ProductionCampaignConfig, _assert_production_config
from transportability_v6.production_strategies import PRODUCTION_STRATEGIES


def test_actual_production_strategy_specs_cover_required_algorithms() -> None:
    required = {
        "ORIGINAL_GG",
        "SELECTED_GG",
        "HISTORICAL_CS",
        "SELECTED_CS",
        "SCALAR_TEMPERATURE_NLL",
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "POWER_SCALING",
        "ISOTONIC_ABS_RESIDUAL",
        "CONFORMAL_INTERVAL_ONLY",
        "SELECTED_CS_EQUIVALENT_DOF_CONTROL",
        "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL",
        "IDENTITY_CONTROL",
    }
    assert required <= set(PRODUCTION_STRATEGIES)
    for spec in PRODUCTION_STRATEGIES.values():
        assert spec.fitting_data
        assert spec.fallback
        assert spec.acquisition_mapping
        assert spec.evaluation_mapping
        assert spec.nominal_parameter_count >= 0
        assert spec.objective
    assert PRODUCTION_STRATEGIES["SELECTED_CS"].objective != PRODUCTION_STRATEGIES[
        "SELECTED_CS_EQUIVALENT_DOF_CONTROL"
    ].objective
    assert PRODUCTION_STRATEGIES["SELECTED_CS_EQUIVALENT_DOF_CONTROL"].acquisition_mapping == "raw_sigma"
    assert PRODUCTION_STRATEGIES["HISTORICAL_CS_EQUIVALENT_DOF_CONTROL"].acquisition_mapping == "raw_sigma"
    assert all(
        PRODUCTION_STRATEGIES[strategy].acquisition_mapping == "raw_sigma"
        for strategy in CALIBRATION_REPLAY_STRATEGIES
    )


def test_production_confirmation_and_unregistered_seed_are_blocked() -> None:
    base = dict(
        job_id="synthetic",
        task="matbench_expt_gap",
        split_protocol="iid_record",
        model="random_forest",
        strategy="RAW",
        seed=6000,
    )
    assert _assert_production_config(ProductionCampaignConfig(**base)).id == "RAW"
    for update in ({"seed": 7000}, {"phase": "confirmation"}, {"seed": 91000}):
        try:
            _assert_production_config(ProductionCampaignConfig(**{**base, **update}))
        except (PermissionError, ValueError):
            pass
        else:  # pragma: no cover - protects the Stage-2.5 hard boundary
            raise AssertionError("forbidden production configuration was accepted")
