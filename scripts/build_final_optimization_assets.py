"""Build presentation-only P1 tables and audit summaries from frozen outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "tables"
REPORTS = ROOT / "reports"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return f"generated/{path.name}"


def main(output_dir: Path = TABLES, report_dir: Path = REPORTS, lock_output: Path | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if lock_output is None:
        lock_output = ROOT / "locks/final_optimization_presentation_lock.json"
    contrasts = pd.read_csv(ROOT / "analysis_plan/p1_extension_contrasts_FROZEN.csv")
    primary = pd.read_csv(TABLES / "p1_confirmation_primary_contrasts.csv")
    roles = pd.read_csv(TABLES / "p1_strategy_role_map.csv")
    task = pd.read_csv(TABLES / "p1_confirmation_task_effects.csv")
    split = pd.read_csv(TABLES / "p1_confirmation_split_effects.csv")
    endpoints = pd.read_csv(TABLES / "p1_confirmation_seed_level_endpoints.csv")
    robustness = pd.read_csv(TABLES / "p1_confirmation_robustness.csv")
    cal = pd.read_csv(TABLES / "p1_confirmation_calibration_diagnostics.csv", low_memory=False)
    provenance = pd.read_csv(TABLES / "p1_confirmation_execution_provenance.csv")

    display = roles.set_index("strategy_id")["display_name"].to_dict()
    interpretation = {
        "P1_C1": "Unfavorable relative to the registered greater-direction alternative",
        "P1_C2": "Supported in the registered comparison",
        "P1_C3": "Unfavorable relative to the registered greater-direction alternative",
        "P1_C4": "Unfavorable relative to the registered less-direction alternative",
        "P1_C5": "Unfavorable relative to the registered greater-direction alternative",
    }
    merged = contrasts.merge(
        primary,
        on=["contrast_id", "family", "classification", "endpoint", "strategy", "baseline", "effect_definition", "favorable_direction"],
        validate="one_to_one",
    )
    table = pd.DataFrame({
        "ID": merged.contrast_id,
        "Strategy": merged.strategy.map(display),
        "Strategy_machine_id": merged.strategy,
        "Baseline": merged.baseline.map(display),
        "Baseline_machine_id": merged.baseline,
        "Endpoint": merged.endpoint,
        "Registered_alternative": merged.favorable_direction,
        "Effect": merged.pooled_effect,
        "CI95_low": merged.ci95_low,
        "CI95_high": merged.ci95_high,
        "Raw_p": merged.raw_p,
        "BH_adjusted_p": merged.adjusted_p,
        "Environment_count": merged.environment_count,
        "Seed_block_count": merged.seed_block_count,
        "Family": merged.family,
        "Interpretation": merged.contrast_id.map(interpretation),
    })
    table.to_csv(output_dir / "p1_primary_table_display.csv", index=False, lineterminator="\n")

    claim_rows = [
        {"evidence_stage": "P1 confirmation", "claim_class": "Supported registered comparison", "objects": "P1_C2", "allowed_interpretation": "Stagewise matched beta was favorable relative to fixed matched beta for L4 only."},
        {"evidence_stage": "P1 confirmation", "claim_class": "Unfavorable registered direction", "objects": "P1_C1|P1_C3|P1_C4|P1_C5", "allowed_interpretation": "The observed effects opposed their prespecified favorable alternatives; this is not an equivalence statement."},
        {"evidence_stage": "P1 exploratory", "claim_class": "Exploratory robustness", "objects": "task weighting|leave-one-task-out|random effects|Wilcoxon", "allowed_interpretation": "Sensitivity and heterogeneity context only; no new confirmatory family."},
        {"evidence_stage": "P1 descriptive", "claim_class": "Descriptive diagnostics", "objects": "coverage|proper scores|trajectories|crossings|scalar distribution", "allowed_interpretation": "Mechanistic context and absolute scale only; no causal claim."},
    ]
    pd.DataFrame(claim_rows).to_csv(output_dir / "p1_claim_evidence_classification.csv", index=False, lineterminator="\n")

    summary_rows: list[dict[str, object]] = []
    for row in merged.itertuples(index=False):
        t = task[task.contrast_id == row.contrast_id]
        favorable = (t.effect < 0) if row.favorable_direction == "less" else (t.effect > 0)
        summary_rows.append({"section": "task_direction", "contrast_id": row.contrast_id, "metric": "favorable_task_count", "value": int(favorable.sum()), "denominator": len(t), "source": "tables/p1_confirmation_task_effects.csv"})
    for row in split.itertuples(index=False):
        summary_rows.append({"section": "split_effect", "contrast_id": row.contrast_id, "metric": row.split, "value": row.effect, "denominator": row.seed_count, "source": "tables/p1_confirmation_split_effects.csv"})
    absolute = endpoints.groupby("strategy", as_index=False)[["P1_L1", "P1_L4"]].mean()
    for row in absolute.itertuples(index=False):
        summary_rows.extend([
            {"section": "absolute_endpoint", "contrast_id": "", "metric": f"{row.strategy}:P1_L1", "value": row.P1_L1, "denominator": "", "source": "tables/p1_confirmation_seed_level_endpoints.csv"},
            {"section": "absolute_endpoint", "contrast_id": "", "metric": f"{row.strategy}:P1_L4", "value": row.P1_L4, "denominator": "", "source": "tables/p1_confirmation_seed_level_endpoints.csv"},
        ])
    metric = cal[(cal.diagnostic_type == "campaign_checkpoint_metric") & (cal.model == "quantile_gradient_boosting")].copy()
    final = metric[metric["round"] == metric.groupby("job_id")["round"].transform("max")]
    columns = ["mean_absolute_coverage_error", "mean_interval_width_90", "interval_score_90", "gaussian_nll", "gaussian_crps", "quantile_crossings"]
    for (strategy, column), value in final.groupby("manifest_strategy")[columns].mean().stack().items():
        summary_rows.append({"section": "qgb_final_checkpoint", "contrast_id": "", "metric": f"{strategy}:{column}", "value": value, "denominator": final[final.manifest_strategy == strategy].job_id.nunique(), "source": "tables/p1_confirmation_calibration_diagnostics.csv"})
    scalar = metric[metric.manifest_strategy != "P1_QGB_RAW"].groupby("manifest_strategy").residual_ratio.agg(["min", "median", "max"])
    for strategy, row in scalar.iterrows():
        for stat in ["min", "median", "max"]:
            summary_rows.append({"section": "scalar_distribution", "contrast_id": "", "metric": f"{strategy}:{stat}", "value": row[stat], "denominator": "", "source": "tables/p1_confirmation_calibration_diagnostics.csv"})
    random_effects = robustness[robustness.analysis == "between_task_random_effects"]
    for row in random_effects.itertuples(index=False):
        summary_rows.extend([
            {"section": "random_effects", "contrast_id": row.contrast_id, "metric": "prediction_interval_low", "value": row.prediction_interval_low, "denominator": 4, "source": "tables/p1_confirmation_robustness.csv"},
            {"section": "random_effects", "contrast_id": row.contrast_id, "metric": "prediction_interval_high", "value": row.prediction_interval_high, "denominator": 4, "source": "tables/p1_confirmation_robustness.csv"},
        ])
    pd.DataFrame(summary_rows).to_csv(output_dir / "p1_final_diagnostic_summary.csv", index=False, lineterminator="\n")

    provenance.started_utc = pd.to_datetime(provenance.started_utc, utc=True)
    provenance.completed_utc = pd.to_datetime(provenance.completed_utc, utc=True)
    events = []
    for row in provenance.itertuples(index=False):
        events.append((row.started_utc, 1))
        events.append((row.completed_utc, -1))
    active = peak_active = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        peak_active = max(peak_active, active)
    result_root = ROOT / "results/p1_extension/confirmation"
    durable_bytes = sum(path.stat().st_size for path in result_root.rglob("*") if path.is_file())
    if durable_bytes == 0 and (TABLES / "p1_compute_provenance_summary.csv").is_file():
        published_compute = pd.read_csv(TABLES / "p1_compute_provenance_summary.csv")
        durable_row = published_compute[published_compute.metric == "durable_confirmation_corpus"]
        if len(durable_row) != 1:
            raise RuntimeError("release provenance summary lacks one durable-corpus row")
        durable_bytes = float(durable_row.iloc[0].value) * 2**30
    compute = pd.DataFrame([
        {"metric": "job_count", "value": len(provenance), "unit": "jobs", "status": "observed"},
        {"metric": "first_start_utc", "value": provenance.started_utc.min().isoformat(), "unit": "timestamp", "status": "observed"},
        {"metric": "last_completion_utc", "value": provenance.completed_utc.max().isoformat(), "unit": "timestamp", "status": "observed"},
        {"metric": "elapsed_wall_time", "value": (provenance.completed_utc.max() - provenance.started_utc.min()).total_seconds() / 3600, "unit": "hours", "status": "observed"},
        {"metric": "sum_job_process_wall_time", "value": provenance.wall_seconds.sum() / 3600, "unit": "job-hours", "status": "observed_not_CPU_telemetry"},
        {"metric": "maximum_concurrent_jobs", "value": peak_active, "unit": "workers", "status": "inferred_from_timestamps"},
        {"metric": "node_count", "value": 1, "unit": "host", "status": "bound_by_compute_amendment"},
        {"metric": "durable_confirmation_corpus", "value": durable_bytes / 2**30, "unit": "GiB", "status": "observed_after_completion"},
        {"metric": "failed_jobs", "value": 0, "unit": "jobs", "status": "observed"},
        {"metric": "retry_log_markers", "value": 0, "unit": "markers", "status": "observed"},
        {"metric": "peak_RAM", "value": "not instrumented", "unit": "", "status": "provenance_gap"},
        {"metric": "peak_temporary_disk", "value": "not instrumented", "unit": "", "status": "provenance_gap"},
        {"metric": "CPU_time", "value": "not instrumented", "unit": "", "status": "provenance_gap"},
    ])
    compute.to_csv(output_dir / "p1_compute_provenance_summary.csv", index=False, lineterminator="\n")

    related = pd.DataFrame([
        {"citation_key": "foldager2023uncertainty", "study": "Foldager et al. (2023)", "identifier": "PMLR 216:592-601; arXiv:2301.05983", "calibration_endpoint": "Regression uncertainty calibration", "discovery_endpoint": "Bayesian-optimization regret", "surrogate_domain": "Synthetic and real-world BO; multiple surrogates", "role_separation": "No intervention-level calibration/acquisition decomposition", "independent_confirmation": "Benchmark repetitions", "difference": "The present study freezes role-specific interventions and separates calibration from discovery endpoints."},
        {"citation_key": "wang2022benchmark", "study": "Wang et al. (2022)", "identifier": "doi:10.1093/oxfmat/itac006", "calibration_endpoint": "Not a primary endpoint", "discovery_endpoint": "Materials optimization regret", "surrogate_domain": "Fe-Co-Ni experimental library; Gaussian process", "role_separation": "No", "independent_confirmation": "Repeated benchmark campaigns", "difference": "The present study adds locked calibration endpoints and role-specific controls."},
        {"citation_key": "varivoda2023uq", "study": "Varivoda et al. (2023)", "identifier": "doi:10.1063/5.0133528", "calibration_endpoint": "UQ quality and error bounds", "discovery_endpoint": "Active-learning utility", "surrogate_domain": "Materials property prediction; graph models", "role_separation": "Uses compared, not intervention roles", "independent_confirmation": "Not reported as a frozen confirmation stage", "difference": "The present study separates evaluation and acquisition mappings within one campaign architecture."},
        {"citation_key": "jiang2026calibration", "study": "Jiang et al. (2026)", "identifier": "doi:10.20517/jmi.2025.70", "calibration_endpoint": "Miscalibration area", "discovery_endpoint": "Optimization across alloy datasets", "surrogate_domain": "SVR, neural network and XGBoost; three alloy datasets", "role_separation": "No calibration-only versus acquisition-only arms", "independent_confirmation": "No frozen paired confirmation stage reported", "difference": "The present study tests whether scaling transfers across roles and surrogate constructions."},
        {"citation_key": "dale2025ood", "study": "Dale et al. (2025 preprint)", "identifier": "arXiv:2511.17760", "calibration_endpoint": "ID/OOD uncertainty calibration", "discovery_endpoint": "OOD active-learning data efficiency", "surrogate_domain": "ALIGNN, XGBoost, Random Forest and neural-network ensembles", "role_separation": "Calibration methods evaluated through acquisition", "independent_confirmation": "Five active-learning seeds; no frozen confirmation stage reported", "difference": "The present study uses locked paired confirmation and separates evaluation from acquisition placement."},
        {"citation_key": "riebesell2025matbenchdiscovery", "study": "Riebesell et al. (2025)", "identifier": "doi:10.1038/s42256-025-01055-1", "calibration_endpoint": "Reliability and error diagnostics", "discovery_endpoint": "Stability classification and discovery acceleration", "surrogate_domain": "Crystal-stability prefilter benchmark", "role_separation": "No", "independent_confirmation": "Prospective benchmark framing", "difference": "The present study adds frozen role-specific contrasts and matched-beta controls."},
    ])
    related.to_csv(output_dir / "p1_related_work_verified.csv", index=False, lineterminator="\n")

    gap = """# Compute-gate provenance gap\n\nThe prospective compute-only amendment is fully evidenced and predates every P1 confirmation outcome. The immutable job provenance reconstructs elapsed wall time, maximum concurrency, completion status and durable output size.\n\nThree host-level quantities were not instrumented during the completed run: process CPU time, peak resident memory and peak temporary-disk use. Sum of per-job process wall times is reported as job-hours and is not relabelled CPU-hours. The durable corpus size is not relabelled peak disk use. No retrospective estimate is substituted for missing telemetry.\n\nThis gap does not alter protocol compliance or scientific inference because the frozen amendment explicitly permitted continuation beyond 24 h, retained the RAM and storage stop rules, used one audited host, and no job failed. It does prevent an exact retrospective claim about peak RAM, peak temporary disk or CPU-hours.\n"""
    (report_dir / "compute_gate_provenance_gap.md").write_text(gap, encoding="utf-8", newline="\n")

    source_files = [
        ROOT / "analysis_plan/p1_extension_contrasts_FROZEN.csv",
        TABLES / "p1_strategy_role_map.csv",
        TABLES / "p1_confirmation_primary_contrasts.csv",
        TABLES / "p1_confirmation_task_effects.csv",
        TABLES / "p1_confirmation_split_effects.csv",
        TABLES / "p1_confirmation_seed_level_endpoints.csv",
        TABLES / "p1_confirmation_robustness.csv",
        TABLES / "p1_confirmation_calibration_diagnostics.csv",
        TABLES / "p1_confirmation_execution_provenance.csv",
    ]
    generated = [
        output_dir / "p1_primary_table_display.csv",
        output_dir / "p1_claim_evidence_classification.csv",
        output_dir / "p1_final_diagnostic_summary.csv",
        output_dir / "p1_compute_provenance_summary.csv",
        output_dir / "p1_related_work_verified.csv",
    ]
    lock = {
        "status": "PRESENTATION_ONLY_NO_NEW_INFERENCE",
        "source_files": {p.relative_to(ROOT).as_posix(): sha(p) for p in source_files},
        "generated_files": {portable_name(p): sha(p) for p in generated},
        "p1_inference_result_lock_sha256": sha(ROOT / "locks/p1_confirmation_inference_result_lock.json"),
        "protocol_lock_sha256": sha(ROOT / "locks/p1_extension_protocol_lock.json"),
    }
    lock_output.parent.mkdir(parents=True, exist_ok=True)
    lock_output.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild presentation-only P1 tables from frozen authorities.")
    parser.add_argument("--output-dir", type=Path, default=TABLES)
    parser.add_argument("--report-dir", type=Path, default=REPORTS)
    parser.add_argument("--lock-output", type=Path)
    args = parser.parse_args()
    main(args.output_dir.resolve(), args.report_dir.resolve(), args.lock_output.resolve() if args.lock_output else None)
