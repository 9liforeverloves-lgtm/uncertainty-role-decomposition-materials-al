from __future__ import annotations

from transportability_v6.development import (
    CALIBRATION_REPLAY_STRATEGIES,
    P0_SEEDS,
    POST_SELECTION_TRAJECTORY_STRATEGIES,
    _manifest_rows,
    _validate_manifest_rows,
)


def test_p0_manifest_design_is_development_only_and_covers_selection_paths() -> None:
    rows = _manifest_rows()
    _validate_manifest_rows(rows)
    assert {int(row["seed"]) for row in rows} == set(P0_SEEDS)
    strategies = {str(row["strategy"]) for row in rows}
    assert {"RAW_FIXED_BETA_MATCHED", "RAW_STAGE_BETA_MATCHED", "IDENTITY_CONTROL"} <= strategies
    assert set(CALIBRATION_REPLAY_STRATEGIES) <= strategies
    assert set(POST_SELECTION_TRAJECTORY_STRATEGIES) <= strategies
    assert all(str(row["evidence_class"]) == "V6-MECH" for row in rows)
    assert all("confirmation" not in str(row["job_id"]).lower() for row in rows)
