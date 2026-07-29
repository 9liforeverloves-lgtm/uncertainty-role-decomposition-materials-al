"""Clean-room replay of exactly the eight recovered V6 P0 development jobs.

This script never touches the original broad-development directory.  It binds
the accepted manifest and final broad lock, selects job IDs only from the
versioned eight-row recovery inventory, and writes into an isolated namespace.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transportability_v6.canonical_adapter import CanonicalV5Adapter  # noqa: E402
from transportability_v6.execution_registry import sha256_file  # noqa: E402
from transportability_v6.production_campaign import (  # noqa: E402
    ProductionCampaignConfig,
    run_production_campaign,
)


MANIFEST = ROOT / "manifests" / "v6_p0_broad_development_manifest.csv"
BROAD_LOCK = ROOT / "locks" / "v6_p0_broad_development_manifest_lock.json"
RECOVERY_INVENTORY = ROOT / "tables" / "v6_p0_broad_recovery_inventory.csv"
CORRECTED_ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints_CORRECTED.csv"
ORIGINAL_ROOT = (
    ROOT / "results" / "v6_p0_broad_development" / "final_broad_development" / "trajectories"
)
REPLAY_ROOT = ROOT / "results" / "v6_p0_recovery_cleanroom_replay"
REPLAY_TRAJECTORIES = REPLAY_ROOT / "trajectories"
OUTPUT_TABLE = ROOT / "tables" / "v6_p0_recovery_cleanroom_replay.csv"
OUTPUT_REPORT = ROOT / "reports" / "05g_recovery_cleanroom_replay.md"
CHECKPOINTS = ("initial", "25pct", "50pct", "75pct")


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(
        path,
        frame.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode("utf-8"),
    )


def json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        parsed = json.loads(value)
    elif isinstance(value, np.ndarray):
        parsed = value.tolist()
    else:
        parsed = value
    return [str(item) for item in parsed]


def checkpoint_logical_hashes(directory: Path) -> dict[str, str]:
    """Hash stable checkpoint identity and verified model payload content."""

    fields = (
        "checkpoint_label",
        "checkpoint_threshold",
        "acquisition_round",
        "queried_count",
        "realized_campaign_progress",
    )
    output: dict[str, str] = {}
    for label in CHECKPOINTS:
        metadata_path = directory / f"checkpoint_{label}.json"
        model_path = directory / f"checkpoint_{label}.joblib"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        model_hash = sha256_file(model_path)
        if metadata.get("model_state_hash") != model_hash:
            raise RuntimeError(f"checkpoint metadata/model mismatch: {directory}/{label}")
        output[label] = canonical_hash(
            {
                "metadata": {field: metadata.get(field) for field in fields},
                "model_state_sha256": model_hash,
            }
        )
    return output


def logical_state(
    directory: Path,
    *,
    accepted_l1: float,
    accepted_l4: float,
) -> dict[str, Any]:
    trace = json.loads((directory / "trajectory.json").read_text(encoding="utf-8"))
    rounds = pd.read_parquet(directory / "rounds.parquet").sort_values("round", kind="stable")
    batches = [
        json_list(value)
        for value in rounds.loc[rounds["round"].astype(int) >= 0, "selected_batch_ids"].tolist()
    ]
    state = {
        "split_hashes": {
            "source": str(trace["source_ids_hash"]),
            "target": str(trace["target_ids_hash"]),
            "diagnostic": str(trace["diagnostic_ids_hash"]),
        },
        "initial_labeled_ids": [str(value) for value in trace["initial_labeled_ids"]],
        "queried_batches": batches,
        "checkpoint_logical_hashes": checkpoint_logical_hashes(directory),
        # The accepted endpoint layer is CSV-backed.  Canonicalizing at the
        # explicit 1e-15 acceptance resolution avoids treating sub-ULP
        # CSV/parser round-trips as scientific trajectory changes.
        "l1_campaign_mace_1e14": format(round(float(accepted_l1), 14), ".14f"),
        "l4_top1pct_recall_nauc_1e14": format(round(float(accepted_l4), 14), ".14f"),
    }
    state["logical_trajectory_sha256"] = canonical_hash(state)
    return state


def execute_one(row: dict[str, Any], manifest_hash: str) -> dict[str, Any]:
    adapter = CanonicalV5Adapter(ROOT)
    result = run_production_campaign(
        ProductionCampaignConfig(
            job_id=str(row["job_id"]),
            task=str(row["task"]),
            split_protocol=str(row["split_protocol"]),
            model=str(row["model"]),
            strategy=str(row["strategy"]),
            seed=int(row["seed"]),
            evidence_class=str(row["evidence_class"]),
            beta=0.5 if str(row["strategy"]) == "SELECTED_GG" else 1.0,
            phase="broad_development",
            manifest_sha256=manifest_hash,
        ),
        output_root=REPLAY_TRAJECTORIES,
        adapter=adapter,
    )
    return {"job_id": str(row["job_id"]), "status": str(result["status"])}


def validate_inputs() -> tuple[pd.DataFrame, dict[str, Any], str]:
    lock = json.loads(BROAD_LOCK.read_text(encoding="utf-8"))
    manifest_hash = sha256_file(MANIFEST)
    if manifest_hash != str(lock["manifest_sha256"]):
        raise RuntimeError("final broad manifest no longer matches the accepted lock")
    inventory = pd.read_csv(RECOVERY_INVENTORY)
    if len(inventory) != 8 or inventory.job_id.nunique() != 8:
        raise RuntimeError("clean-room replay requires exactly eight unique recovery jobs")
    manifest = pd.read_csv(MANIFEST).fillna("")
    rows = manifest[manifest.job_id.astype(str).isin(set(inventory.job_id.astype(str)))].copy()
    if len(rows) != 8 or rows.job_id.nunique() != 8:
        raise RuntimeError("recovery inventory does not resolve to exactly eight manifest rows")
    if set(rows.job_kind.astype(str)) != {"trajectory"}:
        raise RuntimeError("the eight recovered jobs are not all full trajectories")
    if set(rows.execution_phase.astype(str)) != {"base"}:
        raise RuntimeError("the eight recovered jobs are not all base development jobs")
    if set(rows.seed.astype(int)) & set(range(7000, 7040)):
        raise PermissionError("confirmation seed encountered in recovery replay")
    return rows.sort_values("job_id", kind="stable"), lock, manifest_hash


def compare_replays(rows: pd.DataFrame, lock: dict[str, Any]) -> pd.DataFrame:
    endpoints = pd.read_csv(CORRECTED_ENDPOINTS).set_index("job_id")
    records: list[dict[str, Any]] = []
    for row in rows.itertuples(index=False):
        job_id = str(row.job_id)
        reference_dir = ORIGINAL_ROOT / job_id
        replay_dir = REPLAY_TRAJECTORIES / job_id
        accepted_l1 = float(endpoints.loc[job_id, "l1_campaign_mace"])
        accepted_l4 = float(endpoints.loc[job_id, "l4_top1pct_recall_nauc"])
        reference = logical_state(
            reference_dir,
            accepted_l1=accepted_l1,
            accepted_l4=accepted_l4,
        )
        replay_trace = json.loads((replay_dir / "trajectory.json").read_text(encoding="utf-8"))
        replay_l1 = float(replay_trace["endpoints"]["l1_campaign_mace"])
        replay_l4 = float(replay_trace["endpoints"]["l4_top1pct_recall_nauc"])
        replay = logical_state(replay_dir, accepted_l1=replay_l1, accepted_l4=replay_l4)
        split_match = reference["split_hashes"] == replay["split_hashes"]
        initial_match = reference["initial_labeled_ids"] == replay["initial_labeled_ids"]
        batches_match = reference["queried_batches"] == replay["queried_batches"]
        checkpoint_match = (
            reference["checkpoint_logical_hashes"] == replay["checkpoint_logical_hashes"]
        )
        l1_abs_diff = abs(accepted_l1 - replay_l1)
        l4_abs_diff = abs(accepted_l4 - replay_l4)
        l1_match = bool(np.isclose(accepted_l1, replay_l1, rtol=0.0, atol=1e-15))
        l4_match = bool(np.isclose(accepted_l4, replay_l4, rtol=0.0, atol=1e-15))
        logical_match = (
            split_match
            and initial_match
            and batches_match
            and checkpoint_match
            and l1_match
            and l4_match
            and reference["logical_trajectory_sha256"]
            == replay["logical_trajectory_sha256"]
        )
        records.append(
            {
                "job_id": job_id,
                "strategy": str(row.strategy),
                "seed": int(row.seed),
                "final_broad_lock_identity_sha256": str(lock["final_lock_sha256"]),
                "manifest_sha256": str(lock["manifest_sha256"]),
                "reference_split_hashes": json.dumps(
                    reference["split_hashes"], sort_keys=True, separators=(",", ":")
                ),
                "replay_split_hashes": json.dumps(
                    replay["split_hashes"], sort_keys=True, separators=(",", ":")
                ),
                "split_hashes_match": split_match,
                "reference_initial_ids_sha256": canonical_hash(
                    reference["initial_labeled_ids"]
                ),
                "replay_initial_ids_sha256": canonical_hash(replay["initial_labeled_ids"]),
                "initial_ids_match": initial_match,
                "queried_batch_count": len(reference["queried_batches"]),
                "reference_queried_batches_sha256": canonical_hash(
                    reference["queried_batches"]
                ),
                "replay_queried_batches_sha256": canonical_hash(replay["queried_batches"]),
                "every_queried_batch_match": batches_match,
                "reference_checkpoint_logical_hashes": json.dumps(
                    reference["checkpoint_logical_hashes"],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "replay_checkpoint_logical_hashes": json.dumps(
                    replay["checkpoint_logical_hashes"],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "checkpoint_logical_hashes_match": checkpoint_match,
                "reference_logical_trajectory_sha256": reference[
                    "logical_trajectory_sha256"
                ],
                "replay_logical_trajectory_sha256": replay["logical_trajectory_sha256"],
                "logical_trajectory_match": logical_match,
                "accepted_l1_campaign_mace": accepted_l1,
                "replay_l1_campaign_mace": replay_l1,
                "l1_absolute_difference": l1_abs_diff,
                "l1_match": l1_match,
                "accepted_l4_top1pct_recall_nauc": accepted_l4,
                "replay_l4_top1pct_recall_nauc": replay_l4,
                "l4_absolute_difference": l4_abs_diff,
                "l4_match": l4_match,
                "accepted": logical_match,
            }
        )
    return pd.DataFrame(records).sort_values("job_id", kind="stable")


def write_report(frame: pd.DataFrame, lock: dict[str, Any]) -> None:
    passed = int(frame.accepted.sum())
    status = "PASS_8_OF_8" if passed == 8 and len(frame) == 8 else "FAIL"
    failures = frame.loc[~frame.accepted, "job_id"].astype(str).tolist()
    report = f"""# V6 P0 recovery clean-room replay

