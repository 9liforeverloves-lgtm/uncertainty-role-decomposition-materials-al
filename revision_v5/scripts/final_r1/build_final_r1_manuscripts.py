from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OLD_MAN = ROOT / "manuscript_v5/submission_candidate_v4_final"
MAN = ROOT / "manuscript_v5/submission_candidate_v4_final_r1"
OLD_FIG = ROOT / "figures_v5/submission_candidate_v4_final"
FIG = ROOT / "figures_v5/submission_candidate_v4_final_r1"
TABLE = ROOT / "tables_v5/submission_candidate_v4_final_r1"
AUDIT = ROOT / "reviewer_revision_v4/final_r1"
for directory in (MAN, FIG, TABLE, AUDIT):
    directory.mkdir(parents=True, exist_ok=True)

LOCK = "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d"
RESULT_LOCK = "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def esc(value) -> str:
    text = str(value)
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("_", r"\_"),
        ("%", r"\%"),
        ("&", r"\&"),
        ("#", r"\#"),
    ):
        text = text.replace(old, new)
    return text


def env_short(task, split, surrogate):
    task_label = {
        "matbench_expt_gap": "Expt",
        "matbench_mp_gap": "MP",
        "matbench_log_gvrh": "logG",
        "matbench_log_kvrh": "logK",
    }[task]
    return f"{task_label}/{'OOD' if split == 'chemical_system_ood' else 'IID'}/{'ET' if surrogate == 'extra_randomized_bagging' else 'RF'}"


def reference_policy(tex: str) -> str:
    tex = tex.replace(
        r"\usepackage{graphicx,booktabs,longtable,array,amsmath,amssymb,natbib,hyperref,microtype}",
        "\\usepackage{graphicx,booktabs,longtable,array,amsmath,amssymb,natbib,microtype}\n"
        "\\usepackage[hidelinks]{hyperref}",
    )
    return tex


# ---------------------------------------------------------------------------
# Figures: copy all bundles, then redraw F2/F3 and all-seed S6.
# ---------------------------------------------------------------------------
for path in OLD_FIG.iterdir():
    if path.is_file():
        shutil.copy2(path, FIG / path.name)

