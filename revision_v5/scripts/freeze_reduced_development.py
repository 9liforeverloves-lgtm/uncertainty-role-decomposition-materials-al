from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CODE_PACKAGE = next(
    path
    for path in (child / "_code_package" for child in WORKSPACE.iterdir())
    if (path / "transportability_study" / "configs" / "protocol_v1.yaml").is_file()
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(paths):
    return [
        {
            "path": path.relative_to(WORKSPACE).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(paths)
    ]


protocol = ROOT / "14_reduced_development_protocol.md"
manifest_csv = ROOT / "manifests_v4" / "development_manifest_reduced.csv"
manifest_json = ROOT / "manifests_v4" / "development_manifest_reduced.json"
environment = ROOT / "environment-lock.txt"
code_files = [
    path
    for folder in (ROOT / "experiments_v4" / "src", ROOT / "scripts", ROOT / "tests")
    for path in folder.rglob("*.py")
    if "__pycache__" not in path.parts
]
data_files = [
    CODE_PACKAGE / "results" / "benchmark" / task / "materials.csv"
    for task in ("matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh")
]
code_records = records(code_files)
data_records = records(data_files)
code_tree_hash = hashlib.sha256(
    json.dumps(code_records, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
data_tree_hash = hashlib.sha256(
    json.dumps(data_records, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
payload = {
    "status": "REDUCED_DEVELOPMENT_FROZEN_BEFORE_OUTCOMES",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "confirmation_released": False,
    "protocol": {"path": protocol.relative_to(ROOT).as_posix(), "sha256": sha(protocol)},
    "strategy_definitions": {
        "path": "experiments_v4/src/transportability_v5/strategies.py",
        "sha256": sha(ROOT / "experiments_v4/src/transportability_v5/strategies.py"),
    },
    "code_tree_sha256": code_tree_hash,
    "code_files": code_records,
    "data_tree_sha256": data_tree_hash,
    "data_files": data_records,
    "seeds": list(range(1000, 1010)),
    "manifest": {
        "csv_path": manifest_csv.relative_to(ROOT).as_posix(),
        "csv_sha256": sha(manifest_csv),
        "json_path": manifest_json.relative_to(ROOT).as_posix(),
        "json_sha256": sha(manifest_json),
        "job_count": 2240,
    },
    "environment": {"path": environment.relative_to(ROOT).as_posix(), "sha256": sha(environment)},
    "selection_rule": {
        "outer": "leave_one_task_out",
        "primary": "mean_top1_recall_normalized_auc",
        "near_tie_absolute_nauc": 0.005,
        "ordered_ties": ["worst_environment_mean", "lower_complexity", "lexical_identity"],
    },
    "primary_endpoint": "selectable_pool_top1_recall_normalized_auc_including_initial_state",
    "tie_breaking": "descending_score_then_ascending_stable_candidate_id",
    "failure_rule": "atomic resumable; retry unchanged; require 10 paired seeds or explicit exclusion",
}
output = ROOT / "15_development_freeze_lock.json"
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"lock": str(output), "sha256": sha(output), "code_files": len(code_records)}))
