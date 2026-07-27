from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "tables_v5" / "submission_candidate_v4_final"
OUT = ROOT / "tables_v5" / "submission_candidate_v4_final_r1"
SCRIPT = ROOT / "scripts" / "final_r1" / "build_final_r1_analyses.py"
LOCK = "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d"
RESULT = "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50"
TRAJECTORY = "e960743bec1d282e9fb3c0bb01fb0c0b6a03d5744f2902e87ffeed3ad1ab366a"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def relative(path: Path) -> str:
    return "revision_v5/" + path.relative_to(ROOT).as_posix()


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


claim_fields, claim_rows = read_csv(BASE / "09_claim_evidence_matrix_final.csv")
number_fields, number_rows = read_csv(BASE / "10_number_traceability_final.csv")
script_hash = sha256(SCRIPT)

specs = [
    (
        "R1-NLL",
        "NLL numerical-stability decision",
        "post hoc numerical-stability audit",
        "nll_contrast_stability_audit.csv",
        "contrast=ALL;environment=ALL;stage=ALL",
        "5000-5039",
        "NLL sensitivity is numerically unstable and unavailable for scientific interpretation.",
        "41/64",
        "contrasts failing the stability audit",
    ),
    (
        "R1-PRACTICAL-UNIQUE",
        "practical-significance unique comparison count",
        "descriptive analysis",
        "practical_significance_uniqueness_audit.csv",
        "unique_key=task+split+surrogate+contrast_identity;endpoint excluded",
        "5000-5039",
        "The 128 endpoint-indexed rows reduce to 64 unique strategy-environment comparisons.",
        "64",
        "unique comparisons",
    ),
    (
        "R1-PRACTICAL-CI",
        "practical-significance paired uncertainty",
        "descriptive analysis",
        "practical_significance_with_uncertainty.csv",
        "comparison_key=ALL;budget_fraction=0.20",
        "5000-5039",
        "Practical effects are paired-seed mean differences with paired-bootstrap 95% confidence intervals.",
        "95%",
        "paired-bootstrap confidence level",
    ),
    (
        "R1-OOD-ASSIGNMENT",
        "OOD role-assignment variation",
        "descriptive analysis",
        "ood_assignment_invariance_audit.csv",
        "task=ALL;seed=5000-5039",
        "5000-5039",
        "Chemical-system role assignments vary across the 40 confirmation seeds.",
        "40",
        "confirmation seeds",
    ),
    (
        "R1-OOD-DISTANCE",
        "OOD distance all-seed aggregation",
        "descriptive analysis",
        "ood_distance_reference_all_seeds.csv",
        "task=ALL;role_or_reference=ALL;aggregation=median_IQR_min_max_over_seeds",
        "5000-5039",
        "OOD reference distances are summarized over all 40 frozen split assignments.",
        "40",
        "confirmation seeds",
    ),
    (
        "R1-SENSITIVITY",
        "fixed endpoint-sensitivity labels",
        "post hoc sensitivity",
        "endpoint_sensitivity_label_numeric_summary.csv",
        "contrast_family=ALL;sensitivity_definition=ALL;NLL=unavailable",
        "5000-5039",
        "Sensitivity labels follow fixed direction, BH-status, CI-zero, and magnitude rules.",
        "0.75",
        "mostly-preserved direction-agreement threshold",
    ),
    (
        "R1-FIG2",
        "revised Figure 2 readability",
        "locked primary analysis",
        "../figures_v5/submission_candidate_v4_final_r1/Figure2_L1_All_Contrasts_source.csv",
        "endpoint=l1_campaign_mace;environment=ALL;contrast=ALL",
        "5000-5039",
        "Figure 2 preserves the locked L1 values while increasing print readability.",
        "8.5",
        "minimum figure text size in points",
    ),
    (
        "R1-FIG3",
        "revised Figure 3 readability",
        "locked primary analysis",
        "../figures_v5/submission_candidate_v4_final_r1/Figure3_L4_All_Contrasts_source.csv",
        "endpoint=l4_top1pct_recall_nauc;environment=ALL;contrast=ALL",
        "5000-5039",
        "Figure 3 preserves the locked L4 values while increasing print readability.",
        "8.5",
        "minimum figure text size in points",
    ),
]

