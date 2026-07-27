from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transportability_v6.ranking import path_diagnostics, ranking_diagnostics
from transportability_v6.selection import beta_for_budget, fit_matched_beta_map


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
    with pytest.raises(ValueError, match="confirmation seed leakage"):
        fit_matched_beta_map(frame)


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
