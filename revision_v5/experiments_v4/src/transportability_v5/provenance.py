from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import yaml


SCHEMA_VERSION = "transportability-schema-v2"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_relative(project_root: Path, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(project_root).resolve()).as_posix()


def stable_payload_hash(payload) -> str:
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def source_code_hashes(study_root: Path) -> dict:
    study_root = Path(study_root)
    package = study_root / "src" / "transportability_v5"
    files = sorted(package.glob("*.py"))
    if not files:
        raise FileNotFoundError(f"isolated source package is empty: {package}")
    hashes = {path.relative_to(study_root).as_posix(): sha256_file(path) for path in files}
    return {"files": hashes, "overall_sha256": stable_payload_hash(hashes)}


def read_protocol(study_root: Path) -> tuple[Path, bytes, dict]:
    path = Path(study_root) / "configs/protocol_v1.yaml"
    raw = path.read_bytes()
    payload = yaml.safe_load(raw)
    if payload.get("protocol_schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported protocol schema: {payload.get('protocol_schema_version')!r}")
    return path, raw, payload


def build_protocol_identity(project_root: Path, study_root: Path, manifest_path: Path, job_id: str, run_config: dict) -> tuple[dict, bytes]:
    project_root = Path(project_root); study_root = Path(study_root); manifest_path = Path(manifest_path)
    protocol_path, protocol_raw, protocol = read_protocol(study_root)
    analysis_plan = study_root / "docs/ANALYSIS_PLAN.md"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"job manifest missing: {manifest_path}")
    frame = pd.read_csv(manifest_path)
    rows = frame.loc[frame["job_id"] == job_id]
    if len(rows) != 1:
        raise ValueError(f"manifest must contain exactly one row for {job_id!r}; found {len(rows)}")
    row = rows.iloc[0]
    required = ("protocol_path", "protocol_sha256", "analysis_plan_sha256", "schema_version")
    missing = [key for key in required if key not in row.index or pd.isna(row[key])]
    if missing:
        raise ValueError(f"manifest row lacks provenance fields: {missing}")
    protocol_hash = sha256_bytes(protocol_raw); analysis_hash = sha256_file(analysis_plan); manifest_hash = sha256_file(manifest_path)
    expected_path = canonical_relative(project_root, protocol_path)
    if str(row["protocol_path"]) != expected_path:
        raise ValueError("manifest protocol_path mismatch")
    if str(row["protocol_sha256"]) != protocol_hash:
        raise ValueError("protocol hash mismatch: refusing to run")
    if str(row["analysis_plan_sha256"]) != analysis_hash:
        raise ValueError("analysis-plan hash mismatch: refusing to run")
    if str(row["schema_version"]) != protocol["protocol_schema_version"]:
        raise ValueError("schema-version mismatch: refusing to run")
    identity = {
        "protocol_schema_version": protocol["protocol_schema_version"],
        "protocol_path": expected_path,
        "protocol_sha256": protocol_hash,
        "analysis_plan_path": canonical_relative(project_root, analysis_plan),
        "analysis_plan_sha256": analysis_hash,
        "manifest_path": canonical_relative(project_root, manifest_path),
        "manifest_sha256": manifest_hash,
        "run_config_sha256": stable_payload_hash(run_config),
        "job_id": str(job_id),
    }
    return identity, protocol_raw


def atomic_json(path: Path, payload: dict) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def write_job_provenance(output_dir: Path, identity: dict, protocol_raw: bytes, code_hashes: dict) -> None:
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = output_dir / "protocol_snapshot.yaml"
    temporary = snapshot.with_suffix(".yaml.tmp")
    temporary.write_bytes(protocol_raw)
    os.replace(temporary, snapshot)
    if sha256_file(snapshot) != identity["protocol_sha256"]:
        raise RuntimeError("protocol snapshot hash mismatch")
    hashes_path = output_dir / "source_code_hashes.json"
    atomic_json(hashes_path, code_hashes)
    previous={}
    if (output_dir/"provenance.json").is_file():
        previous=json.loads((output_dir/"provenance.json").read_text(encoding="utf-8"))
        immutable=("protocol_schema_version","protocol_path","protocol_sha256","analysis_plan_path","analysis_plan_sha256","run_config_sha256","job_id")
        if any(previous.get(key)!=identity[key] for key in immutable): raise RuntimeError("resume provenance immutable identity mismatch")
    manifest_history=list(previous.get("manifest_sha256_history",[previous.get("manifest_sha256")] if previous.get("manifest_sha256") else []))
    if identity["manifest_sha256"] not in manifest_history: manifest_history.append(identity["manifest_sha256"])
    provenance = dict(identity)
    provenance.update({
        "protocol_snapshot_path": "protocol_snapshot.yaml",
        "protocol_snapshot_sha256": sha256_file(snapshot),
        "source_code_hashes_path": "source_code_hashes.json",
        "source_code_hashes_sha256": sha256_file(hashes_path),
        "source_code_overall_sha256": code_hashes["overall_sha256"],
        "manifest_sha256_history": manifest_history,
    })
    atomic_json(output_dir / "provenance.json", provenance)


def require_schema_v2_columns(frame: pd.DataFrame, artifact_name: str) -> None:
    required={"protocol_schema_version", "protocol_path", "protocol_sha256", "run_config_sha256", "job_id"}
    missing=required-set(frame.columns)
    if missing:
        raise ValueError(f"{artifact_name} is not a {SCHEMA_VERSION} artifact; missing {sorted(missing)}")
    if not frame["protocol_schema_version"].eq(SCHEMA_VERSION).all():
        raise ValueError(f"{artifact_name} contains a non-{SCHEMA_VERSION} row")
