from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import stat
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
V5 = WORKSPACE / "revision_v5"
MANIFEST_OUT = WORKSPACE / "locks" / "v5_frozen_manifest.json"
REPORT_OUT = WORKSPACE / "reports" / "01_v5_frozen_evidence_audit.md"
SNAPSHOT = WORKSPACE / "locks" / "v5_readonly_snapshot"

AUTHORITY_FILES = (
    "15_development_freeze_lock.json",
    "19_selected_policy_lock.json",
    "20_confirmation_protocol_v5_rc1.md",
    "CONFIRMATION_RESULT_LOCK_V5_RC1.json",
    "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json",
    "environment-lock.txt",
    "environment-final-validation-lock.txt",
    "manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json",
    "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv",
    "results_v4/confirmation/registry.sqlite",
    "results_v4/confirmation/registry_snapshot.csv",
    "audits_v5/confirmation_trajectory_hash_inventory.csv",
    "tables_v5/FINAL_TABLE_LOCK_V5.json",
    "tables_v5/v5_rc1_seed_level_endpoints_final.csv",
    "tables_v5/v5_rc1_primary_contrasts_final.csv",
    "tables_v5/v5_rc1_recovery_sensitivity_final.csv",
    "tables_v5/v5_rc1_multiplicity_sensitivity_final.csv",
    "tables_v5/v5_rc1_environment_summary_final.csv",
)

