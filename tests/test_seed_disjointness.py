from __future__ import annotations

import csv
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]


def test_v5_development_and_confirmation_seeds_are_disjoint() -> None:
    development = json.loads((WORKSPACE / "revision_v5/15_development_freeze_lock.json").read_text(encoding="utf-8"))
    with (WORKSPACE / "revision_v5/manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        confirmation = {int(row["seed"]) for row in csv.DictReader(handle)}
    assert set(development["seeds"]).isdisjoint(confirmation)
    assert confirmation == set(range(5000, 5040))
