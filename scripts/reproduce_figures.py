"""Rebuild all P1 figures into a caller-selected directory."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd

from release_common import assert_authorities, repository_root


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="P1 figure rebuild; expected 1–5 min and <2 GiB.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = repository_root(Path(__file__).resolve().parent)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    inventory_path = output / "p1_figure_source_inventory.csv"
    assert_authorities(root)
    print("Expected: 1–5 minutes, CPU only, <2 GiB; no model jobs are run.")
    if not args.verify_only:
        subprocess.run([sys.executable, str(root / "scripts/generate_p1_confirmation_figures.py"), "--output-dir", str(output), "--inventory-output", str(inventory_path)], cwd=root, check=True)
    inventory = pd.read_csv(inventory_path)
    if inventory.figure_id.nunique() != 18 or len(inventory) != 54:
        raise RuntimeError("expected 18 figure sets in three formats")
    for row in inventory.itertuples(index=False):
        path = output / Path(row.output_file).name
        if not path.is_file() or sha(path) != row.output_hash:
            raise RuntimeError(f"figure mismatch: {path}")
    assert_authorities(root)
    print("verified 18 P1 figure sets in PDF/PNG/SVG")


if __name__ == "__main__":
    main()

