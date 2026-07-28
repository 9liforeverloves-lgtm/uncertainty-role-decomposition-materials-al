"""Produce broad-development evidence tables and descriptive stability reports.

This script is intentionally blocked unless the final broad lock exists and
all 2720 registered jobs completed.  It creates only development evidence; it
does not create, read, or freeze confirmation work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.broad_development import BROAD_SEEDS, TASKS
from transportability_v6.registry_freeze import code_tree_sha256
from transportability_v6.selection import fit_matched_beta_map


EVIDENCE_CLASS = "V6-P0-BROAD-DEVELOPMENT"
LOCK = ROOT / "locks" / "v6_p0_broad_development_manifest_lock.json"
MANIFEST = ROOT / "manifests" / "v6_p0_broad_development_manifest.csv"
OUTPUT = ROOT / "results" / "v6_p0_broad_development"
ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints.csv"
BETA = ROOT / "tables" / "v6_p0_broad_effective_beta.csv"
CANDIDATE = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE.json"
STABILITY = ROOT / "analysis_plan" / "v6_p0_broad_selection_stability.json"


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes(path: Path, content: bytes, *, refresh: bool) -> str:
    digest = hashlib.sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and sha256_file(path) != digest and not refresh:
        raise FileExistsError(f"refusing to overwrite divergent broad analysis artifact: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return digest


def write_json(path: Path, payload: dict[str, object], *, refresh: bool) -> str:
    return write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), refresh=refresh)


def environment_id(row: pd.Series | dict[str, object]) -> str:
    return "__".join((str(row["task"]), str(row["split_protocol"]), str(row["model"])))


def registry_frame(path: Path) -> pd.DataFrame:
    connection = sqlite3.connect(path)
    try:
        return pd.read_sql_query("SELECT * FROM jobs ORDER BY job_id", connection)
    finally:
        connection.close()


def require_completed() -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Path]:
    if not LOCK.is_file() or not MANIFEST.is_file():
        raise FileNotFoundError("final broad lock and manifest are required")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if sha256_file(MANIFEST) != str(lock["manifest_sha256"]):
        raise RuntimeError("broad manifest does not match final lock")
    if set(range(7000, 7040)) & set(pd.read_csv(MANIFEST).seed.astype(int)):
        raise RuntimeError("confirmation seed leakage in broad manifest")
    run_root = OUTPUT / str(lock["execution_run_id"])
    registry = registry_frame(run_root / "job_registry.sqlite")
    if len(registry) != int(lock["manifest_job_count"]) or set(registry.status.astype(str)) != {"COMPLETED"}:
        raise RuntimeError("broad analysis requires a fully completed final registry")
    manifest = pd.read_csv(MANIFEST, dtype={"seed": int}).fillna("")
    return lock, manifest, registry, run_root


def endpoint_table(manifest: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    joined = manifest.merge(registry[["job_id", "status", "output_path", "output_hash"]], on="job_id", how="left", validate="one_to_one")
    output_by_job = {str(row.job_id): Path(str(row.output_path)) for row in joined.itertuples(index=False)}
    records: list[dict[str, object]] = []
    for row in joined.itertuples(index=False):
        output_path = Path(str(row.output_path))
        trace = json.loads((output_path / "trajectory.json").read_text(encoding="utf-8"))
        endpoints = dict(trace.get("endpoints", {}))
        l4 = endpoints.get("l4_top1pct_recall_nauc", np.nan)
        l4_reused_from_dependency = False
        dependency_hash_verified = ""
        if str(row.job_kind) == "calibration_replay":
            dependency = str(row.dependency_job_id)
            source_path = output_by_job.get(dependency)
            if source_path is None:
                raise RuntimeError(f"calibration replay has no registered RAW dependency: {row.job_id}")
            source_trace_path = source_path / "trajectory.json"
            observed_source_hash = sha256_file(source_trace_path)
            if str(trace.get("source_trajectory_sha256", "")) != observed_source_hash:
                raise RuntimeError(f"calibration replay source hash mismatch: {row.job_id}")
            source_trace = json.loads(source_trace_path.read_text(encoding="utf-8"))
            l4 = float(source_trace["endpoints"]["l4_top1pct_recall_nauc"])
            l4_reused_from_dependency = True
            dependency_hash_verified = observed_source_hash
        records.append(
            {
                "job_id": str(row.job_id),
                "task": str(row.task),
                "split": str(row.split_protocol),
                "model": str(row.model),
                "strategy": str(row.strategy),
                "seed": int(row.seed),
                "job_kind": str(row.job_kind),
                "execution_phase": str(row.execution_phase),
                "evidence_class": str(row.evidence_class),
                "dependency_job_id": str(row.dependency_job_id),
                "completion_status": str(row.status),
                "l1_campaign_mace": float(endpoints.get("l1_campaign_mace", np.nan)),
                "l4_top1pct_recall_nauc": float(l4),
                "l4_reused_from_dependency": l4_reused_from_dependency,
                "source_trajectory_sha256": str(trace.get("source_trajectory_sha256", "")),
                "dependency_source_trajectory_sha256_verified": dependency_hash_verified,
                "trajectory_sha256": sha256_file(output_path / "trajectory.json"),
                "registry_output_sha256": str(row.output_hash),
            }
        )
    return pd.DataFrame(records).sort_values(["task", "split", "model", "strategy", "seed"], kind="stable")


def beta_maps(beta: pd.DataFrame, candidate: dict[str, Any]) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    maps: dict[str, dict[str, object]] = {}
    consistency: dict[str, object] = {}
    candidate_maps = dict(candidate["leave_one_task_out_maps"])
    for held_out in TASKS:
        source = beta.loc[beta.task.astype(str) != held_out].copy()
        selection = fit_matched_beta_map(source, allowed_seeds=set(BROAD_SEEDS))
        maps[held_out] = selection
        candidate_selection = dict(candidate_maps[held_out])
        consistency[held_out] = {
            "candidate_equals_recomputed": {
                "fixed": float(candidate_selection["fixed_matched_beta"]) == float(selection["fixed_matched_beta"]),
                "stage": dict(candidate_selection["stage_matched_beta"]) == dict(selection["stage_matched_beta"]),
                "source_tasks": sorted(candidate_selection["source_tasks"]) == sorted(set(source.task.astype(str))),
            }
        }
    return maps, consistency


def leave_one_seed_out(beta: pd.DataFrame) -> dict[str, dict[str, dict[str, object]]]:
    output: dict[str, dict[str, dict[str, object]]] = {}
    for held_out in TASKS:
        source = beta.loc[beta.task.astype(str) != held_out].copy()
        output[held_out] = {}
        for seed in BROAD_SEEDS:
            reduced = source.loc[source.seed.astype(int) != int(seed)]
            selection = fit_matched_beta_map(reduced, allowed_seeds=set(BROAD_SEEDS) - {int(seed)})
            output[held_out][str(seed)] = {
                "fixed_matched_beta": float(selection["fixed_matched_beta"]),
                "stage_matched_beta": dict(selection["stage_matched_beta"]),
            }
    return output


def task_bootstrap(beta: pd.DataFrame, *, repetitions: int = 500, root_seed: int = 610003) -> dict[str, object]:
    rng = np.random.default_rng(root_seed)
    output: dict[str, object] = {}
    for held_out in TASKS:
        source = beta.loc[beta.task.astype(str) != held_out].copy()
        task_values = sorted(set(source.task.astype(str)))
        fixed_values: list[float] = []
        for _ in range(repetitions):
            draw = rng.choice(task_values, size=len(task_values), replace=True).tolist()
            replicas: list[pd.DataFrame] = []
            for replicate, task in enumerate(draw):
                frame = source.loc[source.task.astype(str) == str(task)].copy()
                frame["environment"] = frame["environment"].astype(str) + f"__task_bootstrap_{replicate}"
                replicas.append(frame)
            selection = fit_matched_beta_map(pd.concat(replicas, ignore_index=True), allowed_seeds=set(BROAD_SEEDS))
            fixed_values.append(float(selection["fixed_matched_beta"]))
        output[held_out] = {
            "source_task_count": len(task_values),
            "repetitions": repetitions,
            "fixed_beta_quantiles": {
                "q025": float(np.quantile(fixed_values, 0.025)),
                "q50": float(np.quantile(fixed_values, 0.50)),
                "q975": float(np.quantile(fixed_values, 0.975)),
            },
            "interpretation": "descriptive only: each fold has only three source tasks",
        }
    return output


def stratified_maps(beta: pd.DataFrame, column: str) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for held_out in TASKS:
        source = beta.loc[beta.task.astype(str) != held_out]
        output[held_out] = {}
        for value, frame in source.groupby(column, sort=True):
            selection = fit_matched_beta_map(frame, allowed_seeds=set(BROAD_SEEDS))
            output[held_out][str(value)] = float(selection["fixed_matched_beta"])
    return output


def nonidentity_margin(endpoints: pd.DataFrame) -> dict[str, object]:
    strategies = (
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "SCALAR_TEMPERATURE_NLL",
        "POWER_SCALING",
        "ISOTONIC_ABS_RESIDUAL",
        "CONFORMAL_INTERVAL_ONLY",
    )
    frame = endpoints.loc[endpoints.strategy.astype(str).isin(strategies)].copy()
    frame["environment"] = frame.apply(
        lambda row: "__".join((str(row.task), str(row.split), str(row.model))), axis=1
    )
    scores = {
        str(strategy): float(group.groupby("environment", sort=True)["l1_campaign_mace"].median().median())
        for strategy, group in frame.groupby("strategy", sort=True)
    }
    candidate = "SCALAR_TEMPERATURE_RESIDUAL_RATIO"
    alternatives = {key: value for key, value in scores.items() if key != candidate}
    runner_up = min(alternatives, key=lambda key: (alternatives[key], key))
    return {
        "selected_method": candidate,
        "runner_up_method": runner_up,
        "selected_environment_balanced_median_l1": scores[candidate],
        "runner_up_environment_balanced_median_l1": alternatives[runner_up],
        "selected_minus_runner_up_l1": scores[candidate] - alternatives[runner_up],
        "all_nonidentity_scores": scores,
        "policy_interpretation": (
            "descriptive selected-minus-runner-up margin only; the selected method was prespecified "
            "as the simple non-identity baseline and no outcome-selected winner is created"
        ),
    }


def report_execution(lock: dict[str, Any], endpoints: pd.DataFrame, run_root: Path) -> str:
    counts = endpoints.completion_status.value_counts().to_dict()
    return f"""# P0 broad development execution