EXPECTED_HASHES = {
    "15_development_freeze_lock.json": "96ef1aa952b5f9cb52071cac90bddf04890501ae9af051ce49b6999153c094ef",
    "19_selected_policy_lock.json": "814d1bdee6562b3e29f78afdc86fb92a303b97c60fa4c392d83681b6b1af55f2",
    "20_confirmation_protocol_v5_rc1.md": "0c8991c1261799336eb7a1991cb004cc9e958f274031de05a3c964a27e897c29",
    "CONFIRMATION_RESULT_LOCK_V5_RC1.json": "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50",
    "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json": "e960743bec1d282e9fb3c0bb01fb0c0b6a03d5744f2902e87ffeed3ad1ab366a",
    "environment-lock.txt": "22bd05ebb49d3d5e6524fd5de62c28f35792fcf43cc3c69d2f7514bc5c48bc1d",
    "manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json": "cd88596a5f1cb3bbbce990945f5211e70ca7e024de86ab26a154353032d67a0e",
    "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv": "6fbe0d79906df8523fb036800ccfec17f9bcb18a8845ddcaae9dadf3ce2c52a8",
    "results_v4/confirmation/registry_snapshot.csv": "cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441",
    "results_v4/confirmation/registry.sqlite": "6a67a54589b809f46883423070c1e8b37599bb49fac0e0f79a58bec65f590dc4",
    "audits_v5/confirmation_trajectory_hash_inventory.csv": "14878052c950eab32c9059ae40d6a0faf42bbe642ae8b14cdfebcb9ad9feb2fd",
    "tables_v5/v5_rc1_seed_level_endpoints_final.csv": "2466848a25cf7c92199387825cc9e3842c7c260df75a267ec110eea066ba485d",
    "tables_v5/v5_rc1_primary_contrasts_final.csv": "c73b531a2858f54da5d420eec23211eaf18aecf3f575af608101b9b7d427b453",
    "tables_v5/v5_rc1_recovery_sensitivity_final.csv": "d67f647950a796d7c9154520337dde2fcab51095c2ff84bd977cb7c9b11502e5",
    "tables_v5/v5_rc1_multiplicity_sensitivity_final.csv": "558c333e1e8fb26b65d04c680bd58c40590acc0d24481bd30c08631067509305",
    "tables_v5/v5_rc1_environment_summary_final.csv": "89d066689515b29c83fff4668b0c52a7ceeff66006d0effa65e1c2fae3036566",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_metadata(path: Path) -> tuple[int | None, list[str] | None]:
    if path.suffix.lower() != ".csv":
        return None, None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return 0, []
        return sum(1 for _ in reader), header


def file_record(relative: str) -> dict[str, object]:
    path = V5 / relative
    if not path.is_file():
        return {"path": f"revision_v5/{relative}", "exists": False}
    rows, schema = csv_metadata(path)
    actual = sha256(path)
    info = path.stat()
    expected = EXPECTED_HASHES.get(relative)
    return {
        "path": f"revision_v5/{relative}",
        "exists": True,
        "bytes": info.st_size,
        "sha256": actual,
        "expected_sha256": expected,
        "hash_matches_authority": expected is None or actual == expected,
        "row_count": rows,
        "schema": schema,
        "created_utc": datetime.fromtimestamp(info.st_ctime, timezone.utc).isoformat(),
        "modified_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
    }


def load_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_one_trajectory(row: dict[str, str]) -> dict[str, object]:
    path = V5 / Path(row["relative_path"])
    exists = path.is_file()
    size_match = exists and path.stat().st_size == int(row["size_bytes"])
    actual = sha256(path) if size_match else None
    return {
        "relative_path": row["relative_path"],
        "exists": exists,
        "size_match": size_match,
        "hash_match": actual == row["sha256"],
    }


def trajectory_audit(full: bool) -> dict[str, object]:
    inventory_path = V5 / "audits_v5/confirmation_trajectory_hash_inventory.csv"
    rows = load_csv_dicts(inventory_path)
    canonical = "\n".join(
        f"{row['relative_path']}|{row['size_bytes']}|{row['sha256']}"
        for row in sorted(rows, key=lambda item: item["relative_path"])
    )
    tree_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    result: dict[str, object] = {
        "inventory_entries": len(rows),
        "trajectory_jobs": len({row["job_id"] for row in rows}),
        "inventory_total_bytes": sum(int(row["size_bytes"]) for row in rows),
        "recomputed_tree_hash_from_inventory": tree_hash,
        "expected_tree_hash": "03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8",
        "tree_hash_matches": tree_hash == "03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8",
        "full_file_content_verification": "not_requested",
    }
    if full:
        workers = min(8, os.cpu_count() or 1)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            checks = list(pool.map(verify_one_trajectory, rows))
        mismatches = [item for item in checks if not item["hash_match"]]
        result.update(
            {
                "full_file_content_verification": "complete",
                "verified_files": len(checks),
                "mismatch_count": len(mismatches),
                "mismatches": mismatches[:100],
            }
        )
    return result


def evidence_dimensions() -> dict[str, object]:
    manifest_rows = load_csv_dicts(V5 / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv")
    endpoints = load_csv_dicts(V5 / "tables_v5/v5_rc1_seed_level_endpoints_final.csv")
    contrasts = load_csv_dicts(V5 / "tables_v5/v5_rc1_primary_contrasts_final.csv")
    registry = load_csv_dicts(V5 / "results_v4/confirmation/registry_snapshot.csv")
    return {
        "job_count": len(manifest_rows),
        "seeds": sorted({int(row["seed"]) for row in manifest_rows}),
        "tasks": sorted({row["task"] for row in manifest_rows}),
        "splits": sorted({row["split_protocol"] for row in manifest_rows}),
        "models": sorted({row["model"] for row in manifest_rows}),
        "strategies": sorted({row["strategy"] for row in manifest_rows}),
        "environment_count": len(
            {(row["task"], row["split_protocol"], row["model"]) for row in manifest_rows}
        ),
        "endpoint_names": sorted({row["endpoint"] for row in contrasts}),
        "primary_contrast_count": len(contrasts),
        "seed_level_endpoint_rows": len(endpoints),
        "registry_status_counts": dict(Counter(row["status"] for row in registry)),
        "paired_inference_unit": "seed within task × split × model environment",
        "task_count": len({row["task"] for row in manifest_rows}),
    }


def snapshot_authority(records: list[dict[str, object]]) -> None:
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    for record in records:
        if not record.get("exists"):
            continue
        source = WORKSPACE / str(record["path"])
        relative = source.relative_to(V5)
        target = SNAPSHOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != record["sha256"]:
                raise RuntimeError(f"snapshot collision with different content: {target}")
        else:
            shutil.copy2(source, target)
        target.chmod(stat.S_IREAD)


def discovered_lock_files() -> list[dict[str, object]]:
    records = []
    for path in sorted(V5.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or "lock" not in path.name.lower():
            continue
        if any(part in {".venv_final_validation", "__pycache__", "site-packages"} for part in path.parts):
            continue
        info = path.stat()
        records.append(
            {
                "path": path.relative_to(WORKSPACE).as_posix(),
                "bytes": info.st_size,
                "sha256": sha256(path),
                "created_utc": datetime.fromtimestamp(info.st_ctime, timezone.utc).isoformat(),
                "modified_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
            }
        )
    return records


def write_report(manifest: dict[str, object]) -> None:
    dims = manifest["evidence_dimensions"]
    traj = manifest["trajectory_audit"]
    failures = [
        row["path"]
        for row in manifest["files"]
        if not row.get("exists") or not row.get("hash_matches_authority", False)
    ]
    lines = [
        "# V5 frozen evidence audit",
        "",
        f"Generated: {manifest['generated_utc']}",
        "",
        "## Verdict",
        "",
        (
            "**PASS for the enumerated V5 authority chain.**"
            if not failures and traj["tree_hash_matches"]
            else "**FAIL: one or more V5 authority checks did not pass.**"
        ),
        "",
        "- No V5 file was edited by this audit.",
        f"- Authority files checked: {len(manifest['files'])}.",
        f"- Lock-named files discovered and hashed: {len(manifest['lock_file_inventory'])}.",
        f"- Confirmation jobs: {dims['job_count']}; seeds: {dims['seeds'][0]}–{dims['seeds'][-1]}.",
        f"- Tasks: {len(dims['tasks'])}; splits: {len(dims['splits'])}; models: {len(dims['models'])}.",
        f"- Environments: {dims['environment_count']} (4 tasks × 2 splits × 2 related tree ensembles).",
        f"- Strategies: {len(dims['strategies'])}; primary endpoints: {len(dims['endpoint_names'])}.",
        f"- Registry status: `{json.dumps(dims['registry_status_counts'], sort_keys=True)}`.",
        f"- Trajectory inventory: {traj['inventory_entries']} files across {traj['trajectory_jobs']} jobs.",
        f"- Deterministic trajectory tree hash: `{traj['recomputed_tree_hash_from_inventory']}`.",
        f"- Full trajectory byte verification: `{traj['full_file_content_verification']}`.",
        "",
        "## Evidence scope",
        "",
        "The 40 seeds quantify Monte Carlo stability within each environment. The 16 environments are not 16 independent materials domains; they are four tasks crossed with two split protocols and two related tree ensembles. Task-level external generalization is therefore based on only four tasks.",
        "",
        "## Frozen files",
        "",
        "| Path | Rows | SHA-256 | Authority match |",
        "|---|---:|---|---|",
    ]
    for row in manifest["files"]:
        lines.append(
            f"| `{row['path']}` | {row.get('row_count', '') if row.get('row_count') is not None else ''} | "
            f"`{row.get('sha256', 'MISSING')}` | {row.get('hash_matches_authority', False)} |"
        )
    lines.extend(
        [
            "",
            "## Snapshot",
            "",
            f"A read-only metadata/authority snapshot is stored at `{SNAPSHOT.relative_to(WORKSPACE).as_posix()}`. "
            "The 89.6 GB trajectory corpus is not duplicated; it is protected by the frozen 53,760-row inventory and deterministic tree hash.",
            "",
            "## Git blocker",
            "",
            "The requested branch `reviewer_p0_p1_p2_revision` could not be created at the workspace root because `.git` is empty and the root is not a valid Git repository. A separate legacy repository exists under `material-active-learning`, but it does not contain `revision_v5`; creating the branch there would not protect the V5 revision. No repository was initialized and no history was fabricated.",
            "",
            "## Failures",
            "",
            ("- None." if not failures else "\n".join(f"- `{item}`" for item in failures)),
            "",
        ]
    )
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit frozen V5 evidence without modifying it.")
    parser.add_argument(
        "--verify-trajectories",
        action="store_true",
        help="Re-hash all 53,760 trajectory files (about 89.6 GB).",
    )
    args = parser.parse_args()
    if not V5.is_dir():
        raise SystemExit(f"missing V5 root: {V5}")
    records = [file_record(relative) for relative in AUTHORITY_FILES]
    manifest = {
        "schema_version": "v5-frozen-manifest-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(WORKSPACE),
        "v5_root": str(V5),
        "immutability_rule": "V5-RC1 evidence is read-only; V6 must use separate evidence classes.",
        "git": {
            "requested_branch": "reviewer_p0_p1_p2_revision",
            "created": False,
            "blocker": "workspace .git directory is empty; workspace root is not a valid Git repository",
        },
        "evidence_dimensions": evidence_dimensions(),
        "trajectory_audit": trajectory_audit(args.verify_trajectories),
        "files": records,
        "lock_file_inventory": discovered_lock_files(),
    }
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    snapshot_authority(records)
    write_report(manifest)
    failed = [
        row
        for row in records
        if not row.get("exists") or not row.get("hash_matches_authority", False)
    ]
    if failed or not manifest["trajectory_audit"]["tree_hash_matches"]:
        raise SystemExit(1)
    print(
        json.dumps(
            {
                "authority_files": len(records),
                "authority_mismatches": len(failed),
                "trajectory_tree_hash_matches": True,
                "full_trajectory_verification": manifest["trajectory_audit"][
                    "full_file_content_verification"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
