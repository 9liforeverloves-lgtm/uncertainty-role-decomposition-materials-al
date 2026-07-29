from __future__ import annotations

import json
from pathlib import Path

from transportability_v6.freeze_readiness import validate_analysis_only_contrasts


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v4.json"
FROZEN = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_FROZEN.json"

ADMIN_FIELDS = {
    "status",
    "candidate_self_sha256",
    "frozen_map_self_sha256",
    "frozen_utc",
    "freezing_git_commit",
    "frozen_candidate_sha256",
    "freeze_lock_path",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _scientific(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key not in ADMIN_FIELDS}


def test_candidate_v4_and_frozen_map_are_scientifically_identical() -> None:
    candidate = _load(CANDIDATE)
    frozen = _load(FROZEN)
    assert _scientific(candidate) == _scientific(frozen)
    assert candidate["status"] == "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN"
    assert frozen["status"] == "FROZEN_BEFORE_CONFIRMATION_OUTCOMES"


def test_frozen_gg_raw_and_h7_identity() -> None:
    frozen = _load(FROZEN)
    contrasts = {item["id"]: item for item in frozen["prospective_contrasts"]}
    methods = {item["id"]: item for item in frozen["canonical_strategies"]}
    for hypothesis_id in ("H3", "H4"):
        assert contrasts[hypothesis_id]["baseline"] == "ORIGINAL_GG"
        assert (
            contrasts[hypothesis_id]["matched_beta_source_strategy"]
            == "ORIGINAL_GG"
        )
    assert methods["ORIGINAL_GG"]["nominal_beta"] == 1.0
    assert methods["SELECTED_GG"]["nominal_beta"] == 0.5
    assert frozen["raw_policy"]["choice"] == "A"
    assert frozen["raw_policy"]["nominal_beta"] == 1.0
    assert contrasts["H7"]["analysis_only"] is True
    assert contrasts["H7"]["generate_confirmation_job"] is False
    validate_analysis_only_contrasts(frozen["prospective_contrasts"])


def test_frozen_aliases_remain_non_job_aliases() -> None:
    frozen = _load(FROZEN)
    aliases = {
        item["alias_id"]: item for item in frozen["alias_registry"]["aliases"]
    }
    assert aliases["GG_JOINT"]["canonical_id"] == "ORIGINAL_GG"
    assert aliases["CS_JOINT"]["canonical_id"] == "SELECTED_CS"
    assert aliases["GG_JOINT"]["generate_confirmation_job"] is False
    assert aliases["CS_JOINT"]["generate_confirmation_job"] is False


def test_endpoints_families_and_all_loto_maps_are_unchanged() -> None:
    candidate = _load(CANDIDATE)
    frozen = _load(FROZEN)
    candidate_endpoints = {
        item["id"]: item["endpoint"] for item in candidate["canonical_strategies"]
    }
    frozen_endpoints = {
        item["id"]: item["endpoint"] for item in frozen["canonical_strategies"]
    }
    assert candidate_endpoints == frozen_endpoints
    assert candidate["multiplicity_families"] == frozen["multiplicity_families"]
    assert candidate["leave_one_task_out_maps"] == frozen["leave_one_task_out_maps"]
    assert set(frozen["leave_one_task_out_maps"]) == {
        "matbench_expt_gap",
        "matbench_mp_gap",
        "matbench_log_gvrh",
        "matbench_log_kvrh",
    }
