"""V6 execution durability built on the authoritative V5 SQLite registry."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from .canonical_adapter import CanonicalV5Adapter


class CrashInjected(RuntimeError):
    """Intentional test-only interruption at a durable-write boundary."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class CanonicalJobRegistry:
    """Thin V6 facade around V5's legal transitions and atomic claims."""

    def __init__(self, path: str | Path, *, adapter: CanonicalV5Adapter | None = None):
        self.path = Path(path)
        self.adapter = adapter or CanonicalV5Adapter()
        self._registry = self.adapter.modules["registry"]

    def initialize(self, job_ids: list[str], manifest_sha256: str):
        if len(set(map(str, job_ids))) != len(job_ids):
            raise ValueError("job registry cannot initialize duplicate job IDs")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return self._registry.initialize(self.path, list(map(str, job_ids)), str(manifest_sha256))

    def connect(self):
        return self._registry.connect(self.path)

    def claim_next(self, connection, worker_id: str, pid: int, hostname: str):
        return self._registry.claim_next(connection, str(worker_id), int(pid), str(hostname))

    def claim_specific(self, connection, job_id: str, worker_id: str, pid: int, hostname: str):
        return self._registry.claim_specific(
            connection, str(job_id), str(worker_id), int(pid), str(hostname)
        )

    def transition(self, connection, job_id: str, target: str, payload: dict[str, Any] | None = None, **kwargs: Any):
        return self._registry.transition(connection, str(job_id), str(target), payload, **kwargs)

    def snapshot_frame(self) -> pd.DataFrame:
        connection = self.connect()
        try:
            return pd.read_sql_query("SELECT * FROM jobs ORDER BY job_id", connection)
        finally:
            connection.close()