for idx, (cid, section, evidence, filename, row_filter, cohort, sentence, value, units) in enumerate(specs, 1):
    source = OUT / filename
    if filename.startswith("../"):
        source = ROOT / filename[3:]
    source_hash = sha256(source)
    claim_rows.append(
        {
            "claim_id": cid,
            "manuscript_section": section,
            "manuscript_sentence": sentence,
            "evidence_class": evidence,
            "prospective_or_post_hoc": "confirmatory_locked" if "locked primary" in evidence else "post_hoc",
            "source_file": relative(source),
            "exact_row_filter": row_filter,
            "source_hash": source_hash,
            "analysis_script": relative(SCRIPT),
            "analysis_script_hash": script_hash,
            "task": "ALL",
            "split": "ALL",
            "surrogate": "ALL",
            "strategy": "ALL",
            "endpoint": "as stated",
            "seed_cohort": cohort,
            "manifest_hash": "not_applicable_to_derived_audit",
            "result_lock_hash": RESULT,
            "trajectory_lock_hash": TRAJECTORY,
            "final_table_lock_hash": LOCK,
            "limitation": "Post hoc/descriptive scope; frozen primary results unchanged.",
        }
    )
    number_rows.append(
        {
            "number_id": f"R1-N-{idx:03d}",
            "displayed_value": value,
            "units": units,
            "section": section,
            "sentence_id": cid,
            "source_file": relative(source),
            "exact_row_filter": row_filter,
            "source_hash": source_hash,
            "script": relative(SCRIPT),
            "script_hash": script_hash,
            "seed_cohort": cohort,
            "task": "ALL",
            "split": "ALL",
            "surrogate": "ALL",
            "strategy": "ALL",
            "endpoint": "as stated",
            "evidence_class": evidence,
            "rounding_rule": "verbatim count/threshold or displayed decimal as stated",
            "result_lock_hash": RESULT,
            "final_table_lock_hash": LOCK,
        }
    )

# Trace every displayed representative-case numeric value at its exact row.
rep = OUT / "practical_significance_representative_cases_r1.csv"
rep_fields, rep_rows = read_csv(rep)
for row_index, row in enumerate(rep_rows, 1):
    key_parts = []
    for key in ("task", "split", "surrogate", "contrast_identity"):
        if key in row:
            key_parts.append(f"{key}={row[key]}")
    row_filter = ";".join(key_parts) or f"csv_row={row_index}"
    for column in (
        "selectable_pool_size",
        "top_set_size",
        "baseline_mean_discovered",
        "test_mean_discovered",
        "paired_mean_difference",
        "bootstrap_CI_low",
        "bootstrap_CI_high",
    ):
        if column not in rep_fields or row.get(column, "") == "":
            continue
        number_rows.append(
            {
                "number_id": f"R1-REP-{row_index:02d}-{column}",
                "displayed_value": row[column],
                "units": column,
                "section": "Supplement: practical-significance representative cases",
                "sentence_id": f"R1-PRACTICAL-ROW-{row_index:02d}",
                "source_file": relative(rep),
                "exact_row_filter": row_filter,
                "source_hash": sha256(rep),
                "script": relative(SCRIPT),
                "script_hash": script_hash,
                "seed_cohort": "5000-5039",
                "task": row.get("task", "as stated"),
                "split": row.get("split", "as stated"),
                "surrogate": row.get("surrogate", "as stated"),
                "strategy": row.get("contrast_identity", "as stated"),
                "endpoint": "fixed-20%-budget top-1% discovery count",
                "evidence_class": "descriptive analysis",
                "rounding_rule": "as printed in PDF-facing representative table",
                "result_lock_hash": RESULT,
                "final_table_lock_hash": LOCK,
            }
        )

write_csv(OUT / "09_claim_evidence_matrix.csv", claim_fields, claim_rows)
write_csv(OUT / "10_number_traceability.csv", number_fields, number_rows)
print(
    {
        "claims": len(claim_rows),
        "numbers": len(number_rows),
        "claim_output": str(OUT / "09_claim_evidence_matrix.csv"),
        "number_output": str(OUT / "10_number_traceability.csv"),
    }
)
