from __future__ import annotations

from transportability_v6.development import CALIBRATION_REPLAY_STRATEGIES
import numpy as np

from transportability_v6.production_campaign import ProductionCampaignConfig, _assert_production_config
from transportability_v6.production_strategies import AppliedProductionScale, score_production_round
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
    assert PRODUCTION_STRATEGIES["SELECTED_CS"].acquisition_mapping == "scaled_sigma"
    assert PRODUCTION_STRATEGIES["SELECTED_CS"].evaluation_mapping == "scaled_gaussian_sigma"
    assert PRODUCTION_STRATEGIES["CS_ACQUISITION_ONLY"].acquisition_mapping == "scaled_sigma"
    assert PRODUCTION_STRATEGIES["CS_ACQUISITION_ONLY"].evaluation_mapping == "raw_gaussian_sigma"
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


def test_matched_raw_beta_strategies_use_the_registered_raw_acquisition_map() -> None:
    for identifier in ("RAW_FIXED_BETA_MATCHED", "RAW_STAGE_BETA_MATCHED"):
        spec = PRODUCTION_STRATEGIES[identifier]
        application = AppliedProductionScale(
            spec=spec,
            status="identity",
            query_sigma=np.array([1.0, 2.0]),
            diagnostic_sigma=None,
            query_scale_factor=np.ones(2),
            diagnostic_scale_factor=None,
        )
        # score_production_round only needs the adapter's canonical stable-order
        # function; the temporary object avoids a production campaign run here.
        class _Adapter:
            modules = {"strategies": type("S", (), {"stable_order": staticmethod(lambda scores, ids: np.lexsort((ids, -scores)))})}

        scores, order = score_production_round(
            spec, application, np.array([0.0, 0.0]), np.array([0, 1]), beta=2.0, adapter=_Adapter()
        )
        np.testing.assert_allclose(scores, [2.0, 4.0])
        np.testing.assert_array_equal(order, [1, 0])
