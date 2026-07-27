from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CODE_PACKAGE = next(
    path
    for path in (child / "_code_package" for child in WORKSPACE.iterdir())
    if (path / "transportability_study" / "configs" / "protocol_v1.yaml").is_file()
)
sys.path.insert(0, str(ROOT / "experiments_v4" / "src"))

from transportability_v5.data import featurize_formulas, load_materials_csv
from transportability_v5.provenance import stable_payload_hash
from transportability_v5.runner import ControlledInterruption, run_trajectory
from transportability_v5.splits import make_split


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(manifest: Path, job_id: str, config: dict, phase: str):
    protocol = ROOT / (
        "14_reduced_development_protocol.md"
        if phase == "development_reduced"
        else ("20_confirmation_protocol_v5_rc1.md" if phase == "confirmation" else "03_frozen_v4_protocol.md")
    )
    return {
        "protocol_schema_version": (
            "transportability-v5-reduced-development-v1"
            if phase == "development_reduced"
            else ("transportability-v5-rc1-confirmation-v1" if phase == "confirmation" else "transportability-v5-development-v1")
        ),
        "protocol_path": protocol.relative_to(WORKSPACE).as_posix(),
        "protocol_sha256": sha(protocol),
        "analysis_plan_path": protocol.relative_to(WORKSPACE).as_posix(),
        "analysis_plan_sha256": sha(protocol),
        "manifest_path": manifest.relative_to(WORKSPACE).as_posix(),
        "manifest_sha256": sha(manifest),
        "run_config_sha256": stable_payload_hash(config),
        "job_id": job_id,
    }, protocol.read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", choices=["development", "development_reduced", "confirmation"], required=True
    )
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--interrupt-after-checkpoint", choices=["initial", "25pct", "50pct", "75pct"]
    )
    args = parser.parse_args()

    if args.phase == "confirmation":
        manifest = ROOT / "manifests_v4" / "CONFIRMATION_JOB_MANIFEST_V5_RC1.csv"
        lock = ROOT / "manifests_v4" / "CONFIRMATION_FREEZE_LOCK_V5_RC1.json"
        if not lock.is_file() or not manifest.is_file():
            raise SystemExit("confirmation blocked: final manifest and freeze lock are not released")
        if json.loads(lock.read_text(encoding="utf-8")).get("manifest_sha256") != sha(manifest):
            raise SystemExit("confirmation blocked: manifest hash mismatch")
    elif args.phase == "development_reduced":
        manifest = ROOT / "manifests_v4" / "development_manifest_reduced.csv"
    else:
        manifest = ROOT / "manifests_v4" / "DEVELOPMENT_JOB_MANIFEST_V5.csv"

    table = pd.read_csv(manifest)
    selected = table.loc[table.job_id == args.job_id]
    if len(selected) != 1:
        raise SystemExit(f"job id must occur exactly once, found {len(selected)}")
    row = selected.iloc[0]
    seed = int(row.seed)
    expected = range(1000, 1010) if args.phase != "confirmation" else range(5000, 5040)
    if seed not in expected:
        raise SystemExit("seed outside frozen phase range")

    base = yaml.safe_load(
        (CODE_PACKAGE / "transportability_study" / "configs" / "protocol_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = (
        json.loads(row.candidate_specific_config_json)
        if isinstance(row.candidate_specific_config_json, str)
        else {}
    )
    candidate_config = {**base["candidate_specific"], **candidate}
    if row.strategy == "cs_da_oob_hist":
        candidate_config["min_oob_trees_per_sample"] = 3
    elif str(row.strategy).startswith("cs_da_oob"):
        candidate_config["min_oob_trees_per_sample"] = 10
    else:
        candidate_config["min_oob_trees_per_sample"] = base["oob"]["min_oob_trees_per_sample"]

    data = load_materials_csv(CODE_PACKAGE / "results" / "benchmark" / row.task / "materials.csv")
    X = featurize_formulas(data.formula)
    y = data.target.to_numpy()
    formulas = data.formula.to_numpy()
    ids = data.material_id.to_numpy()
    split = make_split(row.split_protocol).split(
        formulas, ids, seed, min_source=30, min_target=50, min_diagnostic=20
    )
    initial = max(30, min(len(split.source), round(len(data) * base["campaign"]["initial_fraction_total"])))
    batch = max(1, round(len(data) * base["campaign"]["batch_fraction_total"]))
    max_queries = max(1, round(len(split.target) * base["campaign"]["maximum_query_fraction_target"]))
    initial_indices = np.sort(np.random.default_rng(seed).choice(split.source, size=initial, replace=False))
    initial_targets = np.asarray(y[initial_indices], float)
    median = float(np.median(initial_targets))
    robust_scale = max(
        float(np.std(initial_targets)),
        float((np.quantile(initial_targets, 0.75) - np.quantile(initial_targets, 0.25)) / 1.349),
        float(1.4826 * np.median(np.abs(initial_targets - median))),
        1e-12,
    )
    floor_grid = sorted({
        float(base["oob"]["uncertainty_floor"]),
        *[max(1e-8, coefficient * robust_scale) for coefficient in (1e-8, 1e-6, 1e-5, 1e-4, 1e-3)],
    })
    config = {
        "task": row.task,
        "campaign": {"initial_count": initial, "batch_size": batch, "max_queries": max_queries},
        "model": base["model"],
        "oob": base["oob"],
        "candidate_specific": candidate_config,
        "acquisition": {},
        "floor_sensitivity": {"robust_initial_target_scale": robust_scale, "absolute_floors": floor_grid},
    }
    ident, protocol_raw = identity(manifest, args.job_id, config, args.phase)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "job": args.job_id,
                    "dry_run": True,
                    "model_trained": False,
                    "trajectory_written": False,
                    "manifest_sha256": ident["manifest_sha256"],
                    "protocol_sha256": ident["protocol_sha256"],
                    "source_count": len(split.source),
                    "target_count": len(split.target),
                    "diagnostic_count": len(split.diagnostic),
                    "candidate_min_oob_trees": candidate_config["min_oob_trees_per_sample"],
                }
            )
        )
        return

    output = ROOT / "results_v4" / args.phase / "trajectories"
    started = time.time()
    try:
        result = run_trajectory(
            X,
            y,
            formulas,
            ids,
            split,
            row.strategy,
            row.model,
            seed,
            config,
            output,
            ident,
            protocol_raw,
            True,
            args.interrupt_after_checkpoint,
        )
    except ControlledInterruption as exc:
        print(json.dumps({"job": args.job_id, "controlled_interruption": str(exc)}))
        raise SystemExit(75)
    print(
        json.dumps(
            {
                "job": result["key"],
                "primary_nauc": result["primary_nauc"],
                "round_rows": len(result["rounds"]),
                "seconds": time.time() - started,
            }
        )
    )


if __name__ == "__main__":
    main()
