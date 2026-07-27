from __future__ import annotations

from pathlib import Path

import pandas as pd

from .provenance import SCHEMA_VERSION, canonical_relative, read_protocol, sha256_file


def write_smoke_manifest(project_root: Path, study_root: Path, rows: list[dict], filename: str) -> Path:
    project_root=Path(project_root); study_root=Path(study_root)
    protocol_path,_,_=read_protocol(study_root); analysis_plan=study_root/"docs/ANALYSIS_PLAN.md"
    frame=pd.DataFrame(rows)
    if frame["job_id"].duplicated().any(): raise ValueError("smoke manifest contains duplicate job IDs")
    frame["protocol_path"]=canonical_relative(project_root,protocol_path)
    frame["protocol_sha256"]=sha256_file(protocol_path)
    frame["analysis_plan_sha256"]=sha256_file(analysis_plan)
    frame["schema_version"]=SCHEMA_VERSION
    frame["status"]="PENDING"
    if filename not in {"SYNTHETIC_SMOKE_JOB_MANIFEST.csv", "REAL_SMOKE_JOB_MANIFEST.csv"}:
        raise ValueError("unrecognized smoke manifest filename")
    path=study_root/"outputs/smoke"/filename; path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_csv(path,index=False)
    return path
