from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


STAGES = (
    ("0_25", 0.0, 0.25),
    ("25_50", 0.25, 0.50),
    ("50_75", 0.50, 0.75),
    ("75_100", 0.75, 1.0),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_development_only(frame: pd.DataFrame) -> None:
    required = {"environment", "budget_fraction", "effective_beta", "seed"}
    if not required <= set(frame.columns):
        raise ValueError(f"missing columns: {sorted(required - set(frame.columns))}")
    seeds = set(frame["seed"].astype(int))
    forbidden = set(range(5000, 5040)) | set(range(7000, 7040))
    collision = seeds & forbidden
    if collision:
        raise ValueError(f"forbidden V5/confirmation seed leakage: {sorted(collision)}")
    unexpected = seeds - set(range(6000, 6010))
    if unexpected:
        raise ValueError(f"non-development seeds: {sorted(unexpected)}")
    if not np.isfinite(frame["effective_beta"]).all() or np.any(frame["effective_beta"] < 0):
        raise ValueError("effective_beta must be finite and nonnegative")


def environment_balanced_median(frame: pd.DataFrame) -> float:
    per_environment = frame.groupby("environment", sort=True)["effective_beta"].median()
    if per_environment.empty:
        raise ValueError("no development effective-beta values")
    return float(per_environment.median())


def fit_matched_beta_map(frame: pd.DataFrame) -> dict[str, object]:
    validate_development_only(frame)
    fixed = environment_balanced_median(frame)
    stagewise: dict[str, float] = {}
    fallbacks: list[str] = []
    for name, lower, upper in STAGES:
        budget = frame["budget_fraction"].astype(float)
        upper_match = budget <= upper if name == "75_100" else budget < upper
        subset = frame[(budget >= lower) & upper_match]
        if subset.empty:
            stagewise[name] = fixed
            fallbacks.append(name)
        else:
            stagewise[name] = environment_balanced_median(subset)
    return {
        "method": "environment_balanced_median_of_environment_medians",
        "fixed_matched_beta": fixed,
        "stage_matched_beta": stagewise,
        "development_seeds": sorted(set(frame["seed"].astype(int))),
        "confirmation_seeds_forbidden": list(range(7000, 7040)),
        "v5_seeds_forbidden": list(range(5000, 5040)),
        "missing_stage_fallback": "fixed_matched_beta",
        "stages_using_fallback": fallbacks,
    }


def beta_for_budget(selection: dict[str, object], budget_fraction: float) -> float:
    if not 0.0 <= budget_fraction <= 1.0:
        raise ValueError("budget_fraction must lie in [0, 1]")
    for name, lower, upper in STAGES:
        if lower <= budget_fraction < upper or (
            name == "75_100" and budget_fraction == upper
        ):
            return float(selection["stage_matched_beta"][name])
    raise ValueError("budget_fraction must lie in [0, 1]")


def freeze_selection_map(
    selection: dict[str, object],
    output: str | Path,
    *,
    source_files: list[str | Path],
) -> None:
    output = Path(output)
    payload = {
        "status": "FROZEN_BEFORE_CONFIRMATION_OUTCOMES",
        "selection": selection,
        "source_files": [
            {"path": str(Path(path)), "sha256": sha256(Path(path))} for path in source_files
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["selection_map_sha256"] = hashlib.sha256(canonical).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


def verify_selection_map(path: str | Path) -> bool:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    recorded = payload.pop("selection_map_sha256", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return recorded == hashlib.sha256(canonical).hexdigest()
