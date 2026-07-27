from pathlib import Path
import hashlib
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"


def test_final_endpoint_and_contrast_completeness():
    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_final.csv")
    contrasts = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    assert len(endpoints) == 3360
    assert endpoints["job_id"].is_unique
    assert len(contrasts) == 128


def test_l4_case_a_is_exact_for_every_trajectory():
    audit = pd.read_csv(
        ROOT / "audits_v5" / "l4_exact_execution_reconstruction_final.csv"
    )
    assert len(audit) == 3360
    assert audit["bitwise_equal_float64"].all()
    assert audit["absolute_difference"].max() == 0.0
    assert (audit["x_axis"] == "budget_fraction").all()


def test_primary_bh_families_have_eight_rows():
    contrasts = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    assert (contrasts.groupby("bh_family_id").size() == 8).all()


def test_log_kvrh_selected_baseline_is_raw_beta_2():
    contrasts = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    rows = contrasts[
        (contrasts["task"] == "matbench_log_kvrh")
        & contrasts["contrast_name"].str.startswith("Selected")
    ]
    assert set(rows["baseline_strategy"]) == {"raw_ucb_beta_2"}


def test_recovery_sensitivity_pairing_and_conclusions():
    sensitivity = pd.read_csv(
        TABLES / "v5_rc1_recovery_sensitivity_final.csv"
    )
    assert len(sensitivity) == 8
    assert set(sensitivity["n_pairs_primary"]) == {40}
    assert set(sensitivity["n_pairs_sensitivity"]) == {34}
    assert sensitivity["direction_sign_changed"].sum() == 0
    assert sensitivity["evidence_label_changed"].sum() == 0
    assert sensitivity["ci_zero_status_changed"].sum() == 0
    assert (sensitivity["relative_effect_change"] > 0.10).sum() == 2
    assert abs(sensitivity["absolute_effect_change"].max() - 0.0018250336342871048) < 1e-15


def test_submission_table_copies_equal_sources():
    pairs = [
        (
            TABLES / "v5_rc1_primary_contrasts_final.csv",
            TABLES / "final_main_text_tables" / "v5_rc1_primary_contrasts_final.csv",
        ),
        (
            TABLES / "v5_rc1_recovery_sensitivity_final.csv",
            TABLES
            / "final_supplement_tables"
            / "v5_rc1_recovery_sensitivity_final.csv",
        ),
    ]
    for source, copy in pairs:
        assert source.read_bytes() == copy.read_bytes()


def test_final_tables_do_not_reference_invalid_or_superseded_sources():
    forbidden = ("INVALID_ANALYSIS", "UNCORRECTED_ARCHIVE", "SUPERSEDED")
    for path in TABLES.glob("*_final.csv"):
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden)


def test_final_figure_sources_match_manifest_hashes():
    figure_dir = ROOT / "figures_v5" / "final"
    manifest = json.loads((figure_dir / "figure_manifest.json").read_text())
    assert len(manifest["figures"]) == 9
    for item in manifest["figures"]:
        source = figure_dir / item["source"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["source_sha256"]
        assert (figure_dir / item["png"]).exists()
        assert (figure_dir / item["pdf"]).exists()


def test_forest_figure_values_equal_final_contrast_rows():
    figure_dir = ROOT / "figures_v5" / "final"
    primary = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    for endpoint, name in [
        ("l1_campaign_mace", "Figure02_L1_forest_source.csv"),
        ("l4_top1pct_recall_nauc", "Figure03_L4_forest_source.csv"),
    ]:
        source = pd.read_csv(figure_dir / name)
        expected = primary[primary["endpoint"] == endpoint]
        keys = ["environment", "contrast_name", "mean_diff", "ci_lower", "ci_upper"]
        left = source[keys].sort_values(keys[:2]).reset_index(drop=True)
        right = expected[keys].sort_values(keys[:2]).reset_index(drop=True)
        pd.testing.assert_frame_equal(left, right, check_exact=True)
