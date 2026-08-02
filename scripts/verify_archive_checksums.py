"""Verify that SHA256SUMS covers every other regular release file exactly once."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    checksum_path = root / "SHA256SUMS"
    records: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if relative in records:
            raise RuntimeError(f"duplicate checksum entry: {relative}")
        records[relative] = expected
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    missing = sorted(actual - records.keys())
    extra = sorted(records.keys() - actual)
    mismatches = sorted(
        relative for relative in actual & records.keys()
        if sha256(root / relative) != records[relative]
    )
    if missing or extra or mismatches:
        raise RuntimeError({"missing": missing, "extra": extra, "mismatches": mismatches})
    print(f"PASS: {len(records)} files covered; zero checksum mismatches")


if __name__ == "__main__":
    main()
