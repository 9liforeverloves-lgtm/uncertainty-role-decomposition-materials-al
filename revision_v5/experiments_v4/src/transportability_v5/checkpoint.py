from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


CHECKPOINTS = (("initial", 0.0), ("25pct", 0.25), ("50pct", 0.50), ("75pct", 0.75))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint_paths(output_dir: Path, label: str) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    return output_dir / f"checkpoint_{label}.joblib", output_dir / f"checkpoint_{label}.json"


def checkpoint_labels_present(output_dir: Path) -> set[str]:
    return {label for label, _ in CHECKPOINTS if all(path.is_file() for path in checkpoint_paths(output_dir, label))}


def write_checkpoint(model, output_dir: Path, label: str, threshold: float, realized_progress: float,
                     acquisition_round: int, queried_count: int, identity: dict) -> dict:
    model_path, metadata_path = checkpoint_paths(output_dir, label)
    if model_path.exists() or metadata_path.exists():
        if not (model_path.exists() and metadata_path.exists()):
            raise RuntimeError(f"partial checkpoint artifact for {label}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected = {"checkpoint_label": label, "checkpoint_threshold": threshold,
                    "protocol_sha256": identity["protocol_sha256"], "run_config_sha256": identity["run_config_sha256"],
                    "job_id": identity["job_id"]}
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"inconsistent existing checkpoint for {label}")
        if metadata.get("model_state_hash") != sha256_file(model_path):
            raise RuntimeError(f"checkpoint model hash mismatch for {label}")
        return metadata
    temporary = model_path.with_suffix(".joblib.tmp")
    model.save_state(temporary)
    os.replace(temporary, model_path)
    metadata = {
        "checkpoint_label": label,
        "checkpoint_threshold": float(threshold),
        "realized_campaign_progress": float(realized_progress),
        "acquisition_round": int(acquisition_round),
        "queried_count": int(queried_count),
        "model_state_hash": sha256_file(model_path),
        "protocol_sha256": identity["protocol_sha256"],
        "run_config_sha256": identity["run_config_sha256"],
        "job_id": identity["job_id"],
    }
    temporary_metadata = metadata_path.with_suffix(".json.tmp")
    temporary_metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary_metadata, metadata_path)
    return metadata


def save_reached_checkpoints(model, output_dir: Path, progress: float, acquisition_round: int,
                             queried_count: int, identity: dict) -> list[str]:
    if not 0.0 <= progress <= 1.0 + 1e-12:
        raise ValueError(f"invalid campaign progress: {progress}")
    saved = []
    for label, threshold in CHECKPOINTS:
        if progress + 1e-12 >= threshold:
            write_checkpoint(model, output_dir, label, threshold, progress, acquisition_round, queried_count, identity)
            saved.append(label)
    return saved


def assert_complete_checkpoint_set(output_dir: Path) -> None:
    expected = {label for label, _ in CHECKPOINTS}; present = checkpoint_labels_present(output_dir)
    if present != expected:
        raise RuntimeError(f"cannot mark job complete; required checkpoints missing: {sorted(expected - present)}")
