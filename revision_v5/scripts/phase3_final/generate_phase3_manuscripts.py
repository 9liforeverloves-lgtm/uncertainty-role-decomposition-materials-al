from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\贝叶斯优化\revision_v5")
WORKSPACE = ROOT.parent
PHASE = ROOT / "reviewer_revision_v4/phase3"
TABLES = ROOT / "tables_v5/submission_candidate_v4/phase3"
FIGS = ROOT / "figures_v5/submission_candidate_v4/phase3"
MANU = ROOT / "manuscript_v5/submission_candidate_v4"
ARCHIVE = ROOT / "archive/superseded_phase3_artifacts"
MANU.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)

LOCK = "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d"
RESULT_LOCK = "cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441"
TRAJECTORY_LOCK = "03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8"
POLICY_LOCK = "f8aefe24eede104976332521dada51bd0486d0192e13fe85f8b4d6c95390db90"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def tex(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\allowbreak\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "|": r"\textbar{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def fmt(value: object, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "NA"
    if isinstance(value, (float, np.floating)):
        if value != 0 and abs(value) < 1e-3:
            return f"{value:.2e}"
        return f"{value:.{digits}f}"
    return str(value)


primary = pd.read_csv(ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv")
recovery = pd.read_csv(ROOT / "audits_v5/reviewer_revision_v4/recovery_identity_reconciliation_VERIFIED.csv")
counts = pd.read_csv(ROOT / "tables_v5/submission_candidate_v4/final_evidence_count_audit_VERIFIED.csv")
gg = pd.read_csv(TABLES / "gg_effective_beta_by_state.csv")
stability = pd.read_csv(TABLES / "development_selection_stability.csv")
endpoint = pd.read_csv(TABLES / "endpoint_sensitivity_contrasts.csv")
practical = pd.read_csv(TABLES / "practical_significance_by_environment.csv")
ood = pd.read_csv(TABLES / "ood_severity_summary.csv")
cross = pd.read_csv(TABLES / "cross_environment_summary_sensitivity.csv")

gg_median = float(gg.effective_beta.median())
gg_iqr = tuple(map(float, gg.effective_beta.quantile([.25, .75])))
gg_fallback = float(gg.fallback_used.mean())
logk_boot = stability[
    (stability.held_out_task == "matbench_log_kvrh")
    & (stability.strategy_family == "raw")
    & (stability.sensitivity_method == "seed_bootstrap")
].iloc[0]
endpoint_counts = endpoint.sensitivity_conclusion.value_counts()
practical_min = float(practical.additional_or_lost_top_candidates_20pct.min())
practical_max = float(practical.additional_or_lost_top_candidates_20pct.max())
ood_min = float(ood.source_nn_target_median.min())
ood_max = float(ood.source_nn_target_median.max())


# ---------------------------------------------------------------------------
# Bibliography: retain only references explicitly used by supporting sentences.
# ---------------------------------------------------------------------------
source_bib = ROOT / "manuscript_v5/submission_candidate_v3/references_submission_candidate_v3.bib"
bib_text = source_bib.read_text(encoding="utf-8")
entries = {}
matches = list(re.finditer(r"(?m)^@\w+\{([^,]+),", bib_text))
for index, match in enumerate(matches):
    end = matches[index + 1].start() if index + 1 < len(matches) else len(bib_text)
    entries[match.group(1)] = bib_text[match.start():end].strip()
retain = [
    "dunn2020matbench", "ward2018matminer", "butler2018mlmaterials",
    "lookman2019active", "xue2016adaptive", "kusne2020closedloop",
    "rohr2020metrics", "hase2021olympus", "shahriari2016bo",
    "frazier2018tutorial", "srinivas2010gpucb", "auer2002ucb",
    "breiman2001rf", "meinshausen2006qrf", "wager2014confidence",
    "mentch2016uncertainty", "gneiting2007proper", "kuleshov2018calibrated",
    "guo2017calibration", "lakshminarayanan2017ensembles",
    "angelopoulos2023conformal", "mandi2022decision", "wilder2019decision",
    "donti2017task", "fanelli2012negative", "liang2021benchmark",
]
missing = [key for key in retain if key not in entries]
if missing:
    raise RuntimeError(f"missing bibliography entries: {missing}")
bib_path = MANU / "references_submission_candidate_v4.bib"
write(bib_path, "\n\n".join(entries[key] for key in retain))


main_preamble = r"""
\documentclass[10pt]{article}
\usepackage[margin=0.82in]{geometry}
\usepackage{graphicx,booktabs,array,longtable,tabularx,amsmath,amssymb}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}
\usepackage{caption}
\usepackage{microtype}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\sloppy
\newcommand{\posthoc}{\textbf{Post hoc sensitivity.}}
\newcommand{\exploratory}{\textbf{Exploratory analysis.}}
\newcommand{\descriptive}{\textbf{Descriptive analysis.}}
"""

main = main_preamble + rf"""
\title{{Calibration-Oriented Uncertainty Scaling in Tree-Ensemble UCB Materials Screening:
A Four-Task Cross-Environment Evaluation}}
\author{{Author names and affiliations pending}}
\date{{}}
\begin{{document}}
\maketitle

\begin{{abstract}}
We evaluated calibration-oriented uncertainty scaling in finite-budget screening
on four Matbench regression tasks, using composition-derived descriptors,
IID-record and chemical-system-group out-of-distribution (OOD) splits, Random
Forest (RF) and Extremely Randomized Trees (ExtraTrees), and upper-confidence-bound
(UCB) acquisition. The locked V5-RC1 confirmation comprised 3,360 jobs and 40
paired seeds per environment. Primary endpoints were L1 Campaign mean absolute
coverage error (MACE) and L4 top-1\% recall normalized area under the curve
(nAUC). Original Gaussian-global (GG) scaling was harmful for L1 in 16/16
environments, while Historical candidate-specific (CS) scaling was harmful for
L4 in 16/16. Development-selected GG and CS policies were heterogeneous across
tasks and environments. Excluding six controlled-restart jobs reduced the
affected comparisons from 40 to 34 paired seeds without changing direction,
BH classification, or confidence-interval zero-crossing in any of eight
affected tests; the largest absolute effect change was 0.001825. \posthoc\
At 20\% budget, representative environment-level changes ranged from
{practical_min:.2f} to {practical_max:.2f} top-1\% candidates, conditional on
task-specific pool size. Results are bounded to this four-task, two-split,
two-related-tree-ensemble offline UCB benchmark.
\end{{abstract}}

\section{{Introduction}}
Finite-budget materials screening asks which candidates to evaluate when labels
are expensive. Materials active learning and adaptive design use predictive
uncertainty to allocate this budget \citep{{lookman2019active,xue2016adaptive,kusne2020closedloop}}.
Sequential-learning benchmarks emphasize discovery acceleration rather than
predictive error alone \citep{{rohr2020metrics,hase2021olympus}}. Bayesian
optimization and UCB methods formalize the mean--uncertainty trade-off
\citep{{shahriari2016bo,frazier2018tutorial,srinivas2010gpucb,auer2002ucb}}.

Calibration, uncertainty ranking, and sequential utility are distinct.
Proper-scoring and calibration work evaluates probabilistic predictions
\citep{{gneiting2007proper,kuleshov2018calibrated,guo2017calibration,angelopoulos2023conformal}},
whereas decision-focused learning evaluates consequences of actions
\citep{{mandi2022decision,wilder2019decision,donti2017task}}. Scaling uncertainty
inside UCB also changes the effective exploration weight, so improved marginal
calibration need not improve acquisition.

Historical evaluations motivated a locked confirmation rather than serving as
confirmation themselves. The present contribution is a layered
calibration-to-policy evaluation and reproducible negative-result benchmark,
not a claim of a universally new algorithm. Explicit reporting of heterogeneous
and negative results is important for reliable cumulative science
\citep{{fanelli2012negative,liang2021benchmark}}.

\section{{Methods}}
\subsection{{Study phases and evidence classes}}
Figure~\ref{{fig:lineage}} separates historical V2 exploratory evidence,
historical V3 calibration-evaluation evidence, development-only selection, and
the sole confirmatory cohort, V5-RC1. Development seeds were 1000--1009;
confirmation seeds were 5000--5039. No historical or development seed was
treated as a confirmatory replicate.

\begin{{figure}}[t]
\centering
\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/Figure1_v4_Evidence_Lineage.pdf}}
\caption{{Verified evidence lineage. Internal version identifiers are secondary
to reader-facing evidence classes.}}
\label{{fig:lineage}}
\end{{figure}}

\subsection{{Tasks and composition-derived descriptors}}
The four regression tasks were Matbench experimental band gap, Materials Project
band gap, log shear modulus, and log bulk modulus. Matbench supplies fixed
benchmark tasks \citep{{dunn2020matbench}}; composition-derived feature tooling
follows the materials-informatics ecosystem \citep{{ward2018matminer,butler2018mlmaterials}}.

\subsection{{IID and chemical-system-group OOD}}
IID-record splits assign records independently. Chemical-system-group OOD splits
assign entire element-set groups to source, selectable, or diagnostic roles with
zero group overlap. This is role disjointness by chemistry, not a general test of
temporal, laboratory, processing-condition, structure-prototype, or
label-mechanism shift.

\subsection{{RF and ExtraTrees surrogates}}
RF and ExtraTrees are related tree-ensemble surrogates, not broadly independent
model families. Tree ensembles have established predictive and uncertainty
estimators \citep{{breiman2001rf,meinshausen2006qrf,wager2014confidence,mentch2016uncertainty,lakshminarayanan2017ensembles}}.

\subsection{{UCB policies and effective beta}}
Raw UCB uses
\[
a_{{\mathrm{{raw}}}}(x,t)=\mu_t(x)+\beta\sigma_t(x).
\]
GG uses $a_{{\mathrm{{GG}}}}(x,t)=\mu_t(x)+\beta c_t\sigma_t(x)$, so
$\beta_{{\mathrm{{eff}},t}}=\beta c_t$. Original GG used nominal $\beta=1$;
the development-selected GG policy used nominal $\beta=0.5$.

\subsection{{Historical and selected candidate-specific scaling}}
Historical CS used six local features and OOB residual information. Selected CS
retained only log raw uncertainty plus an intercept, with the frozen pairwise
ranking objective. This one-feature form limits novelty: the study does not show
that it is uniquely necessary or minimal relative to all simple monotone scalings.

\subsection{{Development selection}}
Leave-one-task-out development selection ranked candidates by mean nAUC, with a
0.005 near-tie band resolved by worst-environment score, then complexity and
lexical order. The task-specific selected Raw map was beta 1 for experimental
gap, MP gap, and log GVRH, and beta 2 for log KVRH. The map remained frozen.

\subsection{{Confirmation design}}
V5-RC1 contained 3,360 locked jobs across four tasks, two splits, two surrogates,
and task-dependent policy cells. Forty paired seeds were the inference unit in
each environment. Campaign geometry, stable-ID tie handling, endpoints,
contrasts, and stopping rules were locked before outcome inspection.

\subsection{{L1 and L4 endpoints}}
L1 Campaign MACE averaged absolute coverage error across the four locked coverage
levels and campaign checkpoints; lower is better. L4 was selectable-pool top-1\%
recall nAUC including the initial state and normalized by the observed budget;
higher is better.

\subsection{{Statistical inference}}
Paired seed was the inference unit. Each contrast used 10,000 paired bootstrap
replicates for the percentile interval and 10,000 paired sign-flip replicates
with an add-one p-value. Benjamini--Hochberg adjustment was applied within each
environment over eight prespecified endpoint-by-contrast tests.

The paired-seed intervals quantify repeated-algorithm uncertainty conditional
on the fixed task, dataset, split construction, surrogate, campaign geometry,
and policy identity. They do not quantify uncertainty over a population of
materials problems. Environment counts are descriptive only.

\subsection{{Post hoc sensitivity analyses}}
\posthoc\ Stored trajectories supported top-0.5\%, 1\%, 2\%, and 5\% recall
nAUC; 5\%, 10\%, and 20\% budget windows; checkpoint-specific MACE; CRPS; NLL;
development resampling; recovery exclusion; and effective-beta diagnostics.
These analyses did not change the primary family.

\subsection{{Practical-significance metrics}}
\descriptive\ Absolute nAUC, fixed-budget recall, top-candidate yield, queries to
fixed recall, discoveries per 1,000 selectable candidates, runtime, and relative
effects were derived from stored trajectories. Unreached targets were recorded
as ``not reached within the observed budget.''

\subsection{{OOD-severity metrics}}
\descriptive\ Severity metrics included composition-descriptor nearest-neighbor
distance, marginal descriptor and element-frequency shifts, group and record
counts, target-distribution differences, and Raw-policy diagnostic shifts.
Targets were used only after split construction.

\subsection{{Recovery and reproducibility}}
Six MP-gap chemical-system-group OOD ExtraTrees Historical-CS jobs, seeds
5013--5018, preserve the event text ``controlled resource restart from 6 to 4
workers.'' Original process exit codes were not recorded; final codes were zero.
All six final trajectory hashes matched the frozen content inventory.

\section{{Results}}
\subsection{{Historical evaluations and motivation}}
V2 and V3 remained historical and non-confirmatory. They motivated the locked
candidate set and evidence-layer separation; they were never pooled with V5.

\subsection{{Development selection and stability}}
The frozen map was retained. \posthoc\ In 500 seed bootstraps, held-out log-KVRH
Raw beta 2 was retained with frequency {float(logk_boot.selected_frequency):.3f};
criterion sensitivity confirmed that its beta-2 versus beta-1 choice depended on
the predeclared near-tie resolution. Other selections were generally more stable.

\subsection{{Original GG: calibration harm and effective-beta behavior}}
Original GG was BH-classified as harmful for L1 in 16/16 environments
(Figure~\ref{{fig:l1}}). \exploratory\ Across {len(gg):,} stored GG states,
median effective beta was {gg_median:.3f} (IQR {gg_iqr[0]:.3f}--{gg_iqr[1]:.3f});
fallback frequency was {gg_fallback:.3f}. Stored-subset ranking reconstruction
supports partial dynamic-beta equivalence, not full-pool rank identity.

\begin{{figure}}[t]
\centering
\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/Figure2_v4_L1_All_Contrasts.pdf}}
\caption{{Complete four-panel L1 forest. Filled markers denote within-environment
BH significance; open markers denote non-BH-significant estimates.}}
\label{{fig:l1}}
\end{{figure}}

\subsection{{Historical CS: mixed L1 behavior and consistent L4 harm}}
Historical CS had mixed L1 classifications but was harmful for L4 in 16/16
environments (Figure~\ref{{fig:l4}}), the most consistent stable negative result.
This does not establish a causal mechanism.

\subsection{{Development-selected policies}}
Selected GG was favorable in six L4 environments, harmful in none, and not
BH-significant in ten; the favorable classifications were task concentrated.
Selected CS was heterogeneous: four favorable, nine harmful, and three
non-BH-significant L4 classifications. Non-significance is not described as no
effect.

\begin{{figure}}[t]
\centering
\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/Figure3_v4_L4_All_Contrasts.pdf}}
\caption{{Complete four-panel L4 forest using the task-specific selected Raw
baseline map. Panel scales are contrast specific.}}
\label{{fig:l4}}
\end{{figure}}

\subsection{{Endpoint sensitivity}}
\posthoc\ Directional conclusions were mostly preserved across stored top-tail,
budget-window, MACE-stage, coverage, CRPS, and NLL sensitivities, with
threshold- and budget-dependent exceptions. The primary top-1\% and Campaign
MACE analysis remains unchanged.

\subsection{{Practical significance}}
\descriptive\ At 20\% budget, environment-level changes ranged from
{practical_min:.2f} to {practical_max:.2f} recovered top-1\% candidates.
Statistical labels did not map uniformly to large screening gains or losses.

\subsection{{Chemical-system-group OOD severity}}
\descriptive\ Median source-to-selectable descriptor distance ranged from
{ood_min:.3f} to {ood_max:.3f} across tasks. Element-frequency, target, and
Raw-diagnostic shifts were likewise task specific; chemical disjointness alone
did not quantify a universal shift magnitude.

\subsection{{Recovery and reproducibility}}
Recovery exclusion changed no direction, BH label, or interval zero-crossing
among eight affected tests. Two of eight relative effect changes exceeded 10\%,
but the maximum absolute change was 0.001825. These facts support computational
robustness of the locked conclusions, not a scientific mechanism claim.

\begin{{figure}}[t]
\centering
\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/Figure4_v4_Direction_Aware_Evidence.pdf}}
\caption{{Direction-aware counts. Descriptive counts of environment-specific BH
classifications; not pooled inference.}}
\label{{fig:counts}}
\end{{figure}}

\section{{Discussion}}
GG is partially equivalent to dynamic beta modulation: $c_t$ changes the
effective exploration weight, and nominal beta 0.5 often offsets scale
inflation. However, state variability and incomplete equivalence to tested
static-beta rankings preclude calling GG merely a relabeled fixed beta.

Marginal calibration and sequential utility diverge because calibration scores
all diagnostic predictions, while acquisition depends on candidate ordering and
finite-budget path dependence. Historical CS L4 harm is the strongest stable
negative result. Selected GG positive signals are task concentrated, and
Selected CS remains heterogeneous. The selected-CS one-feature form has not been
shown uniquely necessary or minimal because no equally powered V5 confirmation
of all simple monotone scalings exists.

Development stability was high for most families but criterion dependent for
held-out log-KVRH Raw beta 2 versus beta 1. Statistical and practical magnitude
also diverged. External scope is limited by four tasks, composition-derived
descriptors, chemical-system-group OOD, related tree ensembles, and UCB-only
acquisition. RF and ExtraTrees do not establish model-family breadth. Broader
claims require prospectively frozen external validation on other datasets,
surrogates, acquisition functions, and shift mechanisms.

\section{{Conclusion}}
Within the tested four-task, two-split, two-tree-ensemble offline UCB benchmark,
calibration-oriented uncertainty scaling was not automatically beneficial to
sequential discovery.

\section*{{Administrative declarations}}
Author names/order, affiliations, corresponding email, CRediT, funding,
competing interests, acknowledgements, repository DOI/URL, code license, data
license, target journal, and journal formatting limits remain pending.

\bibliographystyle{{unsrtnat}}
\bibliography{{references_submission_candidate_v4}}
\end{{document}}
"""

main_path = MANU / "manuscript_submission_candidate_v4.tex"
write(main_path, main)


# ---------------------------------------------------------------------------
# Supplement tables.
# ---------------------------------------------------------------------------
def primary_longtable() -> str:
    lines = [
        r"\scriptsize",
        r"\setlength{\tabcolsep}{2.4pt}",
        r"\begin{longtable}{p{2.35cm}p{1.7cm}p{1.15cm}rrrrrrp{1.25cm}}",
        r"\caption{Complete 128-row locked V5 primary inference table. Effects are test minus baseline.}\label{tab:primary}\\",
        r"\toprule Environment & Contrast & Endpoint & $n$ & Effect & CI low & CI high & $p_{\rm raw}$ & $p_{\rm BH}$ & Label\\\midrule",
        r"\endfirsthead",
        r"\toprule Environment & Contrast & Endpoint & $n$ & Effect & CI low & CI high & $p_{\rm raw}$ & $p_{\rm BH}$ & Label\\\midrule",
        r"\endhead",
    ]
    for row in primary.itertuples(index=False):
        env = str(row.environment).replace("matbench_", "").replace("__", " / ")
        contrast = str(row.contrast_name).replace(" vs Raw", "")
        endpoint_label = "L1" if row.endpoint == "l1_campaign_mace" else "L4"
        label = (
            "fav." if row.significant_after_bh and row.effect_direction == "favors_test"
            else "harm." if row.significant_after_bh and row.effect_direction == "favors_baseline"
            else "not BH-sig."
        )
        lines.append(
            f"{tex(env)} & {tex(contrast)} & {endpoint_label} & {int(row.n_pairs)} & "
            f"{fmt(row.mean_diff)} & {fmt(row.ci_lower)} & {fmt(row.ci_upper)} & "
            f"{fmt(row.p_value_unadjusted, 5)} & {fmt(row.p_value_bh_adjusted, 5)} & {label}\\\\"
        )
    lines += [r"\bottomrule", r"\end{longtable}", r"\normalsize"]
    return "\n".join(lines)


def recovery_table() -> str:
    lines = [
        r"\scriptsize\begin{longtable}{p{2.7cm}rrrrp{3.1cm}p{2.4cm}}",
        r"\toprule Job suffix & Manifest line & Seed & Original exit & Final exit & Preserved event & Verification\\\midrule",
    ]
    for row in recovery.itertuples(index=False):
        lines.append(
            f"{tex(str(row.job_id).split('__')[-1])} & {tex(row.manifest_row_id)} & {row.seed} & "
            f"not recorded & {row.final_exit_code} & {tex(row.original_error)} & "
            f"{tex(row.identity_verification_status)}\\\\"
        )
    lines += [r"\bottomrule\end{longtable}\normalsize"]
    return "\n".join(lines)


inventory = pd.read_csv(ROOT / "tables_v5/submission_candidate_v3/development_configuration_inventory_36.csv")
parameter = pd.read_csv(ROOT / "tables_v5/submission_candidate_v3/candidate_specific_parameter_table.csv")
mapping = pd.read_csv(ROOT / "tables_v5/submission_candidate_v3/development_identity_to_confirmation_identity.csv")


def compact_table(frame: pd.DataFrame, columns: list[str], caption: str, label: str, max_rows: int | None = None) -> str:
    use = frame[columns].head(max_rows) if max_rows else frame[columns]
    widths = "|".join(["p{2.5cm}"] * len(columns))
    lines = [r"\scriptsize", rf"\begin{{longtable}}{{{widths}}}", rf"\caption{{{caption}}}\label{{{label}}}\\", r"\toprule"]
    lines.append(" & ".join(tex(column) for column in columns) + r"\\\midrule")
    for row in use.itertuples(index=False, name=None):
        lines.append(" & ".join(tex(fmt(value)) for value in row) + r"\\")
    lines += [r"\bottomrule", r"\end{longtable}", r"\normalsize"]
    return "\n".join(lines)


supp = main_preamble + rf"""
\title{{Supplementary Information: Calibration-Oriented Uncertainty Scaling in
Tree-Ensemble UCB Materials Screening}}
\author{{Author metadata pending}}
\date{{}}
\begin{{document}}
\maketitle
\tableofcontents

\section{{Authoritative study geometry}}
\descriptive\ V5-RC1 is the sole confirmatory cohort: four tasks, two split
protocols, two related tree-ensemble surrogates, 3,360 jobs, and 40 paired seeds
per environment. The result-lock hash is \texttt{{{RESULT_LOCK}}}; the final-table
lock hash is \texttt{{{LOCK}}}.

\section{{V2/V3 evidence-class audit}}
V2 is a historical exploratory cohort and V3 is a historical calibration
evaluation cohort. Neither had prospectively documented V5 endpoints, and
neither is confirmatory. Historical and V5 seeds are never pooled.

\section{{Exact candidate-specific algorithms}}
\subsection{{Historical CS-DA-OOB-HIST}}
At each executed campaign state, the fitted tree ensemble supplies candidate
mean $\mu(x)$ and raw standard deviation $\sigma(x)$. OOB predictions for
queried observations define residual ratios
$r_i=|y_i-\mu_{{-i}}|/\max(\sigma_{{-i}},10^{{-8}})$ for observations with at
least three OOB trees. Six local features are computed: log raw uncertainty,
log leaf density, log descriptor distance, predictive-mean percentile, log
local standardized residual, and log local residual dispersion. A pairwise
ranking objective uses a top-decile pair weight of 2 and ridge penalties. The
candidate scale is $\exp(\mathrm{{clip}}(z^\top\theta,\log 0.25,\log 4))$.
Acquisition is $\mu(x)+s(x)\max(\sigma(x),10^{{-8}})$. If fewer than 30 valid
queried rows exist, the identity Raw-UCB scale is used.

\subsection{{Selected CS-DA-OOB-PARSIMONIOUS-F1}}
The selected form uses only feature 1, log raw uncertainty, plus an intercept.
It requires at least ten OOB trees, uses the same pairwise ranking objective,
and sets the top-tail pair weight to 1. The same scale bounds, uncertainty floor,
stable-ID tie handling, and fallback rule apply. No diagnostic target enters
acquisition.

{compact_table(parameter, list(parameter.columns[:5]), "Frozen candidate-specific parameter table.", "tab:csparams")}

\section{{Development inventory}}
The complete 36-configuration inventory is reproduced below. This is
development-only evidence.

{compact_table(inventory, ["configuration_id", "strategy", "family", "manifest_job_count"], "Complete 36-configuration development inventory.", "tab:devinventory")}

\section{{Development selection stability}}
\posthoc\ Five hundred seed bootstraps, leave-one-development-environment-out,
mean-only, worst-environment, equal-task/equal-environment, and 0.005 tie-band
sensitivities were applied to stored development results. Held-out log-KVRH Raw
beta 2 versus beta 1 was criterion dependent. The frozen policy map was not changed.

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS2_Development_Stability.pdf}}

\section{{Development-to-confirmation identity mapping}}
{compact_table(mapping, list(mapping.columns[:5]), "Development-to-confirmation policy identity mapping.", "tab:mapping")}

\section{{Chemical-system-group OOD construction}}
Element-set groups are formed from each composition. A deterministic seeded
assignment allocates whole groups to source, selectable, and diagnostic roles.
Records cover all roles exactly once; groups have zero cross-role overlap.
Targets are not used for assignment.

\section{{OOD severity}}
\descriptive\ Post-split severity uses descriptor nearest-neighbor distance,
marginal descriptor shift, element-frequency shift, role counts,
target-distribution difference, and stored Raw-policy diagnostic shifts.

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS6_OOD_Severity.pdf}}

\section{{GG effective-beta analysis}}
\exploratory\ GG satisfies $\beta_{{\rm eff,t}}=\beta c_t$. Stored state-scale
and candidate-subset predictions permit a bounded ranking reconstruction.
Full-pool candidate predictions were not retained.

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS1_GG_Effective_Beta.pdf}}

\section{{Endpoint sensitivity}}
\posthoc\ Stored top-tail, budget, MACE, coverage, CRPS, and NLL metrics were
reconstructed without campaign execution. Budget 5/10/20\% summaries interpolate
between stored batch checkpoints.

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS3_TopTail_Sensitivity.pdf}}

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS4_Budget_Calibration_Sensitivity.pdf}}

\section{{Practical-significance analysis}}
\descriptive\ A neutral rule selected favorable, harmful, largest-absolute, and
non-significant representative cases. Unreached recall targets are reported as
``not reached within the observed budget.''

\includegraphics[width=\linewidth]{{../../figures_v5/submission_candidate_v4/phase3/FigureS5_Practical_Significance.pdf}}

\section{{Complete locked V5 primary table}}
All 128 environment-specific endpoint-by-contrast rows are shown. Raw and
BH-adjusted p-values are distinct columns.

{primary_longtable()}

\section{{Cross-environment descriptive summaries}}
\descriptive\ Counts are environment-specific BH classifications, not pooled
tests. Random-effects or hierarchical task-population inference was not added
because only four fixed tasks were studied.

The paired-seed intervals quantify repeated-algorithm uncertainty conditional
on the fixed task, dataset, split construction, surrogate, campaign geometry,
and policy identity. They do not quantify uncertainty over a population of
materials problems.

\section{{Recovery job-level reconciliation}}
The original process exit code was not recorded and is therefore nullable.
Identity is verified from manifest, registry, retry events, final trajectories,
and locks.

{recovery_table()}

\section{{Recovery sensitivity}}
\posthoc\ The affected cell retained 34 of 40 paired seeds after excluding six
recovered jobs. Direction, BH label, and interval zero-crossing changed in 0/8
tests; two relative changes exceeded 10\%; maximum absolute change was 0.001825.

\section{{Derived-analysis correction and baseline-map audit}}
The verified recovery strategy is \texttt{{cs\_da\_oob\_hist}}, not a random
baseline. Selected Raw baselines are beta 1 for experimental gap, MP gap, and
log GVRH, and beta 2 for log KVRH. These identities are frozen.

\section{{Runtime}}
\descriptive\ Runtime summaries use stored cumulative trajectory runtime.
Runtime per additional discovery is omitted when additional discovery is zero
or negative. Hardware and process scheduling limit cross-machine interpretation.

\section{{Reproducibility and validation}}
Every derived table records source paths and analysis labels. Main-figure sources
are byte-identical to the verified sources. Supplementary figures use Phase 3
tables. The final-table, result, trajectory-content, and selected-policy locks
remain unchanged.

\section{{Optional unexecuted protocols}}
No new model family, acquisition function, dataset, seed, or simple-scaling
campaign was executed. The optional protocol ends with the required explicit
human-approval gate.

\section{{Supplementary figures}}
Supplementary Figures S1--S6 are included in Sections 5 and 8--11. Each figure
has a source CSV, caption, metadata JSON, PDF, PNG, and SHA-256 provenance.

\end{{document}}
"""

supp_path = MANU / "supplement_submission_candidate_v4.tex"
write(supp_path, supp)


# ---------------------------------------------------------------------------
# Reference audit.
# ---------------------------------------------------------------------------
citation_groups = re.findall(r"\\cite[tp]?\{([^}]+)\}", main)
cited = [key.strip() for group in citation_groups for key in group.split(",")]
support_map = {
    "dunn2020matbench": "Matbench benchmark tasks",
    "ward2018matminer": "composition-derived materials descriptors",
    "butler2018mlmaterials": "materials machine-learning context",
    "lookman2019active": "materials active learning and uncertainty",
    "xue2016adaptive": "adaptive materials design",
    "kusne2020closedloop": "closed-loop materials discovery",
    "rohr2020metrics": "sequential-learning discovery metrics",
    "hase2021olympus": "optimization benchmarking",
    "shahriari2016bo": "Bayesian optimization review",
    "frazier2018tutorial": "Bayesian optimization tutorial",
    "srinivas2010gpucb": "GP-UCB formulation",
    "auer2002ucb": "UCB exploration principle",
    "breiman2001rf": "Random Forest",
    "meinshausen2006qrf": "tree-ensemble predictive distribution",
    "wager2014confidence": "Random Forest uncertainty",
    "mentch2016uncertainty": "Random Forest uncertainty",
    "gneiting2007proper": "proper probabilistic scoring",
    "kuleshov2018calibrated": "regression uncertainty calibration",
    "guo2017calibration": "predictive calibration",
    "lakshminarayanan2017ensembles": "ensemble predictive uncertainty",
    "angelopoulos2023conformal": "distribution-free uncertainty background",
    "mandi2022decision": "decision-focused learning",
    "wilder2019decision": "decision-focused learning",
    "donti2017task": "task-based end-to-end learning",
    "fanelli2012negative": "negative-result reporting",
    "liang2021benchmark": "benchmark reporting",
}
audit_rows = []
for key in retain:
    entry = entries[key]
    title_match = re.search(r"title=\{([^}]*(?:\}[^,}]*)*)\}", entry, re.I)
    doi_match = re.search(r"doi=\{([^}]+)\}", entry, re.I)
    audit_rows.append(
        {
            "citation_key": key,
            "retained": True,
            "cited_in_manuscript": key in cited,
            "supporting_role": support_map[key],
            "title": title_match.group(1) if title_match else "",
            "doi_as_stored": doi_match.group(1) if doi_match else "",
            "metadata_action": "retained from existing audited bibliography; DOI not invented",
            "decorative_reference": False,
            "final_status": "verified_used" if key in cited else "failed_unused",
        }
    )
reference_audit = pd.DataFrame(audit_rows)
reference_audit.to_csv(PHASE / "08_reference_audit.csv", index=False)
if not reference_audit.cited_in_manuscript.all():
    raise RuntimeError("retained bibliography contains uncited entries")


# ---------------------------------------------------------------------------
# Traceability matrices.
# ---------------------------------------------------------------------------
claim_backup = ARCHIVE / "09_claim_evidence_matrix_pre_phase3.csv"
number_backup = ARCHIVE / "10_number_traceability_pre_phase3.csv"
old_claim = pd.read_csv(claim_backup if claim_backup.exists() else ROOT / "09_claim_evidence_matrix.csv")
old_num = pd.read_csv(number_backup if number_backup.exists() else ROOT / "10_number_traceability.csv")
for path, label in ((ROOT / "09_claim_evidence_matrix.csv", "09_claim_evidence_matrix_pre_phase3.csv"),
                    (ROOT / "10_number_traceability.csv", "10_number_traceability_pre_phase3.csv")):
    backup = ARCHIVE / label
    if not backup.exists():
        shutil.copy2(path, backup)

claim_rows = []
for row in old_claim.to_dict("records"):
    claim_rows.append(
        {
            "sentence_id": row.get("claim_id", ""),
            "section": row.get("manuscript_section", ""),
            "claim": row.get("claim", ""),
            "status": row.get("status", ""),
            "evidence_class": row.get("evidence_classification", ""),
            "source_table": row.get("source_final_artifact", ""),
            "exact_row_filter": "",
            "task": "", "split": "", "surrogate": "", "strategy": "", "endpoint": "",
            "seed_cohort": "", "analysis_script": "scripts/generate_traceability_final.py",
            "source_hash": "",
            "result_lock_hash": row.get("result_lock_hash", RESULT_LOCK),
            "final_table_lock_hash": row.get("final_table_lock_hash", LOCK),
        }
    )
phase_claims = [
    ("M-ABS-01", "Abstract", "V5-RC1 contains 3,360 jobs and 40 paired seeds per environment.", "frozen confirmation", ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "all rows", "", "", "", "", "", "5000-5039"),
    ("M-ABS-02", "Abstract", "Original GG L1 harm occurred in 16/16 environments.", "confirmatory", ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv", "contrast=Original GG vs Raw; endpoint=L1; BH significant harmful", "", "", "", "gg_ucb_beta_1", "l1_campaign_mace", "5000-5039"),
    ("M-ABS-03", "Abstract", "Historical CS L4 harm occurred in 16/16 environments.", "confirmatory", ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv", "contrast=Historical CS vs Raw; endpoint=L4; BH significant harmful", "", "", "", "cs_da_oob_hist", "l4_top1pct_recall_nauc", "5000-5039"),
    ("M-RES-EB", "Results 3.3", "GG effective beta varies by campaign state.", "exploratory mechanism analysis", TABLES / "gg_effective_beta_by_state.csv", "all stored GG post-initial states", "", "", "", "gg_ucb_beta_0p5|gg_ucb_beta_1", "", "5000-5039"),
    ("M-RES-DEV", "Results 3.2", "Held-out log-KVRH Raw beta selection is criterion dependent.", "post hoc sensitivity", TABLES / "development_selection_stability.csv", "held_out_task=matbench_log_kvrh; family=raw", "matbench_log_kvrh", "", "", "raw_ucb_beta_2|raw_ucb_beta_1", "development primary nAUC", "1000-1009"),
    ("M-RES-END", "Results 3.6", "Endpoint sensitivity is mostly preserved with exceptions.", "post hoc sensitivity", TABLES / "endpoint_sensitivity_contrasts.csv", "all rows", "", "", "", "", "multiple", "5000-5039"),
    ("M-RES-PRAC", "Results 3.7", "Practical top-candidate consequences are heterogeneous.", "descriptive analysis", TABLES / "practical_significance_by_environment.csv", "all environments", "", "", "", "", "top1 recall at 20pct", "5000-5039"),
    ("M-RES-OOD", "Results 3.8", "Chemical-system-group OOD severity is task dependent.", "descriptive analysis", TABLES / "ood_severity_summary.csv", "all four tasks", "", "chemical_system_ood", "", "selected Raw", "OOD severity", "5000-5039"),
    ("M-REC-01", "Results 3.9", "Recovery exclusion changed 0/8 directions, labels, and CI zero status.", "post hoc sensitivity", ROOT / "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "affected recovery cell all 8 rows", "matbench_mp_gap", "chemical_system_ood", "extra_randomized_bagging", "cs_da_oob_hist", "L1|L4", "5000-5039"),
]
for sid, section, claim, evidence, path, filt, task, split, surrogate, strategy, endpoint_name, cohort in phase_claims:
    claim_rows.append(
        {
            "sentence_id": sid, "section": section, "claim": claim, "status": "verified",
            "evidence_class": evidence, "source_table": rel(path), "exact_row_filter": filt,
            "task": task, "split": split, "surrogate": surrogate, "strategy": strategy,
            "endpoint": endpoint_name, "seed_cohort": cohort,
            "analysis_script": "C:/tmp/generate_phase3_analyses.py|C:/tmp/generate_phase3_manuscripts.py",
            "source_hash": sha(path), "result_lock_hash": RESULT_LOCK, "final_table_lock_hash": LOCK,
        }
    )
pd.DataFrame(claim_rows).to_csv(ROOT / "09_claim_evidence_matrix.csv", index=False)

number_rows = []
for row in old_num.to_dict("records"):
    number_rows.append(
        {
            "sentence_id": row.get("sentence_id", ""), "section": row.get("manuscript_section", ""),
            "evidence_class": row.get("evidence_classification", ""),
            "source_table": row.get("source_final_table", ""), "exact_row_filter": row.get("row_filter", ""),
            "task": "", "split": "", "surrogate": "", "strategy": row.get("contrast", ""),
            "endpoint": row.get("endpoint", ""), "seed_cohort": "",
            "analysis_script": row.get("script", ""), "source_hash": "",
            "result_lock_hash": row.get("result_lock_hash", RESULT_LOCK),
            "final_table_lock_hash": row.get("final_table_lock_hash", LOCK),
            "numerical_value": row.get("number", ""), "unit": row.get("unit", ""),
        }
    )
phase_numbers = [
    ("M-ABS-01", "Abstract", "frozen confirmation", ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "all rows", 3360, "jobs"),
    ("M-ABS-01", "Abstract", "frozen confirmation", ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv", "nunique(seed)", 40, "paired seeds/environment"),
    ("M-ABS-02", "Abstract", "confirmatory", ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv", "Original GG L1 BH harmful", 16, "environments"),
    ("M-ABS-03", "Abstract", "confirmatory", ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv", "Historical CS L4 BH harmful", 16, "environments"),
    ("M-RES-EB", "Results 3.3", "exploratory mechanism analysis", TABLES / "gg_effective_beta_by_state.csv", "median effective_beta", gg_median, "effective beta"),
    ("M-RES-EB", "Results 3.3", "exploratory mechanism analysis", TABLES / "gg_effective_beta_by_state.csv", "row count", len(gg), "stored states"),
    ("M-RES-DEV", "Results 3.2", "post hoc sensitivity", TABLES / "development_selection_stability.csv", "log_kvrh raw seed_bootstrap selected_frequency", float(logk_boot.selected_frequency), "frequency"),
    ("M-RES-PRAC", "Results 3.7", "descriptive analysis", TABLES / "practical_significance_by_environment.csv", "min additional_or_lost_top_candidates_20pct", practical_min, "top candidates"),
    ("M-RES-PRAC", "Results 3.7", "descriptive analysis", TABLES / "practical_significance_by_environment.csv", "max additional_or_lost_top_candidates_20pct", practical_max, "top candidates"),
    ("M-RES-OOD", "Results 3.8", "descriptive analysis", TABLES / "ood_severity_summary.csv", "min source_nn_target_median", ood_min, "standardized distance"),
    ("M-RES-OOD", "Results 3.8", "descriptive analysis", TABLES / "ood_severity_summary.csv", "max source_nn_target_median", ood_max, "standardized distance"),
    ("M-REC-01", "Results 3.9", "post hoc sensitivity", ROOT / "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "direction changes", 0, "of 8"),
    ("M-REC-01", "Results 3.9", "post hoc sensitivity", ROOT / "tables_v5/v5_rc1_recovery_sensitivity_final.csv", "maximum absolute effect change", 0.0018250336342871, "effect units"),
]
for sid, section, evidence, path, filt, value, unit in phase_numbers:
    number_rows.append(
        {
            "sentence_id": sid, "section": section, "evidence_class": evidence,
            "source_table": rel(path), "exact_row_filter": filt,
            "task": "", "split": "", "surrogate": "", "strategy": "", "endpoint": "",
            "seed_cohort": "5000-5039" if "development" not in evidence else "1000-1009",
            "analysis_script": "C:/tmp/generate_phase3_analyses.py|C:/tmp/generate_phase3_manuscripts.py",
            "source_hash": sha(path), "result_lock_hash": RESULT_LOCK,
            "final_table_lock_hash": LOCK, "numerical_value": value, "unit": unit,
        }
    )
pd.DataFrame(number_rows).to_csv(ROOT / "10_number_traceability.csv", index=False)


# ---------------------------------------------------------------------------
# Response to reviewer.
# ---------------------------------------------------------------------------
concerns = [
    ("Evidence geometry and historical phases", "Verified and separated", "V2/V3 locks, evidence lineage, V5 manifest", "Rewrote phase language", "No new scientific analysis", "Methods 2.1; Results 3.1", "Supplement 1-2", "No", "V2/V3 remain non-confirmatory"),
    ("GG may only retune beta", "Partially supported", "Stored global_scale and selected candidate predictions", "Added effective-beta analysis", "Exploratory mechanism analysis", "Methods 2.5; Results 3.3", "Supplement 9; Figure S1", "No", "Full-pool rankings unavailable"),
    ("Selected CS lacks simple baselines", "Not empirically resolved in V5", "Development/confirmation manifests", "Narrowed novelty claim", "Availability audit; unexecuted protocol", "Discussion", "Supplement 3 and 19", "No", "No matched V5 simple-scaling cohort"),
    ("Development choice may be unstable", "Sensitivity completed", "2,240 frozen development results", "Added stability report", "Seed bootstrap and criterion sensitivity", "Results 3.2", "Supplement 5; Figure S2", "No", "Only ten development seeds"),
    ("Endpoint dependence", "Sensitivity completed", "Stored rounds and diagnostics", "Added bounded post hoc results", "Top-tail, budget, MACE, CRPS, NLL", "Results 3.6", "Supplement 10; Figures S3-S4", "No", "Budget interpolation at batch checkpoints"),
    ("Practical magnitude", "Descriptively resolved", "Stored trajectories and pool sizes", "Added neutral examples", "Yield, queries, runtime", "Results 3.7", "Supplement 11; Figure S5", "No", "Unreached targets remain unavailable"),
    ("OOD label overstates shift", "Scope narrowed", "Frozen split and task descriptors", "Uses chemical-system-group OOD only", "Descriptive severity", "Methods 2.3; Results 3.8", "Supplement 7-8; Figure S6", "No", "Does not test other shift mechanisms"),
    ("Cross-environment counts imply pooling", "Corrected", "Locked 128-row table", "Added exact scope sentence", "Task-stratified descriptive summary", "Methods 2.10", "Supplement 13", "No", "Four fixed tasks"),
    ("Recovery provenance", "Verified", "Manifest, registry, events, trajectory locks", "Added nullable exit-code wording", "34-seed sensitivity", "Results 3.9", "Supplement 14-15", "No", "Original exit codes not recorded"),
    ("Model/dataset/acquisition breadth", "Not empirically resolved", "Frozen manifest", "Narrowed claims; no unapproved run", "Optional protocols only", "Discussion", "Supplement 19", "No", "RF/ExtraTrees, four tasks, UCB only"),
]
lines = ["# Response to senior reviewer — V4", ""]
for index, row in enumerate(concerns, 1):
    concern, assessment, evidence, action, analysis, main_sec, supp_sec, changed, limitation = row
    lines += [
        f"## Concern {index}: {concern}", "",
        f"- Assessment: {assessment}",
        f"- Evidence examined: {evidence}",
        f"- Action taken: {action}",
        f"- New analysis: {analysis}",
        f"- Manuscript change: {main_sec}",
        f"- Supplement change: {supp_sec}",
        f"- Exact section: Main {main_sec}; Supplement {supp_sec}",
        f"- Primary science changed: {changed}",
        f"- Remaining limitation: {limitation}", "",
    ]
write(PHASE / "09_response_to_reviewer_v4.md", "\n".join(lines))

print(json.dumps({
    "main_tex": rel(main_path),
    "supp_tex": rel(supp_path),
    "references": len(retain),
    "all_references_cited": True,
    "primary_table_rows": len(primary),
    "claim_rows": len(claim_rows),
    "number_rows": len(number_rows),
    "frozen_values_changed": False,
}, indent=2))
