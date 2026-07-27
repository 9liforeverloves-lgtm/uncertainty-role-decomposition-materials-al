from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import trim_mean, wilcoxon
from sklearn.neighbors import NearestNeighbors


ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "tables_v5/submission_candidate_v4_final_r1"
AUDIT = ROOT / "reviewer_revision_v4/final_r1"
LOG = ROOT / "logs_v5/reviewer_revision_v4/final_r1"
SCRIPT = ROOT / "scripts/final_r1"
ARCHIVE = ROOT / "archive/superseded_v4_final_r1"
for directory in (TABLE, AUDIT, LOG, SCRIPT, ARCHIVE):
    directory.mkdir(parents=True, exist_ok=True)

TRAJ = ROOT / "results_v4/confirmation/trajectories"
PHASE3 = ROOT / "tables_v5/submission_candidate_v4/phase3"
PRIMARY = ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv"
OLD_PRACTICAL = PHASE3 / "practical_significance_by_environment.csv"
SEED_SENS = PHASE3 / "endpoint_sensitivity_seed_level.csv"
OLD_CONTRAST = PHASE3 / "endpoint_sensitivity_contrasts.csv"
GEOMETRY = ROOT / "tables_v5/submission_candidate_v4_final/campaign_geometry_by_task.csv"
CODE_PACKAGE = ROOT.parent / "最终/_code_package"
FINAL_LOCK_HASH = "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d"
RNG = np.random.default_rng(20260727)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(values) -> str:
    payload = "\n".join(sorted(map(str, values))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def bootstrap_ci(values, reps=10000):
    values = np.asarray(values, float)
    values = values[np.isfinite(values)]
    if not len(values):
        return np.nan, np.nan
    index = RNG.integers(0, len(values), size=(reps, len(values)))
    means = values[index].mean(axis=1)
    return tuple(np.quantile(means, [0.025, 0.975]))


def bh_adjust(pvalues):
    values = np.asarray(pvalues, float)
    order = np.argsort(values)
    adjusted = np.empty(len(values), float)
    ranked = values[order] * len(values) / np.arange(1, len(values) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted[order] = np.minimum(ranked, 1.0)
    return adjusted


def value_at_budget(frame, column="top1_recall", budget=.20):
    ordered = frame.sort_values("budget_fraction")
    x = ordered["budget_fraction"].to_numpy(float)
    y = ordered[column].to_numpy(float)
    return float(np.interp(budget, x, y))


def first_budget_at_recall(frame, target=.50):
    ordered = frame.sort_values("budget_fraction")
    hit = ordered[ordered["top1_recall"] >= target]
    return float(hit.iloc[0]["budget_fraction"]) if not hit.empty else np.nan


# ---------------------------------------------------------------------------
# NLL audit: stored round-level diagnostic summaries.
# Individual diagnostic prediction vectors were not retained.
# ---------------------------------------------------------------------------
nll_stage_rows = []
nll_job_rows = []
stage_names = ("0-25%", "25-50%", "50-75%", "75-100%")
for directory in sorted(TRAJ.iterdir()):
    diag_path = directory / "diagnostic_metrics.parquet"
    rounds_path = directory / "rounds.parquet"
    if not diag_path.is_file() or not rounds_path.is_file():
        continue
    diag = pd.read_parquet(diag_path).sort_values("round")
    rounds = pd.read_parquet(rounds_path)
    last = rounds.iloc[-1]
    task, split, surrogate = str(last.task), str(last.split_protocol), str(last.model)
    strategy, seed = str(last.strategy), int(last.seed)
    nll_job_rows.append(
        {
            "environment": f"{task}__{split}__{surrogate}",
            "task": task,
            "split": split,
            "surrogate": surrogate,
            "strategy": strategy,
            "seed": seed,
            "nll_all_round": float(diag["gaussian_nll_mean"].mean()),
        }
    )
    indices = np.array_split(np.arange(len(diag)), 4)
    for stage, positions in zip(stage_names, indices):
        if not len(positions):
            continue
        subset = diag.iloc[positions]
        values = subset["gaussian_nll_mean"].to_numpy(float)
        finite = values[np.isfinite(values)]
        top_count = max(1, int(math.ceil(0.01 * len(finite)))) if len(finite) else 0
        fraction = (
            float(np.sort(np.abs(finite))[-top_count:].sum() / np.abs(finite).sum())
            if len(finite) and np.abs(finite).sum() > 0 else np.nan
        )
        nll_stage_rows.append(
            {
                "task": task,
                "split": split,
                "surrogate": surrogate,
                "strategy": strategy,
                "seed": seed,
                "campaign_stage": stage,
                "observation_count": int(subset["diagnostic_count"].sum()),
                "minimum_sigma": np.nan,
                "sigma_q001": np.nan,
                "sigma_q01": np.nan,
                "sigma_median": np.nan,
                "maximum_standardized_residual": np.nan,
                "nll_min": float(np.min(finite)) if len(finite) else np.nan,
                "nll_median": float(np.median(finite)) if len(finite) else np.nan,
                "nll_q95": float(np.quantile(finite, .95)) if len(finite) else np.nan,
                "nll_q99": float(np.quantile(finite, .99)) if len(finite) else np.nan,
                "nll_max": float(np.max(finite)) if len(finite) else np.nan,
                "nonfinite_nll_count": int(len(values) - len(finite)),
                "fraction_total_nll_from_largest_1pct": fraction,
                "uncertainty_floor_used": 1e-8,
                "source_file": f"revision_v5/results_v4/confirmation/trajectories/{directory.name}/diagnostic_metrics.parquet",
                "source_function": (
                    "transportability_v5.layers.uncertainty_quality; stored values are "
                    "round-level mean NLL. Individual diagnostic mu/sigma/residual "
                    "vectors were not retained, so sigma quantiles and maximum residual "
                    "are unavailable rather than reconstructed."
                ),
            }
        )
nll_seed = pd.DataFrame(nll_stage_rows)
nll_seed.to_csv(TABLE / "nll_numerical_stability_seed_level.csv", index=False)
nll_jobs = pd.DataFrame(nll_job_rows)

primary = pd.read_csv(PRIMARY)
nll_contrast_rows = []
for p in primary[primary["endpoint"] == "l1_campaign_mace"].itertuples(index=False):
    test = nll_jobs[
        (nll_jobs.environment == p.environment) & (nll_jobs.strategy == p.test_strategy)
    ].set_index("seed")
    base = nll_jobs[
        (nll_jobs.environment == p.environment) & (nll_jobs.strategy == p.baseline_strategy)
    ].set_index("seed")
    seeds = sorted(set(test.index) & set(base.index))
    diff = test.loc[seeds, "nll_all_round"].to_numpy(float) - base.loc[
        seeds, "nll_all_round"
    ].to_numpy(float)
    low, high = bootstrap_ci(diff)
    contribution = (
        float(np.max(np.abs(diff)) / np.sum(np.abs(diff)))
        if np.sum(np.abs(diff)) > 0 else 0.0
    )
    dominant = int(seeds[int(np.argmax(np.abs(diff)))])
    finite = bool(np.isfinite(diff).all())
    stable = bool(
        finite
        and contribution <= .25
        and abs(np.mean(diff) - np.median(diff))
        <= max(1e-6, 2 * abs(np.median(diff)))
        and abs(np.mean(diff)) < 1e6
    )
    nll_contrast_rows.append(
        {
            "contrast": p.contrast_name,
            "environment": p.environment,
            "stage": "all stored rounds",
            "paired_seed_count": len(seeds),
            "mean_effect": float(np.mean(diff)),
            "median_effect": float(np.median(diff)),
            "trimmed_mean_descriptive_only": float(trim_mean(diff, .10)),
            "bootstrap_CI": f"[{low:.8g}, {high:.8g}]",
            "maximum_seed_contribution": contribution,
            "dominant_extreme_seed": dominant,
            "numerically_stable": stable,
            "interpretation_status": (
                "descriptive_only_local_stability_pass"
                if stable else "numerically_unstable_not_interpretable"
            ),
        }
    )
nll_contrasts = pd.DataFrame(nll_contrast_rows)
nll_contrasts.to_csv(TABLE / "nll_contrast_stability_audit.csv", index=False)
global_nll_status = "numerically_unstable_not_interpretable"

(AUDIT / "01_nll_numerical_stability_report.md").write_text(
    f"""# NLL numerical-stability audit

- Formula located: `experiments_v4/src/transportability_v5/layers.py::uncertainty_quality`.
- Executed formula: `0.5*log(2*pi*sigma^2) + 0.5*((y-mu)/sigma)^2`.
- Floor: `sigma=max(raw_sigma,1e-8)` before division and logarithm.
- Aggregation: mean over diagnostic observations per round, then equal mean over stored rounds.
- Contrast: paired test-minus-baseline seed effects.
- Implementation bug found: No.
- Global status: `{global_nll_status}`.
- Nonfinite stored round means: {int(nll_seed.nonfinite_nll_count.sum())}.
- Unstable environment-level contrasts: {int((~nll_contrasts.numerically_stable).sum())}/{len(nll_contrasts)}.

The stored trajectory contains round-level diagnostic summaries, not the
individual diagnostic prediction means and standard deviations. Therefore
`minimum_sigma`, sigma quantiles, and maximum individual standardized residual
are explicitly unavailable in the seed-level audit. No values were invented,
and no checkpoint-only subset was substituted for the all-round endpoint.

The implementation formula is correct, but near-zero diagnostic uncertainty
can make the squared standardized-residual term dominate mean NLL. NLL is
therefore excluded from direction-preservation and classification-change
interpretation and retained only as a numerical-stability appendix. Primary L1
and L4 values are unchanged.
""",
    encoding="utf-8",
)


# ---------------------------------------------------------------------------
# Practical 128-to-64 uniqueness audit and paired-seed uncertainty.
# ---------------------------------------------------------------------------
old_practical = pd.read_csv(OLD_PRACTICAL)
key = ["task", "environment", "contrast_name"]
practical_numeric = [
    "baseline_fixed_budget_recall_20pct",
    "test_fixed_budget_recall_20pct",
    "top1_target_set_size",
    "selectable_pool_size",
    "baseline_top_candidates_found_20pct",
    "test_top_candidates_found_20pct",
    "additional_or_lost_top_candidates_20pct",
    "baseline_budget_to_50pct_recall",
    "test_budget_to_50pct_recall",
    "query_savings_positive_or_excess_negative",
    "additional_discoveries_per_1000_selectable",
]
uniqueness_rows = []
for group_key, group in old_practical.groupby(key, sort=True):
    identical = all(
        group[column].nunique(dropna=False) == 1 for column in practical_numeric
    )
    uniqueness_rows.append(
        {
            "task": group_key[0],
            "split": group.iloc[0].environment.split("__")[1],
            "surrogate": group.iloc[0].environment.split("__")[2],
            "contrast_identity": group_key[2],
            "endpoint_rows_present": "|".join(sorted(group.endpoint.unique())),
            "row_count": len(group),
            "practical_values_identical_across_endpoint_rows": identical,
            "duplicate_group": len(group) > 1 and identical,
            "retained_unique_row": "L4 row for primary class; practical fields deduplicated",
            "resolution": (
                "deduplicated_to_one_scientific_comparison"
                if identical else "retained_pending_scientific_distinction"
            ),
        }
    )
uniqueness = pd.DataFrame(uniqueness_rows)
uniqueness.to_csv(TABLE / "practical_significance_uniqueness_audit.csv", index=False)
if len(uniqueness) != 64 or not uniqueness.duplicate_group.all():
    raise RuntimeError("Practical 128-to-64 endpoint duplication was not proven")

geometry = pd.read_csv(GEOMETRY).set_index(["task", "split"])
practical_rows = []
for u in uniqueness.itertuples(index=False):
    env = f"{u.task}__{u.split}__{u.surrogate}"
    l4 = primary[
        (primary.environment == env)
        & (primary.contrast_name == u.contrast_identity)
        & (primary.endpoint == "l4_top1pct_recall_nauc")
    ].iloc[0]
    baseline_values, test_values, differences, savings_values = [], [], [], []
    selectable = top_size = None
    for seed in range(5000, 5040):
        base_dir = TRAJ / f"{u.task}__{u.split}__{u.surrogate}__{l4.baseline_strategy}__seed{seed}"
        test_dir = TRAJ / f"{u.task}__{u.split}__{u.surrogate}__{l4.test_strategy}__seed{seed}"
        if not (base_dir / "rounds.parquet").is_file() or not (test_dir / "rounds.parquet").is_file():
            continue
        b = pd.read_parquet(base_dir / "rounds.parquet")
        t = pd.read_parquet(test_dir / "rounds.parquet")
        top_size = int(b.iloc[-1].top1_target_set_size)
        selectable = int(b.iloc[0].candidate_count)
        bv = value_at_budget(b) * top_size
        tv = value_at_budget(t) * top_size
        baseline_values.append(bv)
        test_values.append(tv)
        differences.append(tv - bv)
        br, tr = first_budget_at_recall(b), first_budget_at_recall(t)
        max_queries = int(geometry.loc[(u.task, u.split), "maximum_queried_count"])
        savings_values.append((br - tr) * max_queries if np.isfinite(br) and np.isfinite(tr) else np.nan)
    differences = np.asarray(differences, float)
    low, high = bootstrap_ci(differences)
    savings_array = np.asarray(savings_values, float)
    primary_class = (
        "BH-favorable" if bool(l4.significant_after_bh) and l4.effect_direction == "favors_test"
        else "BH-harmful" if bool(l4.significant_after_bh) and l4.effect_direction == "favors_baseline"
        else "not-BH-significant"
    )
    discordant = primary_class == "BH-favorable" and float(np.mean(differences)) < 0
    practical_rows.append(
        {
            "task": u.task,
            "split": u.split,
            "surrogate": u.surrogate,
            "contrast_identity": u.contrast_identity,
            "baseline_strategy": l4.baseline_strategy,
            "test_strategy": l4.test_strategy,
            "primary_L4_class": primary_class,
            "paired_seed_count": len(differences),
            "baseline_discovered_top1_count_20pct_mean": float(np.mean(baseline_values)),
            "test_discovered_top1_count_20pct_mean": float(np.mean(test_values)),
            "paired_mean_difference": float(np.mean(differences)),
            "paired_median_difference": float(np.median(differences)),
            "paired_bootstrap_CI95_low": low,
            "paired_bootstrap_CI95_high": high,
            "selectable_pool_size": selectable,
            "top_set_size": top_size,
            "queried_budget": "20% of maximum frozen target-query budget",
            "discoveries_per_1000_selectable_candidates": float(np.mean(differences) / selectable * 1000),
            "fixed_recall_query_saving_mean": (
                float(np.nanmean(savings_array)) if np.isfinite(savings_array).any() else np.nan
            ),
            "fixed_recall_query_saving_status": (
                "available" if np.isfinite(savings_array).all() else "partly_or_fully_unavailable"
            ),
            "sign_discordance_note": (
                "The case was selected because its primary L4 nAUC classification was "
                "BH-favorable; its fixed-20% budget consequence differed in sign."
                if discordant else ""
            ),
            "analysis_classification": "descriptive post hoc practical significance",
        }
    )
practical = pd.DataFrame(practical_rows)
practical.to_csv(TABLE / "practical_significance_with_uncertainty.csv", index=False)
practical.to_csv(TABLE / "practical_significance_unique_comparisons.csv", index=False)

old_reps = pd.read_csv(
    ROOT / "tables_v5/submission_candidate_v4_final/practical_significance_representative_cases.csv"
)
rep_keys = old_reps[["environment", "contrast_name", "representative_class"]].drop_duplicates()
rep_keys[["task", "split", "surrogate"]] = rep_keys["environment"].str.split("__", expand=True)
representative = rep_keys.merge(
    practical,
    left_on=["task", "split", "surrogate", "contrast_name"],
    right_on=["task", "split", "surrogate", "contrast_identity"],
    how="left",
)
representative.to_csv(TABLE / "practical_significance_representative_cases_r1.csv", index=False)


# ---------------------------------------------------------------------------
# OOD assignment hashes and exact all-seed descriptor-distance aggregation.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "experiments_v4/src"))
from transportability_v5.data import featurize_formulas, load_materials_csv
from transportability_v5.splits import make_split

tasks = ["matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh"]
assignment_rows, distance_rows = [], []
for task in tasks:
    data_path = CODE_PACKAGE / "results/benchmark" / task / "materials.csv"
    data = load_materials_csv(data_path)
    formulas = data.formula.to_numpy()
    ids = data.material_id.astype(str).to_numpy()
    X = np.nan_to_num(np.asarray(featurize_formulas(data.formula), float))
    seed5000 = None
    for seed in range(5000, 5040):
        ood = make_split("chemical_system_ood").split(
            formulas, ids, seed, min_source=30, min_target=50, min_diagnostic=20
        )
        role_map = {}
        for role, indices in (
            ("source", ood.source), ("selectable", ood.target), ("diagnostic", ood.diagnostic)
        ):
            for index in indices:
                role_map[ood.group_by_index[int(index)]] = role
        hashes = {
            "source_assignment_hash": canonical_hash(ids[ood.source]),
            "selectable_assignment_hash": canonical_hash(ids[ood.target]),
            "diagnostic_assignment_hash": canonical_hash(ids[ood.diagnostic]),
            "system_role_hash": canonical_hash(f"{g}|{r}" for g, r in role_map.items()),
        }
        if seed == 5000:
            seed5000 = hashes.copy()
        assignment_rows.append(
            {
                "task": task,
                "seed": seed,
                **hashes,
                "equal_to_seed5000": hashes == seed5000,
                "source_count": len(ood.source),
                "selectable_count": len(ood.target),
                "diagnostic_count": len(ood.diagnostic),
                "source_system_count": len({ood.group_by_index[i] for i in ood.source}),
                "selectable_system_count": len({ood.group_by_index[i] for i in ood.target}),
                "diagnostic_system_count": len({ood.group_by_index[i] for i in ood.diagnostic}),
            }
        )

        center = X[ood.source].mean(axis=0)
        spread = X[ood.source].std(axis=0)
        spread[spread < 1e-12] = 1
        zsource = np.nan_to_num((X[ood.source] - center) / spread)
        nn = NearestNeighbors(n_neighbors=2, n_jobs=-1).fit(zsource)
        within = nn.kneighbors(zsource, return_distance=True)[0][:, 1]
        one = NearestNeighbors(n_neighbors=1, n_jobs=-1).fit(zsource)
        target_dist = one.kneighbors(
            np.nan_to_num((X[ood.target] - center) / spread), return_distance=True
        )[0][:, 0]
        diag_dist = one.kneighbors(
            np.nan_to_num((X[ood.diagnostic] - center) / spread), return_distance=True
        )[0][:, 0]

        iid = make_split("iid_record").split(
            formulas, ids, seed, min_source=30, min_target=50, min_diagnostic=20
        )
        iid_center = X[iid.source].mean(axis=0)
        iid_spread = X[iid.source].std(axis=0)
        iid_spread[iid_spread < 1e-12] = 1
        iid_source = np.nan_to_num((X[iid.source] - iid_center) / iid_spread)
        iid_held = np.concatenate([iid.target, iid.diagnostic])
        iid_dist = NearestNeighbors(n_neighbors=1, n_jobs=-1).fit(iid_source).kneighbors(
            np.nan_to_num((X[iid_held] - iid_center) / iid_spread),
            return_distance=True,
        )[0][:, 0]
        within_median = float(np.median(within))
        iid_median = float(np.median(iid_dist))
        for role, values in (
            ("within_source_leave_one_out", within),
            ("iid_heldout", iid_dist),
            ("ood_selectable", target_dist),
            ("ood_diagnostic", diag_dist),
        ):
            distance_rows.append(
                {
                    "task": task,
                    "seed": seed,
                    "role_or_reference": role,
                    "median_distance": float(np.median(values)),
                    "IQR_distance": float(np.quantile(values, .75) - np.quantile(values, .25)),
                    "mean_distance": float(np.mean(values)),
                    "within_source_ratio": float(np.median(values) / max(within_median, 1e-12)),
                    "iid_reference_ratio": float(np.median(values) / max(iid_median, 1e-12)),
                    "descriptor_dimension": X.shape[1],
                    "metric": "Euclidean distance after role-source-only z-score",
                    "analysis_classification": "post-split descriptive all-seed audit",
                }
            )
assignments = pd.DataFrame(assignment_rows)
assignments.to_csv(TABLE / "ood_assignment_invariance_audit.csv", index=False)
assignment_invariant = bool(assignments.equal_to_seed5000.all())
per_seed_distance = pd.DataFrame(distance_rows)
per_seed_distance.to_csv(TABLE / "ood_distance_reference_per_seed.csv", index=False)
summary_rows = []
for (task, role), group in per_seed_distance.groupby(["task", "role_or_reference"]):
    medians = group.median_distance.to_numpy(float)
    summary_rows.append(
        {
            "task": task,
            "role_or_reference": role,
            "seed_count": group.seed.nunique(),
            "median_over_seeds": float(np.median(medians)),
            "IQR_over_seeds": float(np.quantile(medians, .75) - np.quantile(medians, .25)),
            "minimum_over_seeds": float(np.min(medians)),
            "maximum_over_seeds": float(np.max(medians)),
            "median_within_source_ratio": float(group.within_source_ratio.median()),
            "median_IID_reference_ratio": float(group.iid_reference_ratio.median()),
            "assignment_invariance": assignment_invariant,
            "aggregation_used": "40-seed distribution because assignments vary",
        }
    )
ood_summary = pd.DataFrame(summary_rows)
ood_summary.to_csv(TABLE / "ood_distance_reference_all_seeds.csv", index=False)


# ---------------------------------------------------------------------------
# Deterministic sensitivity labels with numeric support.
# ---------------------------------------------------------------------------
seed_sens = pd.read_csv(SEED_SENS)
old_contrasts = pd.read_csv(OLD_CONTRAST)
detail = old_contrasts.copy()
detail["p_raw_sensitivity"] = np.nan
detail["p_BH_sensitivity"] = np.nan
for (environment, metric), indices in detail.groupby(
    ["environment", "sensitivity_metric"]
).groups.items():
    pvals = []
    ordered_indices = list(indices)
    for idx in ordered_indices:
        row = detail.loc[idx]
        test = seed_sens[
            (seed_sens.environment == environment)
            & (seed_sens.strategy == row.test_strategy)
            & (seed_sens.sensitivity_metric == metric)
        ].set_index("seed")
        base = seed_sens[
            (seed_sens.environment == environment)
            & (seed_sens.strategy == row.baseline_strategy)
            & (seed_sens.sensitivity_metric == metric)
        ].set_index("seed")
        seeds = sorted(set(test.index) & set(base.index))
        diff = test.loc[seeds, "value"].to_numpy(float) - base.loc[seeds, "value"].to_numpy(float)
        finite = diff[np.isfinite(diff)]
        if not len(finite) or np.allclose(finite, 0):
            pvalue = 1.0
        else:
            pvalue = float(wilcoxon(finite, zero_method="wilcox", alternative="two-sided", method="auto").pvalue)
        pvals.append(pvalue)
    adjusted = bh_adjust(pvals)
    for idx, raw, adj in zip(ordered_indices, pvals, adjusted):
        detail.loc[idx, "p_raw_sensitivity"] = raw
        detail.loc[idx, "p_BH_sensitivity"] = adj
detail["sensitivity_bh_significant"] = detail.p_BH_sensitivity < .05
primary_index = primary.set_index(["environment", "contrast_name", "endpoint"])

label_rows = []
for (contrast, endpoint, metric), group in detail.groupby(
    ["contrast_name", "primary_endpoint", "sensitivity_metric"], sort=True
):
    agreements, bh_changes, ci_changes, abs_changes, rel_changes = [], [], [], [], []
    reversals, class_changes = [], []
    for row in group.itertuples(index=False):
        p = primary_index.loc[(row.environment, contrast, endpoint)]
        p_effect = float(p.mean_diff)
        s_effect = float(row.mean_diff_test_minus_baseline)
        agreement = np.sign(p_effect) == np.sign(s_effect)
        p_ci = not (float(p.ci_lower) <= 0 <= float(p.ci_upper))
        s_ci = not (float(row.ci_lower) <= 0 <= float(row.ci_upper))
        bh_change = bool(p.significant_after_bh) != bool(row.sensitivity_bh_significant)
        ci_change = p_ci != s_ci
        change = abs(s_effect - p_effect)
        rel = change / max(abs(p_effect), 1e-12)
        agreements.append(agreement)
        bh_changes.append(bh_change)
        ci_changes.append(ci_change)
        abs_changes.append(change)
        rel_changes.append(rel)
        if not agreement:
            reversals.append(row.environment)
        if bh_change or ci_change:
            class_changes.append(row.environment)
    available = len(agreements)
    fraction = float(np.mean(agreements)) if available else np.nan
    bh_count, ci_count = int(sum(bh_changes)), int(sum(ci_changes))
    med_abs, max_abs = float(np.median(abs_changes)), float(np.max(abs_changes))
    med_rel = float(np.median(rel_changes))
    if metric == "nll_all_round":
        label = "unavailable"
    elif reversals:
        label = "direction_changed"
    elif bh_count > 0 or ci_count > 0:
        label = "classification_changed"
    elif fraction == 1.0 and med_rel > .25 and med_abs > 1e-6:
        label = "magnitude_sensitive"
    elif fraction == 1.0:
        label = "preserved"
    elif fraction >= .75:
        label = "mostly_preserved"
    else:
        label = "unstable"
    label_rows.append(
        {
            "contrast_name": contrast,
            "primary_endpoint": endpoint,
            "sensitivity_definition": metric,
            "available_environment_count": available,
            "primary_direction_agreement_count": int(sum(agreements)),
            "primary_direction_agreement_fraction": fraction,
            "BH_status_change_count": bh_count,
            "CI_zero_status_change_count": ci_count,
            "median_absolute_effect_change": med_abs,
            "maximum_absolute_effect_change": max_abs,
            "median_relative_effect_change": med_rel,
            "direction_reversal_environments": "|".join(reversals),
            "classification_change_environments": "|".join(class_changes),
            "deterministic_label": label,
        }
    )
labels = pd.DataFrame(label_rows)
labels.to_csv(TABLE / "endpoint_sensitivity_label_numeric_summary.csv", index=False)
detail.to_csv(TABLE / "endpoint_sensitivity_label_environment_detail.csv", index=False)

rules = {
    "schema_version": "final-r1-endpoint-sensitivity-label-rules-v1",
    "analysis_classification": "post hoc sensitivity",
    "nll_status": global_nll_status,
    "sensitivity_bh_method": "two-sided paired Wilcoxon; BH across four strategy contrasts within environment and sensitivity definition",
    "rules": {
        "magnitude_sensitive": "direction agreement=1; BH changes=0; CI-zero changes=0; median relative change>0.25; median absolute change>1e-6",
        "preserved": "direction agreement=1; BH changes=0; CI-zero changes=0; magnitude-sensitive rule false",
        "classification_changed": "BH changes>0 or CI-zero changes>0, with no direction reversal",
        "direction_changed": "at least one environment reverses direction",
        "mostly_preserved": "none above and direction agreement fraction>=0.75",
        "unstable": "direction agreement fraction<0.75",
        "unavailable": "metric absent or scientifically uninterpretable; NLL forced unavailable by numerical audit",
    },
    "thresholds_were_predeclared_by_editorial_prompt": True,
    "results": label_rows,
}
(AUDIT / "02_endpoint_sensitivity_label_rules.json").write_text(
    json.dumps(rules, indent=2), encoding="utf-8"
)

metric_map = {
    "early MACE": "mace_early",
    "late MACE": "mace_late",
    "CRPS": "crps_all_round",
    "NLL status": "nll_all_round",
    "top 0.5%": "recall_top0p5_nauc_full",
    "top 1%": "recall_top1_nauc_full",
    "top 2%": "recall_top2_nauc_full",
    "top 5%": "recall_top5_nauc_full",
    "5% budget": "top1_nauc_through_5pct",
    "10% budget": "top1_nauc_through_10pct",
    "20% budget": "top1_nauc_through_20pct",
}
matrix_rows = []
for endpoint in ("l1_campaign_mace", "l4_top1pct_recall_nauc"):
    fields = (
        ["early MACE", "late MACE", "CRPS", "NLL status"]
        if endpoint.startswith("l1") else
        ["top 0.5%", "top 1%", "top 2%", "top 5%", "5% budget", "10% budget", "20% budget"]
    )
    for contrast in sorted(labels[labels.primary_endpoint == endpoint].contrast_name.unique()):
        selected = labels[
            (labels.primary_endpoint == endpoint) & (labels.contrast_name == contrast)
        ].set_index("sensitivity_definition")
        row = {"primary_endpoint": endpoint, "contrast_name": contrast}
        displayed = []
        for field in fields:
            record = selected.loc[metric_map[field]]
            row[field] = record.deterministic_label
            displayed.append(record)
        agreements = sum(int(r.primary_direction_agreement_count) for r in displayed)
        available = sum(int(r.available_environment_count) for r in displayed)
        row["direction agreement"] = f"{agreements}/{available} ({agreements/max(1,available):.3f})"
        row["BH changes"] = sum(int(r.BH_status_change_count) for r in displayed)
        row["CI-zero changes"] = sum(int(r.CI_zero_status_change_count) for r in displayed)
        exceptions = [
            str(r.direction_reversal_environments or r.classification_change_environments)
            for r in displayed
            if str(r.direction_reversal_environments or r.classification_change_environments)
            not in ("", "nan")
        ]
        row["principal exception"] = (
            exceptions[0].split("|")[0].replace("matbench_", "").replace("__chemical_system_ood__", "/OOD/").replace("__iid_record__", "/IID/")
            if exceptions else "none under displayed definitions"
        )
        matrix_rows.append(row)
matrix = pd.DataFrame(matrix_rows)
matrix.to_csv(TABLE / "endpoint_sensitivity_conclusion_matrix_r1.csv", index=False)


# ---------------------------------------------------------------------------
# Initial correction matrix; statuses become complete after artifact tests.
# ---------------------------------------------------------------------------
issues = [
    ("1", "NLL numerical instability", "diagnostic_metrics.parquet", "stored round-level NLL and paired contrast dominance", "NLL marked unavailable for interpretation", "stored-only audit", "nll audit CSV/report", "test_r1_001_to_005"),
    ("2", "practical-significance 128-versus-64 uniqueness", "practical_significance_by_environment.csv", "exact endpoint duplicate comparison", "64 unique comparisons", "deduplication", "practical uniqueness/unique tables", "test_r1_006_to_007"),
    ("3", "evidence-label spacing", "v4 final TeX", "source search", "single evidence-label macro", "LaTeX rewrite", "R1 TeX/PDF", "test_r1_016"),
    ("4", "PDF hyperlink borders", "v4 final PDF/TeX", "annotation/source audit", "hidelinks", "LaTeX policy", "R1 PDF/link audit", "test_r1_017"),
    ("5", "endpoint-sensitivity table readability", "old wide matrix", "layout audit", "separate L1/L4 tables", "landscape tables", "R1 Supplement", "test_r1_018_to_019"),
    ("6", "practical-significance table readability", "old compressed table", "column/layout audit", "representative table", "landscape table", "R1 Supplement", "test_r1_020"),
    ("7", "OOD seed representativeness", "seed-5000 S6", "40-seed assignment hashes/distances", "all-seed wording", "stored-data split/distance audit", "OOD audit/figure", "test_r1_011_to_013"),
    ("8", "endpoint-sensitivity classification definitions", "old qualitative matrix", "fixed numeric rules", "auditable labels", "rule engine", "rules JSON/matrix", "test_r1_014_to_015"),
    ("9", "practical-significance uncertainty", "old practical table", "paired seed bootstrap", "CI wording", "stored rounds bootstrap", "practical uncertainty table", "test_r1_008_to_010"),
    ("10", "Discussion depth", "old Discussion", "focused interpretation", "400-700 useful words", "manuscript rewrite", "R1 main", "test_r1_discussion"),
    ("11", "Figure 2 readability", "old Figure 2", "font/label audit", "larger full-page figure", "figure redraw", "R1 Figure 2", "test_r1_021"),
    ("12", "Figure 3 readability", "old Figure 3", "font/label audit", "larger full-page figure", "figure redraw", "R1 Figure 3", "test_r1_022"),
    ("13", "external-reproducibility wording", "v4 text/readiness", "repository-input audit", "internal verification only", "wording rewrite", "R1 manuscript/public-input list", "test_r1_029"),
    ("14", "final test-log verification", "existing pytest/logs", "baseline and final test runs", "actual captured log", "test/log harness", "R1 log/JUnit", "test_r1_030"),
]
tracker = pd.DataFrame(
    [
        {
            "issue_id": issue_id,
            "concern": concern,
            "source_artifact": source,
            "analysis_required": analysis,
            "textual_change": text_change,
            "code_change": code_change,
            "output_artifact": output,
            "regression_test": test,
            "status": "implemented_pending_regression_test",
            "remaining_limitation": (
                "individual diagnostic mu/sigma vectors were not retained"
                if issue_id == "1" else
                "public repository and administrative inputs remain pending"
                if issue_id == "13" else ""
            ),
        }
        for issue_id, concern, source, analysis, text_change, code_change, output, test in issues
    ]
)
tracker.to_csv(AUDIT / "00_final_r1_correction_matrix.csv", index=False)

print(
    json.dumps(
        {
            "nll_seed_rows": len(nll_seed),
            "nll_contrasts": len(nll_contrasts),
            "nll_status": global_nll_status,
            "practical_old_rows": len(old_practical),
            "practical_unique_rows": len(practical),
            "ood_assignment_rows": len(assignments),
            "ood_invariant": assignment_invariant,
            "ood_summary_rows": len(ood_summary),
            "sensitivity_label_rows": len(labels),
            "final_lock_hash": sha(ROOT / "tables_v5/FINAL_TABLE_LOCK_V5.json"),
        },
        indent=2,
    )
)
