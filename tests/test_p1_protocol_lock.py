from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p1_protocol_lock_binds_every_frozen_file() -> None:
    lock = json.loads((ROOT / "locks/p1_extension_protocol_lock.json").read_text(encoding="utf-8"))
    assert lock["status"] == "FROZEN_BEFORE_ANY_P1_CONFIRMATION_OUTCOME"
    assert lock["confirmation_outcomes_observed_at_freeze"] is False
    for item in lock["files"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]


def test_p1_seed_namespaces_are_complete_and_disjoint() -> None:
    registry = pd.read_csv(ROOT / "analysis_plan/p1_extension_seed_registry_FROZEN.csv")
    groups = {
        name: set(registry.loc[registry.evidence_class == name, "seed"].astype(int))
        for name in registry.evidence_class.unique()
    }
    assert groups["P1_SENTINEL_IMPLEMENTATION_VALIDATION"] == set(range(8000, 8005))
    assert groups["P1_DEVELOPMENT_EXPLORATORY"] == set(range(8100, 8110))
    assert groups["P1_INDEPENDENT_CONFIRMATION"] == set(range(8200, 8240))
    assert not (groups["P1_SENTINEL_IMPLEMENTATION_VALIDATION"] & groups["P1_DEVELOPMENT_EXPLORATORY"])
    assert not (set().union(*groups.values()) & set(range(7000, 7040)))


def test_p1_contrasts_use_only_independent_families() -> None:
    contrasts = pd.read_csv(ROOT / "analysis_plan/p1_extension_contrasts_FROZEN.csv")
    assert len(contrasts) == 5
    assert set(contrasts.family) == {"P1_DISCOVERY_EXISTING", "P1_NEW_UQ_ROLE"}
    assert set(contrasts.seed_scope) == {"8200-8239"}
    assert not contrasts.family.str.contains("P0|V6", regex=True).any()
    assert set(contrasts.favorable_direction) <= {"less", "greater"}


def test_p1_endpoint_directions_are_defined() -> None:
    endpoints = pd.read_csv(ROOT / "analysis_plan/p1_extension_endpoint_registry_FROZEN.csv")
    assert not endpoints.direction.isna().any()
    assert {"P1_L1", "P1_L4", "P1_CAL_COVERAGE", "P1_REGRET", "P1_SEG_AUC"} <= set(endpoints.endpoint_id)
