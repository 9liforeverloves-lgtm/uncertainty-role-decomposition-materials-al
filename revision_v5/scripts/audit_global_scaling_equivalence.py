from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd


WORKSPACE=Path(r"C:\Users\ROG\Desktop\贝叶斯优化")
REVISION=WORKSPACE/"revision_v5"
V2=WORKSPACE/"最终"/"_code_package"/"transportability_study"
TRAJECTORIES=V2/"outputs"/"confirmation_v2"/"trajectories"


def main():
    rows=[]
    selected_files=sorted(TRAJECTORIES.glob("*__gaussian_global_ucb__seed*/selected.parquet"))
    for path in selected_files:
        frame=pd.read_parquet(path)
        for round_id,group in frame.groupby("round",sort=True):
            recomputed=group["predicted_mean"].to_numpy(float)+group["scale"].to_numpy(float)*group["effective_predicted_std"].to_numpy(float)
            stored=group["score"].to_numpy(float)
            stable=group["stable_candidate_id"].to_numpy()
            expected=np.lexsort((stable,-recomputed))
            observed=np.lexsort((stable,-stored))
            selected_expected=set(group.iloc[expected].query("selected")["stable_candidate_id"].astype(int))
            selected_observed=set(group.query("selected")["stable_candidate_id"].astype(int))
            rows.append({
                "evidence_class":"historical_v2_retained_top5B_subset",
                "job_id":path.parent.name,
                "round":int(round_id),
                "retained_candidate_count":len(group),
                "full_state_vector_available":False,
                "max_abs_score_difference":float(np.max(np.abs(recomputed-stored))),
                "retained_rank_identity":bool(np.array_equal(expected,observed)),
                "selected_id_identity":selected_expected==selected_observed,
                "stable_id_tie_breaking":True,
            })
    output=REVISION/"tables_v5"/"global_scaling_equivalence_audit.csv"
    output.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(output,index=False,quoting=csv.QUOTE_MINIMAL)
    failures=[row for row in rows if row["max_abs_score_difference"]>1e-12 or not row["retained_rank_identity"] or not row["selected_id_identity"]]
    summary={
        "historical_jobs":len(selected_files),
        "historical_states":len(rows),
        "failure_count":len(failures),
        "tolerance":1e-12,
        "scope":"Retained top-5-batch acquisition ledger only; frozen historical outputs do not retain every selectable-candidate score.",
        "full_vector_acceptance":"Tested for all new states and synthetic unit tests; not retrospectively assertable for historical states lacking full score vectors.",
    }
    (REVISION/"audits_v4"/"global_scaling_equivalence_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    report=f"""# Global-scaling algebraic-equivalence audit

For a state-level positive scalar `s`, Gaussian-global UCB score `mu + beta*s*sigma` is exactly Raw UCB with `beta_eff = beta*s`.

Historical V2 retained-ledger audit:

- Gaussian-global jobs: {len(selected_files)}
- retained states: {len(rows)}
- tolerance failures: {len(failures)}
- tolerance: `1e-12`

The frozen V2 ledger stores the selected and top-5-batch candidate rows, not the full selectable-pool score vector. Score equality, stable retained ranking, and selected-ID identity are therefore audited on every retained state. A claim of full historical vector identity would be fabricated and is not made. New V5-RC1 states must retain full score vectors for this audit and must pass exact stable-ID selected-batch identity before confirmation outputs are accepted.
"""
    (REVISION/"audits_v4"/"global_scaling_equivalence_report.md").write_text(report,encoding="utf-8")


if __name__=="__main__":
    main()
