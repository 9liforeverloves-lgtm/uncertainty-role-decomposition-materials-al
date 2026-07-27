from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_v4" / "development_reduced"
TRAJECTORIES = RESULTS / "trajectories"
TABLES = ROOT / "tables_v5"
TASKS = ("matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh")
FAMILIES = {
    "raw": ("raw_ucb_beta_0", "raw_ucb_beta_0p25", "raw_ucb_beta_0p5",
            "raw_ucb_beta_1", "raw_ucb_beta_2", "raw_ucb_beta_4"),
    "gaussian_global": ("gg_ucb_beta_0p25", "gg_ucb_beta_0p5", "gg_ucb_beta_1",
                        "gg_ucb_beta_2", "gg_ucb_beta_4"),
    "candidate_specific": ("cs_da_oob_hist", "cs_da_oob_v5", "cs_da_oob_parsimonious_f1"),
}
COMPLEXITY = {
    name: index for family in FAMILIES.values() for index, name in enumerate(family)
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def auc(frame: pd.DataFrame, column: str) -> float:
    ordered = frame.sort_values("budget_fraction")
    x = ordered["budget_fraction"].to_numpy(float)
    y = ordered[column].to_numpy(float)
    return float(np.trapezoid(y, x) / (x[-1] - x[0])) if len(x) > 1 and x[-1] > x[0] else float("nan")


def choose_family(rows: pd.DataFrame, strategies: tuple[str, ...]) -> tuple[str, pd.DataFrame]:
    subset = rows[rows.strategy.isin(strategies)]
    environment = (
        subset.groupby(["strategy", "task", "split_protocol", "model"], as_index=False)
        .primary_nauc.mean()
    )
    scores = (
        environment.groupby("strategy")
        .primary_nauc.agg(mean_primary="mean", worst_environment="min")
        .reset_index()
    )
    best_mean = scores.mean_primary.max()
    scores["within_near_tie"] = scores.mean_primary >= best_mean - 0.005
    eligible = scores[scores.within_near_tie].copy()
    eligible["complexity"] = eligible.strategy.map(COMPLEXITY)
    eligible = eligible.sort_values(
        ["worst_environment", "complexity", "strategy"],
        ascending=[False, True, True],
    )
    return str(eligible.iloc[0].strategy), scores.sort_values("mean_primary", ascending=False)


def main() -> None:
    registry = sqlite3.connect(RESULTS / "registry.sqlite")
    status = pd.read_sql_query("select job_id,status,retry_count,runtime_seconds from jobs", registry)
    terminal = {"COMPLETED", "RECOVERED", "FAILED", "EXCLUDED_WITH_REASON"}
    if len(status) != 2240 or not set(status.status).issubset(terminal):
        raise SystemExit("development registry is not fully terminal")
    if (status.status.isin(["FAILED", "EXCLUDED_WITH_REASON"])).any():
        raise SystemExit("development contains failed/excluded rows")

    result_rows = []
    floor_frames = []
    for directory in sorted(TRAJECTORIES.iterdir()):
        if not directory.is_dir():
            continue
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        rounds = pd.read_parquet(directory / "rounds.parquet")
        floor_frames.append(pd.read_parquet(directory / "floor_ranking_audit.parquet"))
        last = rounds.iloc[-1]
        result_rows.append(
            {
                "job_id": state["key"],
                "task": last["task"],
                "split_protocol": last["split_protocol"],
                "model": last["model"],
                "strategy": last["strategy"],
                "seed": int(last["seed"]),
                "primary_nauc": float(state["primary_nauc"]),
                "top0p5_nauc": auc(rounds, "top0p5_recall"),
                "top2_nauc": auc(rounds, "top2_recall"),
                "top5_nauc": auc(rounds, "top5_recall"),
                "final_top1_recall": float(last["top1_recall"]),
                "runtime_seconds": float(status.loc[status.job_id == state["key"], "runtime_seconds"].iloc[0]),
                "registry_status": str(status.loc[status.job_id == state["key"], "status"].iloc[0]),
            }
        )
    results = pd.DataFrame(result_rows).sort_values("job_id")
    if len(results) != 2240 or results.job_id.nunique() != 2240:
        raise SystemExit("result count/identity failure")
    paired = results.groupby(["task", "split_protocol", "model", "strategy"]).seed.agg(
        ["count", "nunique", "min", "max"]
    )
    if not ((paired["count"] == 10) & (paired["nunique"] == 10) &
            (paired["min"] == 1000) & (paired["max"] == 1009)).all():
        raise SystemExit("paired-seed completeness failure")
    results.to_csv(TABLES / "development_complete_results.csv", index=False)

    selections = []
    score_frames = []
    for held_out in TASKS:
        training = results[results.task != held_out]
        for family, strategies in FAMILIES.items():
            selected, scores = choose_family(training, strategies)
            scores.insert(0, "held_out_task", held_out)
            scores.insert(1, "family", family)
            score_frames.append(scores)
            selections.append(
                {
                    "held_out_task": held_out,
                    "family": family,
                    "development_tasks": "|".join(task for task in TASKS if task != held_out),
                    "candidate_strategies": "|".join(strategies),
                    "valid_job_count": len(training[training.strategy.isin(strategies)]),
                    "selected_strategy": selected,
                    "tie_breaking_rule": "mean; near-tie<=0.005 then worst environment, complexity, lexical",
                }
            )
    selection_table = pd.DataFrame(selections)
    selection_table.to_csv(TABLES / "loto_selected_policies.csv", index=False)
    pd.concat(score_frames, ignore_index=True).to_csv(
        TABLES / "loto_candidate_scores.csv", index=False
    )
    floors = pd.concat(floor_frames, ignore_index=True)
    floors.to_csv(TABLES / "floor_ranking_change_audit.csv", index=False)

    lock = {
        "status": "DEVELOPMENT_SELECTION_LOCKED",
        "confirmation_outcomes_inspected": False,
        "development_results_sha256": sha(TABLES / "development_complete_results.csv"),
        "selection_table_sha256": sha(TABLES / "loto_selected_policies.csv"),
        "selection_rule_protocol_sha256": sha(ROOT / "14_reduced_development_protocol.md"),
        "selected_policies": selection_table.to_dict("records"),
        "valid_development_jobs": len(results),
        "recovered_jobs": int((results.registry_status == "RECOVERED").sum()),
    }
    lock_path = ROOT / "19_selected_policy_lock.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "results": len(results),
                "selection_rows": len(selection_table),
                "floor_rows": len(floors),
                "floor_deferred": int(floors.requires_offline_candidate_refit.fillna(False).sum()),
                "lock_sha256": sha(lock_path),
            }
        )
    )


if __name__ == "__main__":
    main()
