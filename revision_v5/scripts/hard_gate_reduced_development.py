from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = ROOT / "manifests_v4" / "development_manifest_reduced.csv"
manifest_json = ROOT / "manifests_v4" / "development_manifest_reduced.json"
lock_path = ROOT / "15_development_freeze_lock.json"
lock = json.loads(lock_path.read_text(encoding="utf-8"))
with manifest.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

checks = {
    "manifest_csv_hash": lock["manifest"]["csv_sha256"] == sha(manifest),
    "manifest_json_hash": lock["manifest"]["json_sha256"] == sha(manifest_json),
    "job_count_2240": len(rows) == 2240,
    "unique_job_ids": len({row["job_id"] for row in rows}) == len(rows),
    "development_seeds_only": {int(row["seed"]) for row in rows} == set(range(1000, 1010)),
    "confirmation_seeds_absent": not ({int(row["seed"]) for row in rows} & set(range(5000, 5040))),
    "no_diagnostic_only_trajectories": not any(
        row["strategy"] in {"gg_calibration_only", "gg_acquisition_only"} for row in rows
    ),
    "confirmation_not_released": lock["confirmation_released"] is False,
    "historical_identity_present": sum(row["strategy"] == "cs_da_oob_hist" for row in rows) == 160,
    "v5_identity_present": sum(row["strategy"] == "cs_da_oob_v5" for row in rows) == 160,
}
payload = {
    "status": "PASS" if all(checks.values()) else "FAIL",
    "checks": checks,
    "passed": sum(checks.values()),
    "total": len(checks),
}
output = ROOT / "audits_v4" / "REDUCED_DEVELOPMENT_HARD_GATE.json"
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload))
raise SystemExit(0 if all(checks.values()) else 1)
