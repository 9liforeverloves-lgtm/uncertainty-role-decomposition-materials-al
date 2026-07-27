from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transportability_v6.ranking import path_diagnostics, ranking_diagnostics
from transportability_v6.selection import (
    beta_for_budget,
    fit_matched_beta_map,
    freeze_selection_map,
    verify_selection_map,
)


def test_environment_balanced_matched_beta_and_stages() -> None:
    rows = []
    for environment, base in (("a", 1.0), ("b", 3.0)):
        for seed in (6000, 6001):
            for budget in (0.1, 0.3, 0.6, 0.9):
                rows.append(
                    {
                        "environment": environment,
                        "seed": seed,
                        "budget_fraction": budget,
                        "effective_beta": base + budget,
                    }
                )
    selection = fit_matched_beta_map(pd.DataFrame(rows))
    assert selection["fixed_matched_beta"] == pytest.approx(2.45)
    assert beta_for_budget(selection, 0.1) == pytest.approx(2.1)
    assert beta_for_budget(selection, 0.9) == pytest.approx(2.9)


def test_confirmation_seed_collision_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "environment": ["a"] * 4,
            "seed": [7000] * 4,
            "budget_fraction": [0.1, 0.3, 0.6, 0.9],
            "effective_beta": [1.0] * 4,
        }
    )
    with pytest.raises(ValueError, match="forbidden V5/confirmation"):
        fit_matched_beta_map(frame)


def test_v5_seed_collision_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "environment": ["a"] * 4,
            "seed": [5000] * 4,
            "budget_fraction": [0.1, 0.3, 0.6, 0.9],
            "effective_beta": [1.0] * 4,
        }
    )
    with pytest.raises(ValueError, match="forbidden V5/confirmation"):
        fit_matched_beta_map(frame)


def test_smoke_seed_is_not_accepted_as_development() -> None:
    frame = pd.DataFrame(
        {
            "environment": ["a"] * 4,
            "seed": [91000] * 4,
            "budget_fraction": [0.1, 0.3, 0.6, 0.9],
            "effective_beta": [1.0] * 4,
        }
    )
    with pytest.raises(ValueError, match="non-development"):
        fit_matched_beta_map(frame)


def test_stage_boundary_behavior_and_missing_stage_fallback() -> None:
    frame = pd.DataFrame(
        {
            "environment": ["a", "a", "a"],
            "seed": [6000, 6000, 6000],
            "budget_fraction": [0.1, 0.25, 0.5],
            "effective_beta": [1.0, 2.0, 3.0],
        }
    )
    selection = fit_matched_beta_map(frame)
    assert beta_for_budget(selection, 0.249999) == 1.0
    assert beta_for_budget(selection, 0.25) == 2.0
    assert beta_for_budget(selection, 0.50) == 3.0
    assert beta_for_budget(selection, 0.75) == selection["fixed_matched_beta"]
    assert beta_for_budget(selection, 1.0) == selection["fixed_matched_beta"]
    assert selection["stages_using_fallback"] == ["75_100"]


def test_selection_map_hash_detects_mutation(tmp_path) -> None:
    source = tmp_path / "development.csv"
    source.write_text("seed,effective_beta\n6000,1\n", encoding="utf-8")
    output = tmp_path / "selection.json"
    selection = {
        "fixed_matched_beta": 1.0,
        "stage_matched_beta": {name: 1.0 for name in ("0_25", "25_50", "50_75", "75_100")},
    }
    freeze_selection_map(selection, output, source_files=[source])
    assert verify_selection_map(output)
    text = output.read_text(encoding="utf-8").replace(
        '"fixed_matched_beta": 1.0', '"fixed_matched_beta": 2.0'
    )
    output.write_text(text, encoding="utf-8")
    assert not verify_selection_map(output)


def test_rank_and_path_diagnostics() -> None:
    ids = np.arange(5)
    raw = np.array([5, 4, 3, 2, 1], float)
    same = raw.copy()
    metrics = ranking_diagnostics(raw, same, ids, batch_size=2)
    assert metrics["full_pool_spearman"] == pytest.approx(1.0)
    assert metrics["batch_jaccard_overlap"] == pytest.approx(1.0)
    path = path_diagnostics(
        pd.DataFrame(
            {
                "round": [0, 1],
                "raw_selected_ids": [["a"], ["b"]],
                "test_selected_ids": [["a"], ["c"]],
            }
        )
    )
    assert path["first_divergence_round"] == 1


def test_reversed_ranking_partial_overlap_and_pool_smaller_than_k() -> None:
    ids = np.arange(4)
    raw = np.array([4, 3, 2, 1], float)
    reversed_scores = raw[::-1]
    reversed_metrics = ranking_diagnostics(raw, reversed_scores, ids, batch_size=10)
    assert reversed_metrics["full_pool_spearman"] == pytest.approx(-1.0)
    assert reversed_metrics["full_pool_kendall_tau"] == pytest.approx(-1.0)
    assert reversed_metrics["top_k_overlap"] == 1.0
    partial = ranking_diagnostics(
        raw, np.array([4, 1, 3, 2], float), ids, batch_size=2
    )
    assert partial["top_k_overlap"] == 0.5


def test_ranking_ties_and_retained_pool_consistency() -> None:
    ids = np.array([4, 1, 3, 2])
    scores = np.ones(4)
    metrics = ranking_diagnostics(
        scores, scores, ids, batch_size=2, retained_mask=np.array([True, True, False, True])
    )
    assert metrics["full_pool_spearman"] == pytest.approx(1.0)
    assert metrics["retained_pool_spearman"] == pytest.approx(1.0)
    assert metrics["batch_jaccard_overlap"] == 1.0


@pytest.mark.parametrize(
    "bad",
    [np.array([1.0, np.nan, 2.0]), np.array([1.0, np.inf, 2.0])],
)
def test_ranking_rejects_nan_and_inf(bad) -> None:
    with pytest.raises(ValueError, match="finite"):
        ranking_diagnostics(bad, np.array([1.0, 2.0, 3.0]), np.arange(3), batch_size=1)
