from __future__ import annotations

import argparse
import hashlib
import os
import socket
import subprocess
import sys
import time
from multiprocessing import Process,Value
from pathlib import Path

import pandas as pd


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"experiments_v4"/"src"))
from transportability_v5.registry import claim_next,connect,initialize,transition


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(phase,registry_path,limit_counter,max_jobs):
    connection=connect(registry_path)
    worker_id=f"{socket.gethostname()}-{os.getpid()}"
    while True:
        with limit_counter.get_lock():
            if max_jobs is not None and limit_counter.value>=max_jobs: return
            claim=claim_next(connection,worker_id,os.getpid(),socket.gethostname())
            if claim is None: return
            limit_counter.value+=1
        job_id=claim["job_id"]; started=time.time()
        command=[sys.executable,str(ROOT/"scripts"/"run_job.py"),"--phase",phase,"--job-id",job_id]
        completed=subprocess.run(command,text=True,capture_output=True)
        trajectory=ROOT/"results_v4"/phase/"trajectories"/job_id
        state=trajectory/"state.json"
        payload={
            "exit_code":completed.returncode,
            "runtime_seconds":time.time()-started,
            "output_path":str(trajectory.relative_to(ROOT)) if trajectory.exists() else "",
            "output_hash":sha(state) if state.is_file() else "",
            "last_error":completed.stderr[-4000:] if completed.returncode else "",
        }
        if completed.returncode==0:
            row=connection.execute("SELECT retry_count FROM jobs WHERE job_id=?",(job_id,)).fetchone()
            transition(connection,job_id,"RECOVERED" if row and row[0] else "COMPLETED",payload)
        else:
            transition(connection,job_id,"FAILED",payload)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=["development","development_reduced","confirmation"],required=True)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--max-jobs",type=int)
    args=parser.parse_args()
    if not 1<=args.workers<=8: raise SystemExit("workers must be 1-8")
    manifest={
        "development":ROOT/"manifests_v4"/"DEVELOPMENT_JOB_MANIFEST_V5.csv",
        "development_reduced":ROOT/"manifests_v4"/"development_manifest_reduced.csv",
        "confirmation":ROOT/"manifests_v4"/"CONFIRMATION_JOB_MANIFEST_V5_RC1.csv",
    }[args.phase]
    if not manifest.is_file(): raise SystemExit(f"manifest missing: {manifest}")
    table=pd.read_csv(manifest)
    registry=ROOT/"results_v4"/args.phase/"registry.sqlite"
    registry.parent.mkdir(parents=True,exist_ok=True)
    connection=initialize(registry,table.job_id.astype(str).tolist(),sha(manifest)); connection.close()
    counter=Value("i",0)
    processes=[Process(target=worker,args=(args.phase,registry,counter,args.max_jobs)) for _ in range(args.workers)]
    for process in processes: process.start()
    for process in processes: process.join()
    if any(process.exitcode for process in processes): raise SystemExit("one or more worker processes failed")
    snapshot=pd.read_sql_query("SELECT * FROM jobs ORDER BY job_id",connect(registry))
    snapshot.to_csv(ROOT/"results_v4"/args.phase/"registry_snapshot.csv",index=False)
    print(snapshot.status.value_counts().to_json())


if __name__=="__main__":
    main()
