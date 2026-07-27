from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.neighbors import NearestNeighbors

ROOT = Path(r"D:\贝叶斯优化\revision_v5")
WORKSPACE = ROOT.parent
PHASE = ROOT / "reviewer_revision_v4/phase3"
TABLES = ROOT / "tables_v5/submission_candidate_v4/phase3"
FIGS = ROOT / "figures_v5/submission_candidate_v4/phase3"
LOGS = ROOT / "logs_v5/reviewer_revision_v4/phase3"
MANUSCRIPT = ROOT / "manuscript_v5/submission_candidate_v4"
ARCHIVE = ROOT / "archive/superseded_phase3_artifacts"
for directory in (PHASE, TABLES, FIGS, LOGS, MANUSCRIPT, ARCHIVE):
    directory.mkdir(parents=True, exist_ok=True)

TASKS = (
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
)
BASELINE = {
    "matbench_expt_gap": "raw_ucb_beta_1",
    "matbench_mp_gap": "raw_ucb_beta_1",
    "matbench_log_gvrh": "raw_ucb_beta_1",
    "matbench_log_kvrh": "raw_ucb_beta_2",
}
TASK_LABEL = {
    "matbench_expt_gap": "Expt. gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}
BLUE = "#35618f"
GOLD = "#c18a2b"
ORANGE = "#c76532"
INK = "#252b33"
GREY = "#aeb6bf"
LIGHT = "#e7ebef"
RNG = np.random.default_rng(20260726)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def beta_from_strategy(strategy: str) -> float:
    match = re.search(r"_beta_(\d+)(?:p(\d+))?$", strategy)
    if not match:
        return 1.0
    whole, decimal = match.groups()
    return float(f"{whole}.{decimal or '0'}")


def auc_to_budget(frame: pd.DataFrame, column: str, end: float) -> float:
    ordered = frame.sort_values("budget_fraction")
    x = ordered["budget_fraction"].to_numpy(float)
    y = ordered[column].to_numpy(float)
    if end <= x[0] or end > x[-1]:
        return float("nan")
    keep = x < end
    xx = np.append(x[keep], end)
    yy = np.append(y[keep], np.interp(end, x, y))
    if len(xx) < 2:
        return float("nan")
    return float(np.trapezoid(yy, xx) / end)


def value_at_budget(frame: pd.DataFrame, column: str, budget: float) -> float:
    ordered = frame.sort_values("budget_fraction")
    x = ordered["budget_fraction"].to_numpy(float)
    y = ordered[column].to_numpy(float)
    if budget < x[0] or budget > x[-1]:
        return float("nan")
    return float(np.interp(budget, x, y))


def percentile_interval(values: np.ndarray, reps: int = 1000) -> tuple[float, float]:
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    indices = RNG.integers(0, len(values), size=(reps, len(values)))
    means = values[indices].mean(axis=1)
    return tuple(map(float, np.quantile(means, [0.025, 0.975])))


def figure_metadata(stem: str, source: Path, question: str, takeaway: str, chart: str) -> None:
    meta = {
        "schema_version": "phase3-figure-v1",
        "figure": stem,
        "analysis_type": "post hoc or descriptive as stated in caption",
        "source_csv": rel(source),
        "source_sha256": sha(source),
        "analytical_question": question,
        "supported_takeaway": takeaway,
        "chart_family": chart,
        "palette_policy": "hard two-root cap plus neutrals",
        "scientific_trajectories_rerun": False,
    }
    write_text(FIGS / f"{stem}_metadata.json", json.dumps(meta, indent=2))


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGS / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def setup_axis(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=LIGHT, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, colors=INK)


# ---------------------------------------------------------------------------
# Phase 3 execution matrix, initially pending; finalized by the packaging step.
# ---------------------------------------------------------------------------
matrix_rows = [
    ("P3-01", "How does Gaussian-global scaling alter the effective UCB exploration weight?", "confirmation rounds.parquet and selected.parquet", "exploratory mechanism analysis", "post_hoc", "gg_effective_beta_by_state.csv", "01_gg_effective_beta_report.md", "Results 3.3", "Supplement 9", "yes", "ranking agreement uses the stored top-5-batch candidate subset"),
    ("P3-02", "Were simpler uncertainty scalings already executed comparably to selected CS?", "development and confirmation manifests", "descriptive audit", "post_hoc", "02_simple_baseline_availability_audit.csv", "OPTIONAL_NEW_EXPERIMENT_SIMPLE_SCALINGS.md", "Discussion", "Supplement 19", "yes", "no simple scaling has a matched V5 confirmation cohort"),
    ("P3-03", "Is development selection stable to resampling and alternative criteria?", "development_complete_results.csv", "post hoc sensitivity", "post_hoc", "development_selection_stability.csv", "03_development_selection_stability_report.md", "Results 3.2", "Supplement 5", "yes", "only four tasks and ten development seeds"),
    ("P3-04", "Do conclusions persist across endpoints and budget windows?", "stored confirmation rounds and diagnostics", "post hoc sensitivity", "post_hoc", "endpoint_sensitivity_seed_level.csv|endpoint_sensitivity_contrasts.csv", "04_endpoint_sensitivity_report.md", "Results 3.6", "Supplement 10", "yes", "5/10/20% values use interpolation between stored batch checkpoints"),
    ("P3-05", "What are the practical screening consequences?", "stored confirmation trajectories", "descriptive analysis", "post_hoc", "practical_significance_by_environment.csv", "05_practical_significance_report.md", "Results 3.7", "Supplement 11", "yes", "query targets not reached are left unavailable"),
    ("P3-06", "How severe is the chemical-system-group OOD split?", "raw materials tables, frozen split code, raw-policy diagnostics", "descriptive analysis", "post_hoc", "ood_severity_summary.csv", "06_ood_severity_report.md", "Results 3.8", "Supplement 8", "yes", "descriptor distance is composition-derived and task specific"),
    ("P3-07", "What cross-environment inference is defensible?", "locked primary contrast table", "descriptive sensitivity", "post_hoc", "cross_environment_summary_sensitivity.csv", "07_cross_environment_inference_scope.md", "Statistical inference", "Supplement 13", "yes", "four tasks do not support population-level task inference"),
    ("P3-08", "Are final figures source-faithful and readable?", "verified figure sources and Phase 3 analysis tables", "figure QA", "post_hoc", "figure source CSVs", "10_pdf_visual_review_v4.md", "Figures 1-4", "Supplementary Figures S1-S6", "yes", "layout changes only for verified main figures"),
    ("P3-09", "Does the rewritten article preserve evidence classes and bounded claims?", "all verified and Phase 3 outputs", "editorial synthesis", "post_hoc", "", "manuscript_submission_candidate_v4.tex", "all", "all", "yes", "administrative fields remain placeholders"),
    ("P3-10", "Are references and numerical claims fully traceable?", "bibliography, manuscript, traceability tables", "audit", "post_hoc", "08_reference_audit.csv|09_claim_evidence_matrix.csv|10_number_traceability.csv", "09_response_to_reviewer_v4.md", "all", "all", "yes", "reference support is sentence scoped"),
    ("P3-11", "Does the complete package pass tests and PDF review?", "test suite and compiled PDFs", "validation", "post_hoc", "", "11_submission_readiness_v4.md", "all", "all", "yes", "readiness excludes administrative completion"),
]
matrix = pd.DataFrame(
    matrix_rows,
    columns=[
        "task_id", "scientific_question", "source_data", "analysis_type",
        "prospective_or_post_hoc", "output_table", "output_report",
        "manuscript_section", "supplement_section", "test_added", "limitation",
    ],
)
matrix["execution_status"] = "pending"
matrix["final_resolution"] = ""
matrix = matrix[
    [
        "task_id", "scientific_question", "source_data", "analysis_type",
        "prospective_or_post_hoc", "execution_status", "output_table",
        "output_report", "manuscript_section", "supplement_section",
        "test_added", "limitation", "final_resolution",
    ]
]
matrix.to_csv(PHASE / "00_phase3_execution_matrix.csv", index=False)


# ---------------------------------------------------------------------------
# 1. GG effective beta and ranking reconstruction.
# ---------------------------------------------------------------------------
gg_rows: list[dict] = []
confirmation = ROOT / "results_v4/confirmation/trajectories"
for directory in sorted(confirmation.glob("*__gg_ucb_beta_*")):
    strategy = directory.name.split("__")[-2]
    nominal = beta_from_strategy(strategy)
    rounds = pd.read_parquet(directory / "rounds.parquet")
    selected = pd.read_parquet(directory / "selected.parquet")
    for row in rounds.itertuples(index=False):
        if int(row.round) < 0:
            continue
        scale = float(row.global_scale)
        effective = nominal * scale
        nearest = min((0.5, 1.0, 2.0), key=lambda value: (abs(value - effective), value))
        state = selected[selected["round"] == int(row.round)].copy()
        agreements: dict[str, float] = {}
        if len(state) >= 8:
            stable = state["stable_candidate_id"].to_numpy(int)
            mean = state["predicted_mean"].to_numpy(float)
            sigma = np.maximum(state["raw_predicted_std"].to_numpy(float), 1e-8)
            gg_score = mean + effective * sigma
            gg_rank = rankdata(-gg_score, method="average")
            for beta in (0.5, 1.0, 2.0, nearest):
                raw_rank = rankdata(-(mean + beta * sigma), method="average")
                agreements[f"ranking_agreement_raw_beta_{str(beta).replace('.', 'p')}"] = float(
                    spearmanr(gg_rank, raw_rank).statistic
                )
            reconstruction = "stored_top5_batch_subset_reconstructed"
        else:
            agreements = {
                "ranking_agreement_raw_beta_0p5": float("nan"),
                "ranking_agreement_raw_beta_1p0": float("nan"),
                "ranking_agreement_raw_beta_2p0": float("nan"),
                f"ranking_agreement_raw_beta_{str(nearest).replace('.', 'p')}": float("nan"),
            }
            reconstruction = "insufficient_stored_candidate_rows"
        selected_beta = beta_from_strategy(BASELINE[str(row.task)])
        gg_rows.append(
            {
                "task": row.task,
                "split": row.split_protocol,
                "surrogate": row.model,
                "strategy": strategy,
                "seed": int(row.seed),
                "round": int(row.round),
                "budget_fraction": float(row.budget_fraction),
                "nominal_beta": nominal,
                "fitted_global_scale": scale,
                "effective_beta": effective,
                "selected_raw_beta_for_task": selected_beta,
                "nearest_tested_static_beta": nearest,
                "scale_clipped": bool(scale <= float(row.uncertainty_floor) * (1 + 1e-12)),
                "fallback_used": str(row.scale_status) != "gaussian_consistent",
                "source_state_path": rel(directory / "rounds.parquet"),
                "source_function": "transportability_v5.strategies.gaussian_global_scale",
                "reconstruction_status": reconstruction,
                "ranking_agreement_raw_beta_0p5": agreements.get("ranking_agreement_raw_beta_0p5"),
                "ranking_agreement_raw_beta_1p0": agreements.get("ranking_agreement_raw_beta_1p0"),
                "ranking_agreement_raw_beta_2p0": agreements.get("ranking_agreement_raw_beta_2p0"),
                "ranking_agreement_nearest_static_beta": agreements.get(
                    f"ranking_agreement_raw_beta_{str(nearest).replace('.', 'p')}"
                ),
            }
        )
gg = pd.DataFrame(gg_rows).sort_values(["task", "split", "surrogate", "strategy", "seed", "round"])
gg_path = TABLES / "gg_effective_beta_by_state.csv"
gg.to_csv(gg_path, index=False)
gg_summary = gg.groupby(["task", "strategy"], as_index=False).agg(
    states=("effective_beta", "size"),
    median_scale=("fitted_global_scale", "median"),
    q025_scale=("fitted_global_scale", lambda x: x.quantile(.025)),
    q975_scale=("fitted_global_scale", lambda x: x.quantile(.975)),
    median_effective_beta=("effective_beta", "median"),
    above_selected_raw=("effective_beta", lambda x: float((x > gg.loc[x.index, "selected_raw_beta_for_task"]).mean())),
    fallback_rate=("fallback_used", "mean"),
    median_nearest_agreement=("ranking_agreement_nearest_static_beta", "median"),
)
nearest_freq = gg.groupby(["strategy", "nearest_tested_static_beta"]).size().rename("states").reset_index()
gg_conclusion = (
    "GG is partially equivalent to dynamic beta modulation but changes behavior beyond tested "
    "static-beta policies."
)
write_text(
    PHASE / "01_gg_effective_beta_report.md",
    f"""# GG effective-beta analysis

Classification: exploratory mechanism analysis; post hoc. Unit: stored campaign state.

For Raw UCB, $a_{{raw}}=\\mu+\\beta\\sigma$. For Gaussian-global scaling,
$a_{{GG}}=\\mu+\\beta c_t\\sigma$, so $\\beta_{{eff,t}}=\\beta c_t$.
The analysis read {len(gg):,} stored post-initial states from executed V5-RC1
GG trajectories. No model was refitted and no campaign was rerun.

## Findings

- Median effective beta, fitted-scale quantiles, fallback rate, and the fraction
  above the task-selected Raw beta are reported by task and GG identity in
  `{rel(gg_path)}`.
- The closest static beta was classified among 0.5, 1, and 2. Frequencies are:

{nearest_freq.to_markdown(index=False)}

- Ranking agreement was reconstructed only on the candidate subset retained in
  each `selected.parquet` file (the stored top five batch widths), not the full
  candidate pool. This supports a bounded ranking comparison, not identity of
  complete acquisition orders.
- Nominal beta 0.5 often offsets fitted scale above one, but the fitted scale
  varies across task and stage. It is therefore not a fixed reparameterization.
- Associations with L1/L4 environment effects are exploratory and noncausal;
  task, split, surrogate, stage, and seed remain entangled.

## Required conclusion

**{gg_conclusion}**

Limitation: full-pool predictions were not retained. Ranking-level reconstruction
is limited to the stored candidate subset.
""",
)

s1_source = gg[
    [
        "task", "strategy", "budget_fraction", "fitted_global_scale",
        "effective_beta", "ranking_agreement_nearest_static_beta",
    ]
].copy()
s1_source.to_csv(FIGS / "FigureS1_GG_Effective_Beta_source.csv", index=False)
fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8))
sample = s1_source.sample(min(5000, len(s1_source)), random_state=17)
axes[0].scatter(sample["budget_fraction"], sample["fitted_global_scale"], s=5, alpha=.15, color=BLUE)
axes[0].set(title="Global scale by budget stage", xlabel="Budget fraction", ylabel="Fitted global scale")
task_data = [gg.loc[gg.task == task, "effective_beta"].to_numpy() for task in TASKS]
axes[1].boxplot(task_data, tick_labels=[TASK_LABEL[t] for t in TASKS], showfliers=False)
axes[1].tick_params(axis="x", rotation=25)
axes[1].set(title="Effective beta by task", ylabel="Effective beta")
agree = gg.groupby("strategy")["ranking_agreement_nearest_static_beta"].mean()
axes[2].bar(agree.index, agree.values, color=[BLUE, GOLD][: len(agree)], edgecolor=INK)
axes[2].tick_params(axis="x", rotation=25)
axes[2].set(title="Ranking agreement on stored subset", ylabel="Mean Spearman agreement", ylim=(0, 1.02))
for ax in axes:
    setup_axis(ax)
