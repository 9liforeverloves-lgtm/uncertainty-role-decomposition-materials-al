#!/usr/bin/env python3
"""Build final claim and number traceability from locked V5 artifacts."""

from pathlib import Path
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
LOCK = json.loads((TABLES / "FINAL_TABLE_LOCK_V5.json").read_text(encoding="utf-8"))
PRIMARY = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")

TABLE_LOCK = __import__("hashlib").sha256(
    (TABLES / "FINAL_TABLE_LOCK_V5.json").read_bytes()
).hexdigest()
RESULT_LOCK = PRIMARY["result_lock_hash"].iloc[0]
TREE_LOCK = PRIMARY["trajectory_content_tree_hash"].iloc[0]
POLICY_LOCK = PRIMARY["selected_policy_lock_hash"].iloc[0]


def claim(claim_id, section, text, status, evidence, source, wording):
    return {
        "claim_id": claim_id,
        "manuscript_section": section,
        "claim": text,
        "status": status,
        "evidence_classification": evidence,
        "source_final_artifact": source,
        "allowed_wording": wording,
        "final_table_lock_hash": TABLE_LOCK,
        "result_lock_hash": RESULT_LOCK,
        "trajectory_content_tree_hash": TREE_LOCK,
        "selected_policy_lock_hash": POLICY_LOCK,
    }


