from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

from .strategies import stable_order


def _rank_vector(scores: np.ndarray, ids: np.ndarray) -> np.ndarray:
    order = stable_order(scores, ids)
    ranks = np.empty(len(order), dtype=int)
    ranks[order] = np.arange(len(order))
    return ranks


def ranking_diagnostics(
    raw_scores: np.ndarray,
    test_scores: np.ndarray,
    stable_ids: np.ndarray,
    *,
    batch_size: int,
    retained_mask: np.ndarray | None = None,
) -> dict[str, float]:
    raw_scores = np.asarray(raw_scores, float)
    test_scores = np.asarray(test_scores, float)
    stable_ids = np.asarray(stable_ids)
    if raw_scores.shape != test_scores.shape or raw_scores.shape != stable_ids.shape:
        raise ValueError("ranking vectors must align")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    def metrics(mask: np.ndarray) -> tuple[float, float]:
        raw_rank = _rank_vector(raw_scores[mask], stable_ids[mask])
        test_rank = _rank_vector(test_scores[mask], stable_ids[mask])
        return (
            float(spearmanr(raw_rank, test_rank).statistic),
            float(kendalltau(raw_rank, test_rank).statistic),
        )

    full_mask = np.ones(len(raw_scores), dtype=bool)
    full_spearman, full_kendall = metrics(full_mask)
    retained_mask = full_mask if retained_mask is None else np.asarray(retained_mask, bool)
    retained_spearman, retained_kendall = metrics(retained_mask)
    k = min(batch_size, len(raw_scores))
    raw_order = stable_order(raw_scores, stable_ids)
    test_order = stable_order(test_scores, stable_ids)
    raw_top = set(stable_ids[raw_order[:k]].tolist())
    test_top = set(stable_ids[test_order[:k]].tolist())
    intersection = len(raw_top & test_top)
    union = len(raw_top | test_top)
    return {
        "full_pool_spearman": full_spearman,
        "full_pool_kendall_tau": full_kendall,
        "retained_pool_spearman": retained_spearman,
        "retained_pool_kendall_tau": retained_kendall,
        "top_k_overlap": intersection / max(1, k),
        "batch_jaccard_overlap": intersection / max(1, union),
    }


def path_diagnostics(rounds: pd.DataFrame) -> dict[str, float | int | None]:
    required = {"round", "raw_selected_ids", "test_selected_ids"}
    if not required <= set(rounds.columns):
        raise ValueError("round path table is incomplete")
    ordered = rounds.sort_values("round")
    divergences = []
    cumulative_raw: set[str] = set()
    cumulative_test: set[str] = set()
    first = None
    for row in ordered.itertuples(index=False):
        raw = set(map(str, row.raw_selected_ids))
        test = set(map(str, row.test_selected_ids))
        if raw != test and first is None:
            first = int(row.round)
        cumulative_raw |= raw
        cumulative_test |= test
        union = len(cumulative_raw | cumulative_test)
        divergences.append(1.0 - len(cumulative_raw & cumulative_test) / max(1, union))
    return {
        "first_divergence_round": first,
        "cumulative_query_path_divergence_final": divergences[-1] if divergences else 0.0,
        "cumulative_query_path_divergence_auc": (
            float(np.mean(divergences)) if divergences else 0.0
        ),
    }
