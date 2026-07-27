#!/usr/bin/env python3
"""Publication figure set v2 from locked final tables and frozen manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables_v5"
OUT = ROOT / "figures_v5" / "final_v2"
OUT.mkdir(parents=True, exist_ok=True)

TASKS = [
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
]
TL = {
    "matbench_expt_gap": "Expt gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
CONTRASTS = [
    "Original GG vs Raw",
    "Historical CS vs Raw",
    "Selected GG vs Raw",
    "Selected CS vs Raw",
]
COLORS = {
    "Original GG vs Raw": "#0072B2",
    "Historical CS vs Raw": "#D55E00",
    "Selected GG vs Raw": "#009E73",
    "Selected CS vs Raw": "#CC79A7",
}
TASK_MARKERS = {
    "matbench_expt_gap": "o",
    "matbench_mp_gap": "s",
    "matbench_log_gvrh": "^",
    "matbench_log_kvrh": "D",
}
ENV_MARKERS = {
    ("iid_record", "random_forest"): "o",
    ("iid_record", "extra_randomized_bagging"): "s",
    ("chemical_system_ood", "random_forest"): "^",
    ("chemical_system_ood", "extra_randomized_bagging"): "D",
}

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "pdf.fonttype": 42,
    }
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_label(row):
    split = "OOD" if row["split"] == "chemical_system_ood" else "IID"
    model = "RF" if row["surrogate"] == "random_forest" else "ExtraTrees"
    return f"{TL[row['task']]} | {split} | {model}"


def save(fig, stem, source, caption):
    csv_path = OUT / f"{stem}_source.csv"
    png_path = OUT / f"{stem}.png"
    pdf_path = OUT / f"{stem}.pdf"
    cap_path = OUT / f"{stem}_caption.txt"
    source.to_csv(csv_path, index=False)
    cap_path.write_text(caption.strip() + "\n", encoding="utf-8")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return {
        "figure": stem,
        "source": csv_path.name,
        "source_sha256": sha(csv_path),
        "caption": cap_path.name,
        "caption_sha256": sha(cap_path),
        "png": png_path.name,
        "png_sha256": sha(png_path),
        "pdf": pdf_path.name,
        "pdf_sha256": sha(pdf_path),
    }


def forest(primary, endpoint, stem, title, direction):
    data = primary[primary["endpoint"] == endpoint].copy()
    order = []
    for task in TASKS:
        for split in ["iid_record", "chemical_system_ood"]:
            for model in ["random_forest", "extra_randomized_bagging"]:
                order.append((task, split, model))
    data["env_order"] = data.apply(
        lambda r: order.index((r["task"], r["split"], r["surrogate"])), axis=1
    )
    data["environment_label"] = data.apply(env_label, axis=1)
    data = data.sort_values(["contrast_name", "env_order"], kind="stable")
    fig, axes = plt.subplots(1, 4, figsize=(14.2, 6.5), sharey=True)
    for ax, contrast in zip(axes, CONTRASTS):
        group = data[data["contrast_name"] == contrast].sort_values("env_order")
        y = np.arange(len(group))[::-1]
        for yy, (_, row) in zip(y, group.iterrows()):
            ax.errorbar(
                row["mean_diff"],
                yy,
                xerr=[
                    [row["mean_diff"] - row["ci_lower"]],
                    [row["ci_upper"] - row["mean_diff"]],
                ],
                fmt=ENV_MARKERS[(row["split"], row["surrogate"])],
                color=COLORS[contrast],
                markerfacecolor=(
                    COLORS[contrast] if row["split"] == "iid_record" else "white"
                ),
                markeredgewidth=1.2,
                capsize=2,
                linewidth=1,
                markersize=5,
            )
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(contrast)
        ax.grid(axis="x", alpha=0.25)
        if ax is axes[0]:
            ax.set_yticks(y, group["environment_label"])
    fig.suptitle(title)
    fig.supxlabel(f"Paired test − baseline effect (95% bootstrap CI); {direction}", y=0.035)
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    caption = (
        f"{title}. Each point is one locked environment-level paired effect from "
        "40 confirmation seeds; bars are 95% paired-bootstrap intervals. "
        f"Effect is test minus baseline; {direction}. Filled markers denote IID and "
        "open markers denote chemical-system OOD; circles/triangles denote RF and "
        "squares/diamonds denote ExtraTrees. BH adjustment is within each "
        "prospectively specified eight-test environment family. Confirmatory. "
        "Panel x-scales differ; no pooled-task inference is shown."
    )
    return save(fig, stem, data.drop(columns=["env_order"]), caption)


def main():
    primary = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_final.csv")
    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_final.csv")
    sensitivity = pd.read_csv(TABLES / "v5_rc1_recovery_sensitivity_final.csv")
    registry = pd.read_csv(ROOT / "results_v4/confirmation/registry_snapshot.csv")
    confirmation = pd.read_csv(
        ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv"
    )
    development = pd.read_csv(
        ROOT / "manifests_v4/DEVELOPMENT_JOB_MANIFEST_V5.csv"
    )
    manifest = []

    strategy_cells = confirmation[
        ["task", "split_protocol", "model", "strategy"]
    ].drop_duplicates()
    architecture = pd.DataFrame(
        [
            ("Tasks", confirmation["task"].nunique(), "confirmation manifest"),
            ("Splits", confirmation["split_protocol"].nunique(), "confirmation manifest"),
            ("Surrogates", confirmation["model"].nunique(), "confirmation manifest"),
            ("Development candidate configurations", development["strategy"].nunique(), "development manifest"),
            ("Confirmation strategy identities", confirmation["strategy"].nunique(), "confirmation manifest"),
            ("Confirmation strategy–environment cells", len(strategy_cells), "confirmation manifest"),
            ("Paired-seed jobs", len(confirmation), "confirmation manifest"),
        ],
        columns=["component", "count", "source"],
    )
    fig, ax = plt.subplots(figsize=(10.8, 5.0))
    ax.axis("off")
    positions = [
        (0.8, 1.45),
        (3.0, 1.45),
        (5.2, 1.45),
        (7.4, 1.45),
        (1.9, 0.45),
        (4.6, 0.45),
        (7.3, 0.45),
    ]
    wrapped_labels = {
        "Development candidate configurations": "Development candidate\nconfigurations",
        "Confirmation strategy identities": "Confirmation strategy\nidentities",
        "Confirmation strategy–environment cells": "Confirmation strategy–\nenvironment cells",
    }
    for i, row in architecture.iterrows():
        x, y = positions[i]
        ax.text(
            x,
            y,
            f"{row['count']}\n{wrapped_labels.get(row['component'], row['component'])}",
            ha="center",
            va="center",
            fontsize=9,
            bbox=dict(
                boxstyle="round,pad=0.45",
                facecolor="#EAF3F8",
                edgecolor="#0072B2",
            ),
        )
    for start, end in [
        ((1.55, 1.45), (2.25, 1.45)),
        ((3.75, 1.45), (4.45, 1.45)),
        ((5.95, 1.45), (6.65, 1.45)),
        ((7.4, 1.20), (2.25, 0.70)),
        ((2.65, 0.45), (3.75, 0.45)),
        ((5.45, 0.45), (6.50, 0.45)),
    ]:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color="#555555", lw=1),
        )
    ax.text(
        4.1,
        1.90,
        "Design space",
        ha="center",
        color="#555555",
        fontsize=9,
        fontweight="bold",
    )
    ax.text(
        4.6,
        -0.05,
        "Locked confirmation evidence",
        ha="center",
        color="#555555",
        fontsize=9,
        fontweight="bold",
    )
    ax.set_xlim(-0.4, 8.6)
    ax.set_ylim(-0.25, 2.15)
    ax.set_title("Study architecture and evidence classes")
    caption = (
        "Study architecture. Exact counts come from the frozen development and "
        "confirmation manifests: 36 development candidate configurations, six "
        "confirmation strategy identities, 84 strategy–environment cells, and "
        "3,360 paired-seed jobs. Development selection and confirmation inference "
        "are distinct evidence classes."
    )
    manifest.append(save(fig, "Figure01_study_architecture", architecture, caption))

    manifest.append(
        forest(
            primary,
            "l1_campaign_mace",
            "Figure02_L1_forest",
            "L1 Campaign MACE effects by locked environment",
            "negative favors the test strategy",
        )
    )
    manifest.append(
        forest(
            primary,
            "l4_top1pct_recall_nauc",
            "Figure03_L4_forest",
            "L4 top-1% recall nAUC effects by locked environment",
            "positive favors the test strategy",
        )
    )

    selected = primary[primary["contrast_name"].isin(
        ["Selected GG vs Raw", "Selected CS vs Raw"]
    )].copy()
    selected_summary = (
        selected.groupby(["task", "contrast_name", "endpoint"], as_index=False)
        .agg(
            descriptive_mean=("mean_diff", "mean"),
            environment_min=("mean_diff", "min"),
            environment_max=("mean_diff", "max"),
        )
    )
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    for ax, endpoint, title in zip(
        axes,
        ["l1_campaign_mace", "l4_top1pct_recall_nauc"],
        ["Campaign MACE effect", "Top-1% recall nAUC effect"],
    ):
        group = selected_summary[selected_summary["endpoint"] == endpoint]
        for j, contrast in enumerate(["Selected GG vs Raw", "Selected CS vs Raw"]):
            g = group[group["contrast_name"] == contrast].set_index("task").reindex(TASKS)
            x = np.arange(4) + (-0.12 if j == 0 else 0.12)
            ax.errorbar(
                x,
                g["descriptive_mean"],
                yerr=[
                    g["descriptive_mean"] - g["environment_min"],
                    g["environment_max"] - g["descriptive_mean"],
                ],
                fmt="o" if j == 0 else "s",
                color=COLORS[contrast],
                capsize=3,
                label=contrast,
            )
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(np.arange(4), [TL[t] for t in TASKS], rotation=20)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    axes[1].legend()
    fig.suptitle("Development-selected strategies by task")
    fig.tight_layout()
    caption = (
        "Development-selected strategies by task. Points are descriptive means "
        "across the four locked split–surrogate environments; bars show the observed "
        "environment range. Tasks are categorical and are not connected. L1 effects "
        "are test minus baseline, so negative favors test; L4 effects are test minus "
        "baseline, so positive favors test. No pooled-task inference."
    )
    manifest.append(
        save(fig, "Figure04_selected_strategies_by_task", selected_summary, caption)
    )

    cs = primary[primary["contrast_name"].isin(
        ["Historical CS vs Raw", "Selected CS vs Raw"]
    )].copy()
    cs["environment_label"] = cs.apply(env_label, axis=1)
    order_labels = [
        f"{TL[t]} | {s} | {m}"
        for t in TASKS
        for s in ["IID", "OOD"]
        for m in ["RF", "ExtraTrees"]
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.3), sharey=True)
    for ax, endpoint, title in zip(
        axes,
        ["l1_campaign_mace", "l4_top1pct_recall_nauc"],
        ["Campaign MACE effect", "Top-1% recall nAUC effect"],
    ):
        group = cs[cs["endpoint"] == endpoint]
        for j, contrast in enumerate(["Historical CS vs Raw", "Selected CS vs Raw"]):
            g = group[group["contrast_name"] == contrast].set_index(
                "environment_label"
            ).reindex(order_labels)
            y = np.arange(16)[::-1] + (-0.12 if j == 0 else 0.12)
            ax.scatter(
                g["mean_diff"],
                y,
                color=COLORS[contrast],
                marker="o" if j == 0 else "s",
                label=contrast,
                s=28,
            )
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.25)
    axes[0].set_yticks(np.arange(16)[::-1], order_labels)
    axes[1].legend()
    fig.suptitle("Historical versus selected candidate-specific scaling")
    fig.tight_layout()
    caption = (
        "Historical versus selected candidate-specific scaling. Each point is a "
        "locked environment-level paired effect from 40 seeds. Environment labels "
        "identify task, split, and surrogate. Vertical zero lines mark no effect. "
        "L1 negative and L4 positive favor the test strategy. Confirmatory; no pooled "
        "inference."
    )
    manifest.append(save(fig, "Figure05_historical_vs_selected_CS", cs, caption))

    sensitivity["effect_delta"] = (
        sensitivity["mean_diff_sensitivity"] - sensitivity["mean_diff_primary"]
    )
    sensitivity["label"] = (
        sensitivity["contrast_name"]
        + " | "
        + sensitivity["endpoint"].map(
            {
                "l1_campaign_mace": "L1",
                "l4_top1pct_recall_nauc": "L4",
            }
        )
    )
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4))
    for ax, endpoint, title in zip(
        axes,
        ["l1_campaign_mace", "l4_top1pct_recall_nauc"],
        ["Campaign MACE", "Top-1% recall nAUC"],
    ):
        group = sensitivity[sensitivity["endpoint"] == endpoint].copy()
        group = group.set_index("contrast_name").reindex(CONTRASTS).reset_index()
        y = np.arange(4)[::-1]
        ax.barh(
            y,
            group["effect_delta"] * 1000,
            color=[COLORS[c] for c in group["contrast_name"]],
        )
        ax.axvline(0, color="black", lw=0.8)
        ax.set_yticks(y, group["contrast_name"])
        ax.set_title(title)
        ax.set_xlabel("Sensitivity − primary effect (×10⁻³)")
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Recovery-exclusion sensitivity: paired 40-to-34 seed comparison")
    fig.tight_layout()
    caption = (
        "Recovery-exclusion sensitivity. Bars show the sensitivity effect minus the "
        "primary effect after paired exclusion of seeds 5013–5018 (40 to 34 pairs). "
        "Across eight contrasts, direction changes, BH-label changes, and CI "
        "zero-exclusion changes were each 0/8. Two relative changes exceeded 10%; "
        "the maximum absolute effect change was 0.00182503. Stable inference labels "
        "do not imply identical effect magnitudes. Sensitivity analysis."
    )
    manifest.append(save(fig, "Figure06_recovery_exclusion", sensitivity, caption))

    keep = [
        "raw_ucb_beta_1",
        "raw_ucb_beta_2",
        "gg_ucb_beta_1",
        "gg_ucb_beta_0p5",
        "cs_da_oob_hist",
        "cs_da_oob_parsimonious_f1",
    ]
    calibration = endpoints[endpoints["strategy"].isin(keep)].copy()
    calibration_summary = (
        calibration.groupby(["task", "strategy"], as_index=False)
        .agg(
            mean_campaign_mace=("l1_campaign_mace", "mean"),
            min_campaign_mace=("l1_campaign_mace", "min"),
            max_campaign_mace=("l1_campaign_mace", "max"),
        )
    )
    fig, ax = plt.subplots(figsize=(10.4, 4.8))
    strategies = [s for s in keep if s in set(calibration_summary["strategy"])]
    strategy_labels = {
        "raw_ucb_beta_1": "Raw UCB β=1",
        "raw_ucb_beta_2": "Raw UCB β=2",
        "gg_ucb_beta_1": "Global scaling, UCB β=1",
        "gg_ucb_beta_0p5": "Global scaling, UCB β=0.5",
        "cs_da_oob_hist": "Candidate-specific, historical",
        "cs_da_oob_parsimonious_f1": "Candidate-specific, selected",
    }
    offsets = np.linspace(-0.3, 0.3, len(strategies))
    for off, strategy in zip(offsets, strategies):
        g = calibration_summary[calibration_summary["strategy"] == strategy].set_index(
            "task"
        ).reindex(TASKS)
        valid = g["mean_campaign_mace"].notna()
        x = np.arange(4)[valid] + off
        ax.scatter(
            x,
            g.loc[valid, "mean_campaign_mace"],
            s=24,
            label=strategy_labels[strategy],
        )
    ax.set_xticks(np.arange(4), [TL[t] for t in TASKS])
    ax.set_ylabel("Absolute Campaign MACE (lower is better)")
    ax.set_title("Campaign calibration by task and strategy")
    ax.legend(ncol=2, fontsize=7)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    caption = (
        "Absolute Campaign MACE by task and strategy. Points summarize locked "
        "seed-level endpoints; tasks are categorical and are not connected. Missing "
        "strategy–task cells are omitted, never plotted as zero. Raw beta 2 is the "
        "locked selected baseline only for log-KVRH. Descriptive absolute performance."
    )
    manifest.append(
        save(fig, "Figure07_calibration_campaign_summary", calibration_summary, caption)
    )

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
        .agg(median_runtime_seconds=("runtime_seconds", "median"))
    )
    ratio = runtime_summary.pivot(index="task", columns="family", values="median_runtime_seconds")
    ratio["candidate_to_global_ratio"] = ratio["Candidate-specific"] / ratio["Global"]
    ratio = ratio.reset_index()
    fig, axes = plt.subplots(
        1, 2, figsize=(10, 4.3), gridspec_kw={"width_ratios": [1, 1.8]}
    )
    families = ["Raw", "Global", "Candidate-specific"]
    colors = ["#777777", "#0072B2", "#D55E00"]
    mp = runtime_summary[runtime_summary["task"] == "matbench_mp_gap"]
    axes[0].bar(
        families,
        [mp.set_index("family").loc[f, "median_runtime_seconds"] / 60 for f in families],
        color=colors,
    )
    axes[0].set_title("MP gap")
    axes[0].set_ylabel("Median observed job runtime (min)")
    small_tasks = [t for t in TASKS if t != "matbench_mp_gap"]
    width = 0.22
    for i, family in enumerate(families):
        g = runtime_summary[runtime_summary["family"] == family].set_index("task").reindex(small_tasks)
        axes[1].bar(
            np.arange(3) + (i - 1) * width,
            g["median_runtime_seconds"],
            width,
            label=family,
            color=colors[i],
        )
    axes[1].set_xticks(np.arange(3), [TL[t] for t in small_tasks], rotation=18)
    axes[1].set_ylabel("Median observed job runtime (s)")
    axes[1].set_title("Other tasks")
    axes[1].legend()
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Observed runtime by task and strategy family")
    fig.tight_layout()
    ratios = dict(zip(ratio["task"], ratio["candidate_to_global_ratio"]))
    caption = (
        "Median observed job runtime by task and strategy family. Separate panels "
        "avoid compressing the smaller tasks. Candidate-specific/global median "
        f"runtime ratios were {ratios['matbench_mp_gap']:.1f}× for MP gap and "
        f"{min(ratios[t] for t in small_tasks):.1f}–"
        f"{max(ratios[t] for t in small_tasks):.1f}× for the other tasks. "
        "These measurements are implementation- and hardware-specific observations, "
        "not a formal complexity analysis."
    )
    runtime_source = runtime_summary.merge(
        ratio[["task", "candidate_to_global_ratio"]], on="task"
    )
    manifest.append(save(fig, "Figure08_runtime_by_task", runtime_source, caption))

    cross = primary.pivot_table(
        index=["task", "split", "surrogate", "environment", "contrast_name"],
        columns="endpoint",
        values="mean_diff",
        aggfunc="first",
    ).reset_index()
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    for _, row in cross.iterrows():
        marker = TASK_MARKERS[row["task"]]
        face = COLORS[row["contrast_name"]] if row["split"] == "iid_record" else "white"
        edge = COLORS[row["contrast_name"]]
        ax.scatter(
            -row["l1_campaign_mace"],
            row["l4_top1pct_recall_nauc"],
            marker=marker,
            facecolors=face,
            edgecolors=edge,
            linewidths=1.0 if row["surrogate"] == "random_forest" else 1.8,
            s=46,
        )
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("L1 benefit (− Campaign MACE effect; positive is better)")
    ax.set_ylabel("L4 benefit (top-1% recall nAUC effect; positive is better)")
    ax.set_title("Exploratory L1–L4 environment-level alignment")
    ax.grid(alpha=0.25)
    handles = [
        plt.Line2D([], [], marker=TASK_MARKERS[t], linestyle="", color="black", label=TL[t])
        for t in TASKS
    ]
    handles += [
        plt.Line2D([], [], marker="o", linestyle="", markerfacecolor=COLORS[c],
                   markeredgecolor=COLORS[c], label=c)
        for c in CONTRASTS
    ]
    ax.legend(handles=handles, ncol=2, fontsize=7)
    fig.tight_layout()
    caption = (
        "Exploratory L1–L4 alignment. Each point is one locked environment-level "
        "effect. Color encodes contrast; marker shape encodes task; filled/open "
        "markers encode IID/OOD; edge width distinguishes RF from ExtraTrees. "
        "No pooled-task inference, pooled correlation p-value, or causal mediation "
        "interpretation is made."
    )
    manifest.append(
        save(fig, "Figure09_L1_L4_cross_layer_exploratory", cross, caption)
    )

    lock = json.loads((TABLES / "FINAL_TABLE_LOCK_V5.json").read_text())
    output = {
        "schema_version": "final-figure-manifest-v2",
        "final_table_lock_sha256": sha(TABLES / "FINAL_TABLE_LOCK_V5.json"),
        "final_table_hashes": {x["path"]: x["sha256"] for x in lock["files"]},
        "figures": manifest,
    }
    (OUT / "figure_manifest_v2.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"figures": len(manifest), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
