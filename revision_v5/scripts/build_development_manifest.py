from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path


ROOT=Path(r"C:\Users\ROG\Desktop\贝叶斯优化\revision_v5")
TASKS=("matbench_expt_gap","matbench_mp_gap","matbench_log_gvrh","matbench_log_kvrh")
SPLITS=("iid_record","chemical_system_ood")
MODELS=("random_forest","extra_randomized_bagging")
SEEDS=tuple(range(1000,1010))
BETA_TOKENS=("0","0p125","0p25","0p5","1","2","4","8")
FEATURES=(
    "log_raw_uncertainty","log_leaf_density","log_descriptor_distance",
    "predictive_mean_percentile","log_local_standardized_residual","log_local_residual_dispersion",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variants():
    output=[
        ("random",{}),
        ("uncertainty_only",{}),
        ("gg_calibration_only",{}),
        ("gg_acquisition_only",{}),
        ("candidate_specific_original",{"objective":"pairwise_ranking","feature_indices":list(range(6)),"top_q_pair_weight":2.0}),
        ("candidate_specific_no_top_weight",{"objective":"pairwise_ranking","feature_indices":list(range(6)),"top_q_pair_weight":1.0}),
        ("candidate_specific_direct_ridge",{"objective":"direct_log_abs_standardized_residual","feature_indices":list(range(6))}),
        ("candidate_specific_calibration_ridge",{"objective":"calibration_ridge","feature_indices":list(range(6))}),
    ]
    output.extend((f"raw_ucb_beta_{token}",{}) for token in BETA_TOKENS)
    output.extend((f"gg_ucb_beta_{token}",{}) for token in BETA_TOKENS)
    output.extend((f"candidate_specific_only_f{index+1}",{"objective":"pairwise_ranking","feature_indices":[index]}) for index in range(6))
    output.extend((f"candidate_specific_without_f{index+1}",{"objective":"pairwise_ranking","feature_indices":[j for j in range(6) if j!=index]}) for index in range(6))
    return output


def main():
    protocol=ROOT/"03_frozen_v4_protocol.md"
    rows=[]
    for (name,config),(task,split,model,seed) in itertools.product(variants(),itertools.product(TASKS,SPLITS,MODELS,SEEDS)):
        job_id=f"{task}__{split}__{model}__{name}__seed{seed}"
        rows.append({
            "schema_version":"transportability-v5-development-v1",
            "job_id":job_id,"task":task,"split_protocol":split,"model":model,"strategy":name,"seed":seed,
            "candidate_specific_config_json":json.dumps(config,sort_keys=True,separators=(",",":")),
            "status":"PLANNED",
            "expected_output_relative_path":f"results_v4/development/trajectories/{job_id}",
            "protocol_sha256":sha(protocol),
        })
    path=ROOT/"manifests_v4"/"DEVELOPMENT_JOB_MANIFEST_V5.csv"
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    lock={
        "status":"DEVELOPMENT_SPEC_LOCKED_NO_OUTCOMES_READ",
        "manifest_sha256":sha(path),
        "protocol_sha256":sha(protocol),
        "job_count":len(rows),
        "environment_count":len(TASKS)*len(SPLITS)*len(MODELS),
        "seeds":list(SEEDS),
        "strategies":[name for name,_ in variants()],
        "beta_grid":[0,.125,.25,.5,1,2,4,8],
        "feature_names":list(FEATURES),
        "confirmation_manifest_released":False,
    }
    (ROOT/"manifests_v4"/"DEVELOPMENT_SPEC_LOCK_V5.json").write_text(json.dumps(lock,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
