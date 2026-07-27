from pathlib import Path
import hashlib
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
FIGURES = ROOT / "figures_v5" / "final_v2"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    return json.loads((FIGURES / "figure_manifest_v2.json").read_text(encoding="utf-8"))


def test_v2_manifest_locks_final_tables_and_all_figure_artifacts():
    data = manifest()
    assert data["schema_version"] == "final-figure-manifest-v2"
    assert len(data["figures"]) == 9
    assert data["final_table_lock_sha256"] == sha256(
        TABLES / "FINAL_TABLE_LOCK_V5.json"
    )
    for relative, expected_hash in data["final_table_hashes"].items():
        assert sha256(ROOT / relative) == expected_hash
    for item in data["figures"]:
        for field in ("source", "caption", "png", "pdf"):
            path = FIGURES / item[field]
            assert path.is_file() and path.stat().st_size > 0
            assert sha256(path) == item[f"{field}_sha256"]


def test_v2_architecture_counts_equal_frozen_manifests():
    architecture = pd.read_csv(FIGURES / "Figure01_study_architecture_source.csv")
    observed = dict(zip(architecture["component"], architecture["count"]))
    assert observed == {
        "Tasks": 4,
        "Splits": 2,
        "Surrogates": 2,
        "Development candidate configurations": 36,
        "Confirmation strategy identities": 6,
        "Confirmation strategy–environment cells": 84,
        "Paired-seed jobs": 3360,
    }


def test_v2_forest_values_are_exact_locked_rows():
    primary = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    keys = ["environment", "contrast_name", "mean_diff", "ci_lower", "ci_upper"]
    for endpoint, filename in [
        ("l1_campaign_mace", "Figure02_L1_forest_source.csv"),
        ("l4_top1pct_recall_nauc", "Figure03_L4_forest_source.csv"),
    ]:
        observed = pd.read_csv(FIGURES / filename)[keys]
        expected = primary[primary["endpoint"] == endpoint][keys]
        observed = observed.sort_values(keys[:2]).reset_index(drop=True)
        expected = expected.sort_values(keys[:2]).reset_index(drop=True)
        pd.testing.assert_frame_equal(observed, expected, check_exact=True)


def test_v2_recovery_figure_matches_locked_sensitivity_rows():
    observed = pd.read_csv(FIGURES / "Figure06_recovery_exclusion_source.csv")
    expected = pd.read_csv(TABLES / "v5_rc1_recovery_sensitivity_final.csv")
    expected = expected.assign(
        effect_delta=expected["mean_diff_sensitivity"] - expected["mean_diff_primary"],
        label=expected["contrast_name"]
        + " | "
        + expected["endpoint"].map(
            {"l1_campaign_mace": "L1", "l4_top1pct_recall_nauc": "L4"}
        ),
    )
    base_columns = [column for column in expected.columns if column != "effect_delta"]
    pd.testing.assert_frame_equal(
        observed[base_columns], expected[base_columns], check_exact=True
    )
    pd.testing.assert_series_equal(
        observed["effect_delta"],
        expected["effect_delta"],
        check_exact=False,
        rtol=0,
        atol=5e-16,
    )


def test_v2_captions_state_direction_scope_and_evidence_class():
    captions = {
        item["figure"]: (FIGURES / item["caption"]).read_text(encoding="utf-8")
        for item in manifest()["figures"]
    }
    assert "negative favors" in captions["Figure02_L1_forest"]
    assert "positive favors" in captions["Figure03_L4_forest"]
    assert "40 confirmation seeds" in captions["Figure02_L1_forest"]
    assert "BH adjustment" in captions["Figure03_L4_forest"]
    assert "no pooled-task inference" in captions["Figure02_L1_forest"]
    assert "0/8" in captions["Figure06_recovery_exclusion"]
    assert "2" in captions["Figure06_recovery_exclusion"]
    assert "0.00182503" in captions["Figure06_recovery_exclusion"]
    assert "Exploratory" in captions["Figure09_L1_L4_cross_layer_exploratory"]


def test_v2_sources_and_captions_exclude_invalid_provenance_tokens():
    forbidden = ("INVALID_ANALYSIS", "UNCORRECTED_ARCHIVE", "SUPERSEDED")
    for path in list(FIGURES.glob("*_source.csv")) + list(
        FIGURES.glob("*_caption.txt")
    ):
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden)
