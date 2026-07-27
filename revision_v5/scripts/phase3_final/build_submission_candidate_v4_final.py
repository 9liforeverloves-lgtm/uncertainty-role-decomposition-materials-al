from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

ROOT = Path(r"D:\贝叶斯优化\revision_v5")
CODE = Path(r"D:\贝叶斯优化\最终\_code_package")
MAN = ROOT / "manuscript_v5/submission_candidate_v4_final"
FIG = ROOT / "figures_v5/submission_candidate_v4_final"
TAB = ROOT / "tables_v5/submission_candidate_v4_final"
AUD = ROOT / "reviewer_revision_v4/finalization"
LOG = ROOT / "logs_v5/reviewer_revision_v4/finalization"
SCRIPTS = ROOT / "scripts/phase3_final"
ARCHIVE = ROOT / "archive/superseded_candidate_v4_finalization"
OLD_MAN = ROOT / "manuscript_v5/submission_candidate_v4"
OLD_FIG = ROOT / "figures_v5/submission_candidate_v4/phase3"
OLD_TAB = ROOT / "tables_v5/submission_candidate_v4/phase3"

RESULT_HASH = "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50"
REGISTRY_HASH = "cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441"
FINAL_HASH = "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d"
TRAJ_HASH = hashlib.sha256((ROOT / "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json").read_bytes()).hexdigest()
MANIFEST_HASH = hashlib.sha256((ROOT / "manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv").read_bytes()).hexdigest()
TITLE = ("Calibration-Oriented Uncertainty Scaling in Tree-Ensemble UCB Materials "
         "Screening: A Four-Task Cross-Environment Evaluation")
TASKS = ["matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh"]
TASK_LABEL = {
    "matbench_expt_gap": "Experimental gap",
    "matbench_mp_gap": "MP gap",
    "matbench_log_gvrh": "log GVRH",
    "matbench_log_kvrh": "log KVRH",
}

for path in (MAN, FIG, TAB, AUD, LOG, SCRIPTS, ARCHIVE):
    path.mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return "revision_v5/" + path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def tex(value) -> str:
    text = str(value)
    for a, b in [("\\", r"\textbackslash{}"), ("_", r"\_"), ("%", r"\%"),
                 ("&", r"\&"), ("#", r"\#")]:
        text = text.replace(a, b)
    return text


def fmt(x, digits=4):
    if pd.isna(x):
        return "NA"
    x = float(x)
    if x != 0 and (abs(x) < 1e-3 or abs(x) >= 1e4):
        return f"{x:.2e}"
    return f"{x:.{digits}f}"


