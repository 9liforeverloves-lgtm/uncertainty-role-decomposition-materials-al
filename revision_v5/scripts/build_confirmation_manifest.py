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
SEEDS = tuple(range(5000, 5040))
COMMON = (
    ("raw_ucb_beta_1", {}),
    ("gg_ucb_beta_1", {}),
    ("gg_ucb_beta_0p5", {}),
    ("cs_da_oob_hist", {"objective": "pairwise_ranking", "feature_indices": list(range(6)),
                        "top_q_pair_weight": 2.0, "min_oob_trees_per_sample": 3}),
    ("cs_da_oob_parsimonious_f1", {"objective": "pairwise_ranking", "feature_indices": [0],
                                   "top_q_pair_weight": 1.0, "min_oob_trees_per_sample": 10}),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = ROOT / "20_confirmation_protocol_v5_rc1.md"
selection_lock = ROOT / "19_selected_policy_lock.json"
rows = []
for task in TASKS:
    strategies = COMMON + ((("raw_ucb_beta_2", {}),) if task == "matbench_log_kvrh" else ())
    for (strategy, config), (split, model, seed) in itertools.product(
        strategies, itertools.product(SPLITS, MODELS, SEEDS)
    ):
        job_id = f"{task}__{split}__{model}__{strategy}__seed{seed}"
        rows.append(
            {
                "schema_version": "transportability-v5-rc1-confirmation-v1",
                "job_id": job_id,
                "task": task,
                "split_protocol": split,
                "model": model,
                "strategy": strategy,
                "seed": seed,
                "candidate_specific_config_json": json.dumps(config, sort_keys=True, separators=(",", ":")),
                "status": "PLANNED",
                "expected_output_relative_path": f"results_v4/confirmation/trajectories/{job_id}",
                "protocol_sha256": sha(protocol),
                "selection_lock_sha256": sha(selection_lock),
            }
        )
path = ROOT / "manifests_v4" / "CONFIRMATION_JOB_MANIFEST_V5_RC1.csv"
with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
summary = {
    "status": "CONFIRMATION_MANIFEST_CREATED_BEFORE_OUTCOMES",
    "job_count": len(rows),
    "seeds": list(SEEDS),
    "task_strategy_counts": {
        task: len(COMMON) + (1 if task == "matbench_log_kvrh" else 0) for task in TASKS
    },
    "derived_diagnostic_groups": 640,
    "manifest_sha256": sha(path),
}
(ROOT / "manifests_v4" / "CONFIRMATION_JOB_MANIFEST_V5_RC1.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(summary))
