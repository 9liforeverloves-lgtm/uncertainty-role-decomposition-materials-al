#!/usr/bin/env python3
"""Generate V3 LaTeX tables from frozen/editorial CSV tables."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tables_v5" / "submission_candidate_v3"
OUT = ROOT / "manuscript_v5" / "submission_candidate_v3" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

TASK = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}


def esc(value):
    return (
        str(value).replace("\\", r"\textbackslash{}").replace("_", r"\_")
        .replace("%", r"\%").replace("&", r"\&")
    )


def write(name, lines):
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def break_id(value):
    return esc(value).replace(r"\_", r"\_\allowbreak{}")


lineage = pd.read_csv(SOURCE / "study_evidence_lineage.csv")
lines = [
    r"\begin{longtable}{p{2.0cm}p{2.0cm}p{1.4cm}p{1.6cm}p{2.2cm}p{3.2cm}}",
    r"\caption{Study evolution and evidence classes.}\label{tab:lineage}\\",
    r"\toprule Phase & Evidence class & Seeds & Scientific jobs & Endpoints & Permitted use / limitation\\\midrule",
    r"\endfirsthead\toprule Phase & Evidence class & Seeds & Scientific jobs & Endpoints & Permitted use / limitation\\\midrule\endhead",
]
for row in lineage.itertuples(index=False):
    use = f"{row.permitted_manuscript_use}; {row.principal_limitation}"
    lines.append(
        f"{esc(row.internal_name)} & {esc(row.inference_status)} & {esc(row.seeds)} & "
        f"{int(row.number_of_jobs)} & {esc(row.endpoint_set)} & {esc(use)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("study_evidence_lineage.tex", lines)

dev = pd.read_csv(SOURCE / "development_selection_summary.csv")
lines = [
    r"\begin{longtable}{llrllrrrl}",
    r"\caption{Development selection by held-out task and family. Scores are descriptive development evidence.}\label{tab:devdetail}\\",
    r"\toprule Task & Family & Eligible & Selected & Runner-up & Mean & Worst & Margin & Tie stage\\\midrule",
    r"\endfirsthead\toprule Task & Family & Eligible & Selected & Runner-up & Mean & Worst & Margin & Tie stage\\\midrule\endhead",
]
for row in dev.itertuples(index=False):
    lines.append(
        f"{TASK[row.held_out_task]} & {esc(row.family)} & {row.eligible_candidate_count} & "
        f"{esc(row.selected_candidate)} & {esc(row.runner_up)} & "
        f"{row.selected_mean_nAUC:.4f} & {row.selected_worst_environment_nAUC:.4f} & "
        f"{row.selected_minus_runner_up:.4f} & {esc(row.tie_breaking_stage)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("development_selection_summary.tex", lines)

ood = pd.read_csv(SOURCE / "ood_system_count_manuscript_summary.csv")
lines = [
    r"\begin{tabular}{lrrrrrr}",
    r"\toprule Task & Source records & Selectable records & Diagnostic records & Source systems & Selectable systems & Diagnostic systems\\\midrule",
]
for row in ood.itertuples(index=False):
    lines.append(
        f"{TASK[row.task]} & {row.source_records_summary} & "
        f"{row.selectable_records_summary} & {row.diagnostic_records_summary} & "
        f"{row.source_systems_summary} & {row.selectable_systems_summary} & "
        f"{row.diagnostic_systems_summary}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
write("ood_system_count_summary.tex", lines)

mapping = pd.read_csv(SOURCE / "development_identity_to_confirmation_identity.csv")
lines = [
    r"\begin{tabular}{p{3.3cm}p{3.3cm}p{2.5cm}cccc}",
    r"\toprule Development identity & Confirmation identity & Status & Features & OOB threshold & Pair weight & Other settings\\\midrule",
]
for row in mapping.itertuples(index=False):
    other = all([
        row.regularization_identical, row.clipping_identical,
        row.fallback_identical, row.optimizer_identical,
        row.uncertainty_floor_identical,
    ])
    mark = lambda value: "same" if value else "changed"
    lines.append(
        f"{break_id(row.development_identity)} & "
        f"{break_id(row.confirmation_identity)} & "
        f"{esc(row.mapping_status)} & {mark(row.feature_subset_identical)} & "
        f"{mark(row.minimum_oob_trees_identical)} & "
        f"{mark(row.top_tail_pair_weight_identical)} & {mark(other)}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
write("development_identity_mapping.tex", lines)

# Reuse corrected V2 generators for the complete inventory, parameters, and
# locked 128-row table; the CSV values were copied unchanged.
inventory = pd.read_csv(SOURCE / "development_configuration_inventory_36.csv")
lines = [
    r"\begin{longtable}{rlll}",
    r"\caption{Complete 36-configuration broad development inventory.}\label{tab:dev36}\\",
    r"\toprule ID & Family & Strategy identity & Configuration\\\midrule",
    r"\endfirsthead\toprule ID & Family & Strategy identity & Configuration\\\midrule\endhead",
]
for row in inventory.itertuples(index=False):
    config = row.candidate_specific_config_json
    if config == "{}":
        config = "not applicable"
    lines.append(
        f"{row.configuration_id} & {esc(row.family)} & {esc(row.strategy)} & "
        rf"\texttt{{\detokenize{{{config}}}}}\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("development_inventory_36.tex", lines)

parameters = pd.read_csv(SOURCE / "candidate_specific_parameter_table.csv")
lines = [
    r"\begin{longtable}{lllll}",
    r"\caption{Frozen candidate-specific method parameters.}\label{tab:csparams}\\",
    r"\toprule Parameter & Code key & Historical CS & Selected CS & Interpretation\\\midrule",
    r"\endfirsthead\toprule Parameter & Code key & Historical CS & Selected CS & Interpretation\\\midrule\endhead",
]
for row in parameters.itertuples(index=False):
    lines.append(
        f"{esc(row.parameter)} & {esc(row.code_key)} & {esc(row.historical_CS)} & "
        f"{esc(row.selected_parsimonious_CS)} & {esc(row.interpretation)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("candidate_specific_parameters.tex", lines)

primary = pd.read_csv(SOURCE / "complete_primary_128_with_p_raw_p_BH.csv")
split = {"iid_record": "IID", "chemical_system_ood": "OOD"}
model = {"random_forest": "RF", "extra_randomized_bagging": "ExtraTrees"}
lines = [
    r"\begin{longtable}{llllllrrrrr}",
    r"\caption{Complete 128-row locked V5-RC1 primary table. Effects are test minus baseline.}\label{tab:primary128}\\",
    r"\toprule Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\rm raw}$ & $p_{\rm BH}$ & Label\\\midrule",
    r"\endfirsthead\toprule Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\rm raw}$ & $p_{\rm BH}$ & Label\\\midrule\endhead",
]
for row in primary.sort_values(
    ["task", "split", "surrogate", "endpoint", "contrast_name"]
).itertuples(index=False):
    endpoint = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
    ci = f"[{row.ci_lower:.4f}, {row.ci_upper:.4f}]"
    lines.append(
        f"{TASK[row.task]} & {split[row.split]} & {model[row.surrogate]} & "
        f"{esc(row.contrast_name)} & {endpoint} & {esc(row.baseline_strategy)} & "
        f"{row.mean_diff:.4f} & {ci} & {row.p_raw:.4g} & {row.p_BH:.4g} & "
        f"{esc(row.evidence_label)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("complete_primary_128_p_raw_p_BH.tex", lines)

print({"tables": 7})
