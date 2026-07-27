"""V5-compatible production endpoint definitions for V6 trajectories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .canonical_adapter import CanonicalV5Adapter


CHECKPOINT_ORDER = ("initial", "25pct", "50pct", "75pct")


def campaign_mace(
    diagnostic_metrics: pd.DataFrame,
    checkpoint_rounds: dict[str, int],
) -> float:
    """Canonical L1: equal-weight MACE at V5's four checkpoint definitions."""

    if "mean_absolute_coverage_error" not in diagnostic_metrics:
        raise ValueError("diagnostic metrics lack mean_absolute_coverage_error")
    values: list[float] = []
    for label in CHECKPOINT_ORDER:
        if label not in checkpoint_rounds:
            raise ValueError(f"missing checkpoint definition: {label}")
        row = int(checkpoint_rounds[label])
        if row < 0 or row >= len(diagnostic_metrics):
            raise ValueError(f"checkpoint round is invalid for {label}")
        value = float(diagnostic_metrics.iloc[row]["mean_absolute_coverage_error"])
        if not np.isfinite(value):
            raise ValueError("checkpoint MACE must be finite")
        values.append(value)
    return float(np.mean(values))


def top1_recall_nauc(
    rounds: pd.DataFrame,
    *,
    adapter: CanonicalV5Adapter | None = None,
) -> float:
    """Canonical L4 over frozen V5 budget fractions including the initial state."""

    if not {"budget_fraction", "top1_recall"} <= set(rounds):
        raise ValueError("rounds lack budget_fraction/top1_recall")
    value = (adapter or CanonicalV5Adapter()).modules["metrics"].normalized_auc(
        rounds["budget_fraction"].to_numpy(float), rounds["top1_recall"].to_numpy(float)
    )
    if not np.isfinite(value):
        raise ValueError("L4 top-1% recall nAUC is not finite")
    return float(value)


def checkpoint_rounds_from_directory(directory: str | Path) -> dict[str, int]:
    directory = Path(directory)
    output: dict[str, int] = {}
    for label in CHECKPOINT_ORDER:
        path = directory / f"checkpoint_{label}.json"
        if not path.is_file():
            raise FileNotFoundError(f"missing checkpoint metadata: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        output[label] = int(data["acquisition_round"])
    return output


def endpoints_from_trajectory(directory: str | Path) -> dict[str, float]:
    directory = Path(directory)
    state_path = directory / "state.json"
    if not state_path.is_file():
        raise FileNotFoundError(f"missing trajectory state: {state_path}")
    diagnostic = pd.read_parquet(directory / "diagnostic_metrics.parquet")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    l4 = float(state["primary_nauc"])
    if not np.isfinite(l4):
        raise ValueError("trajectory state contains non-finite L4")
    return {
        "l1_campaign_mace": campaign_mace(diagnostic, checkpoint_rounds_from_directory(directory)),
        "l4_top1pct_recall_nauc": l4,
    }


def diagnostic_quality(
    y: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    *,
    floor: float,
    adapter: CanonicalV5Adapter | None = None,
) -> dict[str, float]:
    """Call the canonical V5 four-coverage calibration evaluator."""

    return dict((adapter or CanonicalV5Adapter()).modules["layers"].uncertainty_quality(y, mu, sigma, floor))

