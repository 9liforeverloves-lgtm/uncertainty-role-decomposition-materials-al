from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = [
    "matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_0__seed1000",
    "matbench_expt_gap__chemical_system_ood__extra_randomized_bagging__raw_ucb_beta_0p25__seed1000",
    "matbench_mp_gap__iid_record__random_forest__raw_ucb_beta_0p5__seed1000",
    "matbench_mp_gap__chemical_system_ood__extra_randomized_bagging__raw_ucb_beta_1__seed1000",
    "matbench_log_gvrh__iid_record__random_forest__raw_ucb_beta_2__seed1000",
    "matbench_log_kvrh__chemical_system_ood__extra_randomized_bagging__raw_ucb_beta_4__seed1000",
    "matbench_expt_gap__iid_record__extra_randomized_bagging__gg_ucb_beta_0p25__seed1000",
    "matbench_expt_gap__chemical_system_ood__random_forest__gg_ucb_beta_0p5__seed1000",
    "matbench_mp_gap__iid_record__extra_randomized_bagging__gg_ucb_beta_1__seed1000",
    "matbench_mp_gap__chemical_system_ood__random_forest__gg_ucb_beta_2__seed1000",
    "matbench_log_gvrh__iid_record__extra_randomized_bagging__gg_ucb_beta_4__seed1000",
    "matbench_log_kvrh__chemical_system_ood__random_forest__cs_da_oob_hist__seed1000",
    "matbench_expt_gap__iid_record__random_forest__cs_da_oob_v5__seed1000",
    "matbench_mp_gap__chemical_system_ood__extra_randomized_bagging__cs_da_oob_parsimonious_f1__seed1000",
]


def run(job: str) -> dict:
    started = time.time()
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_job.py"),
            "--phase",
            "development_reduced",
            "--job-id",
            job,
        ],
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


def main() -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, job) for job in JOBS]
        results = [future.result() for future in as_completed(futures)]
    results.sort(key=lambda row: row["job_id"])
    payload = {
        "status": "PASS" if all(row["exit_code"] == 0 for row in results) else "FAIL",
        "job_count": len(results),
        "completed": sum(row["exit_code"] == 0 for row in results),
        "covers_both_splits": True,
        "covers_both_surrogates": True,
        "covers_all_trajectory_classes": True,
        "covers_small_task_and_mp_gap": True,
        "workers": 4,
        "jobs": results,
    }
    output = ROOT / "audits_v4" / "REDUCED_DEVELOPMENT_CANARY.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "job_count", "completed")}))
    raise SystemExit(0 if payload["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
