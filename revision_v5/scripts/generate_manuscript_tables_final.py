#!/usr/bin/env python3
"""Generate LaTeX tables only from V5 final locked CSV files."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
OUT = ROOT / "manuscript_v5" / "tables" / "final_v2"
OUT.mkdir(parents=True, exist_ok=True)

TASK = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
SPLIT = {"iid_record": "IID", "chemical_system_ood": "OOD"}
MODEL = {
    "random_forest": "RF",
    "extra_randomized_bagging": "ExtraTrees",
}
CONTRAST = {
    "Original GG vs Raw": "Original GG vs Raw",
    "Historical CS vs Raw": "Historical CS vs Raw",
    "Selected GG vs Raw": "Selected GG vs Raw",
    "Selected CS vs Raw": "Selected CS vs Raw",
}


def esc(value):
    return str(value).replace("_", r"\_").replace("%", r"\%")


def fmt(value):
    return f"{float(value):.4f}"


primary = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")

summary = (
    primary.groupby(["contrast_name", "endpoint"], as_index=False)
    .agg(
        environments=("mean_diff", "size"),
        bh_significant=("significant_after_bh", "sum"),
        positive=("mean_diff", lambda x: int((x > 0).sum())),
        negative=("mean_diff", lambda x: int((x < 0).sum())),
        minimum=("mean_diff", "min"),
        maximum=("mean_diff", "max"),
    )
)
lines = [
    r"\begin{tabular}{llrrrrrr}",
    r"\toprule",
    r"Contrast & Endpoint & $n$ & BH sig. & $+$ & $-$ & Min. & Max.\\",
    r"\midrule",
]
for row in summary.itertuples(index=False):
    endpoint = (
        "Campaign MACE"
        if row.endpoint == "l1_campaign_mace"
        else r"Top-1\% recall nAUC"
    )
    lines.append(
        f"{esc(row.contrast_name)} & {endpoint} & {row.environments} & "
        f"{int(row.bh_significant)} & {row.positive} & {row.negative} & "
        f"{fmt(row.minimum)} & {fmt(row.maximum)}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
(OUT / "primary_summary.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

lines = [
    r"\begin{longtable}{llllllrrrr}",
    r"\caption{Complete locked primary contrast table. Effects are test minus baseline.}\label{tab:full-primary}\\",
    r"\toprule",
    r"Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\mathrm{BH}}$ & Label\\",
    r"\midrule",
    r"\endfirsthead",
    r"\toprule",
    r"Task & Split & Model & Contrast & Endpoint & Baseline & Effect & 95\% CI & $p_{\mathrm{BH}}$ & Label\\",
    r"\midrule",
    r"\endhead",
]
for row in primary.sort_values(
    ["task", "split", "surrogate", "endpoint", "contrast_name"]
).itertuples(index=False):
    endpoint = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
    ci = f"[{fmt(row.ci_lower)}, {fmt(row.ci_upper)}]"
    lines.append(
        f"{TASK[row.task]} & {SPLIT[row.split]} & {MODEL[row.surrogate]} & "
        f"{esc(row.contrast_name)} & {endpoint} & {esc(row.baseline_strategy)} & "
        f"{fmt(row.mean_diff)} & {ci} & {float(row.p_value_bh_adjusted):.4g} & "
        f"{esc(row.evidence_label)}\\\\"
    )
lines += [r"\bottomrule", r"\end{longtable}"]
(OUT / "full_primary_128.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

selected = (
    primary[primary["contrast_name"].str.startswith("Selected")]
    [["task", "contrast_name", "baseline_strategy", "test_strategy"]]
    .drop_duplicates()
    .sort_values(["task", "contrast_name"])
)
lines = [
    r"\begin{tabular}{llll}",
    r"\toprule",
    r"Task & Contrast & Locked baseline & Test strategy\\",
    r"\midrule",
]
for row in selected.itertuples(index=False):
    lines.append(
        f"{TASK[row.task]} & {esc(row.contrast_name)} & "
        f"{esc(row.baseline_strategy)} & {esc(row.test_strategy)}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
(OUT / "selected_policy_map.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

sensitivity = pd.read_csv(TABLES / "v5_rc1_recovery_sensitivity_final.csv")
lines = [
    r"\begin{tabular}{llrrrrr}",
    r"\toprule",
    r"Contrast & Endpoint & Primary & Exclusion & Absolute change & Relative change & $>10\%$\\",
    r"\midrule",
]
for row in sensitivity.itertuples(index=False):
    endpoint = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
    lines.append(
        f"{esc(row.contrast_name)} & {endpoint} & {fmt(row.mean_diff_primary)} & "
        f"{fmt(row.mean_diff_sensitivity)} & {float(row.absolute_effect_change):.6f} & "
        f"{100*float(row.relative_effect_change):.1f}\\% & "
        f"{'yes' if float(row.relative_effect_change) > 0.10 else 'no'}\\\\"
    )
lines += [r"\bottomrule", r"\end{tabular}"]
(OUT / "recovery_sensitivity.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

print(OUT)
