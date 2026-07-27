from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


ELEMENT_PATTERN = re.compile(r"([A-Z][a-z]?)([0-9.]*)")


def load_materials_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame.rename(
        columns={"id": "material_id", "composition": "formula", "target_value": "target"}
    )
    required = {"material_id", "formula", "target"}
    if not required <= set(frame):
        raise ValueError(f"missing columns: {sorted(required - set(frame))}")
    clean = frame.loc[:, ["material_id", "formula", "target"]].dropna()
    if clean["material_id"].duplicated().any():
        raise ValueError("duplicate material_id")
    return clean.reset_index(drop=True)


def formula_features(formulas: np.ndarray) -> np.ndarray:
    rows = []
    all_elements = sorted(
        {
            element
            for formula in formulas
            for element, _ in ELEMENT_PATTERN.findall(str(formula))
        }
    )
    if not all_elements:
        raise ValueError("no parsable formulas")
    for formula in formulas:
        parsed = ELEMENT_PATTERN.findall(str(formula))
        amounts: dict[str, float] = {}
        for element, amount in parsed:
            amounts[element] = amounts.get(element, 0.0) + (float(amount) if amount else 1.0)
        total = sum(amounts.values())
        fractions = [amounts.get(element, 0.0) / total for element in all_elements]
        nonzero = np.array([value for value in amounts.values() if value > 0], float)
        rows.append(
            fractions
            + [
                total,
                float(len(amounts)),
                float(nonzero.max()),
                float(nonzero.min()),
                float(np.std(nonzero)),
            ]
        )
    return np.asarray(rows, float)


def synthetic_materials(n: int = 96, seed: int = 310) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 8))
    y = (
        1.2 * X[:, 0]
        - 0.7 * X[:, 1]
        + 0.5 * X[:, 2] ** 2
        + np.sin(X[:, 3])
        + rng.normal(0, 0.08, n)
    )
    frame = pd.DataFrame(
        {
            "material_id": [f"synthetic_{index:04d}" for index in range(n)],
            "formula": [f"H{index % 5 + 1}C{index % 7 + 1}" for index in range(n)],
            "target": y,
        }
    )
    return frame, X