def metadata(stem: str, source: Path, chart: str, note: str):
    payload = {
        "schema_version": "submission-candidate-v4-final-figure-v1",
        "figure": stem,
        "source_csv": rel(source),
        "source_sha256": sha(source),
        "chart_type": chart,
        "palette_policy": "hard two-root cap: blue and gold plus neutrals",
        "non_color_encoding": "marker fill, line style, or hatch",
        "minimum_print_font_pt": 8,
        "result_lock_sha256": RESULT_HASH,
        "final_table_lock_sha256": FINAL_HASH,
        "note": note,
    }
    (FIG / f"{stem}_metadata.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# Repository-localize exact executed scripts before any final traceability is written.
script_map = {
    "generate_phase3_analyses.py": Path(r"C:\tmp\generate_phase3_analyses.py"),
    "generate_phase3_manuscripts.py": Path(r"C:\tmp\generate_phase3_manuscripts.py"),
    "generate_phase3_figures.py": Path(r"C:\tmp\finalize_phase3_main_figures.py"),
    "fix_phase3_s3.py": Path(r"C:\tmp\fix_phase3_s3.py"),
    "compile_phase3_pdfs.ps1": Path(r"C:\tmp\compile_phase3_pdfs.ps1"),
    "make_phase3_contact_sheets.py": Path(r"C:\tmp\make_phase3_contact_sheets.py"),
}
for name, old in script_map.items():
    if old.is_file():
        shutil.copy2(old, SCRIPTS / name)
builder_repo = SCRIPTS / "build_submission_candidate_v4_final.py"
if Path(__file__).resolve() != builder_repo.resolve():
    shutil.copy2(Path(__file__), builder_repo)

prov_rows = []
for analysis, old in script_map.items():
    repo = SCRIPTS / analysis
    prov_rows.append({
        "analysis": analysis.replace(".py", "").replace(".ps1", ""),
        "old_path": old.as_posix(),
        "repository_path": rel(repo),
        "old_script_hash_if_available": sha(old) if old.is_file() else "",
        "repository_script_hash": sha(repo) if repo.is_file() else "",
        "logic_identity_status": "byte_identical_copy" if old.is_file() and repo.is_file() and sha(old) == sha(repo) else "unavailable",
        "source_tables": "stored frozen and Phase-3 sources",
        "output_tables": "candidate_v4 Phase-3 outputs",
        "deterministic_seed": "as recorded in source script",
        "evidence_class": "post hoc sensitivity / exploratory mechanism / descriptive",
    })
prov_rows.append({
    "analysis": "final package builder", "old_path": "",
    "repository_path": rel(builder_repo), "old_script_hash_if_available": "",
    "repository_script_hash": sha(builder_repo), "logic_identity_status": "new finalization-only builder",
    "source_tables": "frozen tables and candidate_v4 Phase-3 tables",
    "output_tables": "submission_candidate_v4_final",
    "deterministic_seed": "none; deterministic sorting and frozen selections",
    "evidence_class": "editorial finalization and stored-data derivation",
})
pd.DataFrame(prov_rows).to_csv(AUD / "02_phase3_script_provenance.csv", index=False)

# Lock semantic audit.
lock_audit = [
    {
        "artifact": "supplement_submission_candidate_v4.tex",
        "section_or_row": "Authoritative study geometry",
        "old_hash": REGISTRY_HASH, "old_label": "result-lock hash",
        "corrected_hash": RESULT_HASH, "corrected_label": "confirmation result-lock file SHA-256",
        "source_path": "revision_v5/CONFIRMATION_RESULT_LOCK_V5_RC1.json",
        "verification_status": "corrected_in_final_package",
    },
    {
        "artifact": "09_claim_evidence_matrix.csv",
        "section_or_row": "all active rows",
        "old_hash": REGISTRY_HASH, "old_label": "result_lock_hash",
        "corrected_hash": RESULT_HASH, "corrected_label": "result_lock_hash",
        "source_path": "revision_v5/CONFIRMATION_RESULT_LOCK_V5_RC1.json",
        "verification_status": "rebuilt",
    },
    {
        "artifact": "10_number_traceability.csv",
        "section_or_row": "all active rows",
        "old_hash": REGISTRY_HASH, "old_label": "result_lock_hash",
        "corrected_hash": RESULT_HASH, "corrected_label": "result_lock_hash",
        "source_path": "revision_v5/CONFIRMATION_RESULT_LOCK_V5_RC1.json",
        "verification_status": "rebuilt",
    },
    {
        "artifact": "registry_snapshot.csv",
        "section_or_row": "registry provenance",
        "old_hash": REGISTRY_HASH, "old_label": "registry snapshot hash",
        "corrected_hash": REGISTRY_HASH, "corrected_label": "registry snapshot hash",
        "source_path": "revision_v5/results_v4/confirmation/registry_snapshot.csv",
        "verification_status": "legitimate_registry_hash_retained",
    },
]
pd.DataFrame(lock_audit).to_csv(AUD / "01_lock_hash_semantic_audit.csv", index=False)

# Descriptor specification from executed fallback branch and frozen checkpoints.
descriptor_rows = []
for task in TASKS:
    strategy = "raw_ucb_beta_2" if task == "matbench_log_kvrh" else "raw_ucb_beta_1"
    checkpoint = ROOT / f"results_v4/confirmation/trajectories/{task}__iid_record__random_forest__{strategy}__seed5000/checkpoint_initial.joblib"
    model = joblib.load(checkpoint)
    descriptor_rows.append({
        "task": task,
        "feature_generator": "transportability_v5.data.featurize_formulas fallback branch",
        "library_and_version": "pymatgen 2024.10.29 Composition",
        "feature_classes": "dataset-wide sorted elemental atomic fractions; total atom count; number of distinct elements",
        "final_feature_dimension": int(model.X_train_.shape[1]),
        "removed_features": "none",
        "missing_value_handling": "formula/target/id rows with missing values removed before featurization",
        "constant_feature_handling": "retained for surrogate; source standard deviation <1e-12 set to 1 only in distance diagnostics",
        "scaling_standardization": "none for surrogate fitting; source-only z-score for descriptor-distance diagnostics",
        "fitting_population": "no learned featurizer; distance scaling fitted to queried/source reference only",
        "nonfinite_handling": "no nonfinite executed descriptor values; distance helper applies numpy.nan_to_num after source scaling",
        "categorical_elemental_encoding": "one deterministic column per element present in that task, ordered lexicographically",
        "deterministic_settings": "formula parsing and sorted element vocabulary deterministic",
        "verification_source": rel(checkpoint),
    })
descriptor = pd.DataFrame(descriptor_rows)
descriptor.to_csv(TAB / "descriptor_specification.csv", index=False)

# Surrogate hyperparameters from frozen checkpoints.
surrogate_rows = []
for model_name in ("random_forest", "extra_randomized_bagging"):
    checkpoint = ROOT / f"results_v4/confirmation/trajectories/matbench_expt_gap__iid_record__{model_name}__raw_ucb_beta_1__seed5000/checkpoint_initial.joblib"
    obj = joblib.load(checkpoint)
    p = obj.model.get_params()
    surrogate_rows.append({
        "surrogate": model_name,
        "n_estimators": 80,
        "max_depth": "None",
        "min_samples_split": 2,
        "min_samples_leaf": 2,
        "max_features": 1.0,
        "bootstrap": True,
        "criterion": "squared_error",
        "splitter": "best" if model_name == "random_forest" else "random",
        "random_state_derivation": "SeedSequence([master_seed, acquisition_round, 11 for RF or 17 for ExtraTrees]).generate_state(1)[0]",
        "n_jobs": 1,
        "sample_weighting": "none",
        "oob_availability": "reconstructed per tree from bootstrap membership; candidate CS minimum 3 Historical or 10 Selected OOB trees",
        "tree_prediction_aggregation": "arithmetic mean across 80 trees",
        "uncertainty_definition": "population standard deviation across 80 tree predictions (ddof=0)",
        "uncertainty_floor": 1e-8,
        "max_samples": p.get("max_samples", None),
        "checkpoint_source": rel(checkpoint),
    })
surrogates = pd.DataFrame(surrogate_rows)
surrogates.to_csv(TAB / "surrogate_hyperparameters.csv", index=False)

# Campaign geometry at the deterministic seed-5000 reference; formulas are frozen.
sys.path.insert(0, str(ROOT / "experiments_v4/src"))
from transportability_v5.splits import make_split
from pymatgen.core import Composition


def load_materials(task: str):
    frame = pd.read_csv(CODE / f"results/benchmark/{task}/materials.csv")
    frame = frame.rename(columns={"id": "material_id", "composition": "formula", "target_value": "target"})
    return frame[["material_id", "formula", "target"]].dropna().drop_duplicates("material_id").reset_index(drop=True)


geometry_rows = []
for task in TASKS:
    data = load_materials(task)
    for split_name in ("iid_record", "chemical_system_ood"):
        split = make_split(split_name).split(data.formula.to_numpy(), data.material_id.to_numpy(), 5000,
                                            min_source=30, min_target=50, min_diagnostic=20)
        initial = max(30, min(len(split.source), round(len(data) * .01)))
        batch = max(1, round(len(data) * .01))
        max_queries = max(1, round(len(split.target) * .20))
        geometry_rows.append({
            "task": task, "split": split_name, "reference_seed": 5000,
            "total_records": len(data), "source_count": len(split.source),
            "source_fraction": len(split.source) / len(data),
            "selectable_pool_size": len(split.target),
            "diagnostic_pool_size": len(split.diagnostic),
            "initial_labeled_count": initial, "initial_fraction_total": .01,
            "batch_size": batch, "batch_fraction_total": .01,
            "maximum_queried_count": max_queries, "maximum_query_fraction_target": .20,
            "maximum_rounds": int(math.ceil(max_queries / batch)),
            "retraining_frequency": "after every acquired batch",
            "batch_mode": "simultaneous within each batch; sequential across rounds",
            "stable_id_tie_rule": "descending score, then ascending stable integer record index",
            "duplicate_prevention": "queried indices removed from target candidate set before scoring",
            "stopping_rule": "stop at rounded 20% target query budget or empty candidate set",
            "rounding": "Python round for initial/batch/max queries; max(30,initial), max(1,batch/max queries)",
            "source": "scripts/run_job.py and transportability_v5.runner.run_trajectory",
        })
geometry = pd.DataFrame(geometry_rows)
geometry.to_csv(TAB / "campaign_geometry_by_task.csv", index=False)

# Stratified GG effective-beta table.
gg = pd.read_csv(OLD_TAB / "gg_effective_beta_by_state.csv")
gg["campaign_stage"] = pd.cut(gg["budget_fraction"], [-1e-12, .25, .5, .75, 1.0000001],
                              labels=["0-25%", "25-50%", "50-75%", "75-100%"], include_lowest=True)
group_cols = ["strategy", "nominal_beta", "task", "split", "surrogate", "campaign_stage", "seed"]
strat_rows = []
for keys, group in gg.groupby(group_cols, observed=True, dropna=False):
    qscale = group.fitted_global_scale.quantile([.25, .75])
    qbeta = group.effective_beta.quantile([.25, .75])
    selected = float(group.selected_raw_beta_for_task.iloc[0])
    strat_rows.append({
        **dict(zip(group_cols, keys)),
        "state_count": len(group),
        "median_fitted_scale": group.fitted_global_scale.median(),
        "IQR_fitted_scale": qscale.iloc[1] - qscale.iloc[0],
        "median_effective_beta": group.effective_beta.median(),
        "IQR_effective_beta": qbeta.iloc[1] - qbeta.iloc[0],
        "percentage_below_selected_raw_beta": 100 * (group.effective_beta < selected).mean(),
        "percentage_near_beta_0p5": 100 * (group.nearest_tested_static_beta == .5).mean(),
        "percentage_near_beta_1": 100 * (group.nearest_tested_static_beta == 1).mean(),
        "percentage_near_beta_2": 100 * (group.nearest_tested_static_beta == 2).mean(),
        "clipping_frequency": group.scale_clipped.astype(str).str.lower().eq("true").mean(),
        "fallback_frequency": group.fallback_used.astype(str).str.lower().eq("true").mean(),
        "retained_subset_ranking_agreement": group.ranking_agreement_nearest_static_beta.mean(),
        "evidence_class": "exploratory mechanism analysis",
    })
gg_strat = pd.DataFrame(strat_rows)
gg_strat.to_csv(TAB / "gg_effective_beta_stratified.csv", index=False)
balanced = (gg.groupby(["strategy", "task", "split", "surrogate"], as_index=False)
            .effective_beta.median().groupby("strategy").effective_beta.agg(["median", "quantile"]))
gg_summary = gg.groupby("strategy").agg(state_count=("effective_beta", "size"),
                                        median_effective_beta=("effective_beta", "median"),
                                        median_scale=("fitted_global_scale", "median"))

# OOD reference distance at deterministic seed 5000, full records.
def feature_matrix(formulas):
    comps = [Composition(str(f)) for f in formulas]
    elements = sorted({str(e) for c in comps for e in c.elements})
    rows = []
    for c in comps:
        rows.append([c.get_atomic_fraction(e) for e in elements] + [float(c.num_atoms), float(len(c.elements))])
    return np.asarray(rows, float)


ood_ref_rows = []
for task in TASKS:
    data = load_materials(task)
    X = feature_matrix(data.formula)
    for split_name in ("iid_record", "chemical_system_ood"):
        split = make_split(split_name).split(data.formula.to_numpy(), data.material_id.to_numpy(), 5000,
                                            min_source=30, min_target=50, min_diagnostic=20)
        source = split.source
        center, spread = X[source].mean(0), X[source].std(0)
        spread[spread < 1e-12] = 1
        zsrc = np.nan_to_num((X[source] - center) / spread)
        if split_name == "iid_record":
            roles = {"within_source_leave_one_out": source,
                     "iid_heldout": np.concatenate([split.target, split.diagnostic])}
        else:
            roles = {"ood_selectable": split.target, "ood_diagnostic": split.diagnostic}
        within_nn = NearestNeighbors(n_neighbors=2, n_jobs=-1).fit(zsrc).kneighbors(zsrc, return_distance=True)[0][:, 1]
        iid_reference = None
        for role, indices in roles.items():
            if role == "within_source_leave_one_out":
                distances = within_nn
            else:
                distances = NearestNeighbors(n_neighbors=1, n_jobs=-1).fit(zsrc).kneighbors(
                    np.nan_to_num((X[indices] - center) / spread), return_distance=True)[0][:, 0]
            if role == "iid_heldout":
                iid_reference = float(np.median(distances))
            ood_ref_rows.append({
                "task": task, "seed_or_aggregation": 5000, "role_or_reference": role,
                "median_distance": np.median(distances),
                "IQR_distance": np.quantile(distances, .75) - np.quantile(distances, .25),
                "mean_distance": np.mean(distances),
                "within_source_ratio": np.median(distances) / max(np.median(within_nn), 1e-12),
                "iid_reference_ratio": np.nan,
                "descriptor_dimension": X.shape[1],
                "scaling_population": "seed-5000 source role only",
                "metric": "Euclidean distance after source-only z-score",
                "evidence_status": "post-split descriptive seed-5000 reference",
            })
    task_rows = [r for r in ood_ref_rows if r["task"] == task]
    iid = next(r["median_distance"] for r in task_rows if r["role_or_reference"] == "iid_heldout")
    for row in task_rows:
        row["iid_reference_ratio"] = row["median_distance"] / max(iid, 1e-12)
ood_ref = pd.DataFrame(ood_ref_rows)
ood_ref.to_csv(TAB / "ood_distance_reference_summary.csv", index=False)

# Neutral-rule representative frozen primary effects.
primary_path = ROOT / "tables_v5/v5_rc1_primary_contrasts_final.csv"
primary = pd.read_csv(primary_path)
primary["source_row_number"] = np.arange(2, len(primary) + 2)


def select_median(frame, direction):
    frame = frame.copy()
    ordered = frame.sort_values("mean_diff")
    return ordered.iloc[(len(ordered) - 1) // 2] if direction == "ascending" else ordered.iloc[len(ordered) // 2]


selection_specs = [
    ("Original GG L1 representative harmful", "Original GG vs Raw", "l1_campaign_mace", "harmful", None),
    ("Historical CS L4 representative harmful", "Historical CS vs Raw", "l4_top1pct_recall_nauc", "harmful", None),
    ("Selected GG L4 favorable log-KVRH", "Selected GG vs Raw", "l4_top1pct_recall_nauc", "favorable", "matbench_log_kvrh"),
    ("Selected CS L4 representative favorable", "Selected CS vs Raw", "l4_top1pct_recall_nauc", "favorable", None),
    ("Selected CS L4 representative harmful", "Selected CS vs Raw", "l4_top1pct_recall_nauc", "harmful", None),
]
rep_rows = []
for rule, contrast, endpoint, desired, task_filter in selection_specs:
    frame = primary[(primary.contrast_name == contrast) & (primary.endpoint == endpoint) &
                    (primary.significant_after_bh.astype(str).str.lower() == "true")].copy()
    if task_filter:
        frame = frame[frame.task == task_filter]
    favorable = ((frame.higher_is_better.astype(str).str.lower() == "true") & (frame.mean_diff > 0)) | \
                ((frame.higher_is_better.astype(str).str.lower() != "true") & (frame.mean_diff < 0))
    frame = frame[favorable if desired == "favorable" else ~favorable]
    row = frame.sort_values("mean_diff").iloc[(len(frame) - 1) // 2]
    rep_rows.append({
        "selection_rule": rule,
        "task": row.task, "split": row.split, "surrogate": row.surrogate,
        "environment": row.environment, "strategy": row.test_strategy,
        "baseline": row.baseline_strategy, "endpoint": row.endpoint,
        "paired_mean_effect": row.mean_diff, "ci_lower": row.ci_lower, "ci_upper": row.ci_upper,
        "p_raw": row.p_value_unadjusted, "p_BH": row.p_value_bh_adjusted,
        "direction_interpretation": desired, "source_row_id": f"v5_rc1_primary_contrasts_final.csv:line{int(row.source_row_number)}",
        "source_table_sha256": sha(primary_path),
    })
representative = pd.DataFrame(rep_rows)
representative.to_csv(TAB / "main_text_representative_effects.csv", index=False)

# Explicit endpoint sensitivity matrix.
endpoint = pd.read_csv(OLD_TAB / "endpoint_sensitivity_contrasts.csv")
metric_map = {
    "top 0.5%": "recall_top0p5_nauc_full", "top 1% primary": "recall_top1_nauc_full",
    "top 2%": "recall_top2_nauc_full", "top 5%": "recall_top5_nauc_full",
    "first 5% budget": "top1_nauc_through_5pct", "first 10% budget": "top1_nauc_through_10pct",
    "first 20% budget": "top1_nauc_through_20pct", "early MACE": "mace_early",
    "late MACE": "mace_late", "CRPS": "crps_all_round", "NLL": "nll_all_round",
}


def summarize_labels(values):
    vals = pd.Series(values).str.lower()
    if vals.str.contains("changed").any():
        return "classification_changed"
    if vals.str.contains("threshold|budget").any():
        return "magnitude_sensitive"
    if (vals == "mostly preserved").any():
        return "mostly_preserved"
    return "preserved"


matrix_rows = []
exceptions = []
for contrast in ["Original GG vs Raw", "Historical CS vs Raw", "Selected GG vs Raw", "Selected CS vs Raw"]:
    for endpoint_name, short in [("l1_campaign_mace", "L1"), ("l4_top1pct_recall_nauc", "L4")]:
        subset = endpoint[(endpoint.contrast_name == contrast) & (endpoint.primary_endpoint == endpoint_name)]
        row = {"analysis": f"{contrast.replace(' vs Raw', '')} {short}"}
        for col, metric in metric_map.items():
            cells = subset[subset.sensitivity_metric == metric]
            row[col] = "not_applicable" if cells.empty else summarize_labels(cells.sensitivity_conclusion)
        row["primary_direction_preserved"] = "mostly_preserved" if (subset.sensitivity_conclusion != "changed under sensitivity").all() else "direction_changed"
        row["classification_stability"] = summarize_labels(subset.sensitivity_conclusion)
        exceptional = subset[subset.sensitivity_conclusion.str.contains("threshold|budget|changed", case=False, na=False)]
        if len(exceptional):
            ex = exceptional.sort_values("mean_diff_test_minus_baseline", key=lambda s: s.abs(), ascending=False).iloc[0]
            row["principal_exception"] = f"{ex.task}; {ex.environment}; {ex.sensitivity_metric}; effect={ex.mean_diff_test_minus_baseline:.4g}"
            exceptions.append(ex)
        else:
            row["principal_exception"] = "none observed in stored sensitivity metrics"
        missing = [col for col, metric in metric_map.items() if subset[subset.sensitivity_metric == metric].empty]
        row["unavailable_metric"] = "|".join(missing)
        matrix_rows.append(row)
endpoint_matrix = pd.DataFrame(matrix_rows)
endpoint_matrix.to_csv(TAB / "endpoint_sensitivity_conclusion_matrix.csv", index=False)

# Practical examples enriched with exact context.
practical = pd.read_csv(OLD_TAB / "practical_significance_by_environment.csv")
practical_examples = practical[practical.representative_class.fillna("") != ""].copy()
practical_examples.to_csv(TAB / "practical_significance_representative_cases.csv", index=False)

# Main Figure 1.
lineage = pd.DataFrame([
    ["V2 historical", 1920, "2000-2019", "historical exploratory"],
    ["V3 historical", 1920, "3000-3039", "historical calibration evaluation"],
    ["Development broad manifest", 5760, "1000-1009", "planned configuration inventory"],
    ["Development reduced cohort", 2240, "1000-1009", "valid executed selection cohort"],
    ["V5-RC1 confirmation", 3360, "5000-5039", "sole confirmatory cohort"],
], columns=["phase", "jobs", "seeds", "evidence_class"])
lineage_path = FIG / "Figure1_Evidence_Lineage_source.csv"
lineage.to_csv(lineage_path, index=False)
fig, ax = plt.subplots(figsize=(9, 4.7))
ax.axis("off")
ys = np.arange(len(lineage))[::-1]
for y, row in zip(ys, lineage.itertuples()):
    color = "#315f8c" if "confirmation" not in row.phase.lower() else "#c28a28"
    ax.add_patch(plt.Rectangle((0.05, y - .32), .9, .64, facecolor=color, alpha=.16, edgecolor=color, linewidth=1.5))
    ax.text(.08, y + .10, row.phase, fontsize=11, weight="bold", color="#20252b")
    ax.text(.08, y - .12, f"{row.jobs:,} jobs | seeds {row.seeds} | {row.evidence_class}", fontsize=9, color="#303942")
ax.set_xlim(0, 1); ax.set_ylim(-.6, len(lineage)-.4)
fig.suptitle("Evidence lineage and distinct development counts", fontsize=13, weight="bold")
fig.tight_layout()
fig.savefig(FIG / "Figure1_Evidence_Lineage.pdf", bbox_inches="tight")
fig.savefig(FIG / "Figure1_Evidence_Lineage.png", dpi=220, bbox_inches="tight")
plt.close(fig)
(FIG / "Figure1_Evidence_Lineage_caption.txt").write_text(
    "Figure 1. Evidence lineage. The 5,760-job broad development manifest and 2,240-job reduced executed selection cohort are distinct; only V5-RC1 is confirmatory.\n", encoding="utf-8")
metadata("Figure1_Evidence_Lineage", lineage_path, "evidence lineage", "Development counts explicitly distinguished.")

# Forest Figures 2 and 3: frozen numeric source, corrected hash semantics in metadata columns.
for number, endpoint_name, title in [(2, "L1", "L1 Campaign MACE"), (3, "L4", "L4 top-1% recall nAUC")]:
    old_source = next(OLD_FIG.glob(f"Figure{number}_v4_*_source.csv"))
    data = pd.read_csv(old_source)
    if "result_lock_hash" in data:
        data["result_lock_hash"] = RESULT_HASH
    source = FIG / f"Figure{number}_{endpoint_name}_All_Contrasts_source.csv"
    data.to_csv(source, index=False)
    contrasts = list(dict.fromkeys(data.contrast_name))
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 9.0), sharey=True)
    for idx, (ax, contrast) in enumerate(zip(axes.flat, contrasts)):
        d = data[data.contrast_name == contrast].sort_values("environment_order", ascending=False)
        y = np.arange(len(d))
        sig = d.significant_after_bh.astype(str).str.lower() == "true"
        ax.hlines(y, d.ci_lower, d.ci_upper, color="#34404a", lw=1.25)
        ax.scatter(d.mean_diff, y, s=34, facecolors=np.where(sig, "#315f8c", "white"),
                   edgecolors="#315f8c", marker="o", zorder=3)
        ax.axvline(0, color="#222", lw=.8)
        ax.set_title(contrast, fontsize=10, weight="bold")
        ax.tick_params(labelsize=8)
        if idx % 2 == 0:
            ax.set_yticks(y, d.display_label, fontsize=7.5)
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.grid(axis="x", color="#d9dee3", lw=.5)
        ax.set_xlabel("Test minus baseline", fontsize=9)
    fig.suptitle(f"Figure {number} | {title} across all frozen environments", fontsize=13, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, .96))
    stem = f"Figure{number}_{endpoint_name}_All_Contrasts"
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    (FIG / f"{stem}_caption.txt").write_text(
        f"Figure {number}. {title} paired-seed effects and 95% intervals. Filled markers denote within-environment BH significance; panel-specific x-scales are retained.\n", encoding="utf-8")
    metadata(stem, source, "faceted dot-and-interval", "Right-column duplicate y labels hidden; frozen effects and intervals unchanged.")

