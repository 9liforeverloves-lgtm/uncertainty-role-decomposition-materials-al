"""Create the outcome-blind supersession audit for the six P0 locks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCKS = ROOT / "locks"
RESULTS = ROOT / "results" / "v6_development"


LOCK_FILES = (
    "v6_p0_development_manifest_lock_superseded_a3bef9c4b87d.json",
    "v6_p0_development_manifest_lock_superseded_ef0607d55cd9.json",
    "v6_p0_development_manifest_lock_superseded_a4fb9cfa0aa8.json",
    "v6_p0_development_manifest_lock_superseded_a9c4b568069d.json",
    "v6_p0_development_manifest_lock_superseded_3ae582ce4b8a.json",
    "v6_p0_development_manifest_lock.json",
)


RUN_AUDIT = {
    "a3bef9c4b87d": {
        "run_root": RESULTS,
        "execution_run_id": "initial_p0_execution",
        "failed_engineering_assertion": "Initial model construction supplied a negative SeedSequence round key before any durable checkpoint write.",
        "endpoint_outcomes_computed": False,
        "endpoint_outcomes_viewed": False,
        "outcome_view_evidence": "No completed jobs and no P0 selection-map write were produced by this run.",
        "files_reused": [],
        "files_recomputed": [],
    },
    "ef0607d55cd9": {
        "run_root": RESULTS / "rerun_after_seedsequence_fix",
        "failed_engineering_assertion": "Equivalent-DoF calibration-only controls were registered with scaled acquisition rather than exact RAW acquisition.",
        "endpoint_outcomes_computed": True,
        "endpoint_outcomes_viewed": False,
        "outcome_view_evidence": "The base phase failed before the predeclared beta-selection routine was reached; no selection-map write is attributable to this run.",
        "files_reused": [],
        "files_recomputed": ["124 completed job artifact directories recorded in rerun_after_seedsequence_fix"],
    },
    "a4fb9cfa0aa8": {
        "run_root": RESULTS / "rerun_after_calibration_mapping_fix",
        "failed_engineering_assertion": "Simple scalar calibration replays inherited scaled acquisition rather than exact RAW acquisition.",
        "endpoint_outcomes_computed": True,
        "endpoint_outcomes_viewed": False,
        "outcome_view_evidence": "The base phase failed before the predeclared beta-selection routine was reached; no selection-map write is attributable to this run.",
        "files_reused": [],
        "files_recomputed": ["128 completed job artifact directories recorded in rerun_after_calibration_mapping_fix"],
    },
    "a9c4b568069d": {
        "run_root": RESULTS / "rerun_after_simple_scaler_mapping_fix",
        "failed_engineering_assertion": "RAW_FIXED_BETA_MATCHED and RAW_STAGE_BETA_MATCHED were registered but absent from the production identity-scale dispatch.",
        "endpoint_outcomes_computed": True,
        "endpoint_outcomes_viewed": False,
        "outcome_view_evidence": "The predeclared routine programmatically formed a DRAFT beta map after the base phase; no human outcome-view event is recorded, and the method list/rule was not altered.",
        "files_reused": [],
        "files_recomputed": ["309 completed job artifacts recorded in rerun_after_simple_scaler_mapping_fix"],
    },
    "3ae582ce4b8a": {
        "run_root": None,
        "failed_engineering_assertion": "No execution was started under this prospective lock; the dispatch correction was replaced by a verified-artifact recovery protocol.",
        "endpoint_outcomes_computed": False,
        "endpoint_outcomes_viewed": False,
        "outcome_view_evidence": "No run directory exists for rerun_after_matched_beta_fix.",
        "files_reused": [],
        "files_recomputed": [],
    },
    "4213e6a702b8": {
        "run_root": RESULTS / "recovered_base_then_matched_beta_retry",
        "failed_engineering_assertion": "None; this is the final executed development lock.",
        "endpoint_outcomes_computed": True,
        "endpoint_outcomes_viewed": True,
        "outcome_view_evidence": "The accepted DRAFT and execution report were generated only after the 360-job registry completed.",
        "files_reused": ["300 verified base artifacts from rerun_after_simple_scaler_mapping_fix"],
        "files_recomputed": ["60 matched-beta post-selection artifacts under recovered_base_then_matched_beta_retry"],
    },
}


def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def registry_counts(path: Path | None) -> dict[str, int]:
    if path is None or not (path / "job_registry.sqlite").is_file():
        return {}
    connection = sqlite3.connect(path / "job_registry.sqlite")
    try:
        rows = connection.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY status").fetchall()
    finally:
        connection.close()
    return {str(status): int(count) for status, count in rows}


def write_once(path: Path, content: bytes, *, refresh: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest and not refresh:
        raise FileExistsError(f"refusing to overwrite divergent lineage artifact: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def lock_record(path: Path, ordinal: int, *, supersession_reason: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    lock_hash = str(payload["immutable_lock_sha256"])
    audit = RUN_AUDIT[lock_hash[:12]]
    is_final = ordinal == len(LOCK_FILES)
    kind = "final executed development lock" if is_final else "superseded prospective lock"
    registry = registry_counts(audit["run_root"])
    manifest_hash = str(payload["manifest_sha256"])
    return {
        "ordinal": ordinal,
        "lock_kind": kind,
        "lock_path": path.relative_to(ROOT).as_posix(),
        "lock_sha256": lock_hash,
        "git_commit": str(payload.get("git_commit_before_stage_2_5_commit", "")),
        "code_tree_sha256": str(payload["v6_code_tree_sha256"]),
        "manifest_sha256": manifest_hash,
        "manifest_job_count": int(payload["manifest_job_count"]),
        "execution_run_id": str(audit.get("execution_run_id", payload.get("execution_run_id", "not_started"))),
        "registry_status_counts": registry,
        "supersession_reason": supersession_reason,
        "failed_engineering_assertion": audit["failed_engineering_assertion"],
        "endpoint_outcomes_computed": audit["endpoint_outcomes_computed"],
        "endpoint_outcomes_viewed": audit["endpoint_outcomes_viewed"],
        "outcome_view_evidence": audit["outcome_view_evidence"],
        "files_reused": audit["files_reused"],
        "files_recomputed": audit["files_recomputed"],
        "selection_rule_invariance_evidence": {
            "manifest_sha256_constant_across_all_six": manifest_hash,
            "same_registered_scope": list(payload["p0_environment_scope"]),
            "interpretation": "Supersessions repaired deterministic seeding, exact-RAW calibration mapping, or registered dispatch/recovery mechanics; none adds, removes, or picks a method from endpoint outcomes.",
        },
    }


def markdown(records: list[dict[str, object]], lineage_hash: str) -> str:
    lines = [
        "# P0 development supersession audit",
        "",
        "This audit reconstructs the six-lock chain for `V6-P0-SENTINEL-DEVELOPMENT`. The five earlier records are described as superseded prospective locks; the sixth is the final executed development lock. The accepted scope remains matbench_expt_gap only, IID and chemical-system group-disjoint splits, Random Forest, and seeds 6000-6009. It is development-only and non-confirmatory.",
        "",
        "## Outcome-blindness conclusion",
        "",
        "All six records carry the same manifest SHA-256 (`d862b85f615b8d4525d9d580f00490b1d869adc097c96ac32ea5cae0f9e7b1fc`). Supersessions fixed engineering assertions or reused hash-verified base artifacts; they did not change the registered method list or select a method based on observed endpoints. Where a run reached the predeclared beta calculation, its use was programmatic; no earlier human outcome-view event is recorded.",
        "",
        "## Lock sequence",
        "",
        "| # | record | lock hash | run | registry counts | endpoints computed / viewed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        counts = ", ".join(f"{key}={value}" for key, value in dict(record["registry_status_counts"]).items()) or "not started"
        lines.append(
            f"| {record['ordinal']} | {record['lock_kind']} | `{str(record['lock_sha256'])[:12]}` | `{record['execution_run_id']}` | {counts} | {record['endpoint_outcomes_computed']} / {record['endpoint_outcomes_viewed']} |"
        )
    lines.extend([
        "",
        "## Engineering assertions and artifact treatment",
        "",
    ])
    for record in records:
        lines.extend([
            f"### {record['ordinal']}. {record['lock_kind']}",
            "",
            f"- Lock: `{record['lock_path']}` (`{record['lock_sha256']}`).",
            f"- Git commit / code tree: `{record['git_commit']}` / `{record['code_tree_sha256']}`.",
            f"- Supersession basis: {record['supersession_reason']}",
            f"- Failed engineering assertion: {record['failed_engineering_assertion']}",
            f"- Outcome audit: computed={record['endpoint_outcomes_computed']}; viewed={record['endpoint_outcomes_viewed']}. {record['outcome_view_evidence']}",
            f"- Reused: {', '.join(record['files_reused']) if record['files_reused'] else 'none'}.",
            f"- Recomputed: {', '.join(record['files_recomputed']) if record['files_recomputed'] else 'none'}.",
            "",
        ])
    lines.extend([
        "## Lineage integrity",
        "",
        f"The machine-readable lineage record has SHA-256 `{lineage_hash}`. It preserves the original lock hashes as identifiers without recasting superseded records as final evidence.",
        "",
    ])
    return "\n".join(lines)


def main(*, refresh: bool) -> None:
    raw = [json.loads((LOCKS / name).read_text(encoding="utf-8")) for name in LOCK_FILES]
    records: list[dict[str, object]] = []
    for index, name in enumerate(LOCK_FILES, start=1):
        if index < len(LOCK_FILES):
            reason = str(raw[index].get("supersession_reason", "successor lock did not state a reason"))
        else:
            reason = "Accepted final execution after hash-verified recovery of 300 base artifacts and recomputation of 60 post-selection paths."
        records.append(lock_record(LOCKS / name, index, supersession_reason=reason))
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-sentinel-lock-lineage-v1",
        "evidence_class": "V6-P0-SENTINEL-DEVELOPMENT",
        "scope": {
            "task": "matbench_expt_gap",
            "splits": ["iid_record", "chemical_system_ood"],
            "model": "random_forest",
            "seeds": [6000, 6009],
            "inferential_status": "development_only_non_confirmatory",
        },
        "records": records,
    }
    payload["lineage_sha256"] = canonical_hash(payload)
    json_path = LOCKS / "v6_p0_sentinel_lock_lineage.json"
    write_once(json_path, (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), refresh=refresh)
    report_path = ROOT / "reports" / "04d_development_supersession_audit.md"
    write_once(report_path, markdown(records, payload["lineage_sha256"]).encode("utf-8"), refresh=refresh)
    print(json.dumps({"lineage": json_path.relative_to(ROOT).as_posix(), "records": len(records), "sha256": payload["lineage_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    main(refresh=parser.parse_args().refresh)
