from __future__ import annotations

import csv
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]

ENDPOINT_REQUIRED = {
    "job_id", "task", "split", "model", "strategy", "seed", "environment",
    "l1_campaign_mace", "l4_top1pct_recall_nauc", "analysis_classification",
}
CONTRAST_REQUIRED = {
    "task", "environment", "contrast_name", "baseline_strategy", "test_strategy",
    "endpoint", "n_pairs", "mean_diff", "ci_lower", "ci_upper",
    "p_value_unadjusted", "p_value_bh_adjusted", "evidence_label",
}


def _header_and_rows(path: Path) -> tuple[set[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = sum(1 for _ in reader)
        return set(reader.fieldnames or []), rows


def test_v5_seed_level_endpoint_schema() -> None:
    columns, rows = _header_and_rows(WORKSPACE / "revision_v5/tables_v5/v5_rc1_seed_level_endpoints_final.csv")
    assert ENDPOINT_REQUIRED <= columns
    assert rows == 3360


def test_v5_primary_contrast_schema() -> None:
    columns, rows = _header_and_rows(WORKSPACE / "revision_v5/tables_v5/v5_rc1_primary_contrasts_final.csv")
    assert CONTRAST_REQUIRED <= columns
    assert rows == 128