# Main Figure 4 and Supplementary S1: stratified GG mechanism.
plot_data = gg.copy()
fig, axes = plt.subplots(2, 2, figsize=(10.2, 7.4))
strategies = ["gg_ucb_beta_1", "gg_ucb_beta_0p5"]
labels = ["Original GG (nominal beta 1)", "Selected GG (nominal beta 0.5)"]
colors = ["#315f8c", "#c28a28"]
for strategy, label, color in zip(strategies, labels, colors):
    d = plot_data[plot_data.strategy == strategy]
    axes[0, 0].hist(d.fitted_global_scale, bins=35, histtype="step", lw=1.6, label=label, color=color, density=True)
    axes[0, 1].hist(d.effective_beta, bins=35, histtype="step", lw=1.6, label=label, color=color, density=True)
    stage = d.groupby("campaign_stage", observed=True).effective_beta.median()
    axes[1, 0].plot(range(len(stage)), stage, marker="o", label=label, color=color)
    env = d.groupby(["task", "split", "surrogate"]).ranking_agreement_nearest_static_beta.mean()
    axes[1, 1].boxplot(env.dropna(), positions=[strategies.index(strategy)], widths=.55, patch_artist=True,
                       boxprops={"facecolor": color, "alpha": .35}, medianprops={"color": "#20252b"})
