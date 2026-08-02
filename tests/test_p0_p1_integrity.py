from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FROZEN = {
    "locks/v6_p0_confirmation_inference_result_lock.json": "0a7ce4f74de5767251d652639b8f327ee83e8e48e43808701e829d0021f12561",
    "tables/v6_p0_confirmation_primary_contrasts.csv": "2b9820a0167a8e875c322d105fe54cdbad614a391f02db59938aabfe06d2a2fa",
    "tables/v6_p0_confirmation_multiplicity.csv": "f117dfaf7766e7dc648088c01d0e7ce1e6a16b1868c109594e77a69efec20e56",
    "tables/v6_p0_confirmation_environment_effects.csv": "379555bc225bf8e052ce5aa201a52ee2266d7b6699a4e7b9e59e699ee2e284e9",
    "tables/v6_p0_confirmation_pair_completeness.csv": "b6e8cf31b19b2c43195171924e292bf8ab36acbbdbc4821c72db8849db6a7ce8",
    "tables/v6_p0_confirmation_seed_level_endpoints.csv": "a56a853083535b76b8e2c7eaeab056bdd81b0a9e73e953fb00c13237c9c8af8d",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v6_designated_locks_are_unchanged() -> None:
    assert {path: digest(ROOT / path) for path in FROZEN} == FROZEN


def test_endpoint_reconstruction_and_directions() -> None:
    frame = pd.read_csv(ROOT / "tables/v6_p0_confirmation_seed_level_endpoints.csv")
    means = {
        (strategy, endpoint): frame.loc[frame.canonical_strategy == strategy, endpoint]
        .dropna()
        .astype(float)
        .mean()
        for strategy, endpoint in [
            ("RAW", "l4_top1pct_recall_nauc"),
            ("ORIGINAL_GG", "l4_top1pct_recall_nauc"),
            ("RAW_STAGE_BETA_MATCHED", "l4_top1pct_recall_nauc"),
            ("IDENTITY_CONTROL", "l1_campaign_mace"),
            ("SCALAR_TEMPERATURE_RESIDUAL_RATIO", "l1_campaign_mace"),
        ]
    }
    assert round(means[("RAW", "l4_top1pct_recall_nauc")], 6) == 0.641635
    assert round(means[("ORIGINAL_GG", "l4_top1pct_recall_nauc")], 6) == 0.565322
    assert round(means[("RAW_STAGE_BETA_MATCHED", "l4_top1pct_recall_nauc")], 6) == 0.596941
    assert round(means[("IDENTITY_CONTROL", "l1_campaign_mace")], 6) == 0.069511
    assert round(means[("SCALAR_TEMPERATURE_RESIDUAL_RATIO", "l1_campaign_mace")], 6) == 0.048069
    assert means[("RAW_STAGE_BETA_MATCHED", "l4_top1pct_recall_nauc")] < means[("RAW", "l4_top1pct_recall_nauc")]
    assert means[("SCALAR_TEMPERATURE_RESIDUAL_RATIO", "l1_campaign_mace")] < means[("IDENTITY_CONTROL", "l1_campaign_mace")]


def test_strategy_role_mapping_is_explicit() -> None:
    registry = (ROOT / "analysis_plan/v6_strategy_registry.json").read_text(encoding="utf-8")
    for strategy in (
        "GG_CALIBRATION_ONLY",
        "GG_ACQUISITION_ONLY",
        "GG_JOINT",
        "CS_CALIBRATION_ONLY",
        "CS_ACQUISITION_ONLY",
        "CS_JOINT",
        "RAW_FIXED_BETA_MATCHED",
        "RAW_STAGE_BETA_MATCHED",
    ):
        assert f'"id": "{strategy}"' in registry


def test_main_claim_uses_bounded_stagewise_baseline() -> None:
    text = (ROOT / "manuscript/manuscript_submission_revised.tex").read_text(encoding="utf-8")
    assert "Stagewise matched-beta improved discovery" not in text
    assert "partly recovered" in text
    assert "0.044694 below RAW" in text


def test_figure_source_inventory_resolves() -> None:
    inventory = pd.read_csv(ROOT / "tables/revised_figure_source_inventory.csv")
    for extension in ("png", "pdf", "svg"):
        for _, row in inventory.iterrows():
            value = str(row[extension])
            path = ROOT / value.replace("\\", "/")
            assert path.exists(), value
            assert digest(path) == str(row[f"{extension}_sha256"]), value
    for value in inventory["authoritative_sources"]:
        for relative in str(value).split(";"):
            relative = relative.strip()
            assert (ROOT / relative).is_file(), relative
