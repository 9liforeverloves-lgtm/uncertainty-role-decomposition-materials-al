from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .campaigns import CampaignConfig, SMOKE_LABEL, run_campaign
from .data import formula_features, load_materials_csv, synthetic_materials
from .provenance import atomic_json, sha256
from .canonical_adapter import CanonicalV5Adapter
from .development import (
    execute_p0_development,
    generate_p0_manifest,
    reissue_p0_manifest_lock,
    selection_stability_summary,
)


WORKSPACE = Path(__file__).resolve().parents[2]


def _resolve_data(job: dict[str, object]) -> tuple[object, np.ndarray]:
    if job["dataset_kind"] == "synthetic":
        return synthetic_materials(int(job["sample_count"]), int(job["data_seed"]))
    path = WORKSPACE / str(job["data_path"])
    frame = load_materials_csv(path)
    count = min(int(job["sample_count"]), len(frame))
    # Seeded selection avoids first-row or target-dependent subset selection.
    positions = np.sort(np.random.default_rng(int(job["data_seed"])).choice(
        len(frame), size=count, replace=False
    ))
    frame = frame.iloc[positions].reset_index(drop=True)
    return frame, formula_features(frame["formula"].to_numpy())


def run_smoke(manifest_path: str | Path) -> dict[str, object]:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("validation_label") != SMOKE_LABEL:
        raise ValueError("smoke manifest lacks required non-inferential label")
    output_root = WORKSPACE / str(manifest["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    registry_rows = []
    artifacts = []
    results_by_job: dict[str, dict[str, dict[str, object]]] = {}
    for job in manifest["jobs"]:
        frame, X = _resolve_data(job)
        ids = frame["material_id"].to_numpy()
        y = frame["target"].to_numpy(float)
        for strategy in job["strategies"]:
            job_id = f"{job['job_id']}__{strategy}"
            started = datetime.now(timezone.utc).isoformat()
            try:
                result = run_campaign(
                    X,
                    y,
                    ids,
                    CampaignConfig(
                        strategy=strategy,
                        seed=int(job["campaign_seed"]),
                        initial_count=int(job["initial_count"]),
                        batch_size=int(job["batch_size"]),
                        max_queries=int(job["max_queries"]),
                        n_estimators=int(job["n_estimators"]),
                    ),
                )
                result["job_id"] = job_id
                result["dataset_kind"] = job["dataset_kind"]
                result["task"] = job["task"]
                results_by_job.setdefault(str(job["job_id"]), {})[strategy] = result
                result_path = output_root / f"{job_id}.json"
                atomic_json(result, result_path)
                artifacts.append(
                    {
                        "path": result_path.relative_to(WORKSPACE).as_posix(),
                        "sha256": sha256(result_path),
                    }
                )
                status, error = "COMPLETED", ""
            except Exception as exc:
                status, error = "FAILED", f"{type(exc).__name__}: {exc}"
            registry_rows.append(
                {
                    "validation_label": SMOKE_LABEL,
                    "job_id": job_id,
                    "status": status,
                    "started_utc": started,
                    "completed_utc": datetime.now(timezone.utc).isoformat(),
                    "error": error,
                }
            )
    registry_path = output_root / "smoke_registry.csv"
    with registry_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=registry_rows[0].keys())
        writer.writeheader()
        writer.writerows(registry_rows)
    log_path = output_root / "smoke_run.log"
    log_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "validation_label": row["validation_label"],
                    "job_id": row["job_id"],
                    "status": row["status"],
                    "started_utc": row["started_utc"],
                    "completed_utc": row["completed_utc"],
                    "error": row["error"],
                },
                sort_keys=True,
            )
            for row in registry_rows
        )
        + "\n",
        encoding="utf-8",
    )
    identity_audit = {
        "schema_version": "v6-smoke-identity-audit-v1",
        "validation_label": SMOKE_LABEL,
        "jobs": [],
    }
    for base_job_id, strategies in results_by_job.items():
        raw = strategies["RAW"]
        checks: dict[str, bool] = {}
        for strategy in (
            "GG_CALIBRATION_ONLY",
            "GG_NORMALIZED_ACQUISITION",
            "CS_CALIBRATION_ONLY",
        ):
            test = strategies[strategy]
            checks[f"{strategy}.initial_labeled_ids"] = (
                test["initial_labeled_ids"] == raw["initial_labeled_ids"]
            )
            checks[f"{strategy}.queried_trajectory"] = (
                test["queried_trajectory"] == raw["queried_trajectory"]
            )
            checks[f"{strategy}.round_count"] = test["round_count"] == raw["round_count"]
            checks[f"{strategy}.top1_recall"] = test["top1_recall"] == raw["top1_recall"]
            checks[f"{strategy}.l4"] = (
                test["l4_top1_recall_nauc"] == raw["l4_top1_recall_nauc"]
            )
            for index, (raw_round, test_round) in enumerate(
                zip(raw["rounds"], test["rounds"])
            ):
                for field in (
                    "training_ids_before",
                    "candidate_ids",
                    "acquisition_scores",
                    "stable_order_ids",
                    "selected_batch_ids",
                ):
                    checks[f"{strategy}.round{index}.{field}"] = (
                        test_round[field] == raw_round[field]
                    )
        identity_audit["jobs"].append(
            {
                "job_id": base_job_id,
                "checks": len(checks),
                "passed": sum(checks.values()),
                "failed_fields": sorted(key for key, passed in checks.items() if not passed),
            }
        )
    identity_audit["all_identity_checks_passed"] = all(
        job["checks"] == job["passed"] for job in identity_audit["jobs"]
    )
    identity_path = output_root / "smoke_identity_audit.json"
    atomic_json(identity_audit, identity_path)
    result_manifest = {
        "schema_version": "v6-smoke-result-manifest-v1",
        "validation_label": SMOKE_LABEL,
        "manifest_path": manifest_path.relative_to(WORKSPACE).as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "registry_path": registry_path.relative_to(WORKSPACE).as_posix(),
        "registry_sha256": sha256(registry_path),
        "log_path": log_path.relative_to(WORKSPACE).as_posix(),
        "log_sha256": sha256(log_path),
        "identity_audit_path": identity_path.relative_to(WORKSPACE).as_posix(),
        "identity_audit_sha256": sha256(identity_path),
        "jobs": len(registry_rows),
        "completed": sum(row["status"] == "COMPLETED" for row in registry_rows),
        "failed": sum(row["status"] == "FAILED" for row in registry_rows),
        "artifacts": artifacts,
    }
    atomic_json(result_manifest, output_root / "smoke_result_manifest.json")
    if result_manifest["failed"] or not identity_audit["all_identity_checks_passed"]:
        raise RuntimeError("one or more smoke jobs failed")
    return result_manifest