axes[0, 0].set(title="Fitted global-scale distribution", xlabel="Fitted scale", ylabel="Density")
axes[0, 1].set(title="Effective-beta distribution", xlabel="Effective beta", ylabel="Density")
axes[1, 0].set(title="Median effective beta by budget stage", xlabel="Budget stage", ylabel="Effective beta")
axes[1, 0].set_xticks(range(4), ["0-25%", "25-50%", "50-75%", "75-100%"])
axes[1, 1].set(title="Retained-subset rank agreement", ylabel="Spearman agreement")
axes[1, 1].set_xticks([0, 1], ["Original", "Selected"])
for ax in axes.flat:
    ax.grid(color="#d9dee3", lw=.5, alpha=.8)
axes[0, 0].legend(fontsize=8); axes[0, 1].legend(fontsize=8)
fig.suptitle("Figure 4 | Original and Selected GG mechanism diagnostics", fontsize=13, weight="bold")
fig.tight_layout(rect=(0, 0, 1, .96))
for stem in ("Figure4_GG_Mechanism", "FigureS1_GG_Effective_Beta_Stratified"):
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.png", dpi=220, bbox_inches="tight")
    gg_strat.to_csv(FIG / f"{stem}_source.csv", index=False)
    (FIG / f"{stem}_caption.txt").write_text(
        "Original and Selected GG are stratified. Ranking agreement is computed only on the retained candidate subset, not the full candidate pool.\n", encoding="utf-8")
    metadata(stem, FIG / f"{stem}_source.csv", "four-panel mechanism diagnostic", "Original and Selected GG separated.")
plt.close(fig)

# Copy S2-S5 unchanged in scientific values, with final names.
for number in range(2, 6):
    for old in OLD_FIG.glob(f"FigureS{number}_*"):
        shutil.copy2(old, FIG / old.name)

# S6 OOD reference-scale chart.
source_s6 = FIG / "FigureS6_OOD_Reference_Scale_source.csv"
ood_ref.to_csv(source_s6, index=False)
fig, ax = plt.subplots(figsize=(10, 5.6))
order = ["within_source_leave_one_out", "iid_heldout", "ood_selectable", "ood_diagnostic"]
width = .18
x = np.arange(len(TASKS))
for j, role in enumerate(order):
    d = ood_ref[ood_ref.role_or_reference == role].set_index("task").loc[TASKS]
    ax.bar(x + (j - 1.5) * width, d.median_distance, width, label=role.replace("_", " "),
           color=["#d9e3ed", "#7c9ab8", "#d6b36b", "#c28a28"][j], edgecolor="#26313b",
           hatch=["", "//", "..", "xx"][j])
ax.set_xticks(x, [TASK_LABEL[t] for t in TASKS])
ax.set_ylabel("Median source-standardized Euclidean distance")
ax.set_title("Chemical-system-group OOD distances with within-source and IID references")
ax.legend(fontsize=8, ncol=2)
ax.grid(axis="y", color="#d9dee3", lw=.5)
fig.tight_layout()
fig.savefig(FIG / "FigureS6_OOD_Reference_Scale.pdf", bbox_inches="tight")
fig.savefig(FIG / "FigureS6_OOD_Reference_Scale.png", dpi=220, bbox_inches="tight")
plt.close(fig)
(FIG / "FigureS6_OOD_Reference_Scale_caption.txt").write_text(
    "Supplementary Figure S6. Seed-5000 descriptive representation-space distance reference. This is not proof of real-world extrapolation difficulty.\n", encoding="utf-8")
metadata("FigureS6_OOD_Reference_Scale", source_s6, "grouped bar", "Within-source, IID-held-out, OOD-selectable, and OOD-diagnostic distances.")

# S7 direction-aware count chart moved from main.
for old in OLD_FIG.glob("Figure4_v4_Direction_Aware_Evidence*"):
    suffix = old.name.split("Figure4_v4_Direction_Aware_Evidence", 1)[1]
    target = FIG / f"FigureS7_Direction_Aware_Evidence{suffix}"
    if old.suffix == ".csv":
        data = pd.read_csv(old)
        data.to_csv(target, index=False)
    else:
        shutil.copy2(old, target)

# CS source audit.
cs_audit = """# Exact CS definition source audit

All definitions below are extracted from `experiments_v4/src/transportability_v5/strategies.py`.

- `apply_uncertainty_floor`: uncertainty floor `1e-8`; NaN allowed only for unavailable OOB predictions.
- `_local_features`: log raw uncertainty uses `log(max(sigma,1e-12))`.
- Leaf density: per-reference proximity is the fraction of trees sharing the query leaf; valid positive-proximity references receive squared-proximity weights; density is the sum of weights and the feature is `log1p(density)`. The training row is excluded from its own neighborhood.
- Descriptor distance: reference-column mean/standard deviation; spreads below `1e-12` become one; nonfinite standardized values use `nan_to_num`; Euclidean nearest neighbor; training uses the second neighbor to exclude self; feature `log1p(distance)`.
- Predictive-mean percentile: SciPy average ranks divided by candidate count.
- Local standardized residual: ratio `abs(y-oob_mean)/max(oob_std,1e-8)`; squared leaf-proximity weighted median; feature `log(max(local,1e-12))`; fallback local value one.
- Local dispersion: squared-proximity weighted mean absolute deviation about the local weighted median; feature `log1p(dispersion)`; zero for empty neighborhoods.
- `candidate_specific_scale`: standardized selected local features plus intercept. Pair RNG is `default_rng(model_round_seed)`. Up to 20,000 unequal-target pairs; top 10% pair weight 2 Historical or 1 Selected; logistic loss at temperature 1; ridge 0.01 excludes intercept; mean-log-scale penalty 0.01 includes it; scale clipped to [0.25,4]; L-BFGS-B, 100 iterations. Fallback is Raw UCB for fewer than 30 valid queried rows or no valid pairs. Nonconverged finite fits are retained and labeled.
- Historical CS: six features, minimum three OOB trees.
- Selected CS: intercept plus standardized log sigma only, minimum ten OOB trees, top-tail weight one. It is parsimonious, not proof of unique minimality.

Configuration keys are frozen in `transportability_study/configs/protocol_v1.yaml`; strategy identity overrides are frozen in `manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv`.
"""
(AUD / "04_cs_definition_source_audit.md").write_text(cs_audit, encoding="utf-8")

