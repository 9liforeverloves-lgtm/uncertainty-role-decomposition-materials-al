from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

root = Path(r"D:\贝叶斯优化\revision_v5")
verified = root / "figures_v5/submission_candidate_v4"
out = verified / "phase3"
out.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


# Figures 1-3 already passed source, visual, and PDF QA. Promote byte-identical
# visual copies under versioned Phase-3 names; source CSVs remain byte-identical.
for number, stem in (
    (1, "Figure1_Evidence_Lineage"),
    (2, "Figure2_L1_All_Contrasts"),
    (3, "Figure3_L4_All_Contrasts"),
):
    target = f"Figure{number}_v4_" + stem.split("_", 1)[1]
    for suffix in (".pdf", ".png", "_source.csv", "_caption.txt"):
        shutil.copy2(verified / f"{stem}{suffix}", out / f"{target}{suffix}")
    if (verified / f"{stem}_source.json").is_file():
        shutil.copy2(verified / f"{stem}_source.json", out / f"{target}_source.json")
    meta = {
        "schema_version": "phase3-main-figure-v1",
        "figure": target,
        "layout_status": "verified layout promoted byte-identically",
        "verified_source": str((verified / f"{stem}_source.csv").relative_to(root.parent)).replace("\\", "/"),
        "source_sha256": sha(out / f"{target}_source.csv"),
        "source_byte_identical_to_verified": (out / f"{target}_source.csv").read_bytes()
        == (verified / f"{stem}_source.csv").read_bytes(),
        "visual_byte_identical_to_verified": (out / f"{target}.pdf").read_bytes()
        == (verified / f"{stem}.pdf").read_bytes(),
        "scientific_values_changed": False,
    }
    write(out / f"{target}_metadata.json", json.dumps(meta, indent=2))


# Figure 4: same verified source values; layout adds exact counts and grayscale hatches.
stem = "Figure4_v4_Direction_Aware_Evidence"
source_in = verified / "Figure4_Direction_Aware_Evidence_source.csv"
source_out = out / f"{stem}_source.csv"
shutil.copy2(source_in, source_out)
data = pd.read_csv(source_out)
order = ["Original GG vs Raw", "Historical CS vs Raw", "Selected GG vs Raw", "Selected CS vs Raw"]
endpoint_order = ["l1_campaign_mace", "l4_top1pct_recall_nauc"]
colors = ["#356f98", "#d6a43a", "#d2d7dd"]
hatches = ["", "///", "..."]
labels = ["BH-significant favorable", "BH-significant harmful", "Not BH-significant"]

fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), sharex=True)
for ax, endpoint, title in zip(axes, endpoint_order, ["L1 Campaign MACE", "L4 top-1% recall nAUC"]):
    subset = data[data.endpoint == endpoint].set_index("contrast_name").loc[order]
    y = np.arange(len(order))
    left = np.zeros(len(order))
    values_list = [
        subset.bh_significant_favorable.to_numpy(int),
        subset.bh_significant_harmful.to_numpy(int),
        subset.not_bh_significant.to_numpy(int),
    ]
    for values, color, hatch, label in zip(values_list, colors, hatches, labels):
        bars = ax.barh(y, values, left=left, color=color, hatch=hatch, edgecolor="#252b33", label=label)
        for bar, value in zip(bars, values):
            if value:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    str(int(value)),
                    ha="center", va="center", fontsize=9, fontweight="bold",
                    color="white" if color != "#d2d7dd" else "#252b33",
                )
        left += values
    ax.set_yticks(y, order, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 16)
    ax.set_xticks([0, 4, 8, 12, 16])
    ax.set_xlabel("Number of environments (of 16)")
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.grid(axis="x", color="#e7ebef", linewidth=.8)
    ax.spines[["top", "right"]].set_visible(False)
fig.suptitle("Direction-aware environment-specific evidence classifications", fontsize=15, fontweight="bold")
fig.text(.5, .925, "Descriptive counts of environment-specific BH classifications; not pooled inference.", ha="center", fontsize=10)
handles, leglabels = axes[0].get_legend_handles_labels()
fig.legend(handles, leglabels, loc="lower center", ncol=3, frameon=False, fontsize=9)
fig.tight_layout(rect=(0, .1, 1, .9))
fig.savefig(out / f"{stem}.pdf", bbox_inches="tight")
fig.savefig(out / f"{stem}.png", dpi=240, bbox_inches="tight")
plt.close(fig)

write(
    out / f"{stem}_caption.txt",
    "Figure 4. Direction-aware descriptive counts of environment-specific BH classifications. "
    "Numbers are printed in each nonzero segment; hatch patterns support grayscale reading. "
    "Counts are not pooled inference.",
)
meta = {
    "schema_version": "phase3-main-figure-v1",
    "figure": stem,
    "verified_source": str(source_in.relative_to(root.parent)).replace("\\", "/"),
    "source_sha256": sha(source_out),
    "source_byte_identical_to_verified": source_out.read_bytes() == source_in.read_bytes(),
    "layout_changes": ["numeric segment labels", "grayscale hatch patterns", "larger typography"],
    "scientific_values_changed": False,
}
write(out / f"{stem}_metadata.json", json.dumps(meta, indent=2))

assert all(
    json.loads((out / f"Figure{i}_v4_{name}_metadata.json").read_text(encoding="utf-8"))[
        "source_byte_identical_to_verified"
    ]
    for i, name in (
        (1, "Evidence_Lineage"),
        (2, "L1_All_Contrasts"),
        (3, "L4_All_Contrasts"),
        (4, "Direction_Aware_Evidence"),
    )
)
print("MAIN_FIGURES=4")
print("SOURCE_BYTE_IDENTICAL=4/4")
print("SCIENTIFIC_VALUES_CHANGED=no")