Status: **{status}**

- Replayed jobs: {len(frame)} (exactly the eight registered recovered development jobs).
- Logical trajectories and corrected endpoints matched: {passed}/8.
- Final broad lock identity: `{lock['final_lock_sha256']}`.
- Final broad manifest SHA-256: `{lock['manifest_sha256']}`.
- Isolated replay directory: `results/v6_p0_recovery_cleanroom_replay/trajectories`.
- Original recovery records overwritten: no.
- Historical point-in-time checkpoint hashes reconstructed: no; they remain unavailable.
- Broad 2,720-job cohort rerun: no.
- Confirmation seeds used: none.

Each row compares source/target/diagnostic split hashes, the ordered initial IDs,
every ordered queried batch, four checkpoint logical hashes, the final logical
trajectory hash, corrected L1, and L4. The checkpoint logical hash binds stable
checkpoint metadata to its internally verified model-state SHA-256.
Endpoint equality uses absolute tolerance `1e-15` solely for CSV/in-memory
round-trip effects; exact values and absolute differences are retained in the
CSV. The aggregate logical hash stores endpoints at `1e-14`; the stricter
standalone endpoint acceptance check remains `1e-15`.

Failed jobs: {json.dumps(failures, ensure_ascii=False)}.

Acceptance rule: all eight rows must pass. If any row fails, the affected jobs
must be excluded from development selection and all LOTO maps regenerated
prospectively from the remaining registered data.
"""
    atomic_bytes(OUTPUT_REPORT, report.encode("utf-8"))


def main(*, workers: int, compare_only: bool = False) -> None:
    rows, lock, manifest_hash = validate_inputs()
    REPLAY_TRAJECTORIES.mkdir(parents=True, exist_ok=True)
    records = rows.to_dict("records")
    if not compare_only:
        outcomes: list[dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute_one, row, manifest_hash) for row in records]
            for future in as_completed(futures):
                outcome = future.result()
                outcomes.append(outcome)
                print(json.dumps(outcome, sort_keys=True), flush=True)
        if len(outcomes) != 8 or {item["status"] for item in outcomes} != {"COMPLETED"}:
            raise RuntimeError("not all eight clean-room replay jobs completed")
    else:
        missing = [
            str(row["job_id"])
            for row in records
            if not (REPLAY_TRAJECTORIES / str(row["job_id"]) / "trajectory.json").is_file()
        ]
        if missing:
            raise FileNotFoundError(f"compare-only replay outputs are missing: {missing}")
    frame = compare_replays(rows, lock)
    atomic_csv(OUTPUT_TABLE, frame)
    write_report(frame, lock)
    passed = int(frame.accepted.sum())
    print(json.dumps({"status": "PASS" if passed == 8 else "FAIL", "passed": passed}), flush=True)
    if passed != 8:
        raise RuntimeError("clean-room replay failed the 8/8 acceptance rule")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--compare-only", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        raise ValueError("workers must lie in [1, 8]")
    main(workers=args.workers, compare_only=args.compare_only)