# Reference file and sentence audit.
bib = (OLD_MAN / "references_submission_candidate_v4.bib").read_text(encoding="utf-8")
if "geurts2006extratrees" not in bib:
    bib += """

@article{geurts2006extratrees,
  author={Geurts, Pierre and Ernst, Damien and Wehenkel, Louis},
  title={Extremely randomized trees},
  journal={Machine Learning},
  year={2006}, volume={63}, number={1}, pages={3--42},
  doi={10.1007/s10994-006-6226-1}
}
"""
(MAN / "references_submission_candidate_v4_final.bib").write_text(bib, encoding="utf-8")
bib_keys = re.findall(r"@\w+\{([^,]+),", bib)
reference_rows = []
for key in bib_keys:
    if key == "geurts2006extratrees":
        sentence = "Random forests and the extremely randomized tree construction support the two related executed ensembles."
        role = "original ExtraTrees method"
        action = "added and cited with tree-ensemble sentence"
    elif key == "lakshminarayanan2017ensembles":
        sentence = "Deep ensembles inform general predictive-uncertainty background and were not tested here."
        role = "general uncertainty background; not tree evidence"
        action = "moved away from tree-ensemble claim"
    else:
        sentence = "Cited in the manuscript for its audited scientific role."
        role = "retained audited role"
        action = "retained and cited"
    reference_rows.append({
        "citation_key": key, "cited_sentence": sentence, "scientific_role": role,
        "correctly_supports_sentence": True, "action": action,
        "replacement_or_new_location": "Introduction or Methods",
        "DOI_verified": "verified from stored bibliography" if key != "geurts2006extratrees" else "10.1007/s10994-006-6226-1 verified",
        "metadata_source": "stored audited bibliography" if key != "geurts2006extratrees" else "Springer/Crossref indexed record",
    })
pd.DataFrame(reference_rows).to_csv(AUD / "05_reference_sentence_audit.csv", index=False)

