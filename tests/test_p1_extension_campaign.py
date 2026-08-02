from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from p1_extension.campaign import CampaignConfig, _stable_descending, _stable_top_set, run_qgb_campaign
from p1_extension.metrics import normalized_auc


def data() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(9)
    X = rng.normal(size=(70, 4))
    y = X[:, 0] - X[:, 1] + rng.normal(scale=0.1, size=70)
    ids = np.asarray([f"record-{index:03d}" for index in range(70)])
    return X, y, ids, np.arange(30), np.arange(30, 60), np.arange(60, 70)


def run(tmp_path: Path, strategy: str):
    X, y, ids, source, target, diagnostic = data()
    config = CampaignConfig(strategy, 8000, 1.0, 10, 2, 8)
    output = tmp_path / strategy
    result = run_qgb_campaign(X, y, material_ids=ids, source=source, target=target, diagnostic=diagnostic, config=config, output_dir=output)
    return result, output


def test_raw_campaign_is_complete_deterministic_and_resumable(tmp_path: Path) -> None:
    first, output = run(tmp_path, "P1_QGB_RAW")
    X, y, ids, source, target, diagnostic = data()
    config = CampaignConfig("P1_QGB_RAW", 8000, 1.0, 10, 2, 8)
    resumed = run_qgb_campaign(X, y, material_ids=ids, source=source, target=target, diagnostic=diagnostic, config=config, output_dir=output, resume=True)
    assert first == resumed
    assert first["complete"] is True
    assert len(first["queried_indices"]) == 8
    assert set(first["endpoints"]) == {"l1_campaign_mace", "l4_top1pct_recall_nauc", "top5pct_recall_nauc", "top10pct_recall_nauc"}
    rounds = pd.read_parquet(output / "rounds.parquet")
    assert rounds.budget_fraction.tolist() == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert rounds[["top1_recall", "top5_recall", "top10_recall"]].apply(lambda s: s.between(0, 1).all()).all()


def test_registered_l1_uses_only_four_checkpoint_rows(tmp_path: Path) -> None:
    X, y, ids, source, target, diagnostic = data()
    config = CampaignConfig("P1_QGB_RAW", 8001, 1.0, 10, 1, 8)
    output = tmp_path / "checkpoint"
    result = run_qgb_campaign(X, y, material_ids=ids, source=source, target=target, diagnostic=diagnostic, config=config, output_dir=output)
    diagnostic_frame = pd.read_parquet(output / "diagnostic_metrics.parquet")
    state = json.loads((output / "state.json").read_text(encoding="utf-8"))
    reconstructed = np.mean([diagnostic_frame.iloc[state["checkpoint_rows"][label]].mean_absolute_coverage_error for label in ("initial", "25pct", "50pct", "75pct")])
    assert result["endpoints"]["l1_campaign_mace"] == pytest.approx(reconstructed)


def test_discovery_endpoints_reconstruct_from_trajectory(tmp_path: Path) -> None:
    result, output = run(tmp_path, "P1_QGB_RAW")
    rounds = pd.read_parquet(output / "rounds.parquet")
    for endpoint, column in (("l4_top1pct_recall_nauc", "top1_recall"), ("top5pct_recall_nauc", "top5_recall"), ("top10pct_recall_nauc", "top10_recall")):
        reconstructed = normalized_auc(rounds.budget_fraction.to_numpy(float), rounds[column].to_numpy(float))
        assert result["endpoints"][endpoint] == pytest.approx(reconstructed)


def test_calibration_only_has_exact_raw_acquisition_path(tmp_path: Path) -> None:
    raw, _ = run(tmp_path, "P1_QGB_RAW")
    calibrated, _ = run(tmp_path, "P1_QGB_CALIBRATION_ONLY_RR")
    assert raw["queried_indices"] == calibrated["queried_indices"]


def test_stable_candidate_and_target_tie_breaking() -> None:
    values = np.array([2.0, 2.0, 1.0])
    ids = np.array(["b", "a", "c"])
    assert _stable_descending(values, ids).tolist() == [1, 0, 2]
    y = np.array([5.0, 5.0, 1.0, 0.0])
    pool = np.arange(4)
    assert _stable_top_set(y, pool, np.array(["b", "a", "c", "d"]), 0.25).tolist() == [1]


def test_queried_records_are_removed_before_rescoring(tmp_path: Path) -> None:
    result, output = run(tmp_path, "P1_QGB_ACQUISITION_ONLY_RR")
    rounds = pd.read_parquet(output / "rounds.parquet")
    selected = []
    for payload in rounds.selected_batch_ids_json.iloc[:-1]:
        batch = json.loads(payload)
        assert not set(batch) & set(selected)
        selected.extend(batch)
    assert len(selected) == len(set(selected)) == len(result["queried_indices"])


def test_role_overlap_fails_closed(tmp_path: Path) -> None:
    X, y, ids, source, target, diagnostic = data()
    config = CampaignConfig("P1_QGB_RAW", 8000, 1.0, 10, 2, 4)
    with pytest.raises(ValueError, match="disjoint"):
        run_qgb_campaign(X, y, material_ids=ids, source=source, target=target, diagnostic=target, config=config, output_dir=tmp_path / "bad")


def test_diagnostic_labels_cannot_change_acquisition_path(tmp_path: Path) -> None:
    X, y, ids, source, target, diagnostic = data()
    config = CampaignConfig("P1_QGB_ACQUISITION_ONLY_RR", 8002, 1.0, 10, 2, 8)
    original = run_qgb_campaign(
        X, y, material_ids=ids, source=source, target=target, diagnostic=diagnostic,
        config=config, output_dir=tmp_path / "original"
    )
    perturbed_y = y.copy()
    perturbed_y[diagnostic] = perturbed_y[diagnostic] * -1000.0 + 777.0
    perturbed = run_qgb_campaign(
        X, perturbed_y, material_ids=ids, source=source, target=target, diagnostic=diagnostic,
        config=config, output_dir=tmp_path / "perturbed"
    )
    assert original["queried_indices"] == perturbed["queried_indices"]
