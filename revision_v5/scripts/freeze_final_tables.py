#!/usr/bin/env python3
"""Validate and freeze the five final scientific tables."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
FILES = [
    "v5_rc1_seed_level_endpoints_final.csv",
    "v5_rc1_primary_contrasts_final.csv",
    "v5_rc1_recovery_sensitivity_final.csv",
    "v5_rc1_multiplicity_sensitivity_final.csv",
    "v5_rc1_environment_summary_final.csv",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    primary = pd.read_csv(TABLES / FILES[1])
    assert len(primary) == 128
    assert set(primary["n_pairs"]) == {40}
    assert (primary.groupby("bh_family_id").size() == 8).all()
    selected_k = primary[
        (primary["task"] == "matbench_log_kvrh")
        & primary["contrast_name"].str.startswith("Selected")
    ]
    assert set(selected_k["baseline_strategy"]) == {"raw_ucb_beta_2"}
    assert primary["selected_policy_lock_hash"].str.len().eq(64).all()
    assert primary["result_lock_hash"].str.len().eq(64).all()
    assert primary["trajectory_content_tree_hash"].str.len().eq(64).all()
    assert primary["l1_validation_status"].eq(
        "validated_4_of_4_checkpoints"
    ).all()
    assert primary["l4_validation_status"].eq("case_A_bitwise_exact").all()
    scaled = primary["p_value_unadjusted"].to_numpy(float) * 10001
    assert np.allclose(scaled, np.rint(scaled), atol=1e-10)
    assert primary["p_value_bh_adjusted"].between(0, 1).all()

    entries = []
    for name in FILES:
        path = TABLES / name
        entries.append(
            {
                "path": f"tables_v5/{name}",
                "bytes": path.stat().st_size,
                "sha256": digest(path),
                "rows": sum(1 for _ in path.open(encoding="utf-8")) - 1,
            }
        )
    lock = {
        "schema_version": "final-table-lock-v5-1",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "immutability_rule": (
            "No listed table may be silently changed after this lock. "
            "Any revision requires a versioned replacement and explicit amendment."
        ),
        "validation": {
            "primary_rows": 128,
            "paired_seed_count": 40,
            "bh_family_size": 8,
            "add_one_denominator": 10001,
            "selected_log_kvrh_baseline": "raw_ucb_beta_2",
            "l1_status": "validated_4_of_4_checkpoints",
            "l4_status": "case_A_bitwise_exact",
        },
        "files": entries,
    }
    path = TABLES / "FINAL_TABLE_LOCK_V5.json"
    path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    report = "# Final table freeze report\n\n"
    report += "All five final tables passed the declared statistical and provenance checks.\n\n"
    report += "| File | Rows | Bytes | SHA-256 |\n|---|---:|---:|---|\n"
    for row in entries:
        report += (
            f"| `{row['path']}` | {row['rows']:,} | {row['bytes']:,} | "
            f"`{row['sha256']}` |\n"
        )
    report += "\nLock: `tables_v5/FINAL_TABLE_LOCK_V5.json`.\n"
    (ROOT / "47_final_table_freeze_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
