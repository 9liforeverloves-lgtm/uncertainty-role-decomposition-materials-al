from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = [
    "matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000",
    "matbench_expt_gap__chemical_system_ood__extra_randomized_bagging__gg_ucb_beta_1__seed5000",
    "matbench_mp_gap__iid_record__random_forest__gg_ucb_beta_0p5__seed5000",
    "matbench_mp_gap__chemical_system_ood__extra_randomized_bagging__cs_da_oob_hist__seed5000",
    "matbench_log_gvrh__iid_record__random_forest__cs_da_oob_parsimonious_f1__seed5000",
    "matbench_log_kvrh__chemical_system_ood__extra_randomized_bagging__raw_ucb_beta_2__seed5000",
]


def run(job: str) -> dict:
    started = time.time()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_job.py"), "--phase", "confirmation", "--job-id", job],
        text=True,
        capture_output=True,
    )
    return {
        "job_id": job,
        "exit_code": completed.returncode,
        "runtime_seconds": time.time() - started,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-4000:],
    }


with ThreadPoolExecutor(max_workers=4) as pool:
    results = [future.result() for future in as_completed([pool.submit(run, job) for job in JOBS])]
results.sort(key=lambda row: row["job_id"])
payload = {
    "status": "PASS" if all(row["exit_code"] == 0 for row in results) else "FAIL",
    "job_count": len(results),
    "completed": sum(row["exit_code"] == 0 for row in results),
    "covers_all_confirmation_strategy_classes": True,
    "covers_both_splits_and_surrogates": True,
    "covers_small_task_and_mp_gap": True,
    "jobs": results,
}
(ROOT / "audits_v4" / "CONFIRMATION_CANARY_V5_RC1.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({key: payload[key] for key in ("status", "job_count", "completed")}))
raise SystemExit(0 if payload["status"] == "PASS" else 1)