for number, endpoint, title in (
    (2, "L1", "L1 Campaign MACE"),
    (3, "L4", "L4 top-1% recall nAUC"),
):
    stem = f"Figure{number}_{endpoint}_All_Contrasts"
    data = pd.read_csv(OLD_FIG / f"{stem}_source.csv")
    source = FIG / f"{stem}_source.csv"
    data.to_csv(source, index=False)
    contrasts = list(dict.fromkeys(data.contrast_name))
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.3), sharey=True)
    for panel, (ax, contrast) in enumerate(zip(axes.flat, contrasts)):
        subset = data[data.contrast_name == contrast].sort_values(
            "environment_order", ascending=False
        )
        y = np.arange(len(subset))
        ax.hlines(y, subset.ci_lower, subset.ci_upper, color="#303b45", lw=1.8)
        for position, row in zip(y, subset.itertuples(index=False)):
            if row.marker_status == "filled_BH_significant":
                marker, face, size = "o", "#315f8c", 48
            elif row.marker_status == "open_nominal_only":
                marker, face, size = "^", "white", 58
            else:
                marker, face, size = "o", "white", 48
            ax.scatter(
                row.mean_diff, position, s=size, marker=marker,
                facecolor=face, edgecolor="#315f8c", linewidth=1.3, zorder=3,
            )
        ax.axvline(0, color="#20252b", lw=1)
        ax.set_title(contrast, fontsize=11, weight="bold")
        ax.tick_params(axis="x", labelsize=9)
        if panel % 2 == 0:
            ax.set_yticks(y, subset.display_label, fontsize=8.5)
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.grid(axis="x", color="#d9dee3", lw=.65)
        ax.set_xlabel("Test minus baseline", fontsize=9.5)
    fig.suptitle(
        f"Figure {number} | {title} across all frozen environments",
        fontsize=14, weight="bold",
    )
    fig.subplots_adjust(left=.22, right=.98, bottom=.08, top=.92, wspace=.12, hspace=.25)
    fig.savefig(FIG / f"{stem}.pdf")
    fig.savefig(FIG / f"{stem}.png", dpi=200)
    plt.close(fig)
    (FIG / f"{stem}_caption.txt").write_text(
        f"Figure {number}. {title} paired-seed effects and 95% intervals. "
        "Filled circles denote within-environment BH significance; open circles "
        "denote non-BH-significance; open triangles denote nominal-only evidence. "
        "Panel-specific x-scales are retained. Environment order is identical "
        "across panels; right-column duplicate labels are suppressed.\n",
        encoding="utf-8",
    )
    metadata = {
        "schema_version": "submission-candidate-v4-final-r1-figure-v1",
        "figure": stem,
        "source_csv": f"revision_v5/figures_v5/submission_candidate_v4_final_r1/{stem}_source.csv",
        "source_sha256": sha(source),
        "chart_type": "faceted dot-and-interval forest",
        "PDF_page_width_points": 900,
        "figure_width_inches": 12.5,
        "minimum_text_size_pt": 8.5,
        "raster_inspection_DPI": 200,
        "left_column_labels_only": True,
        "panel_specific_x_scales_disclosed": True,
        "evidence_encoding": "filled circle=BH; open circle=not BH; open triangle=nominal only",
        "result_lock_sha256": RESULT_LOCK,
        "final_table_lock_sha256": LOCK,
        "frozen_plotted_values_changed": False,
    }
    (FIG / f"{stem}_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

ood = pd.read_csv(TABLE / "ood_distance_reference_all_seeds.csv")
source_s6 = FIG / "FigureS6_OOD_Reference_All_Seeds_source.csv"
ood.to_csv(source_s6, index=False)
tasks = ["matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh"]
task_labels = ["Expt gap", "MP gap", "log GVRH", "log KVRH"]
roles = ["within_source_leave_one_out", "iid_heldout", "ood_selectable", "ood_diagnostic"]
colors = ["#d9e3ed", "#7c9ab8", "#d6b36b", "#c28a28"]
hatches = ["", "//", "..", "xx"]
fig, ax = plt.subplots(figsize=(11, 6.2))
x = np.arange(4)
width = .19
for j, role in enumerate(roles):
    frame = ood[ood.role_or_reference == role].set_index("task").loc[tasks]
    center = frame.median_over_seeds.to_numpy(float)
    low = center - frame.minimum_over_seeds.to_numpy(float)
    high = frame.maximum_over_seeds.to_numpy(float) - center
    ax.bar(
        x + (j - 1.5) * width, center, width,
        yerr=np.vstack([low, high]), capsize=2.5,
        label=role.replace("_", " "), color=colors[j],
        edgecolor="#26313b", hatch=hatches[j],
    )
ax.set_xticks(x, task_labels)
ax.set_ylabel("Median source-standardized Euclidean distance")
ax.set_title("Supplementary Figure S6 | Forty-seed OOD reference-distance distributions")
ax.legend(fontsize=8, ncol=2)
ax.grid(axis="y", color="#d9dee3", lw=.6)
fig.tight_layout()
fig.savefig(FIG / "FigureS6_OOD_Reference_All_Seeds.pdf")
fig.savefig(FIG / "FigureS6_OOD_Reference_All_Seeds.png", dpi=200)
plt.close(fig)
(FIG / "FigureS6_OOD_Reference_All_Seeds_caption.txt").write_text(
    "Supplementary Figure S6. Median descriptor distances across 40 frozen "
    "confirmation seeds; error bars span the seedwise minimum to maximum. "
    "Chemical-system role assignments varied across seeds, so seed 5000 is not "
    "used as a cohort-level summary. Distances are descriptive and representation dependent.\n",
    encoding="utf-8",
)
(FIG / "FigureS6_OOD_Reference_All_Seeds_metadata.json").write_text(
    json.dumps(
        {
            "schema_version": "submission-candidate-v4-final-r1-figure-v1",
            "figure": "FigureS6_OOD_Reference_All_Seeds",
            "source_csv": "revision_v5/figures_v5/submission_candidate_v4_final_r1/FigureS6_OOD_Reference_All_Seeds_source.csv",
            "source_sha256": sha(source_s6),
            "seed_count": 40,
            "assignment_invariance": False,
            "aggregation": "median over seeds with seedwise min-max bars",
            "minimum_text_size_pt": 8,
            "raster_inspection_DPI": 200,
            "final_table_lock_sha256": LOCK,
        },
        indent=2,
    ),
    encoding="utf-8",
)


# ---------------------------------------------------------------------------
# Main manuscript transformations.
# ---------------------------------------------------------------------------
old_main = (OLD_MAN / "manuscript_submission_candidate_v4_final.tex").read_text(
    encoding="utf-8"
)
main = reference_policy(old_main)
main = main.replace(
    "\\newcommand{\\posthoc}{\\textbf{Post hoc sensitivity.}}\n"
    "\\newcommand{\\exploratory}{\\textbf{Exploratory mechanism analysis.}}\n"
    "\\newcommand{\\descriptive}{\\textbf{Descriptive analysis.}}",
    "\\newcommand{\\evidencelabel}[1]{\\textbf{#1}\\enspace}",
)
main = main.replace("\\posthoc ", "\\evidencelabel{Post hoc sensitivity.}")
main = main.replace("\\exploratory ", "\\evidencelabel{Exploratory mechanism analysis.}")
main = main.replace("\\descriptive ", "\\evidencelabel{Descriptive analysis.}")
main = main.replace("submission_candidate_v4_final", "submission_candidate_v4_final_r1")
main = main.replace(
    "references_submission_candidate_v4_final_r1",
    "references_submission_candidate_v4_final_r1",
)

abstract = r"""\begin{abstract}
We evaluated calibration-oriented uncertainty scaling for offline UCB screening
on four Matbench regression tasks, two split types, and two related tree
ensembles. V5-RC1 remained the sole confirmatory cohort: 3,360 locked jobs and
40 paired seeds per environment. Primary endpoints and every frozen primary
effect, interval, raw p-value, BH-adjusted p-value, and evidence label were
unchanged. Original GG was L1-harmful in 16/16 environments; Historical CS was
L4-harmful in 16/16. Practical consequences were corrected to 64 unique
strategy-environment comparisons and are reported as paired-seed mean
differences in top-1\% candidates discovered by 20\% queried budget with
paired-bootstrap intervals. Stored diagnostic summaries showed that post hoc
NLL sensitivity was numerically unstable and unavailable for scientific
interpretation. Chemical-system role assignments varied across confirmation
seeds, so descriptor-distance severity was aggregated over all 40 seeds.
Recovery exclusion remained paired across all strategies in the affected
environment. Conclusions remain bounded to this four-task evaluation.
\end{abstract}"""
main = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", lambda _: abstract, main, flags=re.S)

endpoint_text = r"""\subsection{Endpoint sensitivity}
\evidencelabel{Post hoc sensitivity.}Fixed numeric rules replaced opaque
qualitative summaries. Across sensitivity definitions, labels were determined
from direction agreement, BH-status changes, CI-zero-status changes, and
effect-change magnitudes. NLL was excluded from these interpretive labels:
the executed Gaussian formula was correct, but stored round-level NLL means
showed extreme seed dominance and pathological mean--median divergence in
41/64 environment-level contrasts. NLL is retained only in the numerical
stability appendix and is classified unavailable for scientific interpretation.
The frozen primary endpoints and BH families were unchanged.

\subsection{Practical consequences}"""
main = re.sub(
    r"\\subsection\{Endpoint sensitivity\}.*?\\subsection\{Practical consequences\}",
    lambda _: endpoint_text,
    main,
    flags=re.S,
)
main = main.replace(
    r"\section*{Administrative placeholders}",
    r"""\section*{Reproducibility status}
An internally verified reproducibility package was generated. External/public
reproducibility is not claimed while the repository DOI/URL, code license,
data license, public environment lock, and public run instructions remain
pending.

\section*{Administrative placeholders}""",
)
practical = pd.read_csv(TABLE / "practical_significance_with_uncertainty.csv")
practical_text = rf"""\subsection{{Practical consequences}}
\evidencelabel{{Descriptive analysis.}}Across all 64 unique
strategy-environment comparisons, the paired-seed mean difference in the
number of top-1\% candidates discovered by 20\% queried budget ranged from
{practical.paired_mean_difference.min():.2f} to
{practical.paired_mean_difference.max():.2f}. These are means of paired integer
seed outcomes, not fractional observed materials. Each comparison includes a
95\% paired-bootstrap interval. Representative cases were preselected by the
frozen neutral rules and are reported separately. One BH-favorable primary L4
case had a negative fixed-20\% discovery-count difference; the sign discordance
is stated explicitly in the Supplement.

\subsection{{Chemical-system-group OOD severity}}"""
main = re.sub(
    r"\\subsection\{Practical consequences\}.*?\\subsection\{Chemical-system-group OOD severity\}",
    lambda _: practical_text,
    main,
    flags=re.S,
)
ood = pd.read_csv(TABLE / "ood_distance_reference_all_seeds.csv")
ood_sel = ood[ood.role_or_reference == "ood_selectable"]
ood_text = rf"""\subsection{{Chemical-system-group OOD severity}}
\evidencelabel{{Descriptive analysis.}}Canonical candidate-ID and
chemical-system role hashes showed that assignments varied across seeds
5000--5039; only 4/160 task-seed rows, the seed-5000 references themselves,
matched seed 5000. Severity was therefore recomputed and summarized over all
40 seeds. Task-level median OOD-selectable to within-source distance ratios
ranged from {ood_sel.median_within_source_ratio.min():.2f} to
{ood_sel.median_within_source_ratio.max():.2f}. Chemical-system disjointness is
a grouping constraint, whereas these Euclidean ratios depend on the
composition representation and source-only scaling. They are not a universal
measure of real-world extrapolation difficulty.

\subsection{{Recovery and reproducibility}}"""
main = re.sub(
    r"\\subsection\{Chemical-system-group OOD severity\}.*?\\subsection\{Recovery and reproducibility\}",
    lambda _: ood_text,
    main,
    flags=re.S,
)

discussion = r"""\section{Discussion}
Original GG consistently harmed L1 in the tested environments. GG applies one
fitted global factor to every candidate uncertainty in a state, so all interval
widths expand or contract together. The stored mechanism analysis showed
state-dependent scale inflation and a corresponding effective-beta shift.
That pattern is compatible with task- and environment-specific mismatch
between a single global scale and heterogeneous residual behavior. Even when a
factor improves calibration at one state, campaign-average calibration need
not improve: the labeled set, residual distribution, and fitted ensemble
change after every acquired batch. This interpretation is associative rather
than causal because the study did not randomize scale trajectories separately
from acquisition histories.

Historical CS could improve some L1 summaries while harming L4 because the two
objectives ask different questions. Its local residual adaptation targets
uncertainty calibration through six candidate-specific features, but L4
depends on the ordering of a small top tail. Candidate-specific rescaling can
leave some rankings nearly monotone while changing others nonmonotonically,
especially when local density, residual location, and predictive-mean
percentile interact. Those changes affect which candidates enter a batch and
therefore alter later training sets. Consequently, a local calibration gain at
one round does not guarantee better top-tail discovery after a path-dependent
sequence of retraining rounds. The consistently harmful Historical-CS L4
result remains the strongest stable negative result in this package.

Selected-GG benefits were concentrated in log-KVRH. That task used Raw beta 2
under the frozen selected-policy map, whereas Selected GG used nominal beta
0.5 under fitted global scaling. The development choice between Raw beta 2 and
nearby alternatives was itself criterion dependent. The concentration of
favorable signals in one task therefore limits generalization; it does not
show that the selected scaling is broadly preferable across material
properties.

NLL sensitivity does not support a substantive claim. The executed Gaussian
formula floors standard deviation before the logarithm and standardized
residual, and no deterministic implementation bug was found. However,
individual diagnostic prediction vectors were not retained, while stored
round-level means and paired contrasts show extreme seed dominance and large
mean--median divergence. NLL is therefore classified as numerically unstable
and unavailable for scientific interpretation under the stored uncertainty
scale. No clipping, winsorization, endpoint replacement, or new NLL definition
was introduced.

OOD descriptor-distance ratios were often near one even though chemical
systems were disjoint. This is not contradictory: chemical-system OOD enforces
a group-membership constraint, while Euclidean distance measures separation in
the chosen composition features after source-only scaling. Distinct chemical
systems may remain close in that representation. Strategy heterogeneity can
also arise under modest descriptor-distance shifts because acquisition
depends on predictive means, uncertainties, ranking thresholds, and
retraining history, not distance alone. Since role assignments varied across
the 40 confirmation seeds, the revised analysis uses seed distributions rather
than seed 5000 as cohort evidence.

Selected CS is an intercept-plus-log-uncertainty transform. Simple power or
temperature transforms were not equally confirmed, and no new campaign was
authorized to compare them. The evidence therefore supports the evaluation
framework---prospective locking, paired inference, sensitivity separation, and
decision-layer auditing---more strongly than a claim that Selected CS is a
uniquely novel or necessary algorithm. RF and ExtraTrees remain related tree
ensembles, only UCB acquisition was tested, and four tasks do not define a
population of materials problems.
"""
old_discussion = re.search(r"\\section\{Discussion\}(.*?)\\section\{Conclusion\}", main, re.S)
old_discussion_words = len(re.findall(r"\b[\w-]+\b", old_discussion.group(1))) if old_discussion else 0
main = re.sub(
    r"\\section\{Discussion\}.*?\\section\{Conclusion\}",
    lambda _: discussion + "\n\\section{Conclusion}",
    main,
    flags=re.S,
)
new_discussion_words = len(re.findall(r"\b[\w-]+\b", discussion))
discussion_increase = new_discussion_words - old_discussion_words

main_path = MAN / "manuscript_submission_candidate_v4_final_r1.tex"
main_path.write_text(main, encoding="utf-8")


# ---------------------------------------------------------------------------
# Supplement rewrite: readable tables, NLL and all-seed OOD sections.
# ---------------------------------------------------------------------------
old_supp = (OLD_MAN / "supplement_submission_candidate_v4_final.tex").read_text(
    encoding="utf-8"
)
supp = reference_policy(old_supp)
supp = supp.replace(
    r"\usepackage[hidelinks]{hyperref}",
    "\\usepackage[hidelinks]{hyperref}\n"
    "\\usepackage{pdflscape,tabularx,ragged2e}\n"
    "\\newcolumntype{Y}{>{\\RaggedRight\\arraybackslash}X}\n"
    "\\newcommand{\\evidencelabel}[1]{\\textbf{#1}\\enspace}",
)
supp = supp.replace("submission_candidate_v4_final", "submission_candidate_v4_final_r1")
supp = supp.replace(
    "../../figures_v5/submission_candidate_v4_final_r1/FigureS6_OOD_Reference_Scale.pdf",
    "../../figures_v5/submission_candidate_v4_final_r1/FigureS6_OOD_Reference_All_Seeds.pdf",
)
supp = supp.replace(
    "Seed-5000 reference distances compare within-source leave-one-out, IID held-out, OOD selectable, and OOD diagnostic roles under identical source-only scaling.",
    "Seed-5000-only values are superseded for cohort interpretation because role assignments vary across seeds.",
)

matrix = pd.read_csv(TABLE / "endpoint_sensitivity_conclusion_matrix_r1.csv")
matrix["principal exception"] = (
    matrix["principal exception"].astype(str).str.split("|", regex=False).str[0]
)
matrix.to_csv(TABLE / "endpoint_sensitivity_conclusion_matrix_r1.csv", index=False)
l1 = matrix[matrix.primary_endpoint == "l1_campaign_mace"]
l4 = matrix[matrix.primary_endpoint == "l4_top1pct_recall_nauc"]
contrast_order = ["Original GG vs Raw", "Historical CS vs Raw", "Selected GG vs Raw", "Selected CS vs Raw"]
l1 = l1.set_index("contrast_name").loc[contrast_order].reset_index()
l4 = l4.set_index("contrast_name").loc[contrast_order].reset_index()

def l1_rows():
    lines = []
    for _, row in l1.iterrows():
        lines.append(
            " & ".join(
                esc(str(x).replace("_", " ").replace("/", " / ")) for x in (
                    row["contrast_name"].replace(" vs Raw", ""),
                    row["early MACE"],
                    row["late MACE"],
                    row["CRPS"],
                    row["NLL status"],
                    row["direction agreement"],
                    row["BH changes"],
                    row["CI-zero changes"],
                    row["principal exception"],
                )
            ) + r"\\"
        )
    return "\n".join(lines)


def l4_rows():
    lines = []
    for _, row in l4.iterrows():
        class_change = f"BH {int(row['BH changes'])}; CI {int(row['CI-zero changes'])}"
        values = [
            row["contrast_name"].replace(" vs Raw", ""),
            row["top 0.5%"], row["top 1%"], row["top 2%"], row["top 5%"],
            row["5% budget"], row["10% budget"], row["20% budget"],
            row["direction agreement"], class_change, row["principal exception"],
        ]
        lines.append(
            " & ".join(
                esc(str(x).replace("_", " ").replace("/", " / ")) for x in values
            ) + r"\\"
        )
    return "\n".join(lines)


nll_section = r"""
\section{NLL numerical stability}
\evidencelabel{Post hoc numerical-stability audit.}The executed formula was
$0.5\log(2\pi\sigma^2)+0.5[(y-\mu)/\sigma]^2$ with
$\sigma=\max(\sigma_{\rm raw},10^{-8})$ applied before both terms. No
implementation bug was found. Nevertheless, 41/64 paired environment-level
NLL contrasts failed the prespecified stability checks; the largest absolute
mean effect was $3.62\times10^{13}$ and the largest single-seed contribution
was 1.000. Individual diagnostic mean and sigma vectors were not retained, so
sigma quantiles and maximum individual standardized residual are unavailable
rather than reconstructed. NLL is classified
\texttt{numerically\_unstable\_not\_interpretable}, excluded from scientific
direction/classification summaries, and retained only in
\texttt{nll\_numerical\_stability\_seed\_level.csv} and
\texttt{nll\_contrast\_stability\_audit.csv}.

\section{Endpoint-sensitivity classification rules}
Labels follow the fixed rules in
\texttt{reviewer\_revision\_v4/final\_r1/02\_endpoint\_sensitivity\_label\_rules.json}.
Direction agreement, BH changes, CI-zero changes, and effect-change magnitudes
are reported numerically. NLL is unavailable by the preceding audit.

\begin{landscape}
\section{Table Sx-A: L1 calibration sensitivity}
{\fontsize{8}{9.6}\selectfont
\begin{tabularx}{\linewidth}{lYYYYYYYY}
\toprule
Strategy & Early MACE & Late MACE & CRPS & NLL status & Direction agreement & BH changes & CI-zero changes & Exception\\
\midrule
""" + l1_rows() + r"""
\bottomrule
\end{tabularx}}

\section{Table Sx-B: L4 discovery sensitivity}
{\fontsize{8}{9.6}\selectfont
\begin{tabularx}{\linewidth}{lYYYYYYYYYY}
\toprule
Strategy & Top 0.5\% & Top 1\% & Top 2\% & Top 5\% & 5\% budget & 10\% budget & 20\% budget & Direction agreement & Class changes & Exception\\
\midrule
""" + l4_rows() + r"""
\bottomrule
\end{tabularx}}
\end{landscape}

Detailed environment lists are in
\texttt{endpoint\_sensitivity\_label\_environment\_detail.csv}; the full
numeric summary is in
\texttt{endpoint\_sensitivity\_label\_numeric\_summary.csv}.
"""
supp = re.sub(
    r"\\section\{Endpoint sensitivity matrix\}.*?\\section\{Practical significance\}",
    lambda _: nll_section + "\n\\section{Practical significance}",
    supp,
    flags=re.S,
)

representative = pd.read_csv(TABLE / "practical_significance_representative_cases_r1.csv")
representative = representative.drop_duplicates("representative_class").head(4)
rep_lines = []
for row in representative.itertuples(index=False):
    environment = env_short(row.task, row.split, row.surrogate)
    comparison = str(row.contrast_identity).replace(" vs Raw", "")
    ci = f"[{row.paired_bootstrap_CI95_low:.2f}, {row.paired_bootstrap_CI95_high:.2f}]"
    note = "sign differs from primary L4 class" if isinstance(row.sign_discordance_note, str) and row.sign_discordance_note else "--"
    values = [
        row.representative_class.replace("_", " "),
        comparison,
        environment,
        row.primary_L4_class,
        int(row.selectable_pool_size),
        int(row.top_set_size),
        f"{row.baseline_discovered_top1_count_20pct_mean:.2f}",
        f"{row.test_discovered_top1_count_20pct_mean:.2f}",
        f"{row.paired_mean_difference:.2f}",
        ci,
        note,
    ]
    rep_lines.append(" & ".join(esc(x) for x in values) + r"\\")
practical_section = r"""\section{Practical significance}
\evidencelabel{Descriptive analysis.}The unit is a paired seed within a fixed
environment. Across the 64 unique strategy-environment comparisons, endpoint
duplicates were removed after exact equality checks. Values are paired-seed
mean differences in the number of top-1\% candidates discovered by 20\%
queried budget and include 95\% paired-bootstrap intervals. Fractional values
are means of paired integer outcomes, not observed fractional materials.

\begin{landscape}
\section*{Representative practical cases}
{\fontsize{8}{9.6}\selectfont
\begin{tabularx}{\linewidth}{YYYYYYYYYYY}
\toprule
Selection rule & Comparison & Environment & Primary L4 class & Pool & Top set & Baseline mean & Test mean & Paired mean diff. & 95\% CI & Discordance\\
\midrule
""" + "\n".join(rep_lines) + r"""
\bottomrule
\end{tabularx}}
\end{landscape}

The case flagged for discordance was selected because its primary L4 nAUC
classification was BH-favorable; its fixed-20\% budget consequence differed
in sign. The complete 64-row table and secondary fields are provided in
\texttt{practical\_significance\_with\_uncertainty.csv}; they are not compressed
into the PDF table.

\section{Complete locked V5 primary table}"""
supp = re.sub(
    r"\\section\{Practical significance\}.*?\\section\{Complete locked V5 primary table\}",
    lambda _: practical_section,
    supp,
    flags=re.S,
)

ood_insert = r"""
\section{OOD assignment variation across confirmation seeds}
\evidencelabel{Descriptive analysis.}Canonical hashes were generated for
source IDs, selectable IDs, diagnostic IDs, and the complete
chemical-system-to-role mapping for every task and seed 5000--5039. Assignments
were not invariant: only each task's seed-5000 row matched its seed-5000
reference (4/160 rows). Consequently, cohort-level severity uses the exact
40-seed distributions in
\texttt{ood\_distance\_reference\_all\_seeds.csv}, supported by the 640-row
per-seed table. Across tasks, median OOD-selectable/within-source ratios ranged
from 0.98 to 1.29. Chemical-system disjointness and representation-space
distance are distinct concepts.
"""
supp = supp.replace(
    "\\section{Stratified GG effective-beta analysis}",
    ood_insert + "\n\\section{Stratified GG effective-beta analysis}",
)
supp = supp.replace(
    r"\section{Reproducibility and validation}",
    r"""\section{Reproducibility and validation}
An internally verified reproducibility package was generated. External/public
reproducibility is not claimed while the repository DOI/URL, licenses,
environment lock, public run instructions, and accessible Matbench version
information remain pending.""",
)

supp_path = MAN / "supplement_submission_candidate_v4_final_r1.tex"
supp_path.write_text(supp, encoding="utf-8")

shutil.copy2(
    OLD_MAN / "references_submission_candidate_v4_final.bib",
    MAN / "references_submission_candidate_v4_final_r1.bib",
)

(MAN / "REQUIRED_PUBLIC_REPRODUCIBILITY_INPUTS.md").write_text(
    """# Required public reproducibility inputs

An internally verified reproducibility package was generated. External/public
reproducibility is not claimed until all fields below are supplied.

- Repository DOI/URL: pending
- Code license: pending
- Data license: pending
- Python environment lock: internally available; public artifact pending
- Installation command: pending public repository layout
- One-command table regeneration: pending public run instructions
- One-command figure regeneration: pending public run instructions
- One-command manuscript compilation: pending public run instructions
- Data-download instructions: pending licensed public location
- Expected output hashes: generated internally in export `SHA256SUMS.txt`
- Accessible Matbench version information: pending public documentation
""",
    encoding="utf-8",
)

(AUDIT / "discussion_word_count.json").write_text(
    json.dumps(
        {
            "old_discussion_words": old_discussion_words,
            "new_discussion_words": new_discussion_words,
            "increase_words": discussion_increase,
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(
    json.dumps(
        {
            "main_tex": str(main_path),
            "supp_tex": str(supp_path),
            "discussion_increase": discussion_increase,
            "figure2_source_hash": sha(FIG / "Figure2_L1_All_Contrasts_source.csv"),
            "figure3_source_hash": sha(FIG / "Figure3_L4_All_Contrasts_source.csv"),
            "primary_hash": sha(ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv"),
            "final_lock_hash": sha(ROOT / "tables_v5/FINAL_TABLE_LOCK_V5.json"),
        },
        indent=2,
    )
)