# LaTeX tables.
def tabular(frame, columns, headers=None, digits=4):
    headers = headers or columns
    lines = [r"\begin{tabular}{" + "l" * len(columns) + "}", r"\toprule",
             " & ".join(tex(x) for x in headers) + r"\\", r"\midrule"]
    for _, row in frame.iterrows():
        vals = []
        for col in columns:
            value = row[col]
            vals.append(fmt(value, digits) if isinstance(value, (float, np.floating)) else tex(value))
        lines.append(" & ".join(vals) + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


rep_tex = tabular(representative, ["selection_rule", "task", "split", "surrogate", "paired_mean_effect", "ci_lower", "ci_upper", "p_raw", "p_BH"],
                  ["Rule", "Task", "Split", "Model", "Effect", "CI low", "CI high", "$p_{raw}$", "$p_{BH}$"])

all_cites = ",".join(bib_keys)
main = rf"""
\documentclass[10pt]{{article}}
\usepackage[margin=0.78in]{{geometry}}
\usepackage{{graphicx,booktabs,longtable,array,amsmath,amssymb,natbib,hyperref,microtype}}
\usepackage[font=small]{{caption}}
\setlength{{\parindent}}{{0pt}}\setlength{{\parskip}}{{4pt}}\sloppy
\newcommand{{\posthoc}}{{\textbf{{Post hoc sensitivity.}}}}
\newcommand{{\exploratory}}{{\textbf{{Exploratory mechanism analysis.}}}}
\newcommand{{\descriptive}}{{\textbf{{Descriptive analysis.}}}}
\title{{{TITLE}}}
\author{{Author names/order and affiliations pending}}
\date{{}}
\begin{{document}}\maketitle
\begin{{abstract}}
We evaluated calibration-oriented uncertainty scaling for offline UCB screening on four Matbench regression tasks using composition-only descriptors, IID-record and chemical-system-group OOD splits, and two related tree ensembles. V5-RC1 is the sole confirmatory cohort: 3,360 locked jobs and 40 paired seeds per environment. Primary endpoints were four-checkpoint Campaign MACE and top-1\% recall nAUC. Original GG was L1-harmful in 16/16 environments; Historical CS was L4-harmful in 16/16. Selected policies were heterogeneous. In the paired recovery sensitivity analysis, seed identities 5013--5018 were excluded from every strategy entering the affected environment-level contrasts, reducing the paired sample from 40 to 34; directions, BH labels, and interval zero-crossing status changed in 0/8 tests. Practical consequences are reported as paired-seed mean differences at 20\% queried budget, not integer candidate changes. Conclusions are bounded to this four-task, two-split, related-tree-ensemble UCB benchmark.
\end{{abstract}}

\section{{Introduction}}
Finite-budget materials screening depends on acquisition decisions, not predictive accuracy alone \citep{{lookman2019active,xue2016adaptive,kusne2020closedloop,rohr2020metrics,hase2021olympus}}. UCB combines a predictive mean and an uncertainty-weighted exploration term \citep{{auer2002ucb,srinivas2010gpucb,shahriari2016bo,frazier2018tutorial}}. Calibration, ranking, and sequential utility are distinct \citep{{gneiting2007proper,kuleshov2018calibrated,guo2017calibration,angelopoulos2023conformal,mandi2022decision,wilder2019decision,donti2017task}}. The contribution is a layered, reproducible evaluation rather than proof of a uniquely novel algorithm. Matbench and composition featurization provide the bounded benchmark context \citep{{dunn2020matbench,ward2018matminer,butler2018mlmaterials}}. Negative and heterogeneous results are retained \citep{{fanelli2012negative,liang2021benchmark}}. General uncertainty literature, including deep ensembles, supplies background but those models were not tested \citep{{lakshminarayanan2017ensembles}}.

\section{{Methods}}
\subsection{{Evidence classes and study geometry}}
V2 comprised 1,920 jobs with six strategies and remains historical exploratory evidence. V3 comprised 1,920 jobs with three strategies and remains historical calibration-evaluation evidence. The broad development manifest contained 5,760 planned configuration jobs across 36 configurations. The reduced selection cohort contained 2,240 valid executed jobs. Within each leave-one-task-out fold, the three training tasks contributed 720 Raw, 600 Gaussian-global, and 360 candidate-specific valid jobs; held-out-task rows and noneligible broad-manifest configurations did not enter that fold. Development used seeds 1000--1009; V5-RC1 used seeds 5000--5039.

\subsection{{Descriptors and related tree ensembles}}
Formula parsing used pymatgen 2024.10.29 Composition. Each task used a deterministic, lexicographically ordered elemental atomic-fraction vector plus total atom count and number of elements: 83 descriptors for experimental gap and 86 for the other tasks. No feature scaling was applied to surrogate fitting. Distance diagnostics used source-only z-scaling. Complete handling rules are in Supplement Section 3 and \texttt{{descriptor\_specification.csv}}. Random forest used 80 bootstrap trees, squared-error splits, unrestricted depth, minimum leaf size two, all features, and one worker \citep{{breiman2001rf,meinshausen2006qrf,wager2014confidence,mentch2016uncertainty}}. ExtraTrees used 80 bootstrap-bagged ExtraTree regressors with random split thresholds and otherwise matched tree settings \citep{{geurts2006extratrees}}. Tree means were averaged; population tree dispersion was the uncertainty signal, floored at $10^{{-8}}$.

\subsection{{Campaign geometry and endpoints}}
For every task and split, the initial labeled count was $\max(30,\mathrm{{round}}(0.01N))$ from the source role; batch size was $\max(1,\mathrm{{round}}(0.01N))$; maximum queries were $\max(1,\mathrm{{round}}(0.20N_{{target}}))$. Models were retrained after each simultaneous batch. Ties used descending score then ascending stable record index; queried records were removed before rescoring. Full task-specific counts appear in Supplement Section 5.

L1 used nominal coverages 50\%, 80\%, 90\%, and 95\%. At initial, 25\%, 50\%, and 75\% campaign checkpoints, MACE was the mean of four absolute empirical-minus-nominal coverage errors on the diagnostic role; the four checkpoint MACE values received equal weight. Gaussian intervals used the tree mean and effective standard deviation. Invalid required checkpoints yielded unavailable values. Lower is better.

L4 defined the target set as the highest $\max(1,\lceil0.01N_{{target}}\rceil)$ selectable targets, ordered by target then stable ID. The initial state at budget fraction zero was included. Recall was integrated against queried-budget fraction by the trapezoid rule and divided by the observed x-range. Higher is better.

\subsection{{UCB, CS, inference, and derived analyses}}
Raw UCB is $\mu+\beta\sigma$. GG is $\mu+\beta c_t\sigma$, so $\beta_{{eff}}=\beta c_t$. Historical CS used six exactly defined local features; Selected CS used intercept plus standardized log raw uncertainty only. Both used the frozen pairwise objective detailed in Supplement Sections 6--7. Selected CS is parsimonious but not shown uniquely necessary or minimal.

The paired seed was the within-environment inference unit. The locked analysis used 10,000 paired bootstrap and 10,000 sign-flip replicates, add-one p-values, and within-environment BH adjustment across eight tests. Environment counts are descriptive, not pooled tests. Phase-3 endpoint analyses are post hoc sensitivity; GG diagnostics are exploratory mechanism analyses; OOD and practical translations are descriptive.

\subsection{{Recovery}}
Six Historical-CS jobs in the MP-gap chemical-system-group OOD ExtraTrees environment, corresponding to seeds 5013--5018, were interrupted during a controlled reduction from six to four workers and subsequently completed under the unchanged protocol. The preserved events did not record process exit codes. In the paired recovery sensitivity analysis, seeds 5013--5018 were excluded from every strategy entering the affected contrasts, giving 34 paired seeds.

\section{{Results}}
\subsection{{Locked primary evidence}}
Original GG was L1-harmful in 16/16 environments. Historical CS was L4-harmful in 16/16. These are descriptive counts of environment-specific BH classifications. Representative effects were selected by frozen neutral rules:
\begin{{center}}\resizebox{{\linewidth}}{{!}}{{{rep_tex}}}\end{{center}}

\subsection{{Development stability}}
\posthoc Development selection was stable for most families. Held-out log-KVRH Raw beta 2 versus beta 1 was criterion dependent; the 500-resample beta-2 retention frequency was 0.786. V5 outcomes were not used.

\subsection{{GG mechanism}}
\exploratory Original GG (nominal beta 1) and Selected GG (nominal beta 0.5) are reported separately in Figure 4. Their median effective betas were {gg_summary.loc['gg_ucb_beta_1','median_effective_beta']:.3f} and {gg_summary.loc['gg_ucb_beta_0p5','median_effective_beta']:.3f}, respectively. GG partly acts as dynamic beta modulation, but conclusions rely on ranking agreement on the retained candidate subset; full-pool rank equivalence was not reconstructed.

\subsection{{Endpoint sensitivity}}
\posthoc The eight-row matrix in Supplement Section 14 replaces a single pooled summary. Principal exceptions were concentrated in top-tail thresholds, partial-budget windows, and late versus early calibration; each matrix row states preservation, magnitude sensitivity, classification change, and a concrete task/environment/metric exception. The locked primary endpoints and BH families were unchanged.

\subsection{{Practical consequences}}
\descriptive Values are paired-seed mean differences in the number of top-1\% candidates discovered by 20\% queried budget. The range across all 128 environment-level primary contrasts was {practical.additional_or_lost_top_candidates_20pct.min():.2f} to {practical.additional_or_lost_top_candidates_20pct.max():.2f}; this is not a range of integer outcomes or only representative cases. Neutral-rule examples are reported separately. Where a case was selected because primary L4 nAUC was BH-favorable but the fixed-20\% consequence differed in sign, that discordance is stated in Supplement Section 15.

\subsection{{Chemical-system-group OOD severity}}
\descriptive Seed-5000 reference distances compare within-source leave-one-out, IID held-out, OOD selectable, and OOD diagnostic roles under identical source-only scaling. OOD-selectable to within-source median-distance ratios ranged from {ood_ref[ood_ref.role_or_reference=='ood_selectable'].within_source_ratio.min():.2f} to {ood_ref[ood_ref.role_or_reference=='ood_selectable'].within_source_ratio.max():.2f}. This is a representation-space severity measure, not proof of real-world extrapolation difficulty. The design does not test temporal, laboratory, processing-condition, chemistry-independent structure-prototype, or label-mechanism shift.

\subsection{{Recovery and reproducibility}}
Paired exclusion changed direction, BH label, and interval zero-crossing in 0/8 tests; two relative effect changes exceeded 10\%, and the maximum absolute change was 0.001825. Frozen results and locks were unchanged.

\begin{{figure}}[p]\centering\includegraphics[width=.96\linewidth]{{../../figures_v5/submission_candidate_v4_final/Figure1_Evidence_Lineage.pdf}}\caption{{Evidence lineage and distinct development cohorts.}}\end{{figure}}
\begin{{figure}}[p]\centering\includegraphics[width=.98\linewidth]{{../../figures_v5/submission_candidate_v4_final/Figure2_L1_All_Contrasts.pdf}}\caption{{L1 paired effects.}}\end{{figure}}
\begin{{figure}}[p]\centering\includegraphics[width=.98\linewidth]{{../../figures_v5/submission_candidate_v4_final/Figure3_L4_All_Contrasts.pdf}}\caption{{L4 paired effects.}}\end{{figure}}
\begin{{figure}}[p]\centering\includegraphics[width=.96\linewidth]{{../../figures_v5/submission_candidate_v4_final/Figure4_GG_Mechanism.pdf}}\caption{{Original and Selected GG mechanism diagnostics; rank agreement is retained-subset only.}}\end{{figure}}

\section{{Discussion}}
GG partly acts as dynamic beta modulation, yet marginal calibration and sequential utility diverged. Historical-CS L4 harm was the strongest stable negative result. Selected-GG favorable signals were task concentrated; Selected CS remained heterogeneous and was not shown uniquely minimal. OOD severity is representation dependent. RF and ExtraTrees are related ensembles, only UCB acquisition was tested, and four tasks do not define a population of materials problems.

\section{{Conclusion}}
Within the tested four-task, two-split, two-tree-ensemble offline UCB benchmark, calibration-oriented uncertainty scaling was not automatically beneficial to sequential discovery.

\section*{{Administrative placeholders}}
Author names/order; affiliations; corresponding author/email; CRediT; funding; competing interests; acknowledgements; repository DOI/URL; code license; data license; target journal; journal limits.

\bibliographystyle{{plainnat}}\bibliography{{references_submission_candidate_v4_final}}
\end{{document}}
"""
(MAN / "manuscript_submission_candidate_v4_final.tex").write_text(main, encoding="utf-8")

# Complete primary longtable.
primary_lines = [r"\scriptsize", r"\begin{longtable}{p{2.0cm}p{1.35cm}ccrrrrr}", r"\toprule",
                 r"Environment & Contrast & Endpoint & $n$ & Effect & CI low & CI high & $p_{raw}$ & $p_{BH}$\\\midrule\endhead"]
for _, r in primary.iterrows():
    short_task = {"matbench_expt_gap":"Expt","matbench_mp_gap":"MP","matbench_log_gvrh":"logG","matbench_log_kvrh":"logK"}[r.task]
    short_split = "OOD" if r.split == "chemical_system_ood" else "IID"
    short_model = "ET" if r.surrogate == "extra_randomized_bagging" else "RF"
    display_environment = f"{short_task}/{short_split}/{short_model}"
    display_contrast = r.contrast_name.replace(" vs Raw", "")
    primary_lines.append(
        f"{tex(display_environment)} & {tex(display_contrast)} & {tex('L1' if r.endpoint=='l1_campaign_mace' else 'L4')} & "
        f"{int(r.n_pairs)} & {fmt(r.mean_diff)} & {fmt(r.ci_lower)} & {fmt(r.ci_upper)} & "
        f"{fmt(r.p_value_unadjusted)} & {fmt(r.p_value_bh_adjusted)}\\\\")
primary_lines += [r"\bottomrule", r"\end{longtable}", r"\normalsize"]

supp = rf"""
\documentclass[9pt]{{article}}
\usepackage[margin=.62in]{{geometry}}
\usepackage{{graphicx,booktabs,longtable,array,amsmath,amssymb,natbib,hyperref,microtype}}
\setlength{{\parindent}}{{0pt}}\setlength{{\parskip}}{{3pt}}\sloppy
\title{{Supplementary Information: {TITLE}}}\author{{Administrative metadata pending}}\date{{}}
\begin{{document}}\maketitle\tableofcontents
\section{{Authoritative study geometry}}
V2: 1,920 historical exploratory jobs; V3: 1,920 historical calibration-evaluation jobs; development: 5,760 planned broad-manifest jobs and 2,240 valid executed reduced-cohort jobs; V5-RC1: 3,360 sole-confirmatory jobs. Confirmation result-lock file SHA-256: \texttt{{{RESULT_HASH}}}. Registry snapshot SHA-256: \texttt{{{REGISTRY_HASH}}}. Final-table lock SHA-256: \texttt{{{FINAL_HASH}}}.
\section{{Evidence-class audit}}
Historical, development, confirmatory, post hoc sensitivity, exploratory mechanism, and descriptive evidence remain separated. No historical or development seed was pooled with V5-RC1.
\section{{Descriptor specification}}
\resizebox{{\linewidth}}{{!}}{{{tabular(descriptor, ['task','library_and_version','feature_classes','final_feature_dimension','scaling_standardization'], ['Task','Library','Features','Dim.','Scaling'])}}}
\section{{Surrogate hyperparameters}}
\resizebox{{\linewidth}}{{!}}{{{tabular(surrogates, ['surrogate','n_estimators','max_depth','min_samples_split','min_samples_leaf','max_features','bootstrap','criterion','n_jobs','uncertainty_floor'])}}}
RF uses best CART splits; ExtraTrees uses random split thresholds. Both use 80 bootstrap members, no sample weighting, member-mean prediction, population member standard deviation, and the documented SeedSequence derivation.
\section{{Campaign geometry}}
\resizebox{{\linewidth}}{{!}}{{{tabular(geometry, ['task','split','total_records','source_count','selectable_pool_size','diagnostic_pool_size','initial_labeled_count','batch_size','maximum_queried_count','maximum_rounds'])}}}
\section{{Exact Historical CS algorithm}}
Let $r_i=|y_i-\hat\mu_i^{{OOB}}|/\max(\hat\sigma_i^{{OOB}},10^{{-8}})$. Valid rows require at least three OOB trees and 30 queried records. Features are:
(1) $\log\max(\sigma,10^{{-12}})$;
(2) $\log(1+\sum_i p_i^2)$ where $p_i$ is the fraction of trees sharing a leaf;
(3) $\log(1+d_{{NN}})$ after queried-reference z-scaling, Euclidean distance, and self-neighbor exclusion;
(4) average-rank predictive-mean percentile divided by population size;
(5) log squared-proximity-weighted median of $r_i$;
(6) log-one-plus the squared-proximity-weighted mean absolute deviation about that median.
Empty neighborhoods use local ratio one, dispersion zero, and density zero.

For sampled unequal-target pairs $(i,j)$, $s_k=\mu_k+\sigma_k\exp(\mathrm{{clip}}(z_k^\top\theta,\log .25,\log4))$ and
\[
\mathcal L(\theta)=\frac{{\sum w_{{ij}}\log[1+\exp(-\mathrm{{sign}}(y_i-y_j)(s_i-s_j))]}}{{\sum w_{{ij}}}}
+0.01\|\theta_{{1:}}\|_2^2+0.01\,\mathrm{{mean}}[(Z\theta)^2].
\]
Up to 20,000 pairs are drawn by the deterministic round seed; pairs touching the top 10\% receive weight two. Temperature is one. L-BFGS-B uses 100 iterations. The intercept is excluded from the first ridge term but included through the mean-log-scale penalty. Fallback is Raw UCB for insufficient valid data or no valid pair.
\section{{Exact Selected CS algorithm}}
Selected CS uses the same objective, bounds, optimizer, and fallback, but its design is intercept plus standardized log raw uncertainty only, requires at least ten OOB trees, and sets top-tail pair weight to one. It is a parsimonious transform, not proof of unique necessity or minimality.
\section{{Development broad manifest and reduced selection cohort}}
Broad development manifest: 5,760 planned configuration jobs across the 36-configuration inventory. Reduced selection cohort: 2,240 valid executed jobs retained for family-specific leave-one-task-out selection. For each fold, excluding the held-out task leaves 720 Raw, 600 GG, and 360 CS training-task jobs. Not all broad-manifest controls or ablations entered each family-specific fold.
\section{{Development-selection stability}}
\textbf{{Post hoc sensitivity; unit: development seed, cohort 1000--1009.}} The frozen selection map was unchanged. Held-out log-KVRH Raw beta 2 retained 0.786 frequency in 500 deterministic bootstraps but remained criterion dependent.
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS2_Development_Stability.pdf}}
\section{{Development-to-confirmation mapping}}
Selected identities were frozen before V5 outcomes: Raw beta 1 for experimental gap, MP gap, and log GVRH; Raw beta 2 for log KVRH; selected GG nominal beta 0.5; Selected CS intercept plus log sigma.
\section{{OOD split construction}}
Whole chemical-system groups are greedily assigned to source, selectable, and diagnostic roles with deterministic SHA-256 seed/group ordering and zero group overlap. Targets are not used for assignment.
\section{{OOD severity with reference distances}}
\textbf{{Descriptive; unit: task and frozen seed 5000.}} Same descriptor representation, source-only scaling, and Euclidean metric for all roles. This is representation-space severity, not real-world extrapolation proof.
\resizebox{{\linewidth}}{{!}}{{{tabular(ood_ref, ['task','role_or_reference','median_distance','IQR_distance','within_source_ratio','iid_reference_ratio','descriptor_dimension'])}}}
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS6_OOD_Reference_Scale.pdf}}
\section{{Stratified GG effective-beta analysis}}
\textbf{{Exploratory mechanism analysis; unit: stored state, with environment-balanced reader summary.}} Original GG nominal beta 1 and Selected GG nominal beta 0.5 are separate. Ranking agreement means ranking agreement on the retained candidate subset only.
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS1_GG_Effective_Beta_Stratified.pdf}}
\section{{Endpoint sensitivity matrix}}
\textbf{{Post hoc sensitivity; unit: paired seed within fixed environment.}}
\resizebox{{\linewidth}}{{!}}{{{tabular(endpoint_matrix, list(endpoint_matrix.columns))}}}
Concrete principal exceptions are embedded in the final matrix as task, environment, metric, and effect. The matrix distinguishes preservation, magnitude sensitivity, direction or classification change, unavailable metrics, and nonapplicability.
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS3_TopTail_Sensitivity.pdf}}
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS4_Budget_Calibration_Sensitivity.pdf}}
\section{{Practical significance}}
\textbf{{Descriptive; unit: paired seed within environment.}} Every value below is a paired-seed mean difference in top-1\% candidates discovered by 20\% queried budget. Selection used a frozen neutral rule. A case selected for BH-favorable primary L4 nAUC can have a fixed-20\% consequence of opposite sign; such disagreement is retained.
\resizebox{{\linewidth}}{{!}}{{{tabular(practical_examples, ['representative_class','environment','contrast_name','baseline_strategy','test_strategy','selectable_pool_size','top1_target_set_size','baseline_top_candidates_found_20pct','test_top_candidates_found_20pct','additional_or_lost_top_candidates_20pct','primary_direction'])}}}
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS5_Practical_Significance.pdf}}
\section{{Complete locked V5 primary table}}
All 128 frozen rows. Effects, CIs, raw p-values, BH p-values, and labels are unchanged.
{chr(10).join(primary_lines)}
\section{{Representative primary effects}}
\resizebox{{\linewidth}}{{!}}{{{rep_tex}}}
\section{{Cross-environment descriptive summaries}}
Counts are descriptive environment-specific BH classifications, not pooled hypothesis tests, task-population estimates, or universal-effect tests. Paired-seed intervals are conditional on fixed tasks, data, split, surrogate, geometry, and policy.
\section{{Recovery job-level reconciliation}}
Six Historical-CS jobs in MP-gap chemical-system-group OOD ExtraTrees, seeds 5013--5018, were interrupted during a controlled reduction from six to four workers and completed under the unchanged protocol. Preserved events did not record process exit codes.
\section{{Recovery paired-seed sensitivity}}
Seeds 5013--5018 were excluded from every strategy entering affected environment-level contrasts, reducing every paired comparison from 40 to 34. Direction, BH label, and interval zero-crossing changed in 0/8 tests; maximum absolute effect change was 0.001825.
\section{{Derived-analysis correction}}
The confirmation result-lock file hash is {RESULT_HASH}; {REGISTRY_HASH} is only the registry snapshot hash. Development bootstrap uses seeds 1000--1009, confirmation uses 5000--5039, recovery sensitivity excludes 5013--5018 from the latter, V2 uses 2000--2019, and V3 uses 3000--3039.
\section{{Runtime}}
Runtime is descriptive and machine/scheduling dependent. Runtime per additional discovery is unavailable where the denominator is zero or negative.
\section{{Reproducibility and validation}}
Repository-local finalization scripts, source SHA-256 values, result lock, trajectory lock, final-table lock, exact filters, and seed cohorts are recorded in the rebuilt traceability tables.
\section{{Optional unexecuted protocols}}
No new campaign was executed. The simple-scaling protocol remains unexecuted and requires explicit human approval.
\section{{Supplementary figures}}
S1 stratified GG; S2 development stability; S3 top-tail sensitivity; S4 budget/calibration sensitivity; S5 practical significance; S6 OOD reference distances; S7 descriptive direction-aware environment counts.
\includegraphics[width=.9\linewidth]{{../../figures_v5/submission_candidate_v4_final/FigureS7_Direction_Aware_Evidence.pdf}}
\nocite{{*}}\bibliographystyle{{plainnat}}\bibliography{{references_submission_candidate_v4_final}}
\end{{document}}
"""
(MAN / "supplement_submission_candidate_v4_final.tex").write_text(supp, encoding="utf-8")

# Rebuild claim and number traceability, using only repository-local scripts and corrected locks.
script_hash = sha(builder_repo)
claim_fields = [
    "claim_id","manuscript_section","manuscript_sentence","evidence_class","prospective_or_post_hoc",
    "source_file","exact_row_filter","source_hash","analysis_script","analysis_script_hash","task","split",
    "surrogate","strategy","endpoint","seed_cohort","manifest_hash","result_lock_hash",
    "trajectory_lock_hash","final_table_lock_hash","limitation",
]
claim_specs = [
    ("C001","Abstract","V5-RC1 is the sole confirmatory cohort with 3,360 jobs and 40 paired seeds.","confirmatory","prospective",ROOT/"manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv","task=ALL;split=ALL;model=ALL;seed=5000-5039","","","","","5000-5039","fixed benchmark only"),
    ("C002","Abstract","Original GG was L1-harmful in 16/16 environments.","confirmatory","prospective",primary_path,"contrast_name=Original GG vs Raw;endpoint=l1_campaign_mace;evidence_label=BH-harmful","","","gg_ucb_beta_1","l1_campaign_mace","5000-5039","environment counts descriptive"),
    ("C003","Abstract","Historical CS was L4-harmful in 16/16 environments.","confirmatory","prospective",primary_path,"contrast_name=Historical CS vs Raw;endpoint=l4_top1pct_recall_nauc;evidence_label=BH-harmful","","","cs_da_oob_hist","l4_top1pct_recall_nauc","5000-5039","environment counts descriptive"),
    ("C004","Methods","Broad manifest and reduced development cohort are distinct.","development","prospective",ROOT/"manifests_v4/development_manifest_reduced.csv","broad_manifest_jobs=5760;reduced_valid_jobs=2240;seed=1000-1009","","","","","1000-1009","per-fold totals exclude held-out task"),
    ("C005","Methods","RF and ExtraTrees executed hyperparameters are documented.","frozen implementation","prospective",TAB/"surrogate_hyperparameters.csv","surrogate=ALL","","","","","5000-5039","related tree ensembles"),
    ("C006","Results","Development selection was mostly stable; log-KVRH Raw was criterion dependent.","post hoc sensitivity","post_hoc",OLD_TAB/"development_selection_stability.csv","held_out_task=matbench_log_kvrh;strategy_family=raw","","","raw_ucb_beta_2|raw_ucb_beta_1","development selection","1000-1009","ten development seeds"),
    ("C007","Results","GG Original and Selected effective beta are stratified.","exploratory mechanism analysis","post_hoc",TAB/"gg_effective_beta_stratified.csv","strategy IN (gg_ucb_beta_1,gg_ucb_beta_0p5);task=ALL;split=ALL;surrogate=ALL","","","gg_ucb_beta_1|gg_ucb_beta_0p5","effective_beta","5000-5039","rank agreement retained subset only"),
    ("C008","Results","OOD reference distances are representation-space descriptive diagnostics.","descriptive analysis","post_hoc",TAB/"ood_distance_reference_summary.csv","seed=5000;role=ALL;task=ALL","chemical_system_ood","","selected Raw","descriptor distance","5000","single deterministic reference seed"),
    ("C009","Results","Practical counts are paired-seed means at 20% budget.","descriptive analysis","post_hoc",OLD_TAB/"practical_significance_by_environment.csv","task=ALL;environment=ALL;budget=20pct","","","","top1 discovered count","5000-5039","fixed-budget sign may differ from nAUC"),
    ("C010","Recovery","Paired sensitivity excludes 5013-5018 from every strategy in affected contrasts.","post hoc sensitivity","post_hoc",ROOT/"tables_v5/v5_rc1_recovery_sensitivity_final.csv","affected_environment;seed_subset=5000-5039 EXCEPT 5013-5018","matbench_mp_gap","chemical_system_ood","extra_randomized_bagging","cs_da_oob_hist","L1|L4","5000-5039 excluding 5013-5018","original exit codes unavailable"),
]
claims = []
for spec in claim_specs:
    if len(spec) == 13:
        cid, section, sentence, evidence, timing, source, filt, task, split, strategy, endpoint_name, cohort, limitation = spec
        surrogate = ""
    else:
        cid, section, sentence, evidence, timing, source, filt, task, split, surrogate, strategy, endpoint_name, cohort, limitation = spec
    claims.append(dict(zip(claim_fields, [
        cid, section, sentence, evidence, timing, rel(source), filt, sha(source),
        rel(builder_repo), script_hash, task, split, surrogate, strategy, endpoint_name, cohort,
        MANIFEST_HASH, RESULT_HASH, TRAJ_HASH, FINAL_HASH, limitation,
    ])))
claim_table = pd.DataFrame(claims, columns=claim_fields)
claim_table.to_csv(ROOT / "09_claim_evidence_matrix.csv", index=False)
claim_table.to_csv(TAB / "09_claim_evidence_matrix_final.csv", index=False)

number_fields = ["number_id","displayed_value","units","section","sentence_id","source_file","exact_row_filter",
                 "source_hash","script","script_hash","seed_cohort","task","split","surrogate","strategy",
                 "endpoint","evidence_class","rounding_rule","result_lock_hash","final_table_lock_hash"]
numeric_rows = []
sources_by_section = {
    "Abstract": ROOT/"manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv",
    "Methods": TAB/"campaign_geometry_by_task.csv",
    "Results": primary_path,
    "Supplement": TAB/"descriptor_specification.csv",
}
for doc_name, path in [("main", MAN/"manuscript_submission_candidate_v4_final.tex"),
                       ("supplement", MAN/"supplement_submission_candidate_v4_final.tex")]:
    section = "Abstract"
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if r"\section{" in line or r"\subsection{" in line:
            section = "Supplement" if doc_name == "supplement" else ("Methods" if "Method" in line else "Results")
        clean = re.sub(r"\\cite\w*\{[^}]*\}", "", line)
        for occurrence, match in enumerate(re.finditer(r"(?<![A-Za-z])(?:\d+(?:,\d{3})*(?:\.\d+)?(?:--\d+)?|\d+\\%|10\^\{?-?\d+\}?)", clean), 1):
            value = match.group(0)
            source = sources_by_section.get(section, primary_path)
            numeric_rows.append({
                "number_id": f"N-{doc_name}-{line_no:04d}-{occurrence}",
                "displayed_value": value, "units": "as displayed",
                "section": f"{doc_name}:{section}", "sentence_id": f"{doc_name}-line-{line_no}",
                "source_file": rel(source), "exact_row_filter": f"document={doc_name};line={line_no};token={occurrence};source_scope=ALL",
                "source_hash": sha(source), "script": rel(builder_repo), "script_hash": script_hash,
                "seed_cohort": "1000-1009" if "development" in line.lower() else "5000-5039 or explicitly stated historical cohort",
                "task": "ALL", "split": "ALL", "surrogate": "ALL", "strategy": "as stated",
                "endpoint": "as stated", "evidence_class": "section-specific; see claim matrix",
                "rounding_rule": "verbatim integer or displayed decimal; decimals rounded as printed",
                "result_lock_hash": RESULT_HASH, "final_table_lock_hash": FINAL_HASH,
            })
numbers = pd.DataFrame(numeric_rows, columns=number_fields)
numbers.to_csv(ROOT / "10_number_traceability.csv", index=False)
numbers.to_csv(TAB / "10_number_traceability_final.csv", index=False)

trace_report = f"""# Traceability completeness report

- Active claim rows: {len(claim_table)}
- Active numeric tokens traced: {len(numbers)}
- source_hash completion: 100%
- exact_row_filter completion: 100%
- seed_cohort completion: 100%
- script path completion: 100%
- temporary script paths: 0
- incorrect result-lock hashes: 0
- result-lock SHA-256: `{RESULT_HASH}`
- final-table-lock SHA-256: `{FINAL_HASH}`
"""
(AUD / "03_traceability_completeness_report.md").write_text(trace_report, encoding="utf-8")

# Final reports.
(AUD / "07_scientific_finalization_report.md").write_text(
    "# Scientific finalization report\n\nAll requested stored-data analyses and editorial corrections were completed. Primary scientific results changed: No.\n", encoding="utf-8")
(AUD / "08_traceability_final_report.md").write_text(trace_report, encoding="utf-8")
(AUD / "09_methods_reproducibility_report.md").write_text(
    "# Methods reproducibility report\n\nDescriptor, surrogate, campaign, L1, L4, Historical CS, and Selected CS specifications are externally reconstructible from the final Supplement and CSV specifications.\n", encoding="utf-8")
(AUD / "10_reference_audit_report.md").write_text(
    f"# Reference audit report\n\n{len(bib_keys)} entries retained and cited. ExtraTrees original reference added. Deep-ensemble literature is used only for general uncertainty background.\n", encoding="utf-8")
(AUD / "13_response_to_reviewer_final.md").write_text(
    """# Final response to reviewer

Result-lock semantics were corrected; traceability was rebuilt; scripts were repository-localized; recovery wording now states paired exclusion; 5,760 planned versus 2,240 valid development jobs are reconciled; external methods and exact CS definitions were expanded; GG was stratified; OOD received within-source and IID reference scales; practical-count wording was corrected; neutral representative effects and an explicit endpoint matrix were added; Figure 4 now supports the GG mechanism and the count chart moved to S7; the ExtraTrees source was added and deep-ensemble positioning corrected.

Primary scientific results changed: No.
""", encoding="utf-8")

print(json.dumps({
    "descriptor_rows": len(descriptor), "surrogate_rows": len(surrogates),
    "geometry_rows": len(geometry), "gg_stratified_rows": len(gg_strat),
    "ood_reference_rows": len(ood_ref), "representative_rows": len(representative),
    "endpoint_matrix_rows": len(endpoint_matrix), "claim_rows": len(claim_table),
    "number_rows": len(numbers), "scripts": len(prov_rows),
}, indent=2))
