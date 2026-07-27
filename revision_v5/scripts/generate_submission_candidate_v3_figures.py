#!/usr/bin/env python3
"""Generate editorial V3 figures from frozen source tables only."""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures_v5" / "submission_candidate_v3"
OUT.mkdir(parents=True, exist_ok=True)
TABLES = ROOT / "tables_v5" / "submission_candidate_v3"

plt.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "pdf.fonttype": 42,
})


def box(ax, x, y, w, h, text, color):
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.015,rounding_size=0.02",
        facecolor=color, edgecolor="#333333", linewidth=1.0,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)


# Figure 1: study evolution and final design.
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1.35, 1]})
ax = axes[0]
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.set_title("A  Study evolution and evidence classes", loc="left", fontweight="bold")
items = [
    (0.02, "V2 historical\nL4 confirmation\n1,920 jobs", "#d9e8fb"),
    (0.22, "V3 independent\nL1 confirmation\n1,920 jobs", "#d9e8fb"),
    (0.42, "V5 development\npolicy selection\n2,240 jobs", "#fff0c2"),
    (0.62, "Frozen V5-RC1\nL1 + L4 confirmation\n3,360 jobs", "#d8f0df"),
    (0.82, "Sensitivity and\nreproducibility audit\n0 new jobs", "#eadff4"),
]
for x, text, color in items:
    box(ax, x, .38, .16, .28, text, color)
for i in range(len(items) - 1):
    ax.annotate("", xy=(items[i + 1][0] - .006, .52),
                xytext=(items[i][0] + .166, .52),
                arrowprops={"arrowstyle": "->", "lw": 1.2, "color": "#555555"})
ax.text(.02, .22,
        "Historical cohorts remain separate from V5-RC1; V3 L2–L4 reconstruction is post hoc.\n"
        "No seeds, effects, or p-values are pooled across phases.",
        ha="left", va="top", fontsize=8.5)

ax = axes[1]
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.set_title("B  Frozen V5-RC1 design geometry", loc="left", fontweight="bold")
geometry = [
    ("4", "materials-property tasks"),
    ("2", "split regimes"),
    ("2", "tree-ensemble surrogates"),
    ("6", "strategy identities"),
    ("84", "strategy–environment cells"),
    ("40", "paired seeds (5000–5039)"),
    ("3,360", "scientific jobs"),
]
for i, (value, label) in enumerate(geometry):
    y = .86 - i * .115
    ax.text(.14, y, value, ha="right", va="center", fontsize=14,
            fontweight="bold", color="#1f4e79")
    ax.text(.18, y, label, ha="left", va="center", fontsize=9)
ax.text(.05, .04, "Engineering test counts are not scientific job counts.",
        fontsize=8, color="#555555")
fig.tight_layout()
fig.savefig(OUT / "Main_Figure_1_study_evolution_and_design.pdf", bbox_inches="tight")
fig.savefig(OUT / "Main_Figure_1_study_evolution_and_design.png", dpi=300, bbox_inches="tight")
plt.close(fig)

pd.DataFrame([
    {"phase": "V2 historical L4 confirmation", "jobs": 1920, "evidence_class": "historical confirmatory"},
    {"phase": "V3 independent L1 confirmation", "jobs": 1920, "evidence_class": "historical confirmatory"},
    {"phase": "V5 development selection", "jobs": 2240, "evidence_class": "development"},
    {"phase": "V5-RC1 confirmation", "jobs": 3360, "evidence_class": "confirmatory"},
    {"phase": "sensitivity/reproducibility", "jobs": 0, "evidence_class": "audit"},
]).to_csv(OUT / "Main_Figure_1_source.csv", index=False)

# Figure 2 assets are unchanged, full CI forest panels.
for source, destination in (
    ("Figure02_L1_forest.pdf", "Main_Figure_2A_full_L1_forest.pdf"),
    ("Figure03_L4_forest.pdf", "Main_Figure_2B_full_L4_forest.pdf"),
):
    shutil.copy2(ROOT / "figures_v5" / "final_v2" / source, OUT / destination)

# Figure 3: descriptive selection and confirmatory selected-policy effects.
dev = pd.read_csv(TABLES / "development_selection_summary.csv")
scores = pd.read_csv(ROOT / "tables_v5" / "loto_candidate_scores.csv")
runner_means = []
for row in dev.itertuples(index=False):
    candidate = scores[
        (scores.held_out_task == row.held_out_task)
        & (scores.family == row.family)
        & (scores.strategy == row.runner_up)
    ].iloc[0]
    runner_means.append(candidate.mean_primary)
dev["runner_mean_nAUC"] = runner_means

locked = pd.read_csv(ROOT / "tables_v5" / "v5_rc1_primary_contrasts_final.csv")
confirm = locked[
    locked["contrast_name"].isin(["Selected GG vs Raw", "Selected CS vs Raw"])
    & locked["endpoint"].eq("l4_top1pct_recall_nauc")
].copy()

