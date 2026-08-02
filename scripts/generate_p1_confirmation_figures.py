"""Generate the eighteen registered P1 confirmation/diagnostic figure sets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables"
FIGURES = ROOT / "manuscript/figures_p1_confirmation"
COLORS = {"RAW": "#4E79A7", "P1_QGB_RAW": "#4E79A7", "P1_QGB_CALIBRATION_ONLY_RR": "#59A14F", "P1_QGB_ACQUISITION_ONLY_RR": "#E15759", "RAW_FIXED_BETA_MATCHED": "#F28E2B", "RAW_STAGE_BETA_MATCHED": "#76B7B2", "DEVELOPMENT_SELECTED_CONSTANT_BETA_UCB": "#B07AA1"}
CONTRAST_LABELS = {
    "P1_C1": "Stagewise beta vs RAW",
    "P1_C2": "Stagewise beta vs fixed beta",
    "P1_C3": "Selected constant beta vs RAW",
    "P1_C4": "RR calibration-only vs QGB RAW",
    "P1_C5": "RR acquisition-only vs QGB RAW",
}
TASK_LABELS = {
    "matbench_expt_gap": "Experimental band gap",
    "matbench_mp_gap": "Computed band gap",
    "matbench_log_gvrh": "Shear modulus",
    "matbench_log_kvrh": "Bulk modulus",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output_dir: Path = FIGURES, inventory_output: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if inventory_output is None:
        inventory_output = TABLES / "p1_figure_source_inventory.csv"
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "svg.hashsalt": "p1-confirmation-locked",
        "pdf.fonttype": 42,
    })
    primary_path = TABLES / "p1_confirmation_primary_contrasts.csv"
    env_path = TABLES / "p1_confirmation_environment_effects.csv"
    task_path = TABLES / "p1_confirmation_task_effects.csv"
    endpoints_path = TABLES / "p1_confirmation_seed_level_endpoints.csv"
    check_path = TABLES / "p1_confirmation_checkpoint_endpoints.csv"
    cal_path = TABLES / "p1_confirmation_calibration_diagnostics.csv"
    traj_path = TABLES / "p1_confirmation_trajectory_points.csv"
    disc_path = TABLES / "p1_confirmation_discovery_endpoints.csv"
    seed_path = TABLES / "p1_confirmation_seed_block_effects.csv"
    robustness_path = TABLES / "p1_confirmation_robustness.csv"
    sources = {path.name: pd.read_csv(path, low_memory=False) for path in (primary_path, env_path, task_path, endpoints_path, check_path, cal_path, traj_path, disc_path, seed_path, robustness_path)}
    primary, env, task = sources[primary_path.name], sources[env_path.name], sources[task_path.name]
    endpoints, check, cal = sources[endpoints_path.name], sources[check_path.name], sources[cal_path.name]
    traj, disc, seed = sources[traj_path.name], sources[disc_path.name], sources[seed_path.name]
    robustness = sources[robustness_path.name]
    inventory: list[dict[str, object]] = []

    def save(fig: plt.Figure, number: int, stem: str, source: Path, evidence: str, filters: str = "none") -> None:
        outputs = [
            ("pdf", output_dir / f"P1_Figure{number:02d}_{stem}.pdf"),
            ("svg", output_dir / f"P1_Figure{number:02d}_{stem}.svg"),
            ("png", output_dir / f"P1_Figure{number:02d}_{stem}.png"),
        ]
        fig.savefig(outputs[0][1], bbox_inches="tight", metadata={"Creator": "P1 locked table figure pipeline", "CreationDate": None, "ModDate": None})
        fig.savefig(outputs[1][1], bbox_inches="tight", metadata={"Creator": "P1 locked table figure pipeline", "Date": None})
        fig.savefig(outputs[2][1], dpi=600, bbox_inches="tight", metadata={"Creator": "P1 locked table figure pipeline"})
        for suffix, output in outputs:
            try:
                output_name = output.resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                output_name = f"generated_figures/{output.name}"
            inventory.append({"figure_id": f"P1_Figure{number:02d}", "panel": "all", "source_table": source.relative_to(ROOT).as_posix(), "filters": filters, "script": "scripts/generate_p1_confirmation_figures.py", "evidence_class": evidence, "source_hash": sha(source), "output_file": output_name, "output_hash": sha(output)})
        plt.close(fig)

    # Figure contract: show the one supported control comparison without
    # obscuring that the RAW and QGB-baseline comparisons were unfavorable.
    # Separate L1 and L4 because they have different units and directions.
    fig = plt.figure(figsize=(7.2, 5.4), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=[1.35, 1.0])
    axes = [fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])]
    groups = [["P1_C1", "P1_C2", "P1_C3"], ["P1_C4"], ["P1_C5"]]
    titles = ["a  Tree exploration controls: L4 (greater is favorable)", "b  QGB calibration role: L1 (less is favorable)", "c  QGB acquisition role: L4 (greater is favorable)"]
    for axis, ids, title in zip(axes, groups, titles):
        group = primary.set_index("contrast_id").loc[ids].reset_index()
        y = np.arange(len(group))[::-1]
        colors = ["#2A7F9E" if value else "#C65D3B" for value in group.registered_direction_supported]
        for yi, row, color in zip(y, group.itertuples(index=False), colors):
            axis.errorbar(row.pooled_effect, yi, xerr=[[row.pooled_effect-row.ci95_low], [row.ci95_high-row.pooled_effect]], fmt="o", color=color, ecolor=color, capsize=3, markersize=5, lw=1.3)
            status = "supported" if row.registered_direction_supported else "opposes alternative"
            axis.annotate(status, (row.pooled_effect, yi), xytext=(6, 6), textcoords="offset points", fontsize=6.5, color=color)
        axis.axvline(0, ls="--", lw=.8, color="0.45")
        axis.set_yticks(y, [f"{CONTRAST_LABELS[cid]}\n({cid})" for cid in ids], fontsize=7)
        axis.set_xlabel("Strategy minus baseline")
        axis.set_title(title, loc="left", fontweight="bold", fontsize=8.5)
        axis.grid(axis="x", color="0.9", lw=.6)
    fig.suptitle("Independent P1 confirmation: comparison-specific effects", fontweight="bold", fontsize=10)
    save(fig, 1, "registered_effects", primary_path, "P1_INDEPENDENT_CONFIRMATION", "three endpoint-separated panels; labels joined to frozen contrast registry")

    plot = env.copy()
    plot["label"] = plot.task.str.replace("matbench_", "") + "/" + plot["split"].str.replace("chemical_system_ood", "OOD").str.replace("iid_record", "IID") + "/" + plot.model.str.replace("extra_randomized_bagging", "ET").str.replace("random_forest", "RF").str.replace("quantile_gradient_boosting", "QGB")
    # Main-text heterogeneity display: scientific tasks are the rows; repeated
    # split/model environments are not presented as independent tasks.
    contrast_ids = sorted(task.contrast_id.unique())
    fig, axes = plt.subplots(2, 3, figsize=(10.0, 6.4), constrained_layout=True)
    axes = axes.ravel()
    for axis, contrast_id in zip(axes, contrast_ids):
        group = task[task.contrast_id == contrast_id].copy()
        pooled = primary[primary.contrast_id == contrast_id].iloc[0]
        group["task_label"] = group.task.map(TASK_LABELS)
        group = group.set_index("task").loc[list(TASK_LABELS)].reset_index()
        y = np.arange(len(group), 0, -1)
        axis.errorbar(group.effect, y, xerr=[group.effect-group.ci95_low, group.ci95_high-group.effect], fmt="o", color="#5B6F8F", ecolor="#8A98AB", capsize=2, markersize=4, lw=1)
        axis.errorbar([pooled.pooled_effect], [0], xerr=[[pooled.pooled_effect-pooled.ci95_low], [pooled.ci95_high-pooled.pooled_effect]], fmt="D", color="#202020", capsize=3, markersize=4.5, lw=1.3)
        axis.axvline(0, ls="--", lw=.8, color="0.5")
        axis.set_yticks(list(y)+[0], list(group.task_label)+["Pooled"], fontsize=6.5)
        axis.set_title(f"{CONTRAST_LABELS[contrast_id]}\n({contrast_id})", fontsize=8)
        axis.set_xlabel("Paired effect", fontsize=7)
        axis.grid(axis="x", color="0.92", lw=.5)
    axes[-1].axis("off")
    fig.suptitle("Task-level P1 heterogeneity (exploratory robustness)", fontweight="bold", fontsize=10)
    save(fig, 2, "environment_heterogeneity", task_path, "exploratory_robustness", "four scientific task estimates plus the registered pooled effect; no environment rows")

    # Full task x split x model diagnostics remain in the Supplement. Each
    # exported figure contains at most two panels for final-size readability.
    environment_groups = [(["P1_C1", "P1_C2"], 16, "environment_tree_c1_c2"), (["P1_C3"], 17, "environment_tree_c3"), (["P1_C4", "P1_C5"], 18, "environment_qgb_c4_c5")]
    for ids, number, stem in environment_groups:
        fig, axes = plt.subplots(1, len(ids), figsize=(7.2 if len(ids) == 2 else 4.6, 5.4), squeeze=False, constrained_layout=True)
        for axis, contrast_id in zip(axes.ravel(), ids):
            group = plot[plot.contrast_id == contrast_id].sort_values("effect")
            y = np.arange(len(group))
            axis.errorbar(group.effect, y, xerr=[group.effect-group.ci95_low, group.ci95_high-group.effect], fmt="o", color="#5B6F8F", ecolor="#8A98AB", capsize=2, markersize=3.5, lw=.9)
            axis.axvline(0, ls="--", lw=.8, color="0.5")
            axis.set_yticks(y, group.label, fontsize=5.8)
            axis.set_title(f"{CONTRAST_LABELS[contrast_id]}\n({contrast_id})", fontsize=8)
            axis.set_xlabel("Paired effect")
            axis.grid(axis="x", color="0.92", lw=.5)
        fig.suptitle("Environment-level effects (descriptive diagnostics)", fontweight="bold", fontsize=9.5)
        save(fig, number, stem, env_path, "descriptive_heterogeneity", f"contrast_ids={'|'.join(ids)}; every task/split/model environment retained")

    absolute = endpoints.groupby(["strategy", "model"], as_index=False).agg(P1_L1=("P1_L1", "mean"), P1_L4=("P1_L4", "mean")); fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8), sharey=True); labels = absolute.strategy.str.replace("DEVELOPMENT_SELECTED_CONSTANT_BETA_UCB", "DEV_BETA").str.replace("P1_QGB_", "QGB_"); axes[0].barh(labels, absolute.P1_L1, color=[COLORS.get(v, "#999999") for v in absolute.strategy]); axes[1].barh(labels, absolute.P1_L4, color=[COLORS.get(v, "#999999") for v in absolute.strategy]); axes[1].tick_params(axis="y", labelleft=False); axes[0].set(xlabel="Campaign MACE (lower better)"); axes[1].set(xlabel="Top-1% recall nAUC (higher better)"); fig.suptitle("Absolute endpoint levels"); save(fig, 3, "absolute_endpoints", endpoints_path, "P1_INDEPENDENT_CONFIRMATION_DESCRIPTIVE")

    metrics = cal[(cal.diagnostic_type == "campaign_checkpoint_metric") & (cal.model == "quantile_gradient_boosting")].copy(); coverage = metrics.melt(id_vars=["manifest_strategy"], value_vars=["coverage_50", "coverage_80", "coverage_90", "coverage_95"], var_name="nominal", value_name="empirical"); coverage["nominal"] = coverage.nominal.str[-2:].astype(float)/100; curve = coverage.groupby(["manifest_strategy", "nominal"], as_index=False).empirical.mean(); fig, ax = plt.subplots(figsize=(5.2, 4.2)); ax.plot([.45,1],[.45,1],ls="--",color="0.5");
    for strategy, group in curve.groupby("manifest_strategy"): ax.plot(group.nominal, group.empirical, marker="o", label=strategy, color=COLORS.get(strategy));
    ax.set(xlabel="Nominal coverage", ylabel="Empirical coverage", title="QGB calibration curve"); ax.legend(fontsize=6, frameon=False); save(fig, 4, "nominal_empirical_coverage", cal_path, "P1_EXPLORATORY_DIAGNOSTIC", "campaign_checkpoint_metric")

    fig, ax = plt.subplots(figsize=(5.5, 4.2));
    for strategy, group in metrics.groupby("manifest_strategy"): ax.scatter(group.mean_interval_width_90, group.mean_absolute_coverage_error, s=5, alpha=.15, label=strategy, color=COLORS.get(strategy));
    ax.set(xlabel="Mean 90% interval width", ylabel="MACE", title="Calibration-sharpness diagnostic"); ax.legend(fontsize=6, frameon=False); save(fig, 5, "width_vs_calibration_error", cal_path, "P1_EXPLORATORY_DIAGNOSTIC", "campaign_checkpoint_metric")

    score = metrics.groupby("manifest_strategy", as_index=False)[["interval_score_90", "gaussian_nll", "gaussian_crps"]].mean(); fig, axes = plt.subplots(1,3,figsize=(10,3.5));
    for axis, column in zip(axes, ["interval_score_90", "gaussian_nll", "gaussian_crps"]): axis.bar(range(len(score)), score[column], color=[COLORS.get(v,"#999") for v in score.manifest_strategy]); axis.set_xticks(range(len(score)), score.manifest_strategy.str.replace("P1_QGB_", ""), rotation=70, fontsize=6); axis.set_title(column.replace("_"," "));
    fig.suptitle("Proper-score diagnostics (lower is better)"); save(fig, 6, "proper_scores", cal_path, "P1_EXPLORATORY_DIAGNOSTIC", "campaign_checkpoint_metric")

    qq = cal[cal.diagnostic_type == "standardized_residual_qq"].groupby(["manifest_strategy", "probability"], as_index=False)[["theoretical_quantile", "observed_quantile"]].mean(); fig, ax = plt.subplots(figsize=(5,4.2)); ax.plot([-3,3],[-3,3],ls="--",color="0.5");
    for strategy, group in qq.groupby("manifest_strategy"): ax.plot(group.theoretical_quantile, group.observed_quantile, marker="o", label=strategy, color=COLORS.get(strategy));
    ax.set_yscale("symlog", linthresh=5); ax.set(xlabel="Standard-normal quantile", ylabel="Observed standardized residual quantile (symlog)", title="Standardized-residual QQ"); ax.legend(fontsize=6, frameon=False); save(fig, 7, "standardized_residual_qq", cal_path, "P1_DESCRIPTIVE_MECHANISM", "standardized_residual_qq; symlog display only")

    conditional = cal[cal.diagnostic_type == "conditional_coverage_90_by_uncertainty"].groupby(["manifest_strategy", "bin"], as_index=False).coverage.mean(); fig, ax = plt.subplots(figsize=(5.4,4));
    for strategy, group in conditional.groupby("manifest_strategy"): ax.plot(group.bin+1, group.coverage, marker="o", label=strategy, color=COLORS.get(strategy));
    ax.axhline(.9,ls="--",color="0.5"); ax.set(xlabel="Predicted-spread quintile", ylabel="90% empirical coverage", title="Conditional coverage"); ax.legend(fontsize=6,frameon=False); save(fig, 8, "conditional_coverage", cal_path, "P1_EXPLORATORY_DIAGNOSTIC", "conditional_coverage_90_by_uncertainty")

    qgb = traj[traj.model == "quantile_gradient_boosting"].copy()
    trajectory_grid_values = np.linspace(0.0, 1.0, 21)
    interpolated_rows: list[dict[str, object]] = []
    for (strategy, job_id), group in qgb.groupby(["manifest_strategy", "job_id"]):
        ordered = group.groupby("budget_fraction", as_index=False)[["top1_recall", "top5_recall", "top10_recall", "best_so_far", "simple_regret"]].mean().sort_values("budget_fraction")
        x_values = ordered.budget_fraction.to_numpy()
        best_values = ordered.best_so_far.to_numpy()
        regret_values = ordered.simple_regret.to_numpy()
        best_range = best_values.max() - best_values[0]
        regret_range = regret_values[0] - regret_values.min()
        best_improvement = (best_values - best_values[0]) / best_range if best_range > 0 else np.zeros_like(best_values)
        regret_reduction = (regret_values[0] - regret_values) / regret_range if regret_range > 0 else np.zeros_like(regret_values)
        series = {
            "top1_recall": ordered.top1_recall.to_numpy(),
            "top5_recall": ordered.top5_recall.to_numpy(),
            "top10_recall": ordered.top10_recall.to_numpy(),
            "best_improvement_within_job": best_improvement,
            "regret_reduction_within_job": regret_reduction,
        }
        for budget_fraction in trajectory_grid_values:
            row: dict[str, object] = {"manifest_strategy": strategy, "job_id": job_id, "budget_fraction": budget_fraction}
            for column, values in series.items():
                row[column] = float(np.interp(budget_fraction, x_values, values))
            interpolated_rows.append(row)
    trajectory_grid = pd.DataFrame(interpolated_rows)
    mean_trajectory = trajectory_grid.groupby(["manifest_strategy", "budget_fraction"], as_index=False).mean(numeric_only=True)
    recall = mean_trajectory[["manifest_strategy", "budget_fraction", "top1_recall", "top5_recall", "top10_recall"]]
    fig, axes = plt.subplots(1,3,figsize=(10,3.4));
    for axis, column in zip(axes,["top1_recall","top5_recall","top10_recall"]):
        for strategy, group in recall.groupby("manifest_strategy"): axis.plot(group.budget_fraction,group[column],label=strategy,color=COLORS.get(strategy));
        axis.set(xlabel="Normalized budget",ylabel=column.replace("_"," "));
    axes[0].legend(fontsize=5,frameon=False); fig.suptitle("Top-1/5/10% recall trajectories"); save(fig, 9, "recall_trajectories", traj_path, "P1_EXPLORATORY_DIAGNOSTIC", "QGB only; every job linearly interpolated from all points to a fixed 21-point normalized-budget grid, then averaged")

    regret = mean_trajectory[["manifest_strategy", "budget_fraction", "best_improvement_within_job", "regret_reduction_within_job"]]; fig, axes = plt.subplots(1,2,figsize=(8,3.6));
    for strategy, group in regret.groupby("manifest_strategy"):
        axes[0].plot(group.budget_fraction,group.best_improvement_within_job,label=strategy,color=COLORS.get(strategy)); axes[1].plot(group.budget_fraction,group.regret_reduction_within_job,label=strategy,color=COLORS.get(strategy));
    axes[0].set(xlabel="Normalized budget",ylabel="Realized best-value improvement"); axes[1].set(xlabel="Normalized budget",ylabel="Realized regret reduction"); axes[0].legend(fontsize=5,frameon=False); fig.suptitle("Within-job normalized discovery gains"); save(fig, 10, "best_and_regret", traj_path, "P1_EXPLORATORY_DIAGNOSTIC", "QGB only; normalized relative to each job's initial and best observed value; no-improvement jobs retained as zero; every job interpolated from all points to a fixed 21-point grid, then averaged")

    segments = disc.groupby("strategy",as_index=False)[["segment_auc_early","segment_auc_middle","segment_auc_late"]].mean(); fig, ax = plt.subplots(figsize=(6,4)); x=np.arange(len(segments)); width=.25;
    for index,column in enumerate(["segment_auc_early","segment_auc_middle","segment_auc_late"]): ax.bar(x+(index-1)*width,segments[column],width,label=column.replace("segment_auc_",""));
    short_strategy = segments.strategy.map({"P1_QGB_ACQUISITION_ONLY_RR": "ACQ-only", "P1_QGB_CALIBRATION_ONLY_RR": "CAL-only", "P1_QGB_RAW": "RAW"})
    ax.set_xticks(x,short_strategy); ax.set(ylabel="Segment-normalized AUC",title="Early/middle/late discovery"); ax.legend(frameon=False); save(fig, 11, "budget_segments", disc_path, "P1_EXPLORATORY_DIAGNOSTIC")

    fig, ax = plt.subplots(figsize=(6,4));
    for index,(contrast,group) in enumerate(seed.groupby("contrast_id")):
        deterministic_jitter = np.linspace(-0.05, 0.05, len(group), endpoint=True)
        ax.scatter(index + deterministic_jitter, group.equal_environment_effect, s=12, alpha=.65)
    ax.axhline(0,ls="--",color="0.5"); ax.set_xticks(range(seed.contrast_id.nunique()),sorted(seed.contrast_id.unique())); ax.set(ylabel="Paired seed-block effect",title="Confirmation seed-block distributions"); save(fig, 12, "seed_block_strip", seed_path, "P1_INDEPENDENT_CONFIRMATION")

    loo=robustness[robustness.analysis == "leave_one_task_out"].copy(); loo["excluded_task"] = loo.excluded_task.str.replace("matbench_", ""); fig, ax = plt.subplots(figsize=(6,4)); pivot=loo.pivot(index="excluded_task",columns="contrast_id",values="effect"); pivot.plot(kind="bar",ax=ax); ax.axhline(0,ls="--",color="0.5"); ax.set(ylabel="Pooled effect after exclusion",title="Leave-one-task-out sensitivity",xlabel="Excluded task"); ax.legend(fontsize=6,frameon=False); save(fig, 13, "task_leave_one_out", robustness_path, "P1_EXPLORATORY_ROBUSTNESS", "leave_one_task_out")

    crossing_grid_values = np.linspace(0.0, 1.0, 5)
    crossing_rows: list[dict[str, object]] = []
    for (strategy, job_id), group in metrics.groupby(["manifest_strategy", "job_id"]):
        ordered = group.groupby("budget_fraction", as_index=False).quantile_crossings.mean().sort_values("budget_fraction")
        for budget_fraction in crossing_grid_values:
            crossing_rows.append({"manifest_strategy": strategy, "budget_fraction": budget_fraction, "quantile_crossings": float(np.interp(budget_fraction, ordered.budget_fraction, ordered.quantile_crossings))})
    crossing = pd.DataFrame(crossing_rows).groupby(["manifest_strategy", "budget_fraction"], as_index=False).quantile_crossings.mean(); fig, ax = plt.subplots(figsize=(5.5,4));
    for strategy,group in crossing.groupby("manifest_strategy"): ax.plot(group.budget_fraction,group.quantile_crossings,marker="o",label=strategy,color=COLORS.get(strategy));
    ax.set(xlabel="Normalized budget",ylabel="Mean crossing count",title="Quantile-crossing/floor diagnostic"); ax.legend(fontsize=6,frameon=False); save(fig, 14, "quantile_crossings", cal_path, "P1_DESCRIPTIVE_MECHANISM", "campaign_checkpoint_metric; every job interpolated from all checkpoints to a fixed five-point normalized-budget grid, then averaged")

    scalar=metrics[metrics.manifest_strategy != "P1_QGB_RAW"].copy(); scalar["stage"]=pd.cut(scalar.budget_fraction,[-1,.25,.5,.75,1.01],labels=["initial","early","middle","late"]); fig,ax=plt.subplots(figsize=(6,4)); positions=[];labels=[];values=[];
    for index,((strategy,stage),group) in enumerate(scalar.groupby(["manifest_strategy","stage"],observed=True)):
        stage_values = group.residual_ratio.to_numpy()
        if not np.isfinite(stage_values).all():
            raise ValueError(f"non-finite residual-ratio values for {strategy}/{stage}")
        short_name = {"P1_QGB_ACQUISITION_ONLY_RR": "ACQ-only", "P1_QGB_CALIBRATION_ONLY_RR": "CAL-only"}[strategy]
        positions.append(index); labels.append(short_name+"\n"+str(stage)); values.append(stage_values)
    ax.boxplot(values,positions=positions,showfliers=False); ax.set_xticks(positions,labels,rotation=45,ha="right",fontsize=6); ax.set(ylabel="Residual-ratio scalar",title="Scalar distribution across campaign stages"); save(fig, 15, "scalar_stage_distribution", cal_path, "P1_DESCRIPTIVE_MECHANISM", "non-RAW campaign_checkpoint_metric")

    inventory_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inventory).to_csv(inventory_output, index=False, lineterminator="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild P1 figures from locked machine-readable tables.")
    parser.add_argument("--output-dir", type=Path, default=FIGURES)
    parser.add_argument("--inventory-output", type=Path)
    args = parser.parse_args()
    main(args.output_dir.resolve(), args.inventory_output.resolve() if args.inventory_output else None)
