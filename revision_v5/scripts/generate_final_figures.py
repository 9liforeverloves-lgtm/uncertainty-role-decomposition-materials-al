#!/usr/bin/env python3
"""Generate final figures strictly from approved machine-readable tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
OUT = ROOT / "figures_v5" / "final"
OUT.mkdir(parents=True, exist_ok=True)

TASK_ORDER = [
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
]
TASK_LABEL = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
COLORS = {
    "Original GG vs Raw": "#0072B2",
    "Historical CS vs Raw": "#D55E00",
    "Selected GG vs Raw": "#009E73",
    "Selected CS vs Raw": "#CC79A7",
}
MARKERS = {
    ("iid_record", "random_forest"): "o",
    ("iid_record", "extra_randomized_bagging"): "s",
    ("chemical_system_ood", "random_forest"): "^",
    ("chemical_system_ood", "extra_randomized_bagging"): "D",
}


def save(fig, stem, source):
    source_path = OUT / f"{stem}_source.csv"
    source.to_csv(source_path, index=False)
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    return {
        "figure": stem,
        "source": source_path.name,
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "png": f"{stem}.png",
        "pdf": f"{stem}.pdf",
    }


def forest(data, endpoint, stem, title, positive_note):
    d = data[data["endpoint"] == endpoint].copy()
    d["task"] = pd.Categorical(d["task"], TASK_ORDER, ordered=True)
    d = d.sort_values(["contrast_name", "task", "split", "surrogate"])
    fig, axes = plt.subplots(1, 4, figsize=(16, 8), sharex=False, sharey=True)
    for ax, (contrast, group) in zip(axes, d.groupby("contrast_name", sort=False)):
        group = group.reset_index(drop=True)
        y = np.arange(len(group))
        for i, row in group.iterrows():
            ax.errorbar(
                row["mean_diff"],
                y[i],
                xerr=[[row["mean_diff"] - row["ci_lower"]], [row["ci_upper"] - row["mean_diff"]]],
                fmt=MARKERS[(row["split"], row["surrogate"])],
                color=COLORS[contrast],
                markersize=5,
                capsize=2,
                linewidth=1,
            )
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_title(contrast, fontsize=10)
        ax.grid(axis="x", alpha=0.25)
        if ax is axes[0]:
            labels = [
                f"{TASK_LABEL[r.task]} | {'OOD' if r.split == 'chemical_system_ood' else 'IID'} | "
                f"{'RF' if r.surrogate == 'random_forest' else 'ExtraTrees'}"
                for r in group.itertuples()
            ]
            ax.set_yticks(y, labels, fontsize=7)
        else:
            ax.set_yticks(y)
    fig.suptitle(title)
    fig.supxlabel(
        f"Paired test − baseline effect (95% bootstrap CI); {positive_note}",
        y=0.035,
    )
    fig.text(
        0.5,
        0.012,
        "Inference unit: paired seed (n=40). Confirmatory; BH is applied within each 8-test environment family.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.085, 1, 0.96))
    return save(fig, stem, d)


def main():
    primary = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_final.csv")
    sensitivity = pd.read_csv(TABLES / "v5_rc1_recovery_sensitivity_final.csv")
    registry = pd.read_csv(
        ROOT / "results_v4" / "confirmation" / "registry_snapshot.csv"
    )
    manifest = []

    architecture = pd.DataFrame(
        {
            "stage": ["Tasks", "Splits", "Surrogates", "Strategies", "Seeds", "Jobs"],
            "count": [4, 2, 2, 21, 40, 3360],
            "evidence_class": [
                "design", "design", "design", "design", "paired inference", "execution"
            ],
        }
    )
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.axis("off")
    xs = np.arange(len(architecture))
    for i, row in architecture.iterrows():
        ax.text(
            xs[i], 0.55, f"{row['count']}\n{row['stage']}",
            ha="center", va="center", fontsize=12,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#E6F2F8", edgecolor="#0072B2"),
        )
        if i < len(architecture) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.35, 0.55), xytext=(xs[i] + 0.35, 0.55),
                        arrowprops=dict(arrowstyle="->", color="#555555"))
    ax.text(
        2.5, 0.12,
        "Confirmatory endpoints: L1 campaign MACE and L4 top-1% recall nAUC\n"
        "Sensitivity: paired removal of recovered seeds 5013–5018 in the affected cell",
        ha="center", fontsize=9,
    )
    ax.set_xlim(-0.6, len(xs) - 0.4)
    ax.set_ylim(0, 1)
    ax.set_title("Final study architecture and evidence classes")
    manifest.append(save(fig, "Figure01_study_architecture", architecture))

    manifest.append(
        forest(
            primary, "l1_campaign_mace", "Figure02_L1_forest",
            "L1 campaign calibration effects by locked environment",
            "negative favors the test strategy",
        )
    )
    manifest.append(
        forest(
            primary, "l4_top1pct_recall_nauc", "Figure03_L4_forest",
            "L4 sequential-value effects by locked environment",
            "positive favors the test strategy",
        )
    )

    selected = primary[primary["contrast_name"].str.startswith("Selected")].copy()
    selected_summary = (
        selected.groupby(["task", "contrast_name", "endpoint"], as_index=False)
        .agg(mean_effect=("mean_diff", "mean"), min_effect=("mean_diff", "min"), max_effect=("mean_diff", "max"))
    )
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, endpoint in zip(axes, ["l1_campaign_mace", "l4_top1pct_recall_nauc"]):
        g = selected_summary[selected_summary["endpoint"] == endpoint]
        for contrast, c in g.groupby("contrast_name"):
            x = np.arange(4) + (-0.12 if "GG" in contrast else 0.12)
            c = c.set_index("task").reindex(TASK_ORDER)
            ax.plot(x, c["mean_effect"], marker="o", label=contrast, color=COLORS[contrast])
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(np.arange(4), [TASK_LABEL[t] for t in TASK_ORDER], rotation=25)
        ax.set_title("L1 (negative favors test)" if endpoint.startswith("l1") else "L4 (positive favors test)")
        ax.grid(axis="y", alpha=0.25)
    axes[1].legend(fontsize=8)
    fig.suptitle("Development-selected strategies: descriptive task summaries")
    fig.text(0.5, 0.01, "Descriptive across environments; no pooled-task inference.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    manifest.append(save(fig, "Figure04_selected_strategies_by_task", selected_summary))

    cs = primary[primary["contrast_name"].isin(["Historical CS vs Raw", "Selected CS vs Raw"])].copy()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, endpoint in zip(axes, ["l1_campaign_mace", "l4_top1pct_recall_nauc"]):
        g = cs[cs["endpoint"] == endpoint]
        for contrast, c in g.groupby("contrast_name"):
            ax.scatter(
                np.arange(len(c)), c["mean_diff"], label=contrast,
                color=COLORS[contrast], marker="o" if "Historical" in contrast else "s", alpha=0.8,
            )
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(endpoint)
        ax.set_xlabel("Locked environment index")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Paired test − baseline effect")
    axes[1].legend(fontsize=8)
    fig.suptitle("Historical versus selected candidate-specific strategies")
    fig.tight_layout()
    manifest.append(save(fig, "Figure05_historical_vs_selected_CS", cs))

    fig, ax = plt.subplots(figsize=(6, 5))
    for endpoint, group in sensitivity.groupby("endpoint"):
        ax.scatter(
            group["mean_diff_primary"], group["mean_diff_sensitivity"],
            label=endpoint, s=55, alpha=0.85,
        )
    limits = [
        min(sensitivity["mean_diff_primary"].min(), sensitivity["mean_diff_sensitivity"].min()),
        max(sensitivity["mean_diff_primary"].max(), sensitivity["mean_diff_sensitivity"].max()),
    ]
    ax.plot(limits, limits, "--", color="black", linewidth=0.8)
    ax.set_xlabel("Primary effect (40 paired seeds)")
    ax.set_ylabel("Excluding recovered seeds (34 paired seeds)")
    ax.set_title("Recovery-exclusion sensitivity")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    manifest.append(save(fig, "Figure06_recovery_exclusion", sensitivity))

    calibration = (
        endpoints.groupby(["task", "strategy"], as_index=False)
        .agg(mean_campaign_mace=("l1_campaign_mace", "mean"))
    )
    keep = ["raw_ucb_beta_1", "raw_ucb_beta_2", "gg_ucb_beta_1", "gg_ucb_beta_0p5",
            "cs_da_oob_hist", "cs_da_oob_parsimonious_f1"]
    calibration = calibration[calibration["strategy"].isin(keep)]
    fig, ax = plt.subplots(figsize=(10, 5))
    for strategy, group in calibration.groupby("strategy"):
        group = group.set_index("task").reindex(TASK_ORDER)
        ax.plot(np.arange(4), group["mean_campaign_mace"], marker="o", label=strategy)
    ax.set_xticks(np.arange(4), [TASK_LABEL[t] for t in TASK_ORDER])
    ax.set_ylabel("Mean L1 campaign MACE (lower is better)")
    ax.set_title("Campaign calibration summary by task and strategy")
    ax.legend(ncol=2, fontsize=7)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    manifest.append(save(fig, "Figure07_calibration_campaign_summary", calibration))

    parts = registry["job_id"].str.split("__", expand=True)
    runtime = registry.assign(task=parts[0], strategy=parts[3])
    runtime["family"] = np.select(
        [
            runtime["strategy"].str.startswith("raw_"),
            runtime["strategy"].str.startswith("gg_"),
            runtime["strategy"].str.startswith("cs_"),
        ],
        ["Raw", "Global", "Candidate-specific"],
        default="Other",
    )
    runtime_summary = (
        runtime.groupby(["task", "family"], as_index=False)
        .agg(median_runtime_seconds=("runtime_seconds", "median"),
             q25_runtime_seconds=("runtime_seconds", lambda x: x.quantile(0.25)),
             q75_runtime_seconds=("runtime_seconds", lambda x: x.quantile(0.75)))
    )
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.24
    for i, family in enumerate(["Raw", "Global", "Candidate-specific"]):
        g = runtime_summary[runtime_summary["family"] == family].set_index("task").reindex(TASK_ORDER)
        ax.bar(np.arange(4) + (i - 1) * width, g["median_runtime_seconds"] / 60, width, label=family)
    ax.set_xticks(np.arange(4), [TASK_LABEL[t] for t in TASK_ORDER])
    ax.set_ylabel("Median job runtime (minutes)")
    ax.set_title("Observed runtime by task and strategy family")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    manifest.append(save(fig, "Figure08_runtime_by_task", runtime_summary))

    cross = primary.pivot_table(
        index=["environment", "contrast_name"],
        columns="endpoint", values="mean_diff", aggfunc="first",
    ).reset_index()
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for contrast, g in cross.groupby("contrast_name"):
        ax.scatter(
            -g["l1_campaign_mace"], g["l4_top1pct_recall_nauc"],
            label=contrast, color=COLORS[contrast], alpha=0.8,
        )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("L1 benefit (− paired MACE effect; positive is better)")
    ax.set_ylabel("L4 benefit (paired nAUC effect; positive is better)")
    ax.set_title("Exploratory L1–L4 cross-layer alignment")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    manifest.append(save(fig, "Figure09_L1_L4_cross_layer_exploratory", cross))

    (OUT / "figure_manifest.json").write_text(
        json.dumps(
            {
                "generated_from": [
                    "tables_v5/v5_rc1_primary_contrasts_final.csv",
                    "tables_v5/v5_rc1_seed_level_endpoints_final.csv",
                    "tables_v5/v5_rc1_recovery_sensitivity_final.csv",
                    "results_v4/confirmation/registry_snapshot.csv",
                ],
                "figures": manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"figures_generated": len(manifest), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
