from __future__ import annotations

import hashlib
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_v5_authority_hashes_unchanged() -> None:
    manifest = json.loads((WORKSPACE / "locks/v5_frozen_manifest.json").read_text(encoding="utf-8"))
    for record in manifest["files"]:
        path = WORKSPACE / record["path"]
        assert path.is_file(), record["path"]
        assert _sha256(path) == record["sha256"], record["path"]
        if record["expected_sha256"] is not None:
            assert record["sha256"] == record["expected_sha256"], record["path"]
    for record in manifest["lock_file_inventory"]:
        path = WORKSPACE / record["path"]
        assert path.is_file(), record["path"]
        assert _sha256(path) == record["sha256"], record["path"]


def test_v5_trajectory_inventory_tree_hash_unchanged() -> None:
    manifest = json.loads((WORKSPACE / "locks/v5_frozen_manifest.json").read_text(encoding="utf-8"))
    audit = manifest["trajectory_audit"]
    assert audit["tree_hash_matches"]
    assert audit["inventory_entries"] == 53760
    assert audit["trajectory_jobs"] == 3360
