from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CODE_PACKAGE = next(
    path for path in (child / "_code_package" for child in WORKSPACE.iterdir())
    if (path / "transportability_study/configs/protocol_v1.yaml").is_file()
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(paths):
    rows = [{"path": p.relative_to(WORKSPACE).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
            for p in sorted(paths)]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return digest, rows


protocol = ROOT / "20_confirmation_protocol_v5_rc1.md"
manifest = ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv"
manifest_json = ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.json"
selection = ROOT / "19_selected_policy_lock.json"
code_files = [
    path for folder in (ROOT / "experiments_v4/src", ROOT / "scripts", ROOT / "tests")
    for path in folder.rglob("*.py") if "__pycache__" not in path.parts
]
data_files = [
    CODE_PACKAGE / "results" / "benchmark" / task / "materials.csv"
    for task in ("matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh")
]
code_hash, code_rows = tree(code_files)
data_hash, data_rows = tree(data_files)
manifest_meta = json.loads(manifest_json.read_text(encoding="utf-8"))
selection_meta = json.loads(selection.read_text(encoding="utf-8"))
if selection_meta["status"] != "DEVELOPMENT_SELECTION_LOCKED":
    raise SystemExit("selected-policy lock is not valid")
payload = {
    "status": "CONFIRMATION_FROZEN_BEFORE_OUTCOMES",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "manifest_path": manifest.relative_to(ROOT).as_posix(),
    "manifest_sha256": sha(manifest),
    "manifest_json_sha256": sha(manifest_json),
    "job_count": manifest_meta["job_count"],
    "protocol_path": protocol.relative_to(ROOT).as_posix(),
    "protocol_sha256": sha(protocol),
    "selected_policy_lock_sha256": sha(selection),
    "code_tree_sha256": code_hash,
    "code_files": code_rows,
    "data_tree_sha256": data_hash,
    "data_files": data_rows,
    "environment_sha256": sha(ROOT / "environment-lock.txt"),
    "confirmation_seeds": list(range(5000, 5040)),
    "inference_unit": "paired_seed_within_environment",
    "primary_endpoints": ["campaign_mace", "top1_recall_normalized_auc"],
    "tie_breaking": "descending_score_then_ascending_stable_candidate_id",
    "failure_rule": "atomic resumable unchanged retry; require 40 pairs or explicit exclusion",
    "stopping_rule": "no interim outcome-based stopping",
}
output = ROOT / "manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json"
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"job_count": payload["job_count"], "lock_sha256": sha(output)}))
