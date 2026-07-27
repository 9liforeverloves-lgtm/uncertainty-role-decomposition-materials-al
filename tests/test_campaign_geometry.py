from __future__ import annotations

import numpy as np

from transportability_v5.metrics import normalized_auc


def test_normalized_auc_uses_budget_fraction_geometry() -> None:
    budget = np.array([0.0, 0.25, 0.5, 1.0])
    recall = np.array([0.0, 0.25, 0.5, 1.0])
    assert normalized_auc(budget, recall) == 0.5


def test_normalized_auc_rejects_degenerate_budget_axis() -> None:
    budget = np.array([0.0, 0.0])
    recall = np.array([0.0, 1.0])
    assert np.isnan(normalized_auc(budget, recall))
