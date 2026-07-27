from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

root = Path(r"D:\贝叶斯优化\revision_v5\figures_v5\submission_candidate_v4\phase3")
source = root / "FigureS3_TopTail_Sensitivity_source.csv"
data = pd.read_csv(source)
summary = data.groupby(["contrast_name", "sensitivity_metric"], as_index=False).mean_diff_test_minus_baseline.mean()
metrics = list(summary.sensitivity_metric.unique())
contrasts = list(summary.contrast_name.unique())
colors = ["#35618f", "#8ba9c2", "#c18a2b", "#e2c486"]
hatches = ["", "//", "..", "xx"]
x = np.arange(len(contrasts))
width = .18
fig, ax = plt.subplots(figsize=(10, 5.5))
for i, metric in enumerate(metrics):
    values = [
        float(summary[(summary.contrast_name == contrast) & (summary.sensitivity_metric == metric)].mean_diff_test_minus_baseline.iloc[0])
        for contrast in contrasts
    ]
    ax.bar(
        x + (i - 1.5) * width, values, width,
        label=metric.replace("recall_", "").replace("_nauc_full", ""),
        color=colors[i], hatch=hatches[i], edgecolor="#252b33",
    )
ax.axhline(0, color="#252b33", linewidth=.8)
ax.set_xticks(x, contrasts, rotation=20, ha="right")
ax.set(title="Top-tail recall nAUC sensitivity", ylabel="Mean test-minus-baseline effect across environments")
ax.legend(ncol=4, fontsize=8)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e7ebef", linewidth=.7)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(root / "FigureS3_TopTail_Sensitivity.pdf", bbox_inches="tight")
fig.savefig(root / "FigureS3_TopTail_Sensitivity.png", dpi=240, bbox_inches="tight")
plt.close(fig)
print("S3_PALETTE=two-root")
print("S3_NONCOLOR_ENCODING=hatches")
