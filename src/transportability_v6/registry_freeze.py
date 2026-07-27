"""Immutable, source-addressed freeze metadata for Stage-2.5 registries."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def code_tree_sha256(root: str | Path) -> str:
    """Hash source path names and bytes in deterministic order."""

    root = Path(root)
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def current_git_commit(workspace: str | Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=Path(workspace), text=True
    ).strip()


def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def freeze_document(
    document: dict[str, Any],
    *,
    git_commit: str,
    source_hashes: dict[str, str],
    creation_time_utc: str | None = None,
) -> dict[str, Any]:
    """Attach required immutable metadata and return a canonical document."""

    payload = dict(document)
    if not payload.get("schema_version"):
        raise ValueError("registry document requires schema_version")
    if not payload.get("status"):
        raise ValueError("registry document requires status")
    payload.pop("immutable_freeze_hash", None)
    payload["creation_time_utc"] = creation_time_utc or datetime.now(timezone.utc).isoformat()
    payload["git_commit"] = str(git_commit)
    payload["source_hashes"] = dict(sorted(source_hashes.items()))
    payload["immutable_freeze_hash"] = canonical_hash(payload)
    return payload


def verify_frozen_document(document: dict[str, Any]) -> bool:
    required = {"schema_version", "creation_time_utc", "git_commit", "source_hashes", "status", "immutable_freeze_hash"}
    if not required <= set(document):
        return False
    recorded = str(document["immutable_freeze_hash"])
    candidate = dict(document)
    candidate.pop("immutable_freeze_hash", None)
    return recorded == canonical_hash(candidate)


def write_frozen_document(path: str | Path, document: dict[str, Any]) -> None:
    """Atomically replace an explicitly generated registry document."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
