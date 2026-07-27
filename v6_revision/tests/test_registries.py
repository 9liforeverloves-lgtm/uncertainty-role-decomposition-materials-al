from __future__ import annotations

import inspect
import json
from pathlib import Path

from transportability_v6.calibration import (
    fit_historical_cs_equivalent_dof,
    fit_selected_cs_equivalent_dof,
)
from transportability_v6.strategies import STRATEGIES


ROOT = Path(__file__).resolve().parents[2]


def _json(name: str):
    return json.loads((ROOT / "analysis_plan" / name).read_text(encoding="utf-8"))


def test_strategy_registry_covers_all_executable_decoupling_strategies() -> None:
    registry = _json("v6_strategy_registry.json")
    registered = {item["id"] for item in registry["strategies"]}
    assert set(STRATEGIES) <= registered
    required = {
        "evidence_class",
        "development_status",
        "confirmation_status",
        "nominal_beta",
        "calibration_mapping",
        "acquisition_mapping",
        "primary_baseline",
        "endpoint",
        "direction",
        "family",
        "classification",
        "selection_criterion",
        "required_paired_seed_count",
        "missing_data_handling",
        "retry_rule",
        "fallback",
    }
    for item in registry["strategies"]:
        merged = {**registry["defaults"], **item}
        assert required <= set(merged), item["id"]


def test_seed_registry_separates_v5_development_confirmation_and_smoke() -> None:
    registry = _json("v6_seed_registry.json")
    namespaces = {item["class"]: item for item in registry["namespaces"]}
    assert namespaces["V5-RC1"]["range"] == [5000, 5039]
    assert namespaces["V6-development"]["range"] == [6000, 6009]
    assert namespaces["V6-confirmation"]["range"] == [7000, 7039]
    assert namespaces["Stage2-smoke"]["values"] == [91000, 91001]


def test_equivalent_dof_fit_apis_accept_oob_inputs_only() -> None:
    selected = inspect.signature(fit_selected_cs_equivalent_dof)
    historical = inspect.signature(fit_historical_cs_equivalent_dof)
    assert list(selected.parameters)[:2] == ["residual_oob", "sigma_oob"]
    assert list(historical.parameters)[:3] == [
        "residual_oob",
        "sigma_oob",
        "features_oob",
    ]
    assert not any("selectable" in name or "diagnostic" in name for name in selected.parameters)
    assert not any("selectable" in name or "diagnostic" in name for name in historical.parameters)


def test_smoke_manifest_is_noninferential_and_uses_reserved_seeds() -> None:
    manifest = json.loads(
        (ROOT / "configs/smoke/v6_smoke_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["validation_label"] == "NON-INFERENTIAL ENGINEERING VALIDATION"
    seeds = {int(job["campaign_seed"]) for job in manifest["jobs"]}
    assert seeds == {91000, 91001}
    assert not seeds & (set(range(5000, 5040)) | set(range(6000, 6010)) | set(range(7000, 7040)))
