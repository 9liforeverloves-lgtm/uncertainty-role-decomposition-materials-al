from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh")
SPLITS = ("iid_record", "chemical_system_ood")
MODELS = ("random_forest", "extra_randomized_bagging")
SEEDS = tuple(range(1000, 1010))
STRATEGIES = (
    ("raw_ucb_beta_0", {}),
    ("raw_ucb_beta_0p25", {}),
    ("raw_ucb_beta_0p5", {}),
    ("raw_ucb_beta_1", {}),
    ("raw_ucb_beta_2", {}),
    ("raw_ucb_beta_4", {}),
    ("gg_ucb_beta_0p25", {}),
    ("gg_ucb_beta_0p5", {}),
    ("gg_ucb_beta_1", {}),
    ("gg_ucb_beta_2", {}),
    ("gg_ucb_beta_4", {}),
    ("cs_da_oob_hist", {"objective": "pairwise_ranking", "feature_indices": list(range(6)),
                        "top_q_pair_weight": 2.0, "min_oob_trees_per_sample": 3}),
    ("cs_da_oob_v5", {"objective": "pairwise_ranking", "feature_indices": list(range(6)),
                      "top_q_pair_weight": 2.0, "min_oob_trees_per_sample": 10}),
    ("cs_da_oob_parsimonious_f1", {"objective": "pairwise_ranking", "feature_indices": [0],
                                   "top_q_pair_weight": 1.0, "min_oob_trees_per_sample": 10}),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = ROOT / "14_reduced_development_protocol.md"
    rows = []
    for (strategy, config), (task, split, model, seed) in itertools.product(
        STRATEGIES, itertools.product(TASKS, SPLITS, MODELS, SEEDS)
    ):
        job_id = f"{task}__{split}__{model}__{strategy}__seed{seed}"
        rows.append(
            {
                "schema_version": "transportability-v5-reduced-development-v1",
                "job_id": job_id,
                "task": task,
                "split_protocol": split,
                "model": model,
                "strategy": strategy,
                "seed": seed,
                "candidate_specific_config_json": json.dumps(config, sort_keys=True, separators=(",", ":")),
                "execution_class": "NEW_TRAJECTORY",
                "status": "PLANNED",
                "expected_output_relative_path": f"results_v4/development_reduced/trajectories/{job_id}",
                "protocol_sha256": sha(protocol),
            }
        )
    csv_path = ROOT / "manifests_v4" / "development_manifest_reduced.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    json_path = ROOT / "manifests_v4" / "development_manifest_reduced.json"
    json_path.write_text(
        json.dumps(
            {
                "schema_version": "transportability-v5-reduced-development-v1",
                "status": "FROZEN_BEFORE_REDUCED_DEVELOPMENT_OUTCOMES",
                "job_count": len(rows),
                "new_trajectory_count": len(rows),
                "historical_reuse_count": 0,
                "derived_diagnostic_trajectory_count": 320,
                "seeds": list(SEEDS),
                "strategies": [name for name, _ in STRATEGIES],
                "csv_sha256": sha(csv_path),
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"jobs": len(rows), "csv_sha256": sha(csv_path), "json_sha256": sha(json_path)}))


if __name__ == "__main__":
    main()
