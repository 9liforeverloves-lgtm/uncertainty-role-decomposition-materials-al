from __future__ import annotations

import numpy as np
import pandas as pd
import transportability_v6.broad_development as broad_development

from transportability_v6.broad_development import (
    BROAD_SEEDS,
    CALIBRATION_REPLAY_STRATEGIES,
    ENVIRONMENTS,
    FULL_BASE_STRATEGIES,
    POST_SELECTION_FULL_STRATEGIES,
    SIMPLE_SCALER_ROLES,
    _record_recovery_event,
    _manifest_rows,
    _validate_manifest_rows,
)
from transportability_v6.calibration_replay import _ordered_targets_at_checkpoint
from transportability_v6.production_campaign import ProductionCampaignConfig, _assert_production_config


def test_broad_manifest_is_full_universe_and_seed_disjoint() -> None:
    rows = _manifest_rows()
    _validate_manifest_rows(rows, seeds=set(BROAD_SEEDS), evidence_class="V6-P0-BROAD-DEVELOPMENT")
    assert len(ENVIRONMENTS) == 16
    assert len(rows) == 16 * 10 * 17
    assert {int(row["seed"]) for row in rows} == set(range(6100, 6110))
    assert not {int(row["seed"]) for row in rows} & set(range(7000, 7040))
    assert len(FULL_BASE_STRATEGIES) + len(CALIBRATION_REPLAY_STRATEGIES) + len(POST_SELECTION_FULL_STRATEGIES) == 17


def test_broad_calibration_rows_have_exact_raw_dependencies() -> None:
    rows = _manifest_rows()
    for row in rows:
        if row["job_kind"] == "calibration_replay":
            assert row["dependency_job_id"]
            assert row["dependency_kind"] == "exact_RAW_acquisition_replay"
            assert row["execution_phase"] == "base"


def test_selected_gg_is_the_historical_half_beta_comparator_not_a_loto_raw_variant() -> None:
    rows = _manifest_rows()
    selected = [row for row in rows if row["strategy"] == "SELECTED_GG"]
    assert selected
    assert {row["execution_phase"] for row in selected} == {"base"}
    assert {row["beta_rule"] for row in selected} == {"historical_selected_gg_nominal_beta_0p5"}
    assert "SELECTED_GG" in FULL_BASE_STRATEGIES
    assert "SELECTED_GG" not in POST_SELECTION_FULL_STRATEGIES


def test_simple_scaler_roles_do_not_promote_identity_to_a_winner() -> None:
    assert SIMPLE_SCALER_ROLES["IDENTITY_CONTROL"] == "negative_implementation_control_not_scaling_winner"
    assert SIMPLE_SCALER_ROLES["SCALAR_TEMPERATURE_RESIDUAL_RATIO"] == "candidate_simple_nonidentity_scalar_baseline"
    assert "winner" not in SIMPLE_SCALER_ROLES["SCALAR_TEMPERATURE_NLL"]


def test_production_guards_accept_only_registered_broad_seed_and_evidence_class() -> None:
    valid = ProductionCampaignConfig(
        job_id="test",
        task="matbench_expt_gap",
        split_protocol="iid_record",
        model="random_forest",
        strategy="RAW",
        seed=6100,
        evidence_class="V6-P0-BROAD-DEVELOPMENT",
        phase="broad_development",
    )
    assert _assert_production_config(valid).id == "RAW"
    invalid = ProductionCampaignConfig(
        job_id="test",
        task="matbench_expt_gap",
        split_protocol="iid_record",
        model="random_forest",
        strategy="RAW",
        seed=7000,
        evidence_class="V6-P0-BROAD-DEVELOPMENT",
        phase="broad_development",
    )
    try:
        _assert_production_config(invalid)
    except PermissionError:
        pass
    else:  # pragma: no cover - regression guard
        raise AssertionError("confirmation seed was accepted")


def test_calibration_replay_preserves_initial_checkpoint_query_order() -> None:
    source = {"initial_labeled_ids": ["a", "b"]}
    rounds = pd.DataFrame(
        [
            {"round": -1, "selected_batch_ids": []},
            {"round": 0, "selected_batch_ids": ["c", "d"]},
        ]
    )
    ids = np.asarray(["a", "b", "c", "d"])
    y = np.asarray([1.0, 2.0, 3.0, 4.0])
    initial = _ordered_targets_at_checkpoint(
        source=source,
        source_rounds=rounds,
        metadata={"queried_count": 2},
        ids=ids,
        y=y,
    )
    after_round_zero = _ordered_targets_at_checkpoint(
        source=source,
        source_rounds=rounds,
        metadata={"queried_count": 4},
        ids=ids,
        y=y,
    )
    assert np.array_equal(initial, np.asarray([1.0, 2.0]))
    assert np.array_equal(after_round_zero, y)


def test_recovery_records_are_lock_addressed_and_append_only(monkeypatch) -> None:
    row = _manifest_rows(seeds=(6100,))[0]
    records: list[tuple[object, object]] = []

    def capture(path, payload):
        records.append((path, payload))
        return "captured"

    monkeypatch.setattr(broad_development, "_write_json_once", capture)
    first = _record_recovery_event(
        run_root=broad_development.WORKSPACE / "test-recovery-root",
        final_lock_sha256="final-lock",
        manifest_sha256="manifest-lock",
        recovery_run_id="resume-test",
        event_kind="execution_failed",
        row=row,
        attempt=1,
        prior_status="RUNNING",
        details={"last_error": "test"},
    )
    second = _record_recovery_event(
        run_root=broad_development.WORKSPACE / "test-recovery-root",
        final_lock_sha256="final-lock",
        manifest_sha256="manifest-lock",
        recovery_run_id="resume-test",
        event_kind="retry_authorized",
        row=row,
        attempt=1,
        prior_status="FAILED",
        details={"rule": "unchanged lock"},
    )
    assert first != second
    assert len(records) == 2
    assert all(payload["final_lock_sha256"] == "final-lock" for _, payload in records)
