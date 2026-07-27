from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from transportability_v6.campaigns import CampaignConfig, run_campaign
from transportability_v6.data import formula_features, load_materials_csv, synthetic_materials


IDENTITY_STRATEGIES = (
    "RAW",
    "GG_CALIBRATION_ONLY",
    "GG_NORMALIZED_ACQUISITION",
    "CS_CALIBRATION_ONLY",
)


def _run_all(X, y, ids, seed=91000):
    return {
        strategy: run_campaign(
            X,
            y,
            ids,
            CampaignConfig(
                strategy=strategy,
                seed=seed,
                initial_count=16,
                batch_size=2,
                max_queries=8,
                n_estimators=16,
            ),
        )
        for strategy in IDENTITY_STRATEGIES
    }


def _assert_identity(results):
    raw = results["RAW"]
    for strategy in IDENTITY_STRATEGIES[1:]:
        test = results[strategy]
        assert test["initial_labeled_ids"] == raw["initial_labeled_ids"]
        assert test["queried_trajectory"] == raw["queried_trajectory"]
        assert test["round_count"] == raw["round_count"]
        assert test["budget_fraction"] == raw["budget_fraction"]
        assert test["top1_recall"] == raw["top1_recall"]
        assert test["l4_top1_recall_nauc"] == raw["l4_top1_recall_nauc"]
        for raw_round, test_round in zip(raw["rounds"], test["rounds"]):
            assert test_round["training_ids_before"] == raw_round["training_ids_before"]
            assert test_round["candidate_ids"] == raw_round["candidate_ids"]
            assert test_round["acquisition_scores"] == raw_round["acquisition_scores"]
            assert test_round["stable_order_ids"] == raw_round["stable_order_ids"]
            assert test_round["selected_batch_ids"] == raw_round["selected_batch_ids"]


def test_synthetic_end_to_end_campaign_identity() -> None:
    frame, X = synthetic_materials(80, 44)
    results = _run_all(X, frame["target"].to_numpy(), frame["material_id"].to_numpy())
    _assert_identity(results)
    assert any(
        gg["evaluation_sigma"] != raw["evaluation_sigma"]
        for raw, gg in zip(results["RAW"]["rounds"], results["GG_CALIBRATION_ONLY"]["rounds"])
    )


def test_reduced_real_task_end_to_end_campaign_identity() -> None:
    workspace = Path(__file__).resolve().parents[2]
    path = (
        workspace
        / "最终"
        / "_code_package"
        / "results"
        / "benchmark"
        / "matbench_expt_gap"
        / "materials.csv"
    )
    if not path.is_file():
        pytest.skip("real Matbench smoke asset unavailable")
    frame = load_materials_csv(path).sample(n=80, random_state=91001).sort_index()
    X = formula_features(frame["formula"].to_numpy())
    results = _run_all(
        X,
        frame["target"].to_numpy(),
        frame["material_id"].to_numpy(),
        seed=91001,
    )
    _assert_identity(results)