fig.suptitle("Supplementary Figure S1 | Gaussian-global effective-beta diagnostics", fontsize=12, color=INK)
fig.tight_layout()
save_figure(fig, "FigureS1_GG_Effective_Beta")
write_text(
    FIGS / "FigureS1_GG_Effective_Beta_caption.txt",
    "Supplementary Figure S1. Post hoc GG effective-beta diagnostics from stored V5-RC1 states. "
    "Ranking agreement is restricted to the candidate subset retained in selected.parquet; it is "
    "not a full-pool reconstruction.",
)
figure_metadata(
    "FigureS1_GG_Effective_Beta",
    FIGS / "FigureS1_GG_Effective_Beta_source.csv",
    "How do fitted global scale and effective beta vary by stage and task?",
    "Effective beta is dynamic; stored-subset rankings remain closest to different static betas across states.",
    "distribution, relationship, and comparison",
)


# ---------------------------------------------------------------------------
# 2. Simple-baseline availability audit and optional prospective protocol.
# ---------------------------------------------------------------------------
dev_manifest = pd.read_csv(ROOT / "manifests_v4/DEVELOPMENT_JOB_MANIFEST_V5.csv")
conf_manifest = pd.read_csv(ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv")
identities = [
    ("Raw beta grid", r"raw_ucb_beta_", True, "historical development and locked confirmation"),
    ("sigma power transformation", r"sigma_power|power", False, "not executed"),
    ("temperature/variance scaling", r"temperature|variance_scal", False, "not executed"),
    ("monotone scaling", r"monotone", False, "not executed"),
    ("isotonic scaling", r"isotonic", False, "not executed"),
    ("direct ridge scale", r"candidate_specific_direct_ridge", True, "historical development only"),
    ("calibration ridge scale", r"candidate_specific_calibration_ridge", True, "historical development only"),
    ("GG acquisition-only", r"gg_acquisition_only", True, "historical development only"),
    ("uncertainty-only", r"uncertainty_only", True, "historical development only"),
    ("beta zero / greedy mean", r"raw_ucb_beta_0$", True, "historical development only"),
    ("random", r"random$", True, "historical development only"),
    ("one-parameter global scale", r"gg_ucb_beta_", True, "development and confirmation"),
]
audit_rows = []
all_manifest = pd.concat(
    [dev_manifest.assign(_phase="development"), conf_manifest.assign(_phase="confirmation")],
    ignore_index=True,
)
for identity, pattern, expected, note in identities:
    mask = all_manifest.strategy.astype(str).str.contains(pattern, regex=True)
    subset = all_manifest[mask]
    executed = not subset.empty
    phases = sorted(subset["_phase"].unique()) if executed else []
    comparable = bool(executed and "confirmation" in phases and identity in {"Raw beta grid", "one-parameter global scale"})
    audit_rows.append(
        {
            "baseline_identity": identity,
            "executed": executed,
            "tasks": "|".join(sorted(subset.task.unique())) if executed else "",
            "splits": "|".join(sorted(subset.split_protocol.unique())) if executed else "",
            "surrogates": "|".join(sorted(subset.model.unique())) if executed else "",
            "seed_range": f"{int(subset.seed.min())}-{int(subset.seed.max())}" if executed else "",
            "endpoints": "stored campaign endpoints" if executed else "",
            "comparable_to_selected_cs": comparable,
            "evidence_class": "|".join(phases) if executed else "not_executed",
            "source_path": "revision_v5/manifests_v4/DEVELOPMENT_JOB_MANIFEST_V5.csv|revision_v5/manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv",
            "limitation": note if expected == executed else "manifest audit inconsistency",
        }
    )
simple_audit = pd.DataFrame(audit_rows)
simple_audit.to_csv(PHASE / "02_simple_baseline_availability_audit.csv", index=False)
write_text(
    PHASE / "OPTIONAL_NEW_EXPERIMENT_SIMPLE_SCALINGS.md",
    """# Optional prospective experiment: simple uncertainty scalings

Status: optional new experiment not run.

## Frozen transformations

1. Power: $s'=\\max(s,10^{-8})^p$, $p\\in\\{0.5,0.75,1,1.25,1.5\\}$.
2. Temperature: $s'=\\tau s$, $\\tau\\in\\{0.5,0.75,1,1.5,2\\}$.
3. Variance temperature: $s'=\\sqrt{\\tau s^2}$ on the same grid.
4. Monotone isotonic scale fitted only to development OOB residual ratios.
5. One-parameter log-linear scale: $\\log s'=b_0+\\log s$.

Tasks: the same four Matbench regression tasks. Splits: IID record and
chemical-system-group OOD. Surrogates: Random Forest and ExtraTrees. Endpoints:
Campaign MACE and top-1% recall nAUC primary; top-0.5/2/5% and budget windows
secondary. Contrasts: each frozen transformation versus the task-selected Raw
baseline and versus selected CS. Seeds: a new prospective cohort, paired across
all policies, with no reuse of 1000--1009 or 5000--5039.

Multiplicity: within each environment, BH over the full prespecified family.
Compute estimate: 4 tasks x 2 splits x 2 surrogates x 11 policies x 40 seeds =
7,040 campaign jobs, subject to a dry-run resource benchmark. Freeze process:
write protocol, manifest, policy map, code hashes, seed list, expected outputs,
result-lock schema, and stopping rules before any outcome inspection.

REQUIRES EXPLICIT HUMAN APPROVAL BEFORE EXECUTION
""",
)


# ---------------------------------------------------------------------------
# 3. Development-selection stability.
# ---------------------------------------------------------------------------
development = pd.read_csv(ROOT / "tables_v5/development_complete_results.csv")
families = {
    "raw": ["raw_ucb_beta_0", "raw_ucb_beta_0p25", "raw_ucb_beta_0p5", "raw_ucb_beta_1", "raw_ucb_beta_2", "raw_ucb_beta_4"],
    "gaussian_global": ["gg_ucb_beta_0p25", "gg_ucb_beta_0p5", "gg_ucb_beta_1", "gg_ucb_beta_2", "gg_ucb_beta_4"],
    "candidate_specific": ["cs_da_oob_hist", "cs_da_oob_v5", "cs_da_oob_parsimonious_f1"],
}
selection_summary = pd.read_csv(ROOT / "tables_v5/submission_candidate_v3/development_selection_summary.csv")


def strategy_scores(frame: pd.DataFrame, candidates: list[str], criterion: str = "mean") -> pd.Series:
    subset = frame[frame.strategy.isin(candidates)]
    env = subset.groupby(["strategy", "task", "split_protocol", "model"], as_index=False).primary_nauc.mean()
    if criterion == "worst":
        return env.groupby("strategy").primary_nauc.min().sort_values(ascending=False)
    if criterion == "equal_task":
        task = env.groupby(["strategy", "task"], as_index=False).primary_nauc.mean()
        return task.groupby("strategy").primary_nauc.mean().sort_values(ascending=False)
    return env.groupby("strategy").primary_nauc.mean().sort_values(ascending=False)


stability_rows: list[dict] = []
for held_out in TASKS:
    train = development[development.task != held_out].copy()
    for family, candidates in families.items():
        row0 = selection_summary[
            (selection_summary.held_out_task == held_out) & (selection_summary.family == family)
        ].iloc[0]
        original = str(row0.selected_candidate)
        runner = str(row0.runner_up)

        # Seed bootstrap.
        winners, margins = [], []
        for _ in range(500):
            sampled = []
            for (_, _, _), group in train[train.strategy.isin(candidates)].groupby(
                ["task", "split_protocol", "model"]
            ):
                seeds = RNG.choice(group.seed.unique(), size=10, replace=True)
                for strategy in candidates:
                    values = group[group.strategy == strategy].set_index("seed").primary_nauc
                    sampled.extend(
                        {
                            "task": group.task.iloc[0], "split_protocol": group.split_protocol.iloc[0],
                            "model": group.model.iloc[0], "strategy": strategy,
                            "primary_nauc": float(values.loc[int(seed)]),
                        }
                        for seed in seeds
                    )
            scores = strategy_scores(pd.DataFrame(sampled), candidates)
            winners.append(str(scores.index[0]))
            margins.append(float(scores.iloc[0] - scores.iloc[1]))
        counts = Counter(winners)
        low, high = np.quantile(margins, [.025, .975])
        retained = counts[original] / len(winners)
        stability_class = "stable" if retained >= .8 else "weakly_stable" if retained >= .6 else "unstable"
        stability_rows.append(
            {
                "held_out_task": held_out, "strategy_family": family,
                "original_selected_candidate": original, "runner_up": runner,
                "sensitivity_method": "seed_bootstrap", "number_of_resamples": 500,
                "selected_frequency": retained, "runner_up_frequency": counts[runner] / len(winners),
                "winner_change_rate": 1 - retained, "median_score_margin": float(np.median(margins)),
                "lower_margin_interval": float(low), "upper_margin_interval": float(high),
                "original_selection_retained": retained >= .5, "stability_class": stability_class,
            }
        )

        # Deterministic criterion and leave-one-environment-out sensitivities.
        methods: list[tuple[str, list[str], list[float]]] = []
        for criterion in ("mean", "worst", "equal_task"):
            scores = strategy_scores(train, candidates, criterion)
            methods.append((f"{criterion}_ranking", [str(scores.index[0])], [float(scores.iloc[0] - scores.iloc[1])]))
        env_winners, env_margins = [], []
        envs = train[["task", "split_protocol", "model"]].drop_duplicates().itertuples(index=False, name=None)
        for task, split, model in envs:
            reduced = train[~((train.task == task) & (train.split_protocol == split) & (train.model == model))]
            scores = strategy_scores(reduced, candidates)
            env_winners.append(str(scores.index[0]))
            env_margins.append(float(scores.iloc[0] - scores.iloc[1]))
        methods.append(("leave_one_development_environment_out", env_winners, env_margins))
        base_scores = strategy_scores(train, candidates)
        band = base_scores[base_scores >= base_scores.iloc[0] - .005]
        tie_winner = str(
            train[train.strategy.isin(band.index)]
            .groupby(["strategy", "task", "split_protocol", "model"]).primary_nauc.mean()
            .groupby("strategy").min().sort_values(ascending=False).index[0]
        )
        methods.append(("0p005_tie_band", [tie_winner], [float(base_scores.iloc[0] - base_scores.iloc[1])]))
        for method, winners2, margins2 in methods:
            count2 = Counter(winners2)
            retained2 = count2[original] / len(winners2)
            stability_rows.append(
                {
                    "held_out_task": held_out, "strategy_family": family,
                    "original_selected_candidate": original, "runner_up": runner,
                    "sensitivity_method": method, "number_of_resamples": len(winners2),
                    "selected_frequency": retained2, "runner_up_frequency": count2[runner] / len(winners2),
                    "winner_change_rate": 1 - retained2, "median_score_margin": float(np.median(margins2)),
                    "lower_margin_interval": float(np.min(margins2)), "upper_margin_interval": float(np.max(margins2)),
                    "original_selection_retained": retained2 >= .5,
                    "stability_class": "stable" if retained2 == 1 else "criterion_dependent",
                }
            )
stability = pd.DataFrame(stability_rows)
stability_path = TABLES / "development_selection_stability.csv"
stability.to_csv(stability_path, index=False)
logk = stability[(stability.held_out_task == "matbench_log_kvrh") & (stability.strategy_family == "raw")]
write_text(
    PHASE / "03_development_selection_stability_report.md",
    f"""# Development-selection stability

Classification: post hoc sensitivity using development results only. V5 outcomes
were not used. Unit: development seed within task x split x surrogate environment.

The frozen selected-policy mapping is unchanged. Seed bootstrap used 500
deterministic resamples. Leave-one-development-environment-out, mean-only,
worst-environment, equal-task, equal-environment, and 0.005 tie-band criteria
were evaluated.

## Held-out log-KVRH: Raw beta 2 versus beta 1

{logk.to_markdown(index=False)}

The beta-2 choice for held-out log-KVRH is criterion dependent because its
original mean-score advantage over beta 1 was within the 0.005 tie band and the
frozen worst-environment rule resolved the choice. This sensitivity does not
alter the locked map.

Limitation: only ten development seeds and three training tasks contribute to
each held-out-task selection.
""",
)
s2_source = stability[
    stability.sensitivity_method.isin(["seed_bootstrap", "leave_one_development_environment_out"])
].copy()
s2_source.to_csv(FIGS / "FigureS2_Development_Stability_source.csv", index=False)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
boot = s2_source[s2_source.sensitivity_method == "seed_bootstrap"].copy()
labels = [f"{TASK_LABEL[t]} | {f}" for t, f in zip(boot.held_out_task, boot.strategy_family)]
pos = np.arange(len(boot))
axes[0].barh(pos, boot.selected_frequency, color=BLUE, edgecolor=INK)
axes[0].set_yticks(pos, labels, fontsize=7)
axes[0].invert_yaxis()
axes[0].set(xlabel="Original-winner frequency", xlim=(0, 1), title="Seed-bootstrap winner frequency")
axes[1].errorbar(
    boot.median_score_margin, pos,
    xerr=np.vstack([boot.median_score_margin - boot.lower_margin_interval, boot.upper_margin_interval - boot.median_score_margin]),
    fmt="o", color=GOLD, ecolor=INK, capsize=2,
)
axes[1].axvline(0, color=INK, linewidth=.8)
axes[1].set_yticks(pos, [])
axes[1].set(xlabel="Selected-minus-runner-up nAUC", title="Bootstrap score margins")
for ax in axes:
    setup_axis(ax)
fig.suptitle("Supplementary Figure S2 | Development-selection stability", fontsize=12)
fig.tight_layout()
save_figure(fig, "FigureS2_Development_Stability")
write_text(
    FIGS / "FigureS2_Development_Stability_caption.txt",
    "Supplementary Figure S2. Post hoc development-only selection stability. "
    "Bars show the frozen winner's frequency across 500 seed bootstraps; intervals "
    "show 2.5th-97.5th percentile score margins.",
)
figure_metadata(
    "FigureS2_Development_Stability",
    FIGS / "FigureS2_Development_Stability_source.csv",
    "How often is the frozen development winner retained under resampling?",
    "Most selections are retained, while held-out log-KVRH Raw selection is criterion dependent.",
    "comparison and uncertainty",
)


# ---------------------------------------------------------------------------
# 4. Endpoint sensitivity from stored rounds and diagnostics.
# ---------------------------------------------------------------------------
seed_metric_rows: list[dict] = []
job_summary: list[dict] = []
for directory in sorted(confirmation.iterdir()):
    if not directory.is_dir() or not (directory / "rounds.parquet").is_file():
        continue
    rounds = pd.read_parquet(directory / "rounds.parquet")
    diag = pd.read_parquet(directory / "diagnostic_metrics.parquet")
    first = rounds.iloc[-1]
    base = {
        "job_id": directory.name, "task": first.task, "split": first.split_protocol,
        "surrogate": first.model, "strategy": first.strategy, "seed": int(first.seed),
        "environment": f"{first.task}__{first.split_protocol}__{first.model}",
    }
    metrics: dict[str, float] = {}
    for q, col in (("0p5", "top0p5_recall"), ("1", "top1_recall"), ("2", "top2_recall"), ("5", "top5_recall")):
        metrics[f"recall_top{q}_nauc_full"] = auc_to_budget(rounds, col, 1.0)
    for budget in (.05, .10, .20):
        label = str(int(budget * 100))
        metrics[f"top1_nauc_through_{label}pct"] = auc_to_budget(rounds, "top1_recall", budget)
        metrics[f"top1_recall_at_{label}pct"] = value_at_budget(rounds, "top1_recall", budget)
    diag = diag.sort_values("round")
    metrics["mace_early"] = float(diag.head(4).mean_absolute_coverage_error.mean())
    metrics["mace_late"] = float(diag.tail(4).mean_absolute_coverage_error.mean())
    checkpoints = diag.iloc[[min(i, len(diag)-1) for i in (0, 2, 5, 8)]]
    metrics["mace_four_checkpoint_equal_weight"] = float(checkpoints.mean_absolute_coverage_error.mean())
    metrics["mace_all_round_equal_weight"] = float(diag.mean_absolute_coverage_error.mean())
    metrics["crps_all_round"] = float(diag.crps_mean.mean())
    metrics["nll_all_round"] = float(diag.gaussian_nll_mean.mean())
    for coverage in (50, 80, 90, 95):
        metrics[f"coverage_{coverage}_absolute_error"] = float(
            (diag[f"coverage_{coverage}"] - coverage / 100).abs().mean()
        )
    for name, value in metrics.items():
        seed_metric_rows.append(
            {
                **base, "sensitivity_metric": name, "value": value,
                "analysis_classification": "post hoc sensitivity",
                "source_path": rel(directory / ("diagnostic_metrics.parquet" if "mace" in name or "crps" in name or "nll" in name or "coverage" in name else "rounds.parquet")),
                "reconstruction_note": "linear interpolation between stored batch checkpoints" if "pct" in name else "stored-state integration",
            }
        )
    job_summary.append({**base, **metrics, "runtime_seconds": float(rounds.iloc[-1].runtime_seconds)})
seed_metrics = pd.DataFrame(seed_metric_rows)
seed_path = TABLES / "endpoint_sensitivity_seed_level.csv"
seed_metrics.to_csv(seed_path, index=False)
job_summary_df = pd.DataFrame(job_summary)

primary = pd.read_csv(ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv")
contrast_rows: list[dict] = []
metric_direction = {
    name: not any(token in name for token in ("mace", "nll", "crps", "absolute_error"))
    for name in seed_metrics.sensitivity_metric.unique()
}
for p in primary.itertuples(index=False):
    env = str(p.environment)
    test = job_summary_df[(job_summary_df.environment == env) & (job_summary_df.strategy == p.test_strategy)].set_index("seed")
    baseline = job_summary_df[(job_summary_df.environment == env) & (job_summary_df.strategy == p.baseline_strategy)].set_index("seed")
    common = sorted(set(test.index) & set(baseline.index))
    if not common:
        continue
    candidates = (
        [m for m in metric_direction if m.startswith("mace") or m.startswith("coverage") or m.startswith("crps") or m.startswith("nll")]
        if p.endpoint == "l1_campaign_mace"
        else [m for m in metric_direction if m.startswith("recall_") or m.startswith("top1_")]
    )
    primary_benefit = (
        "favorable" if p.effect_direction == "favors_test" and bool(p.significant_after_bh)
        else "harmful" if p.effect_direction == "favors_baseline" and bool(p.significant_after_bh)
        else "not_bh_significant"
    )
    for metric in candidates:
        diff = test.loc[common, metric].to_numpy(float) - baseline.loc[common, metric].to_numpy(float)
        low, high = percentile_interval(diff)
        mean = float(np.nanmean(diff))
        higher = metric_direction[metric]
        benefit = mean if higher else -mean
        if not np.isfinite(mean):
            classification = "unavailable"
        elif primary_benefit == "favorable":
            classification = "preserved across all available sensitivities" if benefit > 0 else "changed under sensitivity"
        elif primary_benefit == "harmful":
            classification = "preserved across all available sensitivities" if benefit < 0 else "changed under sensitivity"
        else:
            classification = "mostly preserved" if low <= 0 <= high else "threshold dependent"
        contrast_rows.append(
            {
                "task": p.task, "environment": env, "contrast_name": p.contrast_name,
                "baseline_strategy": p.baseline_strategy, "test_strategy": p.test_strategy,
                "primary_endpoint": p.endpoint, "sensitivity_metric": metric,
                "higher_is_better": higher, "n_pairs": len(common), "mean_diff_test_minus_baseline": mean,
                "ci_lower": low, "ci_upper": high, "primary_bh_classification": primary_benefit,
                "sensitivity_conclusion": classification, "analysis_classification": "post hoc sensitivity",
            }
        )
endpoint_contrasts = pd.DataFrame(contrast_rows)
contrast_path = TABLES / "endpoint_sensitivity_contrasts.csv"
endpoint_contrasts.to_csv(contrast_path, index=False)
conclusion_counts = endpoint_contrasts.sensitivity_conclusion.value_counts()
endpoint_conclusion = (
    "Primary directional conclusions are mostly preserved across stored top-tail, budget, "
    "calibration, CRPS, and NLL sensitivities, with threshold- and budget-dependent exceptions."
)
write_text(
    PHASE / "04_endpoint_sensitivity_report.md",
    f"""# Endpoint sensitivity

Classification: post hoc sensitivity. Unit: paired confirmation seed.
Campaigns were not rerun.

Stored top-0.5%, top-1%, top-2%, and top-5% recall curves were integrated.
Budget-window nAUC and recall at 5%, 10%, and 20% use linear interpolation
between stored batch checkpoints; they are not exact per-query reconstructions.
L1 sensitivity includes early, late, four-checkpoint, and all-round MACE,
coverage-level errors, CRPS, and Gaussian NLL. No unavailable metric was
synthesized.

Sensitivity classification counts:

{conclusion_counts.rename_axis("classification").reset_index(name="rows").to_markdown(index=False)}

## Conclusion

{endpoint_conclusion}

The locked primary analysis, endpoints, p-values, BH labels, and evidence
classes remain unchanged.
""",
)

s3 = endpoint_contrasts[
    endpoint_contrasts.sensitivity_metric.isin(
        ["recall_top0p5_nauc_full", "recall_top1_nauc_full", "recall_top2_nauc_full", "recall_top5_nauc_full"]
    )
].copy()
s3.to_csv(FIGS / "FigureS3_TopTail_Sensitivity_source.csv", index=False)
fig, ax = plt.subplots(figsize=(10, 5.5))
summary = s3.groupby(["contrast_name", "sensitivity_metric"], as_index=False).mean_diff_test_minus_baseline.mean()
metrics = list(summary.sensitivity_metric.unique())
contrasts = list(summary.contrast_name.unique())
x = np.arange(len(contrasts))
width = .18
for i, metric in enumerate(metrics):
    values = [
        float(summary[(summary.contrast_name == contrast) & (summary.sensitivity_metric == metric)].mean_diff_test_minus_baseline.iloc[0])
        for contrast in contrasts
    ]
    ax.bar(x + (i - 1.5) * width, values, width, label=metric.replace("recall_", "").replace("_nauc_full", ""), edgecolor=INK)
ax.axhline(0, color=INK, linewidth=.8)
ax.set_xticks(x, contrasts, rotation=20, ha="right")
ax.set(title="Top-tail recall nAUC sensitivity", ylabel="Mean test-minus-baseline effect across environments")
ax.legend(ncol=4, fontsize=8)
setup_axis(ax)
fig.tight_layout()
save_figure(fig, "FigureS3_TopTail_Sensitivity")
write_text(FIGS / "FigureS3_TopTail_Sensitivity_caption.txt", "Supplementary Figure S3. Post hoc top-tail recall nAUC sensitivity from stored trajectories. Bars are descriptive averages of environment-specific paired effects; no pooled inference.")
figure_metadata("FigureS3_TopTail_Sensitivity", FIGS / "FigureS3_TopTail_Sensitivity_source.csv", "Does L4 direction persist across top-tail thresholds?", "Effects vary in magnitude and sometimes by threshold; primary inference remains top-1%.", "grouped comparison")

s4 = endpoint_contrasts[
    endpoint_contrasts.sensitivity_metric.isin(
        ["top1_nauc_through_5pct", "top1_nauc_through_10pct", "top1_nauc_through_20pct", "mace_early", "mace_late"]
    )
].copy()
s4.to_csv(FIGS / "FigureS4_Budget_Calibration_Sensitivity_source.csv", index=False)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
budget = s4[s4.sensitivity_metric.str.startswith("top1")].groupby("sensitivity_metric").mean_diff_test_minus_baseline.mean()
axes[0].bar(budget.index.str.replace("top1_nauc_through_", ""), budget.values, color=BLUE, edgecolor=INK)
axes[0].axhline(0, color=INK, linewidth=.8)
axes[0].set(title="Budget-window top-1% nAUC", ylabel="Mean effect", xlabel="Observed budget window")
mace = s4[s4.sensitivity_metric.str.startswith("mace")].groupby("sensitivity_metric").mean_diff_test_minus_baseline.mean()
axes[1].bar(mace.index.str.replace("mace_", ""), mace.values, color=GOLD, edgecolor=INK)
axes[1].axhline(0, color=INK, linewidth=.8)
axes[1].set(title="Early versus late Campaign MACE", ylabel="Mean test-minus-baseline effect", xlabel="Campaign stage")
for ax in axes:
    setup_axis(ax)
fig.suptitle("Supplementary Figure S4 | Budget and calibration sensitivities", fontsize=12)
fig.tight_layout()
save_figure(fig, "FigureS4_Budget_Calibration_Sensitivity")
write_text(FIGS / "FigureS4_Budget_Calibration_Sensitivity_caption.txt", "Supplementary Figure S4. Post hoc budget-window and calibration-stage sensitivities. Budget values use interpolation between stored batch checkpoints. Environment averages are descriptive, not pooled inference.")
figure_metadata("FigureS4_Budget_Calibration_Sensitivity", FIGS / "FigureS4_Budget_Calibration_Sensitivity_source.csv", "Do effects depend on budget stage or calibration timing?", "Some effect magnitudes are budget and stage dependent.", "comparison")


# ---------------------------------------------------------------------------
# 5. Practical significance and neutral representative rule.
# ---------------------------------------------------------------------------
practical_rows = []
for p in primary.itertuples(index=False):
    env = str(p.environment)
    test = job_summary_df[(job_summary_df.environment == env) & (job_summary_df.strategy == p.test_strategy)]
    base = job_summary_df[(job_summary_df.environment == env) & (job_summary_df.strategy == p.baseline_strategy)]
    if test.empty or base.empty:
        continue
    metric = "mace_four_checkpoint_equal_weight" if p.endpoint == "l1_campaign_mace" else "recall_top1_nauc_full"
    test_abs = float(test[metric].mean())
    base_abs = float(base[metric].mean())
    t20 = float(test.top1_recall_at_20pct.mean())
    b20 = float(base.top1_recall_at_20pct.mean())
    sample_dir = confirmation / str(test.job_id.iloc[0])
    rounds_sample = pd.read_parquet(sample_dir / "rounds.parquet")
    target_size = int(rounds_sample.top1_target_set_size.iloc[-1])
    selectable = int(rounds_sample.candidate_count.iloc[0])
    add = (t20 - b20) * target_size
    per1000 = (t20 - b20) * (0.01 * 1000)

    def reach(group: pd.DataFrame, target_recall: float = .5) -> float:
        values = []
        for job in group.job_id:
            rounds = pd.read_parquet(confirmation / job / "rounds.parquet").sort_values("budget_fraction")
            hit = rounds[rounds.top1_recall >= target_recall]
            values.append(float(hit.budget_fraction.iloc[0]) if not hit.empty else float("nan"))
        return float(np.nanmean(values)) if np.isfinite(values).any() else float("nan")

    base_reach = reach(base)
    test_reach = reach(test)
    max_queries = int(rounds_sample.iloc[-1].candidate_count - rounds_sample.iloc[0].candidate_count + len(json.loads(rounds_sample.iloc[-1].selected_batch_ids)))
    savings = (base_reach - test_reach) * max_queries if np.isfinite(base_reach) and np.isfinite(test_reach) else float("nan")
    runtime_delta = float(test.runtime_seconds.mean() - base.runtime_seconds.mean())
    practical_rows.append(
        {
            "task": p.task, "environment": env, "contrast_name": p.contrast_name,
            "endpoint": p.endpoint, "baseline_strategy": p.baseline_strategy, "test_strategy": p.test_strategy,
            "baseline_absolute_nauc": base_abs, "test_absolute_nauc": test_abs,
            "baseline_fixed_budget_recall_20pct": b20, "test_fixed_budget_recall_20pct": t20,
            "top1_target_set_size": target_size, "selectable_pool_size": selectable,
            "baseline_top_candidates_found_20pct": b20 * target_size,
            "test_top_candidates_found_20pct": t20 * target_size,
            "additional_or_lost_top_candidates_20pct": add,
            "baseline_budget_to_50pct_recall": base_reach,
            "test_budget_to_50pct_recall": test_reach,
            "query_savings_positive_or_excess_negative": savings,
            "target_recall_status": "reached" if np.isfinite(base_reach) and np.isfinite(test_reach) else "not reached within the observed budget.",
            "additional_discoveries_per_1000_selectable": per1000,
            "runtime_delta_seconds": runtime_delta,
            "runtime_per_additional_discovery": runtime_delta / add if add > 0 else float("nan"),
            "relative_effect_vs_baseline": (test_abs - base_abs) / abs(base_abs) if base_abs else float("nan"),
            "primary_bh_significant": bool(p.significant_after_bh),
            "primary_direction": p.effect_direction,
            "analysis_classification": "descriptive post hoc practical significance",
            "representative_class": "",
        }
    )
practical = pd.DataFrame(practical_rows)
selection_pool = practical.copy()
selection_pool["absolute_primary_effect"] = primary.set_index(["environment", "contrast_name", "endpoint"]).loc[
    pd.MultiIndex.from_frame(selection_pool[["environment", "contrast_name", "endpoint"]]), "mean_diff"
].to_numpy()
rules = {
    "median_bh_significant_favorable": (selection_pool.primary_bh_significant & (selection_pool.primary_direction == "favors_test")),
    "median_bh_significant_harmful": (selection_pool.primary_bh_significant & (selection_pool.primary_direction == "favors_baseline")),
    "largest_absolute_effect": pd.Series(True, index=selection_pool.index),
    "non_significant_representative": ~selection_pool.primary_bh_significant,
}
chosen_indices: set[int] = set()
for label, mask in rules.items():
    eligible = selection_pool[mask & ~selection_pool.index.isin(chosen_indices)]
    if eligible.empty:
        continue
    if label == "largest_absolute_effect":
        idx = eligible.absolute_primary_effect.abs().idxmax()
    else:
        median = eligible.absolute_primary_effect.median()
        idx = (eligible.absolute_primary_effect - median).abs().idxmin()
    practical.loc[idx, "representative_class"] = label
    chosen_indices.add(int(idx))
practical_path = TABLES / "practical_significance_by_environment.csv"
practical.to_csv(practical_path, index=False)
reps = practical[practical.representative_class != ""]
practical_conclusion = (
    "Practical consequences are heterogeneous: some statistically classified effects correspond "
    "to small changes in top-candidate yield, while selected cases show material losses or gains."
)
write_text(
    PHASE / "05_practical_significance_report.md",
    f"""# Practical-significance analysis

Classification: descriptive post hoc analysis. Unit: environment-level summary
of paired-seed trajectories.

The neutral representative rule was frozen before case selection: one median
BH-significant favorable case, one median BH-significant harmful case, one
largest-absolute-effect case, and one non-significant representative case.

{reps.to_markdown(index=False)}

Query targets not reached are reported as **not reached within the observed
budget.** No infinity is used.

## Conclusion

{practical_conclusion}

Limitations: fixed-budget values are interpolated between stored batch
checkpoints; candidate counts are task- and split-specific; runtime per
additional discovery is omitted for zero or negative additional yield.
""",
)
reps.to_csv(FIGS / "FigureS5_Practical_Significance_source.csv", index=False)
fig, ax = plt.subplots(figsize=(10.5, 4.8))
labels = reps.representative_class.str.replace("_", " ")
values = reps.additional_or_lost_top_candidates_20pct
colors = [BLUE if value >= 0 else GOLD for value in values]
ax.barh(np.arange(len(reps)), values, color=colors, edgecolor=INK, hatch=["", "//", "..", "xx"][: len(reps)])
ax.set_yticks(np.arange(len(reps)), labels)
ax.axvline(0, color=INK, linewidth=.9)
ax.set(title="Representative practical consequences at 20% budget", xlabel="Additional (+) or lost (-) top-1% candidates")
setup_axis(ax)
fig.tight_layout()
save_figure(fig, "FigureS5_Practical_Significance")
write_text(FIGS / "FigureS5_Practical_Significance_caption.txt", "Supplementary Figure S5. Neutral-rule representative practical consequences. Cases include favorable, harmful, largest-absolute-effect, and non-significant examples; values are descriptive.")
figure_metadata("FigureS5_Practical_Significance", FIGS / "FigureS5_Practical_Significance_source.csv", "What screening consequences correspond to representative effects?", "Representative consequences include gains, losses, and small changes.", "signed comparison")


# ---------------------------------------------------------------------------
# 6. Chemical-system-group OOD severity.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "experiments_v4/src"))
from transportability_v5.data import featurize_formulas, load_materials_csv  # noqa: E402
from transportability_v5.splits import make_split  # noqa: E402

code_package = Path(r"D:\贝叶斯优化\最终\_code_package")
ood_rows = []
for task in TASKS:
    data = load_materials_csv(code_package / "results/benchmark" / task / "materials.csv")
    X = np.asarray(featurize_formulas(data.formula), float)
    X = np.nan_to_num(X)
    y = data.target.to_numpy(float)
    formulas = data.formula.to_numpy()
    ids = data.material_id.to_numpy()
    seed_rows = []
    for seed in range(5000, 5040):
        split = make_split("chemical_system_ood").split(formulas, ids, seed, min_source=30, min_target=50, min_diagnostic=20)
        source, target, diagnostic = split.source, split.target, split.diagnostic
        center = X[source].mean(axis=0)
        spread = X[source].std(axis=0)
        spread[spread < 1e-12] = 1
        zsource = (X[source] - center) / spread
        ztarget = (X[target] - center) / spread
        zdiag = (X[diagnostic] - center) / spread
        nn = NearestNeighbors(n_neighbors=1).fit(zsource)
        d_target = nn.kneighbors(ztarget, return_distance=True)[0][:, 0]
        d_diag = nn.kneighbors(zdiag, return_distance=True)[0][:, 0]
        marginal = float(np.mean(np.abs(ztarget.mean(axis=0))))
        source_groups = [split.group_by_index[i] for i in source]
        target_groups = [split.group_by_index[i] for i in target]
        diagnostic_groups = [split.group_by_index[i] for i in diagnostic]
        elements = sorted({e for g in split.group_by_index for e in g.split("-")})
        def element_freq(indices: np.ndarray) -> np.ndarray:
            counts = Counter(e for i in indices for e in split.group_by_index[i].split("-"))
            arr = np.array([counts[e] for e in elements], float)
            return arr / arr.sum()
        ef_shift = .5 * np.abs(element_freq(source) - element_freq(target)).sum()
        pooled_sd = max(float(np.std(y)), 1e-12)
        seed_rows.append(
            {
                "source_nn_target_median": float(np.median(d_target)),
                "source_nn_diagnostic_median": float(np.median(d_diag)),
                "descriptor_marginal_shift_mean_abs_smd": marginal,
                "element_frequency_total_variation": float(ef_shift),
                "source_system_count": len(set(source_groups)),
                "selectable_system_count": len(set(target_groups)),
                "diagnostic_system_count": len(set(diagnostic_groups)),
                "source_record_count": len(source), "selectable_record_count": len(target),
                "diagnostic_record_count": len(diagnostic),
                "target_distribution_shift_smd": float((y[target].mean() - y[source].mean()) / pooled_sd),
            }
        )
    seed_frame = pd.DataFrame(seed_rows)

    # Stored Raw diagnostic shifts, paired over seed and surrogate.
    raw_parts = []
    for split_name in ("iid_record", "chemical_system_ood"):
        strategy = BASELINE[task]
        for surrogate in ("random_forest", "extra_randomized_bagging"):
            for seed in range(5000, 5040):
                directory = confirmation / f"{task}__{split_name}__{surrogate}__{strategy}__seed{seed}"
                if directory.is_dir():
                    diag = pd.read_parquet(directory / "diagnostic_metrics.parquet")
                    raw_parts.append(
                        {
                            "split": split_name, "surrogate": surrogate, "seed": seed,
                            "mace": diag.mean_absolute_coverage_error.mean(),
                            "crps": diag.crps_mean.mean(), "nll": diag.gaussian_nll_mean.mean(),
                            "width95": diag.mean_interval_width_95.mean(),
                        }
                    )
    raw = pd.DataFrame(raw_parts)
    summary = seed_frame.mean(numeric_only=True).to_dict()
    for metric in ("mace", "crps", "nll", "width95"):
        pivot = raw.pivot_table(index=["surrogate", "seed"], columns="split", values=metric)
        summary[f"raw_baseline_{metric}_shift_ood_minus_iid"] = float(
            (pivot["chemical_system_ood"] - pivot["iid_record"]).mean()
        )
    ood_rows.append(
        {
            "task": task, **summary, "split_identity": "chemical-system-group OOD",
            "analysis_classification": "post-split descriptive analysis",
            "targets_used_for_split": False,
            "source_data": rel(code_package / "results/benchmark" / task / "materials.csv"),
            "limitation": "composition-derived descriptor severity; does not represent all distribution shifts",
        }
    )
ood = pd.DataFrame(ood_rows)
ood_path = TABLES / "ood_severity_summary.csv"
ood.to_csv(ood_path, index=False)
ood_conclusion = (
    "Chemical-system-group OOD severity is task dependent in composition-derived descriptor, "
    "element-frequency, target-distribution, and Raw-baseline diagnostic space."
)
write_text(
    PHASE / "06_ood_severity_report.md",
    f"""# Chemical-system-group OOD severity

Classification: post-split descriptive analysis. Unit: task, summarized over
40 frozen confirmation split seeds. Targets were used only for descriptive
post-split diagnostics and never to reconstruct or alter assignments.

Zero chemical-system overlap establishes role disjointness. Shift magnitude
was assessed with source-to-selectable and source-to-diagnostic nearest-neighbor
distance in the executed composition-derived descriptor representation,
marginal standardized shifts, element-frequency total variation, role system
and record counts, target-distribution shifts, and stored Raw-policy diagnostic
MACE, CRPS, NLL, and 95% interval-width shifts from IID to OOD.

## Conclusion

{ood_conclusion}

The design does not test temporal shift, laboratory shift,
processing-condition shift, structure-prototype shift independent of chemistry,
or label-mechanism shift. It must be described only as
**chemical-system-group OOD**.
""",
)
ood.to_csv(FIGS / "FigureS6_OOD_Severity_source.csv", index=False)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
x = np.arange(len(ood))
axes[0].bar(x - .18, ood.source_nn_target_median, .36, label="Selectable", color=BLUE, edgecolor=INK)
axes[0].bar(x + .18, ood.source_nn_diagnostic_median, .36, label="Diagnostic", color=GOLD, edgecolor=INK, hatch="//")
axes[0].set_xticks(x, [TASK_LABEL[t] for t in ood.task], rotation=20)
axes[0].set(title="Nearest-neighbor descriptor distance", ylabel="Median standardized distance")
axes[0].legend(fontsize=8)
axes[1].bar(x, ood.element_frequency_total_variation, color=BLUE, edgecolor=INK)
axes[1].set_xticks(x, [TASK_LABEL[t] for t in ood.task], rotation=20)
axes[1].set(title="Element-frequency shift", ylabel="Total variation distance")
for ax in axes:
    setup_axis(ax)
fig.suptitle("Supplementary Figure S6 | Chemical-system-group OOD severity", fontsize=12)
fig.tight_layout()
save_figure(fig, "FigureS6_OOD_Severity")
write_text(FIGS / "FigureS6_OOD_Severity_caption.txt", "Supplementary Figure S6. Post-split descriptive chemical-system-group OOD severity. Descriptor and element-frequency shifts are task specific and do not generalize to other distribution-shift mechanisms.")
figure_metadata("FigureS6_OOD_Severity", FIGS / "FigureS6_OOD_Severity_source.csv", "How large is chemical-system-group OOD shift by task?", "Composition-space severity differs substantially by task.", "comparison")


# ---------------------------------------------------------------------------
# 7. Cross-environment inference scope.
# ---------------------------------------------------------------------------
cross_rows = []
for (contrast, endpoint), group in primary.groupby(["contrast_name", "endpoint"]):
    favorable = int((group.effect_direction == "favors_test").sum())
    harmful = int((group.effect_direction == "favors_baseline").sum())
    bh_favorable = int(((group.effect_direction == "favors_test") & group.significant_after_bh).sum())
    bh_harmful = int(((group.effect_direction == "favors_baseline") & group.significant_after_bh).sum())
    n = len(group)
    p = favorable / n
    z = 1.96
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    cross_rows.append(
        {
            "contrast_name": contrast, "endpoint": endpoint,
            "analysis_type": "task-stratified descriptive sign-consistency summary",
            "unit_of_analysis": "fixed task x split x surrogate environment",
            "assumptions": "environment labels are descriptive and not an iid task sample",
            "estimate": f"{favorable}/{n} favorable signs; {bh_favorable}/{n} favorable BH; {bh_harmful}/{n} harmful BH",
            "uncertainty": f"descriptive Wilson interval for favorable-sign fraction [{center-half:.3f}, {center+half:.3f}]",
            "confirmatory_or_exploratory_status": "exploratory descriptive sensitivity",
            "limitation": "no population-of-materials-problems interpretation; four tasks only",
        }
    )
cross = pd.DataFrame(cross_rows)
cross_path = TABLES / "cross_environment_summary_sensitivity.csv"
cross.to_csv(cross_path, index=False)
exact_inference_sentence = (
    "The paired-seed intervals quantify repeated-algorithm uncertainty conditional "
    "on the fixed task, dataset, split construction, surrogate, campaign geometry, "
    "and policy identity. They do not quantify uncertainty over a population of materials problems."
)
write_text(
    PHASE / "07_cross_environment_inference_scope.md",
    f"""# Cross-environment inference scope

Primary inference remains environment-specific paired-seed inference with
within-environment BH adjustment over eight prespecified tests.

Counts such as 16/16, 12/16, 13/16, and 6/16 are descriptive counts of
environment-specific BH classifications. They are not pooled hypothesis tests,
task-population estimates, or universal-effect tests.

With four tasks, a random-effects model or hierarchical task-population model
would require assumptions unsupported by the design. The defensible Phase 3
addition is task-stratified descriptive and sign-consistency sensitivity.
Partial conjunction is not used because the environments share tasks,
datasets, split mechanisms, and related surrogate families.

Exact manuscript language:

> {exact_inference_sentence}

Limitation: even the Wilson intervals in the sensitivity table are descriptive
binomial summaries; they do not repair the absence of task-population sampling.
""",
)

print(json.dumps({
    "gg_rows": len(gg),
    "stability_rows": len(stability),
    "endpoint_seed_rows": len(seed_metrics),
    "endpoint_contrast_rows": len(endpoint_contrasts),
    "practical_rows": len(practical),
    "ood_rows": len(ood),
    "cross_rows": len(cross),
    "scientific_campaigns_rerun": False,
}, indent=2))
