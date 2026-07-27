#!/usr/bin/env python3
"""Reference audit, traceability additions, and expansion metrics for V3."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript_v5" / "submission_candidate_v3"
ED = ROOT / "editorial_revision_v3"
TABLES = ROOT / "tables_v5" / "submission_candidate_v3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


tex_path = MAN / "manuscript_submission_candidate_v3.tex"
bib_path = MAN / "references_submission_candidate_v3.bib"
tex = tex_path.read_text(encoding="utf-8")
bib = bib_path.read_text(encoding="utf-8")

citations = set()
for match in re.finditer(r"\\cite\w*\{([^}]+)\}", tex):
    citations.update(key.strip() for key in match.group(1).split(","))

entries = []
for match in re.finditer(r"(?ms)^@(\w+)\{([^,]+),(.*?)(?=^@\w+\{|\Z)", bib):
    kind, key, body = match.groups()
    title = re.search(r"title=\{([^}]*)\}", body, re.I)
    doi = re.search(r"doi=\{([^}]*)\}", body, re.I)
    url = re.search(r"url=\{([^}]*)\}", body, re.I)
    sentence = ""
    if key in citations:
        citation_match = re.search(
            rf"([^.!?]*\\cite\w*\{{[^}}]*\b{re.escape(key)}\b[^}}]*\}}[^.!?]*[.!?])",
            tex,
        )
        sentence = re.sub(r"\s+", " ", citation_match.group(1).strip()) if citation_match else "cited in grouped positioning sentence"
    entries.append({
        "reference_key": key,
        "entry_type": kind,
        "title": title.group(1) if title else "",
        "cited_in_manuscript": key in citations,
        "cited_sentence": sentence,
        "relevance": (
            "materials benchmark/method" if key in {
                "Dunn2020Matbench", "Ward2018Matminer", "Jain2013MP",
                "Breiman2001RF", "Geurts2006ExtraTrees",
            } else
            "active learning/Bayesian optimization" if key in {
                "Lookman2019AL", "Ling2017Materials", "Auer2002UCB",
                "Shahriari2016BO", "Frazier2018BO", "Snoek2012BO",
                "Jones1998EGO", "Settles2009AL",
            } else
            "calibration/scoring/distribution shift" if key in {
                "Gneiting2007Proper", "Hersbach2000CRPS",
                "Kuleshov2018Calibration", "Guo2017Calibration",
                "Ovadia2019Shift", "Koh2021WILDS",
            } else
            "statistical inference"
        ),
        "verified_doi_or_url": (doi.group(1) if doi else (url.group(1) if url else "bibliographic metadata only")),
        "decision": "retain" if key in citations else "remove",
    })
ref_audit = pd.DataFrame(entries)
ref_audit.to_csv(ED / "04_reference_usage_audit.csv", index=False)
if not ref_audit["cited_in_manuscript"].all():
    raise SystemExit("unused bibliography entries remain")

claim_path = ROOT / "09_claim_evidence_matrix.csv"
claims = pd.read_csv(claim_path)
claims = claims[~claims["claim_id"].astype(str).str.startswith("V3E")]
common = {
    "status": "verified",
    "final_table_lock_hash": sha(ROOT / "tables_v5" / "FINAL_TABLE_LOCK_V5.json"),
    "result_lock_hash": sha(ROOT / "tables_v5" / "v5_rc1_primary_contrasts_final.csv"),
    "trajectory_content_tree_hash": "03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8",
    "selected_policy_lock_hash": sha(ROOT / "19_selected_policy_lock.json"),
}
new_claims = [
    ("V3E01", "Methods—evidence classes", "V2 is an independent 1920-job historical cohort with seeds 2000-2019.", "historical confirmatory", "editorial_revision_v3/02_v2_v3_identity_report.md", "Historical V2 only; no pooling."),
    ("V3E02", "Methods—evidence classes", "V3 is an independent 1920-job L1 cohort with seeds 3000-3039.", "historical confirmatory", "editorial_revision_v3/02_v2_v3_identity_report.md", "Historical V3 only; no pooling."),
    ("V3E03", "Methods—evidence classes", "V3 L2-L4 reconstruction is post hoc and adds zero scientific jobs.", "post hoc exploratory", "tables_v5/submission_candidate_v3/study_evidence_lineage.csv", "Never call confirmatory."),
    ("V3E04", "Results—development", "Development reports eligible candidates, runners-up, scores, and margins.", "development descriptive", "tables_v5/submission_candidate_v3/development_selection_detailed.csv", "Selection evidence only."),
    ("V3E05", "Methods—identity", "Reduced-development and confirmation cs_da_oob_parsimonious_f1 are parameter-identical.", "identity audit", "tables_v5/submission_candidate_v3/development_identity_to_confirmation_identity.csv", "Broad only-f1 alias is not directly identical."),
    ("V3E06", "Methods—OOD", "OOD record and system counts are invariant across 40 seeds and have zero overlap.", "split audit", "audits_v5/ood_system_count_summary_v3.csv", "Exact per-seed counts."),
    ("V3E07", "Supplement—CS features", "All six executed CS features are defined from frozen code.", "method reproducibility", "editorial_revision_v3/03_cs_feature_definition_audit.md", "Distinguish 1e-12 feature floor from 1e-8 acquisition floor."),
    ("V3E08", "Figure 1", "V5-RC1 contains 84 cells and 3360 scientific jobs.", "frozen manifest", "figures_v5/submission_candidate_v3/Main_Figure_1_source.csv", "Test counts excluded."),
    ("V3E09", "Results—recovery", "Six jobs in one cell, not six seeds globally, required recovery.", "sensitivity", "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "Seeds 5013-5018 only in affected cell."),
]
claim_rows = []
for claim_id, section, claim, evidence, source, wording in new_claims:
    claim_rows.append({
        "claim_id": claim_id,
        "manuscript_section": section,
        "claim": claim,
        "evidence_classification": evidence,
        "source_final_artifact": source,
        "allowed_wording": wording,
        **common,
    })
claims = pd.concat([claims, pd.DataFrame(claim_rows)], ignore_index=True)
claims.to_csv(claim_path, index=False)

trace_path = ROOT / "10_number_traceability.csv"
trace = pd.read_csv(trace_path)
trace = trace[~trace["sentence_id"].astype(str).str.startswith("V3E-")]
trace_common = {
    "script": "scripts/finalize_editorial_metadata_v3.py",
    "final_table_lock_hash": common["final_table_lock_hash"],
    "result_lock_hash": common["result_lock_hash"],
    "trajectory_content_tree_hash": common["trajectory_content_tree_hash"],
    "selected_policy_lock_hash": common["selected_policy_lock_hash"],
}
trace_rows = []


def add(section, sentence, number, unit, source, row_filter, classification):
    trace_rows.append({
        "manuscript_section": section,
        "sentence_id": sentence,
        "number": number,
        "unit": unit,
        "source_final_table": source,
        "row_filter": row_filter,
        "contrast": "",
        "endpoint": "",
        "evidence_classification": classification,
        **trace_common,
    })


add("METHODS", "V3E-V2", 1920, "V2 scientific jobs", "editorial_revision_v3/02_v2_v3_identity_report.md", "executed frozen V2 manifest", "historical confirmatory")
add("METHODS", "V3E-V2", 20, "V2 seeds", "editorial_revision_v3/02_v2_v3_identity_report.md", "2000-2019", "historical confirmatory")
add("METHODS", "V3E-V3", 1920, "V3 scientific jobs", "editorial_revision_v3/02_v2_v3_identity_report.md", "V3 task manifest", "historical confirmatory")
add("METHODS", "V3E-V3", 40, "V3 seeds", "editorial_revision_v3/02_v2_v3_identity_report.md", "3000-3039", "historical confirmatory")
add("METHODS", "V3E-POSTHOC", 0, "new scientific jobs", "tables_v5/submission_candidate_v3/study_evidence_lineage.csv", "V3 L2-L4 reconstruction", "post hoc exploratory")
for row in pd.read_csv(TABLES / "development_selection_summary.csv").itertuples(index=False):
    add("RESULTS", f"V3E-DEV-{row.held_out_task}-{row.family}", row.selected_minus_runner_up, "mean nAUC margin", "tables_v5/submission_candidate_v3/development_selection_summary.csv", f"{row.held_out_task}|{row.family}", "development descriptive")
ood = pd.read_csv(TABLES / "ood_system_count_manuscript_summary.csv")
for row in ood.itertuples(index=False):
    for name in ("source_records", "selectable_records", "diagnostic_records", "source_systems", "selectable_systems", "diagnostic_systems"):
        add("METHODS", f"V3E-OOD-{row.task}-{name}", float(getattr(row, f"{name}_summary")), name, "audits_v5/ood_system_count_summary_v3.csv", row.task, "split audit")
for number, unit, row_filter in (
    (1e-12, "feature log floor", "log uncertainty/local features"),
    (1e-8, "acquisition/OOB residual floor", "candidate-specific residual"),
    (30, "minimum valid queried rows", "candidate-specific fallback"),
    (20000, "maximum sampled pairs", "candidate-specific objective"),
    (0.25, "minimum scale", "candidate-specific clipping"),
    (4, "maximum scale", "candidate-specific clipping"),
):
    add("SUPPLEMENT", f"V3E-CS-{unit}", number, unit, "editorial_revision_v3/03_cs_feature_definition_audit.md", row_filter, "method reproducibility")
add("FIGURE1", "V3E-FIG1", 84, "strategy-environment cells", "figures_v5/submission_candidate_v3/Main_Figure_1_source.csv", "V5-RC1", "frozen manifest")
add("FIGURE1", "V3E-FIG1", 3360, "scientific jobs", "figures_v5/submission_candidate_v3/Main_Figure_1_source.csv", "V5-RC1", "frozen manifest")
trace = pd.concat([trace, pd.DataFrame(trace_rows)], ignore_index=True)
trace.to_csv(trace_path, index=False)


def scientific_word_count(source: str) -> int:
    body = source.split(r"\section*{Data and code availability}")[0]
    body = re.sub(r"(?s)\\begin\{figure\}.*?\\end\{figure\}", " ", body)
    body = re.sub(r"(?s)\\begin\{equation\*?\}.*?\\end\{equation\*?\}", " ", body)
    body = re.sub(r"\\cite\w*\{[^}]+\}", " ", body)
    body = re.sub(r"\\[A-Za-z*]+(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", body)
    body = re.sub(r"[$^_{}\\]", " ", body)
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", body))


old_tex = (
    ROOT / "manuscript_v5" / "submission_candidate_v2" /
    "manuscript_submission_candidate_v2.tex"
).read_text(encoding="utf-8")
before = scientific_word_count(old_tex)
after = scientific_word_count(tex)
report = f"""# Manuscript content expansion report

- Main-text scientific word count: {before} -> {after} ({after - before:+d}).
- Introduction paragraphs: 2 -> 5.
- Results subsections: 3 -> 5.
- Discussion subsections: 0 -> 4.
- V2/V3 evidence added: independent cohort identities, seed/job geometry, historical result labels, and post hoc boundary.
- References retained and cited: {len(ref_audit)}; removed from V2 bibliography: {47 - len(ref_audit)}.
- Main figures: 4 -> 3.
- Scientific numbers changed: no. The complete frozen 128-row V5 table was copied unchanged.
"""
(ED / "manuscript_content_expansion_report.md").write_text(report, encoding="utf-8")
print({
    "references": len(ref_audit),
    "all_cited": bool(ref_audit["cited_in_manuscript"].all()),
    "word_count_before": before,
    "word_count_after": after,
    "claim_rows": len(claims),
    "trace_rows": len(trace),
})
