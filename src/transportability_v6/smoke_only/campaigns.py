"""Reduced random-partition campaign used only for Stage-2 engineering smoke."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..calibration import fit_scalar_nll, fit_selected_cs_equivalent_dof
from ..strategies import STRATEGIES, score_round
from . import SMOKE_LABEL, require_smoke_context
from .surrogates import RandomForestEnsemble


@dataclass(frozen=True)
class CampaignConfig:
    strategy: str
    seed: int
    initial_count: int = 12
    batch_size: int = 3
    max_queries: int = 12
    beta_raw: float = 1.0
    n_estimators: int = 24
    min_samples_leaf: int = 2
    sigma_floor: float = 1e-8
    evidence_class: str = SMOKE_LABEL


def _partitions(n: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.random.default_rng(seed).permutation(n)
    source_end = max(16, int(round(0.25 * n)))
    diagnostic_count = max(8, int(round(0.15 * n)))
    if n - source_end - diagnostic_count < 20:
        raise ValueError("smoke dataset too small")
    return (
        np.sort(order[:source_end]),
        np.sort(order[source_end:-diagnostic_count]),
        np.sort(order[-diagnostic_count:]),
    )


def _top_recall(y: np.ndarray, queried: set[int], selectable: np.ndarray) -> float:
    k = max(1, int(np.ceil(0.01 * len(selectable))))
    top = selectable[np.lexsort((selectable, -y[selectable]))[:k]]
    return len(set(map(int, top)) & queried) / k


def _l4(budget: list[float], recall: list[float]) -> float:
    x = np.asarray(budget, float)
    y = np.asarray(recall, float)
    if len(x) < 2 or x[-1] <= x[0]:
        return float("nan")
    return float(np.trapezoid(y, x) / (x[-1] - x[0]))


def run_campaign(
    X: np.ndarray,
    y: np.ndarray,
    ids: np.ndarray,
    config: CampaignConfig,
) -> dict[str, object]:
    """Run the explicitly labelled non-inferential simplified campaign."""

    require_smoke_context(config.evidence_class)
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    ids = np.asarray(ids).astype(str)
    if X.ndim != 2 or y.shape != (len(X),) or ids.shape != (len(X),):
        raise ValueError("campaign arrays must align")
    if len(np.unique(ids)) != len(ids):
        raise ValueError("duplicate material IDs")
    if config.strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {config.strategy}")
    spec = STRATEGIES[config.strategy]
    source, selectable, diagnostic = _partitions(len(y), config.seed)
    initial_count = min(config.initial_count, len(source))
    initial = np.sort(
        np.random.default_rng(config.seed + 1).choice(source, size=initial_count, replace=False)
    )
    training = list(map(int, initial))
    queried_selectable: set[int] = set()
    traces: list[dict[str, object]] = []
    budgets = [0.0]
    recalls = [_top_recall(y, queried_selectable, selectable)]
    round_index = 0
    while len(queried_selectable) < min(config.max_queries, len(selectable)):
        candidates = np.array(sorted(set(map(int, selectable)) - queried_selectable), dtype=int)
        model_seed = int(np.random.SeedSequence([config.seed, round_index, 401]).generate_state(1)[0])
        model = RandomForestEnsemble(config.n_estimators, config.min_samples_leaf).fit(
            X[training], y[training], seed=model_seed, stable_ids=ids[training]
        )
        mean, raw_sigma = model.predict_mean_std(X[candidates])
        oob_mean, oob_sigma, oob_count = model.oob_mean_std()
        valid = np.isfinite(oob_mean) & np.isfinite(oob_sigma) & (oob_count >= 3)
        if valid.sum() >= 3:
            global_fit = fit_scalar_nll(
                model.y_train_[valid] - oob_mean[valid], oob_sigma[valid], floor=config.sigma_floor
            )
            global_scale = global_fit.scale
        else:
            global_scale = 1.0
        if valid.sum() >= 20:
            selected_fit = fit_selected_cs_equivalent_dof(
                model.y_train_[valid] - oob_mean[valid], oob_sigma[valid], floor=config.sigma_floor
            )
            selected_sigma = selected_fit.transform(raw_sigma, floor=config.sigma_floor)
            candidate_scale = selected_sigma / np.maximum(raw_sigma, config.sigma_floor)
        else:
            candidate_scale = np.ones(len(candidates))
        scored = score_round(
            spec,
            mean,
            raw_sigma,
            ids[candidates],
            beta_raw=config.beta_raw,
            global_scale=global_scale,
            candidate_scale=candidate_scale,
            sigma_floor=config.sigma_floor,
        )
        batch_count = min(config.batch_size, config.max_queries - len(queried_selectable), len(candidates))
        chosen_positions = np.asarray(scored["stable_order"][:batch_count], int)
        chosen = candidates[chosen_positions]
        traces.append(
            {
                "round": round_index,
                "initial_labeled_ids": ids[initial].tolist(),
                "training_ids_before": ids[np.asarray(training, int)].tolist(),
                "candidate_ids": ids[candidates].tolist(),
                "acquisition_scores": np.asarray(scored["scores"], float).tolist(),
                "stable_order_ids": ids[candidates][np.asarray(scored["stable_order"], int)].tolist(),
                "selected_batch_ids": ids[chosen].tolist(),
                "evaluation_sigma": np.asarray(scored["evaluation_sigma"], float).tolist(),
                "raw_sigma": np.asarray(scored["raw_sigma_floored"], float).tolist(),
                "global_scale": float(global_scale),
            }
        )
        training.extend(map(int, chosen))
        queried_selectable.update(map(int, chosen))
        budgets.append(len(queried_selectable) / config.max_queries)
        recalls.append(_top_recall(y, queried_selectable, selectable))
        round_index += 1
    return {
        "validation_label": SMOKE_LABEL,
        "config": asdict(config),
        "source_ids": ids[source].tolist(),
        "selectable_ids": ids[selectable].tolist(),
        "diagnostic_ids": ids[diagnostic].tolist(),
        "initial_labeled_ids": ids[initial].tolist(),
        "rounds": traces,
        "queried_trajectory": [candidate for trace in traces for candidate in trace["selected_batch_ids"]],
        "round_count": len(traces),
        "budget_fraction": budgets,
        "top1_recall": recalls,
        "l4_top1_recall_nauc": _l4(budgets, recalls),
    }

