#!/usr/bin/env python3
"""Generate submission-candidate LaTeX tables from editorial CSVs."""

from pathlib import Path
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tables_v5" / "submission_candidate_v2"
OUT = ROOT / "manuscript_v5" / "submission_candidate_v2" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

TASK = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
SPLIT = {"iid_record": "IID", "chemical_system_ood": "OOD"}
MODEL = {"random_forest": "RF", "extra_randomized_bagging": "ExtraTrees"}


def esc(value):
    return (
        str(value)
        .replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("–", "--")
    )


def write(name, lines):
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


inventory = pd.read_csv(SOURCE / "development_configuration_inventory_36.csv")
lines = [
    r"\begin{longtable}{rlll}",
    r"\caption{Complete 36-configuration development inventory from the frozen development manifest.}\label{tab:dev36}\\",
    r"\toprule ID & Family & Strategy identity & Candidate-specific configuration\\\midrule",
    r"\endfirsthead\toprule ID & Family & Strategy identity & Candidate-specific configuration\\\midrule\endhead",
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


selection = pd.read_csv(SOURCE / "development_selection_by_fold.csv")
lines = [
    r"\begin{longtable}{llllr}",
    r"\caption{Leave-one-task-out development selection by held-out task and strategy family.}\label{tab:loto}\\",
    r"\toprule Held-out task & Family & Development tasks & Selected strategy & Valid jobs\\\midrule",
    r"\endfirsthead\toprule Held-out task & Family & Development tasks & Selected strategy & Valid jobs\\\midrule\endhead",
]
for row in selection.itertuples(index=False):
    development_tasks = ", ".join(TASK[item] for item in row.development_tasks.split("|"))
    lines.append(
        f"{TASK[row.held_out_task]} & {esc(row.family)} & {development_tasks} & "
        f"{esc(row.selected_strategy)} & {row.valid_job_count}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("development_selection_by_fold.tex", lines)


ood = pd.read_csv(SOURCE / "chemical_system_ood_split_summary.csv")
lines = [
    r"\begin{tabular}{lrrrrrr}",
    r"\toprule Task & Seeds & Source & Selectable target & Diagnostic & Group overlap & ID overlap\\\midrule",
]
for row in ood.itertuples(index=False):
    lines.append(
        f"{TASK[row.task]} & {row.audited_seeds} & {row.source_records} & "
        f"{row.target_records} & {row.diagnostic_records} & "
        f"{row.maximum_group_overlap} & {row.maximum_candidate_id_overlap}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
write("chemical_system_ood_split_summary.tex", lines)


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
lines = [
    r"\begin{longtable}{llllllrrrrr}",
    r"\caption{Complete 128-row locked primary table. Effects are test minus baseline. Both raw and within-environment BH-adjusted p-values are shown.}\label{tab:primary128}\\",
    r"\toprule Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\mathrm{raw}}$ & $p_{\mathrm{BH}}$ & Label\\\midrule",
    r"\endfirsthead\toprule Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\mathrm{raw}}$ & $p_{\mathrm{BH}}$ & Label\\\midrule\endhead",
]
for row in primary.sort_values(
    ["task", "split", "surrogate", "endpoint", "contrast_name"]
).itertuples(index=False):
    endpoint = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
    ci = f"[{row.ci_lower:.4f}, {row.ci_upper:.4f}]"
    lines.append(
        f"{TASK[row.task]} & {SPLIT[row.split]} & {MODEL[row.surrogate]} & "
        f"{esc(row.contrast_name)} & {endpoint} & {esc(row.baseline_strategy)} & "
        f"{row.mean_diff:.4f} & {ci} & {row.p_raw:.4g} & {row.p_BH:.4g} & "
        f"{esc(row.evidence_label)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
write("complete_primary_128_p_raw_p_BH.tex", lines)


manifest = {
    "tables": [
        "development_inventory_36.tex",
        "development_selection_by_fold.tex",
        "chemical_system_ood_split_summary.tex",
        "candidate_specific_parameters.tex",
        "complete_primary_128_p_raw_p_BH.tex",
    ],
    "source_only_no_scientific_recomputation": True,
}
(OUT / "latex_table_manifest.json").write_text(
    json.dumps(manifest, indent=2), encoding="utf-8"
)
print(manifest)