def main() -> None:
    parser = argparse.ArgumentParser(prog="transportability-v6")
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("smoke", help="run non-inferential Stage-2 smoke jobs")
    smoke.add_argument("--manifest", required=True)
    replay = subparsers.add_parser("canonical-replay", help="run a read-only V5 RAW compatibility replay")
    replay.add_argument("--output-root", required=True)
    p0_manifest = subparsers.add_parser("p0-manifest", help="generate, but do not execute, the P0 development manifest")
    p0_manifest.add_argument("--workspace", default=str(WORKSPACE))
    p0_reissue = subparsers.add_parser("p0-reissue-lock", help="explicitly supersede a P0 lock after a recorded canary defect")
    p0_reissue.add_argument("--workspace", default=str(WORKSPACE))
    p0_reissue.add_argument("--reason", required=True)
    p0_run = subparsers.add_parser("p0-run", help="execute only the already locked P0 development manifest")
    p0_run.add_argument("--workspace", default=str(WORKSPACE))
    p0_stability = subparsers.add_parser("p0-selection-stability", help="write the descriptive P0 selection-stability summary")
    p0_stability.add_argument("--workspace", default=str(WORKSPACE))
    args = parser.parse_args()
    if args.command == "smoke":
        print(json.dumps(run_smoke(args.manifest), indent=2))
    elif args.command == "canonical-replay":
        print(json.dumps(CanonicalV5Adapter(WORKSPACE).replay_raw(output_root=args.output_root).__dict__, indent=2))
    elif args.command == "p0-manifest":
        print(json.dumps(generate_p0_manifest(workspace=args.workspace), indent=2))
    elif args.command == "p0-reissue-lock":
        print(json.dumps(reissue_p0_manifest_lock(workspace=args.workspace, reason=args.reason), indent=2))
    elif args.command == "p0-run":
        print(json.dumps(execute_p0_development(workspace=args.workspace), indent=2))
    elif args.command == "p0-selection-stability":
        print(json.dumps(selection_stability_summary(workspace=args.workspace), indent=2))


if __name__ == "__main__":
    main()