claims = [
    claim("C01", "Methods—Study design", "Confirmation design contains four tasks, two splits, two surrogates, 84 strategy-environment cells, and 3360 jobs.", "verified", "frozen_manifest", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "Exact manifest counts."),
    claim("C02", "Methods—Endpoints", "L1 Campaign MACE passed all four checkpoint validation gates.", "verified", "endpoint_validation", "tables_v5/FINAL_TABLE_LOCK_V5.json", "L1 validated at 4/4 checkpoints."),
    claim("C03", "Methods—Endpoints", "L4 is Case A and all 3360 cached values reconstruct bitwise exactly.", "verified", "endpoint_validation", "audits_v5/l4_exact_execution_reconstruction_final.csv", "L4 Case A; 3360/3360 exact; maximum error 0."),
    claim("C04", "Results—Original GG", "Original GG causes significant L1 harm in all 16 environments.", "verified", "confirmatory", "tables_v5/v5_rc1_primary_contrasts_final.csv", "Original GG L1 harm in 16/16 environments."),
    claim("C05", "Results—Original GG", "Original GG L4 is heterogeneous.", "verified", "confirmatory", "tables_v5/v5_rc1_primary_contrasts_final.csv", "12/16 BH-significant, with favorable and harmful directions."),
    claim("C06", "Results—Historical CS", "Historical CS significantly harms L4 in all 16 environments.", "verified", "confirmatory", "tables_v5/v5_rc1_primary_contrasts_final.csv", "Historical CS L4 harm in 16/16 environments."),
    claim("C07", "Results—Selected GG", "Selected GG has no universal L1 or L4 benefit.", "verified", "confirmatory", "tables_v5/v5_rc1_primary_contrasts_final.csv", "Effects are environment dependent; do not claim universal superiority."),
    claim("C08", "Results—Selected CS", "Selected CS remains heterogeneous.", "verified", "confirmatory", "tables_v5/v5_rc1_primary_contrasts_final.csv", "13/16 L4 effects are BH-significant with both favorable and harmful directions."),
    claim("C09", "Results—Recovery", "Recovery exclusion preserves all eight direction, BH-label, and CI-status decisions.", "verified", "sensitivity", "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "0/8 changes for each inferential status."),
    claim("C10", "Results—Recovery", "Recovery effect magnitudes are not universally robust under the 10 percent relative criterion.", "verified", "sensitivity", "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "2/8 exceed 10 percent; maximum absolute change 0.00182503."),
    claim("C11", "Discussion", "No tested strategy has a universal transferable benefit.", "supported_with_scope", "cross_environment_summary", "tables_v5/v5_rc1_primary_contrasts_final.csv", "Limit claim to the four tasks, two splits, and two tree ensembles."),
    claim("C12", "Methods—Provenance", "Phase 5 discrepancy is newline normalization only and changes no scientific result.", "verified", "provenance", "45_phase5_hash_forensics_report.md", "46 CRLF versus 46 LF terminators; decoded lines identical."),
    claim("C13", "Limitations", "The freeze was internal, not an external preregistration.", "verified", "protocol_scope", "03_frozen_v4_protocol.md", "Internal pre-execution freeze; no external preregistration claim."),
    claim("C14", "Limitations", "The original recovery failure mechanism is unknown.", "verified", "recovery_audit", "43_recovery_sensitivity_final_report.md", "Cause unavailable; do not attribute to I/O."),
    claim("C15", "Runtime", "Observed runtime is implementation- and hardware-specific.", "verified", "descriptive", "figures_v5/final_v2/Figure08_runtime_by_task_source.csv", "Not a formal complexity analysis."),
]
pd.DataFrame(claims).to_csv(ROOT / "09_claim_evidence_matrix.csv", index=False)


rows = []


def number(section, sentence_id, value, unit, source, row_filter, contrast="", endpoint="", classification="confirmatory"):
    rows.append(
        {
            "manuscript_section": section,
            "sentence_id": sentence_id,
            "number": value,
            "unit": unit,
            "source_final_table": source,
            "row_filter": row_filter,
            "contrast": contrast,
            "endpoint": endpoint,
            "script": "scripts/generate_traceability_final.py",
            "final_table_lock_hash": TABLE_LOCK,
            "result_lock_hash": RESULT_LOCK,
            "trajectory_content_tree_hash": TREE_LOCK,
            "selected_policy_lock_hash": POLICY_LOCK,
            "evidence_classification": classification,
        }
    )


for sentence_id, value, unit, source, row_filter, classification in [
    ("M-DESIGN-01", 4, "tasks", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "nunique(task)", "frozen_manifest"),
    ("M-DESIGN-01", 2, "splits", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "nunique(split_protocol)", "frozen_manifest"),
    ("M-DESIGN-01", 2, "surrogates", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "nunique(model)", "frozen_manifest"),
    ("M-DESIGN-01", 36, "development configurations", "manifests_v4/DEVELOPMENT_JOB_MANIFEST_V5.csv", "nunique(strategy)", "development"),
    ("M-DESIGN-01", 6, "confirmation strategy identities", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "nunique(strategy)", "frozen_manifest"),
    ("M-DESIGN-01", 84, "strategy-environment cells", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "drop_duplicates(task,split,model,strategy)", "frozen_manifest"),
    ("M-DESIGN-01", 3360, "jobs", "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "all rows", "frozen_manifest"),
    ("M-INF-01", 40, "paired seeds", "tables_v5/v5_rc1_primary_contrasts_final.csv", "unique(n_pairs)", "confirmatory"),
    ("M-INF-02", 10000, "bootstrap replicates", "20_confirmation_protocol_v5_rc1.md", "protocol inference", "protocol"),
    ("M-INF-02", 10000, "sign-flip replicates", "20_confirmation_protocol_v5_rc1.md", "protocol inference", "protocol"),
    ("M-INF-02", 10001, "add-one denominator", "tables_v5/FINAL_TABLE_LOCK_V5.json", "validation.add_one_denominator", "protocol"),
    ("M-INF-03", 8, "tests per BH family", "tables_v5/v5_rc1_primary_contrasts_final.csv", "groupby(bh_family_id).size()", "confirmatory"),
    ("M-L4-01", 3360, "bitwise-exact trajectories", "audits_v5/l4_exact_execution_reconstruction_final.csv", "bitwise_equal_float64==True", "endpoint_validation"),
    ("M-L4-01", 0.0, "maximum absolute error", "audits_v5/l4_exact_execution_reconstruction_final.csv", "max(absolute_difference)", "endpoint_validation"),
    ("M-COMP-01", 3354, "COMPLETED jobs", "results_v4/confirmation/registry_snapshot.csv", "state==COMPLETED", "execution_audit"),
    ("M-COMP-01", 6, "RECOVERED jobs", "results_v4/confirmation/registry_snapshot.csv", "state==RECOVERED", "execution_audit"),
    ("M-COMP-01", 3360, "zero exit codes", "results_v4/confirmation/registry_snapshot.csv", "exit_code==0", "execution_audit"),
]:
    number(section=sentence_id.split("-")[1], sentence_id=sentence_id, value=value, unit=unit, source=source, row_filter=row_filter, classification=classification)

summary = (
    PRIMARY.groupby(["contrast_name", "endpoint"], as_index=False)
    .agg(
        significant=("significant_after_bh", "sum"),
        positive=("mean_diff", lambda x: int((x > 0).sum())),
        negative=("mean_diff", lambda x: int((x < 0).sum())),
        minimum=("mean_diff", "min"),
        maximum=("mean_diff", "max"),
    )
)
for row in summary.itertuples(index=False):
    tag = {
        "Original GG vs Raw": "OGG",
        "Historical CS vs Raw": "HCS",
        "Selected GG vs Raw": "SGG",
        "Selected CS vs Raw": "SCS",
    }[row.contrast_name]
    ep = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
    sid = f"M-RESULT-{tag}-{ep}"
    filt = f"contrast_name=={row.contrast_name}; endpoint=={row.endpoint}"
    number("Results", sid, int(row.significant), "BH-significant environments of 16", "tables_v5/v5_rc1_primary_contrasts_final.csv", filt, row.contrast_name, row.endpoint)
    number("Results", sid, int(row.positive), "positive effects of 16", "tables_v5/v5_rc1_primary_contrasts_final.csv", filt, row.contrast_name, row.endpoint)
    number("Results", sid, int(row.negative), "negative effects of 16", "tables_v5/v5_rc1_primary_contrasts_final.csv", filt, row.contrast_name, row.endpoint)
    number("Results", sid, row.minimum, "minimum effect", "tables_v5/v5_rc1_primary_contrasts_final.csv", filt, row.contrast_name, row.endpoint)
    number("Results", sid, row.maximum, "maximum effect", "tables_v5/v5_rc1_primary_contrasts_final.csv", filt, row.contrast_name, row.endpoint)

sensitivity = pd.read_csv(TABLES / "v5_rc1_recovery_sensitivity_final.csv")
for sid, value, unit, filt in [
    ("M-REC-01", 40, "primary pairs", "unique(n_pairs_primary)"),
    ("M-REC-01", 34, "sensitivity pairs", "unique(n_pairs_sensitivity)"),
    ("M-REC-02", int(sensitivity["direction_sign_changed"].sum()), "direction changes of 8", "sum(direction_sign_changed)"),
    ("M-REC-02", int(sensitivity["evidence_label_changed"].sum()), "BH-label changes of 8", "sum(evidence_label_changed)"),
    ("M-REC-02", int(sensitivity["ci_zero_status_changed"].sum()), "CI-status changes of 8", "sum(ci_zero_status_changed)"),
    ("M-REC-03", int((sensitivity["relative_effect_change"] > 0.10).sum()), "relative changes above 10 percent of 8", "relative_effect_change>0.10"),
    ("M-REC-03", sensitivity["absolute_effect_change"].max(), "maximum absolute effect change", "max(absolute_effect_change)"),
]:
    number("Recovery", sid, value, unit, "tables_v5/v5_rc1_recovery_sensitivity_final.csv", filt, classification="sensitivity")

runtime = pd.read_csv(ROOT / "figures_v5/final_v2/Figure08_runtime_by_task_source.csv")
for task in runtime["task"].unique():
    ratio = runtime.loc[runtime["task"] == task, "candidate_to_global_ratio"].iloc[0]
    number("Runtime", f"M-RUNTIME-{task}", ratio, "candidate-specific/global median ratio", "figures_v5/final_v2/Figure08_runtime_by_task_source.csv", f"task=={task}", classification="descriptive")

number("Provenance", "M-PROV-01", 4188, "frozen bytes", "45_phase5_hash_forensics_report.md", "historical frozen file", classification="provenance")
number("Provenance", "M-PROV-01", 4142, "LF-normalized bytes", "45_phase5_hash_forensics_report.md", "amended LF file", classification="provenance")
number("Provenance", "M-PROV-01", 46, "line terminators", "audits_v5/phase5_hash_chain_audit.csv", "CRLF versus LF", classification="provenance")

pd.DataFrame(rows).to_csv(ROOT / "10_number_traceability.csv", index=False)
print({"claims": len(claims), "numbers": len(rows)})
