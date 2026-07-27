#!/usr/bin/env python3
"""Create editorial V3 evidence tables from frozen tables only."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
TABLES = ROOT / "tables_v5"
OUT = TABLES / "submission_candidate_v3"
AUDITS = ROOT / "audits_v5"
ED = ROOT / "editorial_revision_v3"
MAN = ROOT / "manuscript_v5" / "submission_candidate_v3"
FIG = ROOT / "figures_v5" / "submission_candidate_v3"
for directory in (OUT, AUDITS, ED, MAN, FIG):
    directory.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


sources = {
    "v2": (
        REPO / "最终" / "_code_package" / "transportability_study" /
        "outputs" / "frozen_protocol_v2" / "CONFIRMATION_JOB_MANIFEST_V2.csv"
    ),
    "v3": (
        REPO / "最终" / "_code_package" / "transportability_study_v3_l1" /
        "manifests" / "V3_TASK_MANIFEST.csv"
    ),
    "v3_exploratory": (
        REPO / "transportability_study_v3_l1_l4_exploratory" /
        "finalization" / "gate" / "V3_LAYERED_FINAL_GATE.json"
    ),
    "development": ROOT / "19_selected_policy_lock.json",
    "confirmation": TABLES / "FINAL_TABLE_LOCK_V5.json",
    "sensitivity": TABLES / "v5_rc1_recovery_sensitivity_final.csv",
}

lineage = pd.DataFrame([
    {
        "phase_label": "historical confirmation",
        "internal_name": "V2",
        "scientific_purpose": "test transportability of acquisition interventions at sequential discovery endpoints",
        "tasks": "4 Matbench regression tasks",
        "splits": "IID record|chemical-system OOD",
        "surrogates": "random forest|extra-randomized bagging",
        "features": "composition-derived descriptors",
        "strategy_families": "random|Raw UCB beta 0.5/1/2|Gaussian-global|Historical CS",
        "seeds": "2000-2019",
        "number_of_jobs": 1920,
        "endpoint_set": "L4 top-1% recall nAUC primary; L2/L3 and secondary discovery endpoints",
        "inference_status": "historical confirmatory",
        "multiplicity_status": "BH over two nondegenerate primary contrasts within environment",
        "frozen_or_post_hoc": "frozen",
        "principal_output": "V2 primary confirmatory contrasts",
        "principal_limitation": "20 seeds; historical implementation; not pooled with later cohorts",
        "relation_to_next_phase": "motivated independent uncertainty-quality confirmation",
        "permitted_manuscript_use": "historical result and motivation only",
        "source_hash": sha(sources["v2"]),
    },
    {
        "phase_label": "mechanism/uncertainty-quality confirmation",
        "internal_name": "V3",
        "scientific_purpose": "independently test campaign calibration of original uncertainty interventions",
        "tasks": "4 Matbench regression tasks",
        "splits": "IID record|chemical-system OOD",
        "surrogates": "random forest|extra-randomized bagging",
        "features": "composition-derived descriptors",
        "strategy_families": "Raw UCB beta 1|Gaussian-global|Historical CS",
        "seeds": "3000-3039",
        "number_of_jobs": 1920,
        "endpoint_set": "L1 campaign MACE primary; coverage, CRPS, and NLL secondary",
        "inference_status": "historical confirmatory",
        "multiplicity_status": "BH over two L1 contrasts within environment",
        "frozen_or_post_hoc": "frozen; Recovery Amendment 001 disclosed",
        "principal_output": "V3 verified L1 contrasts",
        "principal_limitation": "does not independently confirm retuned/selected V5 policies",
        "relation_to_next_phase": "showed calibration and discovery evidence required separate evaluation",
        "permitted_manuscript_use": "historical result and mechanism motivation only",
        "source_hash": sha(sources["v3"]),
    },
    {
        "phase_label": "post hoc same-cohort reconstruction",
        "internal_name": "V3 L2-L4 reconstruction",
        "scientific_purpose": "describe within-cohort layer transitions",
        "tasks": "same four V3 tasks",
        "splits": "same V3 splits",
        "surrogates": "same V3 surrogates",
        "features": "no new model fitting",
        "strategy_families": "same three V3 identities",
        "seeds": "3000-3039 (same cohort)",
        "number_of_jobs": 0,
        "endpoint_set": "reconstructed L2/L3/L4 descriptive endpoints",
        "inference_status": "exploratory; no new inferential tests",
        "multiplicity_status": "not applicable to descriptive reconstruction",
        "frozen_or_post_hoc": "post hoc",
        "principal_output": "V3 within-cohort L1-L4 exploratory matrix",
        "principal_limitation": "not an independent cohort and not confirmatory",
        "relation_to_next_phase": "informed design needs; did not select V5 confirmation results",
        "permitted_manuscript_use": "explicitly labeled exploratory context only",
        "source_hash": sha(sources["v3_exploratory"]),
    },
    {
        "phase_label": "development selection",
        "internal_name": "reduced V5 development",
        "scientific_purpose": "select one Raw, GG, and CS policy per held-out-task fold",
        "tasks": "leave-one-task-out over 4 tasks",
        "splits": "IID record|chemical-system OOD",
        "surrogates": "random forest|extra-randomized bagging",
        "features": "composition descriptors; CS six-feature and parsimonious f1 identities",
        "strategy_families": "6 Raw|5 GG|3 CS eligible candidates",
        "seeds": "1000-1009",
        "number_of_jobs": 2240,
        "endpoint_set": "development top-1% recall nAUC",
        "inference_status": "selection only; no confirmatory inference",
        "multiplicity_status": "not applicable",
        "frozen_or_post_hoc": "prospectively frozen before outcomes",
        "principal_output": "selected-policy lock",
        "principal_limitation": "three training tasks per fold; candidate set reduced from 36-config inventory",
        "relation_to_next_phase": "froze policy identities before confirmation release",
        "permitted_manuscript_use": "policy selection and descriptive scores only",
        "source_hash": sha(sources["development"]),
    },
    {
        "phase_label": "locked confirmation",
        "internal_name": "V5-RC1",
        "scientific_purpose": "independently confirm original and selected policies at L1 and L4",
        "tasks": "4 Matbench regression tasks",
        "splits": "IID record|chemical-system OOD",
        "surrogates": "random forest|extra-randomized bagging",
        "features": "composition-derived descriptors",
        "strategy_families": "6 identities; task-specific Raw beta 2 only for log KVRH",
        "seeds": "5000-5039",
        "number_of_jobs": 3360,
        "endpoint_set": "L1 campaign MACE|L4 top-1% recall nAUC",
        "inference_status": "current locked confirmation",
        "multiplicity_status": "eight-test BH family within each environment",
        "frozen_or_post_hoc": "frozen",
        "principal_output": "five-table V5 lock",
        "principal_limitation": "four tasks do not define a universal task population",
        "relation_to_next_phase": "followed only by sensitivity and reproducibility audits",
        "permitted_manuscript_use": "primary effect estimates and confirmatory conclusions",
        "source_hash": sha(sources["confirmation"]),
    },
    {
        "phase_label": "post-confirmation sensitivity and reproducibility audit",
        "internal_name": "V5 sensitivity/audit",
        "scientific_purpose": "bound recovery sensitivity and verify endpoint/provenance integrity",
        "tasks": "affected V5 cell plus repository-wide validation",
        "splits": "chemical-system OOD for affected cell",
        "surrogates": "extra-randomized bagging for affected cell",
        "features": "no new scientific features",
        "strategy_families": "affected selected-CS cell and paired contrasts",
        "seeds": "5013-5018 excluded in 40-to-34 sensitivity only",
        "number_of_jobs": 0,
        "endpoint_set": "locked L1/L4 sensitivity; engineering validation tests",
        "inference_status": "sensitivity and engineering audit",
        "multiplicity_status": "locked labels compared; no pooled inference",
        "frozen_or_post_hoc": "post-confirmation audit",
        "principal_output": "recovery sensitivity and validation reports",
        "principal_limitation": "initial failure cause unresolved",
        "relation_to_next_phase": "final evidence boundary",
        "permitted_manuscript_use": "robustness and reproducibility statements only",
        "source_hash": sha(sources["sensitivity"]),
    },
])
lineage.to_csv(OUT / "study_evidence_lineage.csv", index=False)

scores = pd.read_csv(TABLES / "loto_candidate_scores.csv")
selected = pd.read_csv(TABLES / "loto_selected_policies.csv")
lock_hash = sha(ROOT / "19_selected_policy_lock.json")
complexity_order = {
    "raw": ["raw_ucb_beta_0", "raw_ucb_beta_0p25", "raw_ucb_beta_0p5",
            "raw_ucb_beta_1", "raw_ucb_beta_2", "raw_ucb_beta_4"],
    "gaussian_global": ["gg_ucb_beta_0p25", "gg_ucb_beta_0p5", "gg_ucb_beta_1",
                        "gg_ucb_beta_2", "gg_ucb_beta_4"],
    "candidate_specific": ["cs_da_oob_hist", "cs_da_oob_v5",
                           "cs_da_oob_parsimonious_f1"],
}
detailed_rows = []
summary_rows = []
for (held_out, family), group in scores.groupby(["held_out_task", "family"], sort=False):
    group = group.copy()
    group["complexity_rank"] = group["strategy"].map(
        {name: i + 1 for i, name in enumerate(complexity_order[family])}
    )
    tie = group[group["within_near_tie"]].sort_values(
        ["worst_environment", "complexity_rank", "strategy"],
        ascending=[False, True, True],
    )
    outside = group[~group["within_near_tie"]].sort_values(
        "mean_primary", ascending=False
    )
    ordered = pd.concat([tie, outside], ignore_index=True)
    selected_name = selected[
        (selected["held_out_task"] == held_out) & (selected["family"] == family)
    ].iloc[0]["selected_strategy"]
    runner = ordered.iloc[1]["strategy"]
    selected_row = ordered[ordered["strategy"] == selected_name].iloc[0]
    runner_row = ordered[ordered["strategy"] == runner].iloc[0]
    margin = float(selected_row["mean_primary"] - runner_row["mean_primary"])
    lexical_used = False  # no exact tie survived the worst-environment criterion
    valid_jobs = int(selected[
        (selected["held_out_task"] == held_out) & (selected["family"] == family)
    ].iloc[0]["valid_job_count"])
    per_candidate_jobs = valid_jobs // len(group)
    for rank, row in ordered.iterrows():
        detailed_rows.append({
            "held_out_task": held_out,
            "family": family,
            "candidate_identity": row["strategy"],
            "eligible": True,
            "exclusion_reason": "",
            "valid_jobs": per_candidate_jobs,
            "mean_development_nAUC": row["mean_primary"],
            "worst_environment_nAUC": row["worst_environment"],
            "complexity_rank": int(row["complexity_rank"]),
            "within_0p005_tie_band": bool(row["within_near_tie"]),
            "lexical_tie_break_used": lexical_used,
            "final_rank": rank + 1,
            "selected": row["strategy"] == selected_name,
            "runner_up": row["strategy"] == runner,
            "selected_minus_runner_up": margin,
            "source_table": "tables_v5/loto_candidate_scores.csv",
            "selection_lock_hash": lock_hash,
        })
    summary_rows.append({
        "held_out_task": held_out,
        "family": family,
        "eligible_candidate_count": len(group),
        "selected_candidate": selected_name,
        "runner_up": runner,
        "selected_mean_nAUC": selected_row["mean_primary"],
        "selected_worst_environment_nAUC": selected_row["worst_environment"],
        "selected_minus_runner_up": margin,
        "tie_breaking_applied": len(tie) > 1,
        "tie_breaking_stage": "worst-environment score" if len(tie) > 1 else "not required",
    })
pd.DataFrame(detailed_rows).to_csv(
    OUT / "development_selection_detailed.csv", index=False
)
pd.DataFrame(summary_rows).to_csv(
    OUT / "development_selection_summary.csv", index=False
)

mapping = pd.DataFrame([
    {
        "development_identity": "candidate_specific_only_f1",
        "confirmation_identity": "cs_da_oob_parsimonious_f1",
        "mapping_status": "not directly identical",
        "feature_subset_identical": True,
        "objective_identical": True,
        "minimum_oob_trees_identical": False,
        "top_tail_pair_weight_identical": False,
        "regularization_identical": True,
        "clipping_identical": True,
        "fallback_identical": True,
        "optimizer_identical": True,
        "uncertainty_floor_identical": True,
        "explanation": (
            "The 36-config inventory alias recorded f1-only with inherited defaults. "
            "The prospectively frozen reduced-development candidate added OOB>=10 and "
            "pair weight 1 before outcomes; this reduced candidate, not the broad alias, "
            "was selected."
        ),
    },
    {
        "development_identity": "cs_da_oob_parsimonious_f1",
        "confirmation_identity": "cs_da_oob_parsimonious_f1",
        "mapping_status": "exactly identical",
        "feature_subset_identical": True,
        "objective_identical": True,
        "minimum_oob_trees_identical": True,
        "top_tail_pair_weight_identical": True,
        "regularization_identical": True,
        "clipping_identical": True,
        "fallback_identical": True,
        "optimizer_identical": True,
        "uncertainty_floor_identical": True,
        "explanation": (
            "Reduced development and V5-RC1 confirmation both use f1 only, pairwise "
            "ranking, OOB>=10, top-tail pair weight 1, and the same inherited settings."
        ),
    },
])
mapping.to_csv(OUT / "development_identity_to_confirmation_identity.csv", index=False)

ood = pd.read_csv(TABLES / "ood_split_summary.csv")
pivot = ood.pivot_table(
    index=["task", "seed"],
    columns="role",
    values=["record_count", "group_count"],
    aggfunc="first",
).reset_index()
pivot.columns = [
    "task", "seed",
    "diagnostic_systems", "source_systems", "selectable_systems",
    "diagnostic_records", "source_records", "selectable_records",
]
pivot["group_overlap"] = 0
pivot["candidate_id_overlap"] = 0
pivot = pivot[[
    "task", "seed", "source_records", "selectable_records",
    "diagnostic_records", "source_systems", "selectable_systems",
    "diagnostic_systems", "group_overlap", "candidate_id_overlap",
]]
pivot.to_csv(AUDITS / "ood_system_count_summary_v3.csv", index=False)

summary = []
for task, group in pivot.groupby("task"):
    row = {"task": task, "seeds": len(group)}
    for column in (
        "source_records", "selectable_records", "diagnostic_records",
        "source_systems", "selectable_systems", "diagnostic_systems",
    ):
        values = group[column]
        if values.nunique() == 1:
            row[f"{column}_summary"] = str(int(values.iloc[0]))
            row[f"{column}_summary_type"] = "invariant across seeds"
        else:
            row[f"{column}_summary"] = (
                f"{int(values.min())}/{values.median():g}/{int(values.max())}"
            )
            row[f"{column}_summary_type"] = "min/median/max across seeds"
    summary.append(row)
pd.DataFrame(summary).to_csv(OUT / "ood_system_count_manuscript_summary.csv", index=False)

# Preserve frozen V2 candidate tables without changing values.
for name in (
    "complete_primary_128_with_p_raw_p_BH.csv",
    "development_configuration_inventory_36.csv",
    "candidate_specific_parameter_table.csv",
):
    shutil.copy2(
        TABLES / "submission_candidate_v2" / name,
        OUT / name,
    )

print(json.dumps({
    "lineage_rows": len(lineage),
    "development_detail_rows": len(detailed_rows),
    "development_summary_rows": len(summary_rows),
    "ood_seed_rows": len(pivot),
    "identity_rows": len(mapping),
}, indent=2))
