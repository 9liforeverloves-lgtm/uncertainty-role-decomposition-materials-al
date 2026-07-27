from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]


def _ids(path: Path) -> tuple[list[str], Counter[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row["job_id"] for row in rows], Counter(row.get("status", "") for row in rows)


def test_confirmation_manifest_and_registry_are_one_to_one() -> None:
    manifest_ids, _ = _ids(WORKSPACE / "revision_v5/manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv")
    registry_ids, statuses = _ids(WORKSPACE / "revision_v5/results_v4/confirmation/registry_snapshot.csv")
    assert len(manifest_ids) == len(set(manifest_ids)) == 3360
    assert len(registry_ids) == len(set(registry_ids)) == 3360
    assert set(manifest_ids) == set(registry_ids)
    assert statuses == Counter({"COMPLETED": 3354, "RECOVERED": 6})