Status: **COMPLETED, development-only**. Evidence class: `V6-P0-BROAD-DEVELOPMENT`.

The final prospective broad lock `{lock['final_lock_sha256']}` covers `{lock['manifest_job_count']}` jobs: 16 task/split/model environments × 10 non-overlapping development seeds × 17 registered jobs. The final registry counts are `{counts}`.

Scope: four frozen Matbench tasks, IID-record and chemical-system group-disjoint splits, Random Forest and ExtraTrees-compatible ensembles, seeds 6100–6109. The sentinel cohort remains separate and is not pooled into this table.

- Manifest: `manifests/v6_p0_broad_development_manifest.csv` (`{lock['manifest_sha256']}`)
- Final run root: `{run_root.relative_to(ROOT).as_posix()}`
- Endpoint table: `tables/v6_p0_broad_seed_endpoints.csv`
- Effective-beta table: `tables/v6_p0_broad_effective_beta.csv`
- Candidate-only LOTO map: `analysis_plan/v6_p0_confirmation_selection_map_CANDIDATE.json`

No confirmation manifest or confirmation jobs were generated. Seeds 7000–7039 were neither read nor run. This report stops at broad-development analysis.
"""


def report_loto(candidate: dict[str, Any], consistency: dict[str, object]) -> str:
    lines = [
        "# P0 leave-one-task-out beta selection",
        "",
        "Status: **CANDIDATE, development-only; not frozen for confirmation**.",
        "",
        "Each held-out task map uses only the other three tasks' Original-GG effective-beta rows. The candidate is generated after the final broad development run, but its selection rules were prospectively locked before endpoints were read.",
        "",
        "| held-out task | fixed beta | 0–25% | 25–50% | 50–75% | 75–100% | source tasks | source seeds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for task, item in dict(candidate["leave_one_task_out_maps"]).items():
        stages = item["stage_matched_beta"]
        lines.append(
            f"| {task} | {float(item['fixed_matched_beta']):.17g} | {float(stages['0_25']):.17g} | "
            f"{float(stages['25_50']):.17g} | {float(stages['50_75']):.17g} | {float(stages['75_100']):.17g} | "
            f"{', '.join(item['source_tasks'])} | {min(item['source_seeds'])}–{max(item['source_seeds'])} |"
        )
    lines.extend([
        "",
        "## Consistency checks",
        "",
        "All candidate maps were recomputed from the hash-addressed broad effective-beta table before this report. Results:",
        "",
        "```json",
        json.dumps(consistency, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "The output intentionally remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`; no confirmation policy has been frozen.",
        "",
    ])
    return "\n".join(lines)


def report_stability(stability: dict[str, object]) -> str:
    lines = [
        "# P0 broad selection stability",
        "",
        "All quantities here are descriptive broad-development diagnostics. They do not trigger a confirmation freeze or alter the predeclared simple-scaling roles.",
        "",
        "## Leave-one-development-seed-out fixed-beta ranges",
        "",
        "| held-out task | minimum | maximum |",
        "| --- | ---: | ---: |",
    ]
    for task, values in dict(stability["leave_one_seed_out"]).items():
        fixed = [float(value["fixed_matched_beta"]) for value in dict(values).values()]
        lines.append(f"| {task} | {min(fixed):.17g} | {max(fixed):.17g} |")
    lines.extend([
        "",
        "## Task bootstrap",
        "",
        "Each LOTO fold contains only three source tasks, so the bootstrap is reported cautiously as a descriptive sensitivity analysis.",
        "",
        "```json",
        json.dumps(stability["task_bootstrap"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Model and split stratification",
        "",
        "```json",
        json.dumps({"model_stratified_fixed_beta": stability["model_stratified_fixed_beta"], "split_stratified_fixed_beta": stability["split_stratified_fixed_beta"]}, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Prespecified non-identity selected-minus-runner-up margin",
        "",
        "```json",
        json.dumps(stability["nonidentity_scalar_descriptive_margin"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "Identity remains a negative control. Residual-ratio retains its predeclared role as the selected simple non-identity baseline; the displayed selected-minus-runner-up margin is descriptive and is not an outcome-driven winner selection.",
        "",
    ])
    return "\n".join(lines)


def main(*, refresh: bool) -> None:
    lock, manifest, registry, run_root = require_completed()
    endpoints = endpoint_table(manifest, registry)
    endpoints_hash = write_bytes(
        ENDPOINTS,
        endpoints.to_csv(index=False, float_format="%.17g", lineterminator="\n").encode("utf-8"),
        refresh=refresh,
    )
    if not BETA.is_file():
        raise FileNotFoundError("broad effective-beta table was not written by the final locked execution")
    beta = pd.read_csv(BETA)
    required_beta = {"task", "split", "model", "seed", "environment", "effective_beta", "budget_fraction"}
    if not required_beta <= set(beta):
        raise ValueError(f"broad effective-beta table lacks required fields: {sorted(required_beta - set(beta))}")
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if candidate.get("status") != "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN":
        raise ValueError("broad candidate selection map has an invalid status")
    maps, consistency = beta_maps(beta, candidate)
    if not all(all(item["candidate_equals_recomputed"].values()) for item in consistency.values()):
        raise RuntimeError("candidate LOTO maps diverge from broad effective-beta table")
    stability: dict[str, object] = {
        "schema_version": "v6-p0-broad-selection-stability-v1",
        "status": "DESCRIPTIVE_BROAD_DEVELOPMENT_ONLY",
        "evidence_class": EVIDENCE_CLASS,
        "confirmation_outcomes_inspected": False,
        "candidate_selection_map_sha256": str(candidate["candidate_selection_map_sha256"]),
        "broad_effective_beta_sha256": sha256_file(BETA),
        "leave_one_seed_out": leave_one_seed_out(beta),
        "task_bootstrap": task_bootstrap(beta),
        "model_stratified_fixed_beta": stratified_maps(beta, "model"),
        "split_stratified_fixed_beta": stratified_maps(beta, "split"),
        "nonidentity_scalar_descriptive_margin": nonidentity_margin(endpoints),
        "candidate_map_consistency": consistency,
        "source_hashes": {"v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6")},
    }
    stability["stability_sha256"] = canonical_hash(stability)
    write_json(STABILITY, stability, refresh=refresh)
    write_bytes(ROOT / "reports" / "05_p0_broad_development_execution.md", report_execution(lock, endpoints, run_root).encode("utf-8"), refresh=refresh)
    write_bytes(ROOT / "reports" / "05a_p0_leave_one_task_out_selection.md", report_loto(candidate, consistency).encode("utf-8"), refresh=refresh)
    write_bytes(ROOT / "reports" / "05b_p0_broad_selection_stability.md", report_stability(stability).encode("utf-8"), refresh=refresh)
    print(json.dumps({"endpoints_sha256": endpoints_hash, "stability_sha256": stability["stability_sha256"], "candidate_maps": list(maps)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    main(refresh=parser.parse_args().refresh)