task_label = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
family_label = {"raw": "Raw", "gaussian_global": "GG", "candidate_specific": "CS"}
model_label = {"random_forest": "RF", "extra_randomized_bagging": "ET"}

fig, axes = plt.subplots(1, 2, figsize=(12, 7.2), gridspec_kw={"width_ratios": [0.85, 1.55]})
ax = axes[0]
order = []
for task in task_label:
    for family in ("raw", "gaussian_global", "candidate_specific"):
        order.append((task, family))
dev = dev.set_index(["held_out_task", "family"]).loc[order].reset_index()
y = np.arange(len(dev))[::-1]
ax.hlines(y, dev["runner_mean_nAUC"], dev["selected_mean_nAUC"],
          color="#9e9e9e", lw=1.2)
ax.scatter(dev["runner_mean_nAUC"], y, marker="x", color="#777777", label="Runner-up")
ax.scatter(dev["selected_mean_nAUC"], y, marker="o", color="#1f77b4", label="Selected")
ax.set_yticks(y)
ax.set_yticklabels([
    f"{task_label[t]} · {family_label[f]}" for t, f in zip(dev.held_out_task, dev.family)
])
ax.set_xlabel("Mean development nAUC")
ax.set_title("A  Development selection (descriptive)", loc="left", fontweight="bold")
ax.grid(axis="x", alpha=.2)
ax.legend(frameon=False, loc="lower right")

ax = axes[1]
confirm["label"] = confirm.apply(
    lambda r: (
        f"{task_label[r.task]} · {'OOD' if r.split == 'chemical_system_ood' else 'IID'}"
        f" · {model_label[r.surrogate]}"
    ), axis=1,
)
environment_order = (
    confirm[["task", "split", "surrogate", "label"]]
    .drop_duplicates()
    .sort_values(["task", "split", "surrogate"])
)
labels = environment_order["label"].tolist()
positions = {label: i for i, label in enumerate(labels[::-1])}
colors = {"Selected GG vs Raw": "#d97706", "Selected CS vs Raw": "#7c3aed"}
offsets = {"Selected GG vs Raw": -.16, "Selected CS vs Raw": .16}
for contrast, group in confirm.groupby("contrast_name"):
    yy = np.array([positions[label] for label in group["label"]]) + offsets[contrast]
    ax.errorbar(
        group["mean_diff"], yy,
        xerr=[group["mean_diff"] - group["ci_lower"], group["ci_upper"] - group["mean_diff"]],
        fmt="o", ms=3.5, capsize=2, lw=.8, color=colors[contrast], label=contrast,
    )
ax.axvline(0, color="#333333", lw=.8)
ax.set_yticks(np.arange(len(labels)))
ax.set_yticklabels(labels[::-1], fontsize=7)
ax.set_xlabel("L4 nAUC effect (selected policy minus task-specific Raw baseline)")
ax.set_title("B  V5-RC1 selected-policy effects (confirmatory, 95% CIs)",
             loc="left", fontweight="bold")
ax.grid(axis="x", alpha=.2)
ax.legend(frameon=False, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "Main_Figure_3_selected_policy_evidence.pdf", bbox_inches="tight")
fig.savefig(OUT / "Main_Figure_3_selected_policy_evidence.png", dpi=300, bbox_inches="tight")
plt.close(fig)

dev.to_csv(OUT / "Main_Figure_3A_source.csv", index=False)
confirm.to_csv(OUT / "Main_Figure_3B_source.csv", index=False)

# Supplement-only recovery/runtime and standalone enlargements.
copy_map = {
    "Figure06_recovery_exclusion.pdf": "Supplementary_Figure_recovery_sensitivity.pdf",
    "Figure08_runtime_by_task.pdf": "Supplementary_Figure_runtime.pdf",
    "Figure02_L1_forest.pdf": "Supplementary_Figure_full_L1_forest.pdf",
    "Figure03_L4_forest.pdf": "Supplementary_Figure_full_L4_forest.pdf",
    "Figure04_selected_strategies_by_task.pdf": "Supplementary_Figure_selected_task_summary.pdf",
    "Figure05_historical_vs_selected_CS.pdf": "Supplementary_Figure_candidate_specific_detail.pdf",
    "Figure07_calibration_campaign_summary.pdf": "Supplementary_Figure_absolute_calibration.pdf",
    "Figure09_L1_L4_cross_layer_exploratory.pdf": "Supplementary_Figure_exploratory_alignment.pdf",
}
for source, destination in copy_map.items():
    shutil.copy2(ROOT / "figures_v5" / "final_v2" / source, OUT / destination)

print({"main_figures": 3, "supplement_assets": len(copy_map)})
