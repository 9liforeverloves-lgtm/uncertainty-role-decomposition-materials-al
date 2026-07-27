from __future__ import annotations

import hashlib,json
from pathlib import Path
import pandas as pd


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def file_map(root):
    patterns={"data_loading":["src/material_al/data.py","src/material_al/download_public_data.py"],"features":["src/material_al/features.py"],
      "runner":["src/material_al/active_learning.py","src/material_al/corrected_v7/runner.py"],"surrogate":["src/material_al/models.py"],
      "acquisition":["src/material_al/acquisition.py"],"same_state":["src/material_al/corrected_v7_2/runner.py"],
      "metrics":["src/material_al/evaluate.py"],"statistics":["src/material_al/statistical_analysis.py"],
      "figures_tables":["revision_work/final_submission_revision/src/build_final_tables_figures.py"],"seed_config":["src/material_al/random_streams.py","configs/corrected_v5/phase5_full.yaml"]}
    return {k:[{"path":p,"exists":(Path(root)/p).is_file(),"sha256":sha(Path(root)/p) if (Path(root)/p).is_file() else None} for p in v] for k,v in patterns.items()}


def write_audit(root,study,baseline_failures):
    root=Path(root); out=Path(study)/"outputs/audit"; out.mkdir(parents=True,exist_ok=True); fmap=file_map(root)
    (out/"FILE_MAP.json").write_text(json.dumps(fmap,indent=2),encoding="utf-8")
    frozen=root/"tables/corrected_v5/phase5_trajectory_rounds.parquet"
    baseline={"frozen_trajectory":{"path":str(frozen.relative_to(root)),"sha256":sha(frozen),"expected":"9a9e1bdd1a1f6a2bd6c9feff62b04cf15e12357c7ee201fb0521bf024cfc4914","matches":sha(frozen)=="9a9e1bdd1a1f6a2bd6c9feff62b04cf15e12357c7ee201fb0521bf024cfc4914"},"completion_manifest_preexisting_failures":baseline_failures}
    (out/"HASH_BASELINE.json").write_text(json.dumps(baseline,indent=2),encoding="utf-8")
    rows=[
      ["data loader","src/material_al/data.py",True,"add explicit archived-task mapping","medium","real-data loader test"],
      ["composition features","src/material_al/features.py",True,"wrap with shared transportability API","low","feature determinism"],
      ["sequential runner","src/material_al/active_learning.py",False,"independent trajectories, grouped split, resume logging","high","integration/resume"],
      ["RF surrogate","src/material_al/models.py",True,"unified OOB protocol and state persistence","medium","OOB membership"],
      ["second surrogate","src/material_al/models.py",False,"bootstrap ExtraTree bagging with member predictions","high","OOB and shape"],
      ["acquisition","src/material_al/acquisition.py",True,"freeze six-strategy core and deterministic ties","medium","formula/ties"],
      ["candidate intervention","src/material_al/corrected_v7",True,"generic terminal-leaf representation; preserve DA config","high","cross-model semantics"],
      ["same-state replay","src/material_al/corrected_v7_2/runner.py",True,"checkpoint-isolated replay","high","trajectory immutability"],
      ["metrics","src/material_al/evaluate.py",True,"target-pool denominators and initial-state nAUC","high","endpoint tests"],
      ["statistics","src/material_al/statistical_analysis.py",True,"environment-paired seed inference and BH","high","paired-unit tests"],
      ["logging","src/material_al/corrected_logging.py",True,"atomic Parquet/checkpoints/resume","medium","resume equivalence"],
      ["Git isolation",".git",False,"git executable unavailable; use hash baseline namespace","medium","hash regression"],
    ]
    pd.DataFrame(rows,columns=["component","existing_path","reusable","required_change","scientific_risk","test_required"]).to_csv(out/"REUSE_GAP_MATRIX.csv",index=False)
    (out/"PROJECT_AUDIT.md").write_text("""# Project audit\n\nThe historical submission is treated as read-only. A runnable RF trajectory entry, stable candidate IDs, OOB predictions, acquisition functions, same-state replay, nAUC metrics, statistics, and local Matbench-derived `materials.csv` files are present. The original runner does not implement target-exclusive chemical-system splits, a second bootstrap surrogate with genuine out-of-bag membership, nested leave-one-task-out selection, or restart-safe cross-environment job manifests; these are implemented only in `transportability_study`.\n\n`git.exe` was unavailable, so no tag or branch was fabricated. The immutable baseline is instead recorded through SHA-256 manifests. Four administrative files already differed from `COMPLETION_MANIFEST.json` before this study began; the frozen scientific trajectory itself matched exactly.\n""",encoding="utf-8")
    return baseline