class DurableCheckpointStore:
    """Atomic V5-checkpoint-compatible payload store with crash recovery hooks."""

    def __init__(self, output_dir: str | Path, *, adapter: CanonicalV5Adapter | None = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.adapter = adapter or CanonicalV5Adapter()
        self._checkpoint = self.adapter.modules["checkpoint"]

    @property
    def definitions(self) -> tuple[tuple[str, float], ...]:
        return tuple(self._checkpoint.CHECKPOINTS)

    def _paths(self, label: str) -> tuple[Path, Path, Path, Path]:
        if label not in {item[0] for item in self.definitions}:
            raise KeyError(f"unknown V5 checkpoint label: {label}")
        payload, metadata = self._checkpoint.checkpoint_paths(self.output_dir, label)
        return payload, metadata, payload.with_suffix(payload.suffix + ".tmp"), metadata.with_suffix(metadata.suffix + ".tmp")

    def _metadata(
        self,
        label: str,
        payload: Path,
        identity: dict[str, Any],
        *,
        realized_progress: float = 0.0,
        acquisition_round: int = -1,
        queried_count: int = 0,
    ) -> dict[str, Any]:
        """Return V5 checkpoint metadata plus V6 durability fields."""

        threshold = dict(self.definitions)[label]
        if not 0.0 <= float(realized_progress) <= 1.0 + 1e-12:
            raise ValueError("checkpoint progress must lie in [0, 1]")
        return {
            "checkpoint_label": label,
            "checkpoint_threshold": float(threshold),
            "realized_campaign_progress": float(realized_progress),
            "acquisition_round": int(acquisition_round),
            "queried_count": int(queried_count),
            "model_state_hash": sha256_file(payload),
            "protocol_sha256": identity.get("protocol_sha256"),
            "run_config_sha256": identity.get("run_config_sha256"),
            "job_id": identity.get("job_id"),
        }

    def write_payload(
        self,
        label: str,
        payload_bytes: bytes,
        identity: dict[str, Any],
        *,
        realized_progress: float = 0.0,
        acquisition_round: int = -1,
        queried_count: int = 0,
        crash_at: str | None = None,
    ) -> str:
        """Commit one checkpoint, rejecting a conflicting rerun/output overwrite."""

        final, metadata, temporary, temporary_metadata = self._paths(label)
        new_hash = hashlib.sha256(payload_bytes).hexdigest()
        if final.exists() or metadata.exists():
            if not (final.exists() and metadata.exists()):
                raise RuntimeError(f"partial committed checkpoint exists for {label}")
            old = json.loads(metadata.read_text(encoding="utf-8"))
            if old.get("model_state_hash") != sha256_file(final):
                raise RuntimeError(f"checkpoint hash mismatch for {label}")
            for key in ("protocol_sha256", "run_config_sha256", "job_id"):
                if old.get(key) != identity.get(key):
                    raise RuntimeError(f"checkpoint identity mismatch for {label}: {key}")
            if sha256_file(final) != new_hash:
                raise FileExistsError(f"refusing to overwrite checkpoint {label} with different content")
            return "existing_identical"
        if crash_at == "before_model_checkpoint_write":
            raise CrashInjected("before_model_checkpoint_write")
        temporary.write_bytes(payload_bytes)
        if sha256_file(temporary) != new_hash:
            raise RuntimeError("temporary checkpoint hash mismatch")
        document = self._metadata(
            label,
            temporary,
            identity,
            realized_progress=realized_progress,
            acquisition_round=acquisition_round,
            queried_count=queried_count,
        )
        temporary_metadata.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
        if crash_at == "after_temporary_write_before_rename":
            raise CrashInjected("after_temporary_write_before_rename")
        os.replace(temporary, final)
        os.replace(temporary_metadata, metadata)
        return "committed"

    def recover(self, identity: dict[str, Any]) -> list[str]:
        """Promote valid temporary payloads and discard only superseded temporary files."""

        actions: list[str] = []
        for label, _ in self.definitions:
            final, metadata, temporary, temporary_metadata = self._paths(label)
            if final.exists() and temporary.exists():
                temporary.unlink()
                actions.append(f"{label}:temporary_discarded_committed_exists")
            elif not final.exists() and temporary.exists():
                if not temporary.read_bytes():
                    temporary.unlink()
                    if temporary_metadata.exists():
                        temporary_metadata.unlink()
                    actions.append(f"{label}:empty_temporary_discarded")
                else:
                    if temporary_metadata.exists():
                        document = json.loads(temporary_metadata.read_text(encoding="utf-8"))
                        if document.get("model_state_hash") != sha256_file(temporary):
                            raise RuntimeError(f"temporary checkpoint hash mismatch for {label}")
                    else:
                        document = self._metadata(label, temporary, identity)
                        temporary_metadata.write_text(
                            json.dumps(document, indent=2, sort_keys=True), encoding="utf-8"
                        )
                    os.replace(temporary, final)
                    os.replace(temporary_metadata, metadata)
                    actions.append(f"{label}:temporary_promoted")
            if metadata.exists() and temporary_metadata.exists():
                temporary_metadata.unlink()
                actions.append(f"{label}:metadata_temporary_discarded")
            if final.exists() and not metadata.exists():
                document = self._metadata(label, final, identity)
                temporary_metadata.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
                os.replace(temporary_metadata, metadata)
                actions.append(f"{label}:metadata_reconstructed")
        return actions

    def last_valid_checkpoint(self) -> str | None:
        valid: list[str] = []
        for label, _ in self.definitions:
            final, metadata, _, _ = self._paths(label)
            if final.exists() and metadata.exists():
                document = json.loads(metadata.read_text(encoding="utf-8"))
                if document.get("model_state_hash") == sha256_file(final):
                    valid.append(label)
        return valid[-1] if valid else None


def atomic_write_json_no_overwrite(payload: dict[str, Any], path: str | Path) -> str:
    """Write a stable JSON artifact or reject a divergent output at the same path."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    candidate_hash = hashlib.sha256(content).hexdigest()
    if destination.exists():
        if sha256_file(destination) != candidate_hash:
            raise FileExistsError(f"refusing to overwrite committed JSON artifact: {destination}")
        return "existing_identical"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, destination)
    return "committed"
