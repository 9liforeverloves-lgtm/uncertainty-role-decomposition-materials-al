"""Write the required P0 execution and descriptive selection reports."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "v6_development"


def write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def registry_counts(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    connection = sqlite3.connect(path)
    try:
        return {
            str(status): int(count)
            for status, count in connection.execute(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status"
            ).fetchall()
        }
    finally:
        connection.close()


def main() -> None:
    summary = json.loads((OUTPUT / "execution_summary.json").read_text(encoding="utf-8"))
    selection = json.loads(
        (ROOT / "analysis_plan" / "v6_selection_map_DRAFT.json").read_text(encoding="utf-8")
    )
    stability = json.loads((OUTPUT / "p0_selection_stability.json").read_text(encoding="utf-8"))
    final_counts = registry_counts(
        OUTPUT / "recovered_base_then_matched_beta_retry" / "job_registry.sqlite"
    )
    recovered_counts = registry_counts(
        OUTPUT / "rerun_after_simple_scaler_mapping_fix" / "job_registry.sqlite"
    )
    beta = selection["selection"]
    loo = stability["matched_beta_leave_one_seed_out"]
    fixed_values = [float(value["fixed_matched_beta"]) for value in loo.values()]
    reports = ROOT / "reports"
    write(
        reports / "04_p0_development_execution.md",
        f"""# P0 development execution

Status: **V6-P0-SENTINEL-DEVELOPMENT, completed development-only**. The locked manifest `{summary['manifest_sha256']}` planned {summary['planned']} jobs and the final registry records {summary['completed']} completed, {summary['failed']} failed, and {summary['excluded']} excluded jobs.

- Final execution root: `{summary['execution_run_root']}`
- Required final snapshot: `{summary['registry_snapshot']}`
- Scope: `matbench_expt_gap` only; IID-record and chemical-system group-disjoint splits; Random Forest only.
- Seeds: 6000–6009 only.
- Inferential status: development-only and non-confirmatory; this sentinel cohort is not transferable to all 16 V5 environments.
- The accepted DRAFT remains unchanged at `analysis_plan/v6_selection_map_SENTINEL_DRAFT.json`; it is not a confirmation selection map.
- No confirmation manifest was created and no confirmation job was run.

## Recovery audit

Five superseded prospective locks recorded deterministic engineering defects or a recovery transition before the final executed development lock was accepted: a negative SeedSequence round key, calibration-only acquisition-map mismatches, omitted matched-beta identity dispatch, and the final verified-recovery handoff. Their registries and lock lineage remain on disk. The final run used verified recovery: all 300 completed base artifacts from `rerun_after_simple_scaler_mapping_fix` had matching registry and trace hashes before copying into the final run ledger; only the 60 matched-beta paths were recomputed.

- Source recovery-run registry counts: `{recovered_counts}`
- Final registry counts: `{final_counts}`

This is an execution/recovery record, not inferential evidence.
""",
    )
    stage = beta["stage_matched_beta"]
    simple = selection["simple_scaling_development_summary"]
    winner_counts = stability["simple_scaler_leave_one_seed_out_winner_count"]
    write(
        reports / "04a_p0_selection_stability.md",
        f"""# P0 selection stability

Status: **sentinel DRAFT, descriptive development-only**. No confirmation selection map has been frozen; this two-environment expt-gap result cannot define a full-universe policy.

## Matched-beta map

- Fixed matched beta: `{beta['fixed_matched_beta']:.12g}`
- Stage values: 0-25% `{stage['0_25']:.12g}`, 25-50% `{stage['25_50']:.12g}`, 50-75% `{stage['50_75']:.12g}`, 75-100% `{stage['75_100']:.12g}`.
- Missing-stage fallback used: `{beta['stages_using_fallback']}`.
- Leave-one-development-seed-out fixed-beta range: `{min(fixed_values):.12g}` to `{max(fixed_values):.12g}`.

## Simple-scaling draft selection

The sentinel descriptive minimum was `{simple['selected_strategy_draft']}`. Development summaries were `{simple['environment_balanced_median_l1']}`. Leave-one-seed-out winner counts were `{winner_counts}`. Identity remains a negative implementation control, not a scaling winner; residual-ratio remains the candidate simple non-identity scalar baseline, and NLL remains the prespecified mechanistic scalar baseline. No post-hoc winner selection across all simple scalers is made from these sentinel outcomes.

## Scope limits

The result is limited to the two declared expt-gap sentinel environments and ten development seeds. It is suitable only to form the archived sentinel DRAFT, not a confirmation policy. The 40-pair completeness gate, multiplicity-adjusted confirmation inference, confirmation manifest, and all P1 work remain deliberately unperformed.

DRAFT map: `analysis_plan/v6_selection_map_SENTINEL_DRAFT.json` (byte-identical archive; hash `{selection['draft_selection_map_sha256']}`).
""",
    )


if __name__ == "__main__":
    main()
