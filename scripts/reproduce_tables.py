"""Rebuild manuscript-facing tables into a caller-selected directory."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

from release_common import assert_authorities, repository_root


NAMES = ["p1_primary_table_display.csv", "p1_claim_evidence_classification.csv", "p1_final_diagnostic_summary.csv", "p1_compute_provenance_summary.csv", "p1_related_work_verified.csv"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Table rebuild; expected <2 min and <1 GiB.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = repository_root(Path(__file__).resolve().parent)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    assert_authorities(root)
    print("Expected: <2 minutes, CPU only, <1 GiB; reads frozen CSVs only.")
    if not args.verify_only:
        subprocess.run([sys.executable, str(root / "scripts/build_final_optimization_assets.py"), "--output-dir", str(output), "--report-dir", str(output / "reports"), "--lock-output", str(output / "presentation_lock.json")], cwd=root, check=True)
    for name in NAMES:
        produced = pd.read_csv(output / name)
        reference = pd.read_csv(root / "tables" / name)
        if list(produced.columns) != list(reference.columns) or len(produced) != len(reference):
            raise RuntimeError(f"table schema/row mismatch: {name}")
        pd.testing.assert_frame_equal(produced, reference, check_exact=False, rtol=1e-12, atol=1e-12)
    assert_authorities(root)
    print(f"verified {len(NAMES)} rebuilt tables")


if __name__ == "__main__":
    main()

