from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures_v5/submission_candidate_v4_final"
SOURCE = FIG / "FigureS1_GG_Effective_Beta_Stratified_source.csv"
OUT = FIG / "FigureS1_GG_Effective_Beta_Stratified"

data = pd.read_csv(SOURCE)
strategies = ["gg_ucb_beta_1", "gg_ucb_beta_0p5"]
labels = ["Original GG (nominal beta 1)", "Selected GG (nominal beta 0.5)"]
colors = ["#315f8c", "#c28a28"]

fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4))
for index, (strategy, label, color) in enumerate(zip(strategies, labels, colors)):
    subset = data[data["strategy"] == strategy]
    axes[0, 0].hist(subset["median_fitted_scale"], bins=35, histtype="step",
                    linewidth=1.6, label=label, color=color, density=True)
    axes[0, 1].hist(subset["median_effective_beta"], bins=35, histtype="step",
                    linewidth=1.6, label=label, color=color, density=True)
    stage = subset.groupby("campaign_stage", sort=False)["median_effective_beta"].median()
    stage = stage.reindex(["0-25%", "25-50%", "50-75%", "75-100%"])
    axes[1, 0].plot(range(4), stage, marker="o", label=label, color=color)
    env = subset.groupby(["task", "split", "surrogate"])[
        "retained_subset_ranking_agreement"
    ].mean()
    axes[1, 1].boxplot(
        env.dropna(), positions=[index], widths=0.55, patch_artist=True,
        boxprops={"facecolor": color, "alpha": 0.35},
        medianprops={"color": "#20252b"},
    )

axes[0, 0].set(title="Fitted global-scale distribution",
               xlabel="Fitted scale", ylabel="Density")
axes[0, 1].set(title="Effective-beta distribution",
               xlabel="Effective beta", ylabel="Density")
axes[1, 0].set(title="Median effective beta by budget stage",
               xlabel="Budget stage", ylabel="Effective beta")
axes[1, 0].set_xticks(range(4), ["0-25%", "25-50%", "50-75%", "75-100%"])
axes[1, 1].set(title="Retained-subset rank agreement",
               ylabel="Spearman agreement")
axes[1, 1].set_xticks([0, 1], ["Original", "Selected"])
for axis in axes.flat:
    axis.grid(color="#d9dee3", linewidth=0.5, alpha=0.8)
axes[0, 0].legend(fontsize=8)
axes[0, 1].legend(fontsize=8)
fig.suptitle(
    "Supplementary Figure S1 | Stratified Original and Selected GG diagnostics",
    fontsize=13, weight="bold",
)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight")
fig.savefig(OUT.with_suffix(".png"), dpi=220, bbox_inches="tight")
plt.close(fig)

(OUT.parent / f"{OUT.name}_caption.txt").write_text(
    "Supplementary Figure S1. Original and Selected GG are stratified. "
    "Ranking agreement is computed only on the retained candidate subset, "
    "not the full candidate pool.\n",
    encoding="utf-8",
)
