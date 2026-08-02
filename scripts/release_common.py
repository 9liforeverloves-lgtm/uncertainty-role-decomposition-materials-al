"""Shared read-only authority verification for release entry points."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "locks/p1_confirmation_inference_result_lock.json").is_file():
            return candidate
    script_root = Path(__file__).resolve().parents[1]
    if (script_root / "pyproject.toml").is_file():
        return script_root
    raise RuntimeError("repository root not found; use a complete release candidate")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_authorities(root: Path) -> list[dict[str, object]]:
    lock_path = root / "locks/p1_confirmation_inference_result_lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    rows = []
    for stage, key in (("V6", "v6_files_verified_unchanged"), ("P1", "files")):
        for relative, expected in lock[key].items():
            path = root / relative
            actual = sha256(path) if path.is_file() else "MISSING"
            rows.append({"stage": stage, "path": relative, "expected": expected, "actual": actual, "passed": actual == expected})
    return rows


def assert_authorities(root: Path) -> list[dict[str, object]]:
    rows = verify_authorities(root)
    failures = [row for row in rows if not row["passed"]]
    if failures:
        raise RuntimeError(f"frozen authority mismatch: {failures}")
    return rows

