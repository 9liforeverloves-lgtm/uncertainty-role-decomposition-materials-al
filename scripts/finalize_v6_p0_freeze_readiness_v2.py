"""Reconcile V6 P0 policy identity and build Candidate v4 without running jobs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import finalize_v6_p0_freeze_readiness as prior
from transportability_v6.freeze_readiness import (
    canonical_strategy_id,
    effective_beta,
    validate_analysis_only_contrasts,
    validate_gg_policy_identity,
    validate_manifest_policy_identity,
)


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_V3 = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v3.json"
CANDIDATE_V4 = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v4.json"
IDENTITY_TABLE = ROOT / "tables" / "v6_p0_matched_beta_baseline_identity_audit.csv"
IDENTITY_REPORT = ROOT / "reports" / "05i_matched_beta_baseline_identity_audit.md"
READINESS_REPORT = ROOT / "reports" / "05j_p0_confirmation_freeze_readiness_v2.md"
V5_POLICY_LOCK = ROOT / "locks" / "v5_readonly_snapshot" / "19_selected_policy_lock.json"

H7_METHOD_CONTRASTS = [
    {"hypothesis_id": "H1", "endpoint": "L1", "strategy_id": "GG_CALIBRATION_ONLY", "baseline": "RAW"},
    {"hypothesis_id": "H5A", "endpoint": "L1", "strategy_id": "CS_CALIBRATION_ONLY", "baseline": "RAW"},
    {"hypothesis_id": "H2A", "endpoint": "L4", "strategy_id": "GG_ACQUISITION_ONLY", "baseline": "RAW"},
    {"hypothesis_id": "H2B", "endpoint": "L4", "strategy_id": "ORIGINAL_GG", "baseline": "RAW"},
    {"hypothesis_id": "H5B", "endpoint": "L4", "strategy_id": "CS_ACQUISITION_ONLY", "baseline": "RAW"},
    {"hypothesis_id": "H5C", "endpoint": "L4", "strategy_id": "SELECTED_CS", "baseline": "RAW"},
    {"hypothesis_id": "H3", "endpoint": "L4", "strategy_id": "RAW_FIXED_BETA_MATCHED", "baseline": "ORIGINAL_GG"},
    {"hypothesis_id": "H4", "endpoint": "L4", "strategy_id": "RAW_STAGE_BETA_MATCHED", "baseline": "ORIGINAL_GG"},
    {"hypothesis_id": "H6A", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_NLL", "baseline": "IDENTITY_CONTROL"},
    {"hypothesis_id": "H6B", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_RESIDUAL_RATIO", "baseline": "IDENTITY_CONTROL"},
    {"hypothesis_id": "H6", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_RESIDUAL_RATIO", "baseline": "SELECTED_CS"},
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def selected_gg_provenance() -> dict[str, Any]:
    lock = load_json(V5_POLICY_LOCK)
    rows = [
        row
        for row in lock["selected_policies"]
        if str(row["family"]) == "gaussian_global"
    ]
    if len(rows) != 4 or {str(row["selected_strategy"]) for row in rows} != {
        "gg_ucb_beta_0p5"
    }:
        raise RuntimeError("V5 Selected GG provenance is not the frozen beta-0.5 policy")
    return {
        "v5_strategy_id": "gg_ucb_beta_0p5",
        "nominal_beta": 0.5,
        "selection_lock_path": relative(V5_POLICY_LOCK),
        "selection_lock_sha256": prior.sha256_file(V5_POLICY_LOCK),
        "task_policy_rows": [
            {
                "held_out_task": str(row["held_out_task"]),
                "development_tasks": str(row["development_tasks"]),
                "selected_strategy": str(row["selected_strategy"]),
                "tie_breaking_rule": str(row["tie_breaking_rule"]),
            }
            for row in rows
        ],
    }


def identity_rows(candidate_v3: dict[str, Any]) -> list[dict[str, Any]]:
    maps = candidate_v3["leave_one_task_out_maps"]
    fixed_source = {
        task: {
            "fixed_matched_beta": values["fixed_matched_beta"],
            "source_tasks": values["source_tasks"],
            "source_seeds": values["source_seeds"],
            "source_table_sha256": values["source_table_sha256"],
        }
        for task, values in maps.items()
    }
    stage_source = {
        task: {
            "stage_matched_beta": values["stage_matched_beta"],
            "source_tasks": values["source_tasks"],
            "source_seeds": values["source_seeds"],
            "source_table_sha256": values["source_table_sha256"],
        }
        for task, values in maps.items()
    }
    common = {
        "earliest_registered_baseline": "GG_JOINT",
        "alias_resolved_canonical_baseline": "ORIGINAL_GG",
        "development_effective_beta_source_strategy": "ORIGINAL_GG",
        "candidate_v3_baseline": "SELECTED_GG",
        "final_candidate_v4_baseline": "ORIGINAL_GG",
        "original_gg_nominal_beta": 1.0,
        "selected_gg_nominal_beta": 0.5,
        "definition_point_outcome_availability": (
            "earliest_registry_fa4ec48=false;"
            "accepted_alias_registry_postdevelopment=true;"
            "matched_beta_source_strategy_registration=false;"
            "matched_beta_value_fit_postdevelopment=true;"
            "candidate_v3_postdevelopment=true;"
            "candidate_v4_human_reconciliation=true"
        ),
        "baseline_decision_basis": (
            "earliest pre-development registry plus accepted alias identity; "
            "development outcomes not used"
        ),
    }
    return [
        {
            "hypothesis_id": "H3",
            "earliest_registered_strategy": "RAW_FIXED_BETA_MATCHED",
            **common,
            "fixed_stage_beta_source": json.dumps(fixed_source, sort_keys=True, separators=(",", ":")),
        },
        {
            "hypothesis_id": "H4",
            "earliest_registered_strategy": "RAW_STAGE_BETA_MATCHED",
            **common,
            "fixed_stage_beta_source": json.dumps(stage_source, sort_keys=True, separators=(",", ":")),
        },
    ]


def write_identity_audit(candidate_v3: dict[str, Any]) -> None:
    rows = identity_rows(candidate_v3)
    IDENTITY_TABLE.parent.mkdir(parents=True, exist_ok=True)
    with IDENTITY_TABLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# V6 P0 matched-beta baseline identity audit",
        "",
        "Decision: H3 and H4 must use `ORIGINAL_GG` as the final baseline. The earliest "
        "pre-development registry (`fa4ec48`) named `GG_JOINT`; the accepted alias registry "
        "resolves `GG_JOINT -> ORIGINAL_GG`. No pre-development record supports "
        "`SELECTED_GG` for these contrasts.",
        "",
        "| Hypothesis | Earliest comparison | Alias-resolved baseline | Candidate v3 | Candidate v4 |",
        "|---|---|---|---|---|",
        "| H3 | `RAW_FIXED_BETA_MATCHED vs GG_JOINT` | `ORIGINAL_GG` | `SELECTED_GG` | `ORIGINAL_GG` |",
        "| H4 | `RAW_STAGE_BETA_MATCHED vs GG_JOINT` | `ORIGINAL_GG` | `SELECTED_GG` | `ORIGINAL_GG` |",
        "",
        "Both matched controls were fit from development-only `ORIGINAL_GG` effective-beta "
        "summaries in `tables/v6_p0_broad_effective_beta.csv`. Fixed and stage values are "
        "unchanged; their exact held-out-task sources are preserved in the machine-readable audit.",
        "",
        "The beta identity is `ORIGINAL_GG = 1.0` and `SELECTED_GG = 0.5`. Broad-development "
        "dispatch and the V5 replay used 0.5 for `SELECTED_GG`, so Candidate v3's beta 1.0 was "
        "a metadata-only error, not a production-dispatch error and not a new V6 method.",
        "",
        "Outcome availability is recorded at every definition point in the CSV. The final "
        "baseline decision uses only the earliest registry and alias identity, not development outcomes.",
        "",
        f"Machine-readable audit: `{relative(IDENTITY_TABLE)}` "
        f"(SHA-256 `{prior.sha256_file(IDENTITY_TABLE)}`).",
    ]
    prior.atomic_bytes(IDENTITY_REPORT, ("\n".join(lines) + "\n").encode("utf-8"))


def build_candidate_v4(candidate_v3: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(candidate_v3))
    payload.pop("candidate_self_sha256", None)
    payload["schema_version"] = "v6-p0-confirmation-selection-map-candidate-v4"
    payload["status"] = "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN"

    provenance = selected_gg_provenance()
    methods = {str(item["id"]): item for item in payload["canonical_strategies"]}
    for strategy_id, item in methods.items():
        item["policy_key"] = strategy_id
    methods["ORIGINAL_GG"]["nominal_beta"] = 1.0
    methods["ORIGINAL_GG"]["policy_key"] = "ORIGINAL_GG__beta_1"
    methods["ORIGINAL_GG"]["policy_provenance"] = {
        "v5_strategy_id": "gg_ucb_beta_1",
        "nominal_beta": 1.0,
        "authority": "frozen V5 evidence",
    }
    methods["SELECTED_GG"]["nominal_beta"] = 0.5
    methods["SELECTED_GG"]["policy_key"] = "SELECTED_GG__beta_0p5"
    methods["SELECTED_GG"]["role_detail"] = (
        "V5 development-selected GG reference; distinct from ORIGINAL_GG"
    )
    methods["SELECTED_GG"]["policy_provenance"] = provenance
    methods["RAW"]["policy_key"] = "RAW__universal_beta_1"
    methods["RAW"]["raw_policy_definition"] = "A_UNIVERSAL_BETA_1_MECHANISM_REFERENCE"

    for contrast in payload["prospective_contrasts"]:
        hypothesis_id = str(contrast["id"])
        if hypothesis_id in {"H3", "H4"}:
            contrast["baseline"] = "ORIGINAL_GG"
            contrast["comparison"] = (
                f"{contrast['strategy_id']} vs ORIGINAL_GG"
            )
            contrast["registered_baseline_alias"] = "GG_JOINT"
            contrast["alias_resolved_baseline"] = "ORIGINAL_GG"
            contrast["matched_beta_source_strategy"] = "ORIGINAL_GG"
        if hypothesis_id == "H7":
            contrast.pop("strategy_id", None)
            contrast.pop("baseline", None)
            contrast.update(
                {
                    "analysis_only": True,
                    "generate_confirmation_job": False,
                    "method_contrasts": H7_METHOD_CONTRASTS,
                    "family": "NONE_DESCRIPTIVE",
                    "binary_claim": False,
                    "alternative": "none",
                    "classification": "secondary_descriptive_analysis_only",
                    "comparison": "descriptive cross-endpoint L1/L4 direction divergence",
                    "effect_definition": "descriptive direction table; no binary claim",
                }
            )

    payload["matched_beta_baseline_identity"] = {
        "earliest_registered_baseline": "GG_JOINT",
        "alias_resolution": {"GG_JOINT": "ORIGINAL_GG"},
        "canonical_baseline": "ORIGINAL_GG",
        "effective_beta_source_strategy": "ORIGINAL_GG",
        "decision_uses_development_outcomes": False,
        "audit_path": relative(IDENTITY_TABLE),
        "audit_sha256": prior.sha256_file(IDENTITY_TABLE),
    }
    payload["selected_gg_policy_metadata_correction"] = {
        "classification": "metadata_only_error",
        "production_dispatch_error": False,
        "deliberate_new_v6_policy": False,
        "candidate_v3_recorded_nominal_beta": 1.0,
        "correct_nominal_beta": 0.5,
        "production_evidence": [
            "src/transportability_v6/broad_development.py dispatches SELECTED_GG at beta 0.5",
            "tables/v6_v5_strategy_replay_audit.csv records SELECTED_GG nominal_beta 0.5",
        ],
        "policy_provenance": provenance,
    }
    payload["raw_policy"] = {
        "choice": "A",
        "definition": "universal beta-1 mechanism reference",
        "canonical_id": "RAW",
        "nominal_beta": 1.0,
        "applies_to_hypotheses": ["H1", "H2A", "H2B", "H5A", "H5B", "H5C"],
        "task_specific_nominal_beta_map": None,
        "v5_selected_raw_policy_reused": False,
        "v5_historical_note": (
            "The V5 development-selected RAW policy used beta 2 for matbench_log_kvrh; "
            "that task-specific policy is historical provenance and is not V6 RAW."
        ),
        "immutable_after_confirmation_outcomes": True,
    }
    payload["confirmation_job_policy_contract"] = {
        "required_manifest_fields": ["strategy_id", "nominal_beta", "policy_key"],
        "policy_identity_rule": (
            "all three fields must match the same canonical strategy record; aliases and "
            "cross-policy beta substitution are rejected"
        ),
        "analysis_only_hypotheses_generate_jobs": False,
    }

    sources = payload["source_tables"]
    existing = {str(item["path"]) for item in sources}
    for path in (CANDIDATE_V3, IDENTITY_TABLE, V5_POLICY_LOCK):
        if relative(path) not in existing:
            sources.append(prior.source_entry(path))
    payload["source_hashes"].update(
        {
            "candidate_v3_sha256": prior.sha256_file(CANDIDATE_V3),
            "matched_beta_baseline_identity_audit_sha256": prior.sha256_file(IDENTITY_TABLE),
            "v5_selected_policy_lock_sha256": prior.sha256_file(V5_POLICY_LOCK),
            "v6_code_tree_sha256": prior.code_tree_sha256(
                ROOT / "src" / "transportability_v6"
            ),
        }
    )
    payload["unresolved"] = [
        "Candidate only; human freeze approval is still required.",
        "No confirmation manifest has been generated or executed.",
    ]
    payload["candidate_self_sha256"] = prior.canonical_hash(payload)
    prior.atomic_json(CANDIDATE_V4, payload)
    return payload


def run_validation(candidate_v4: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    _, checks = prior.run_readiness_validation(candidate_v4)

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    record(
        "Candidate v4 self-hash",
        prior.verify_candidate_hash(CANDIDATE_V4),
        str(candidate_v4["candidate_self_sha256"]),
    )
    methods = candidate_v4["canonical_strategies"]
    method_map = {str(item["id"]): item for item in methods}
    contrasts = {str(item["id"]): item for item in candidate_v4["prospective_contrasts"]}
    aliases = {
        str(item["alias_id"]): str(item["canonical_id"])
        for item in candidate_v4["alias_registry"]["aliases"]
    }
    matched_ok = all(
        contrasts[hypothesis_id]["matched_beta_source_strategy"]
        == contrasts[hypothesis_id]["baseline"]
        == "ORIGINAL_GG"
        for hypothesis_id in ("H3", "H4")
    )
    record(
        "matched-beta source strategy equals registered joint baseline",
        matched_ok,
        "H3/H4 source=baseline=ORIGINAL_GG",
    )
    alias_ok = canonical_strategy_id("GG_JOINT", aliases) == "ORIGINAL_GG" and all(
        contrasts[hypothesis_id]["alias_resolved_baseline"] == "ORIGINAL_GG"
        for hypothesis_id in ("H3", "H4")
    )
    record("alias-resolved baseline identity", alias_ok, "GG_JOINT -> ORIGINAL_GG")
    try:
        validate_gg_policy_identity(methods)
        gg_ok = True
        gg_detail = "ORIGINAL_GG=1.0; SELECTED_GG=0.5; exact V5 provenance present"
    except ValueError as exc:
        gg_ok = False
        gg_detail = str(exc)
    record("Original/Selected GG policy identity and nominal beta", gg_ok, gg_detail)
    formula_ok = (
        effective_beta(method_map["ORIGINAL_GG"]["nominal_beta"], 2.4) == 2.4
        and effective_beta(method_map["SELECTED_GG"]["nominal_beta"], 2.4) == 1.2
    )
    record(
        "effective beta equals nominal beta times fitted scale",
        formula_ok,
        "scale=2.4 control gives 2.4 and 1.2",
    )
    try:
        validate_manifest_policy_identity(
            [
                {
                    "strategy_id": "ORIGINAL_GG",
                    "nominal_beta": 1.0,
                    "policy_key": "ORIGINAL_GG__beta_1",
                },
                {
                    "strategy_id": "SELECTED_GG",
                    "nominal_beta": 0.5,
                    "policy_key": "SELECTED_GG__beta_0p5",
                },
            ],
            methods,
        )
        mismatch_rejected = False
        try:
            validate_manifest_policy_identity(
                [
                    {
                        "strategy_id": "SELECTED_GG",
                        "nominal_beta": 1.0,
                        "policy_key": "ORIGINAL_GG__beta_1",
                    }
                ],
                methods,
            )
        except ValueError:
            mismatch_rejected = True
        manifest_ok = mismatch_rejected
    except ValueError:
        manifest_ok = False
    record(
        "no strategy-name/policy mismatch and no manifest substitution",
        manifest_ok,
        "canonical ID, nominal beta, and policy key are bound",
    )
    try:
        validate_analysis_only_contrasts(candidate_v4["prospective_contrasts"])
        analysis_ok = True
        analysis_detail = f"H7 has {len(contrasts['H7']['method_contrasts'])} explicit contrasts and no job"
    except ValueError as exc:
        analysis_ok = False
        analysis_detail = str(exc)
    record("analysis-only hypotheses generate no jobs", analysis_ok, analysis_detail)
    raw = candidate_v4["raw_policy"]
    raw_ok = (
        raw["choice"] == "A"
        and raw["nominal_beta"] == 1.0
        and raw["task_specific_nominal_beta_map"] is None
        and not raw["v5_selected_raw_policy_reused"]
    )
    record("RAW policy is explicit and immutable", raw_ok, raw["definition"])
    code_ok = candidate_v4["source_hashes"]["v6_code_tree_sha256"] == prior.code_tree_sha256(
        ROOT / "src" / "transportability_v6"
    )
    record("updated code-tree hash", code_ok, candidate_v4["source_hashes"]["v6_code_tree_sha256"])
    manifest_path = ROOT / "manifests" / "v6_p0_confirmation_manifest.csv"
    record(
        "no confirmation manifest generated",
        not manifest_path.exists(),
        relative(manifest_path),
    )
    status = (
        "READY_FOR_HUMAN_FREEZE_APPROVAL"
        if all(bool(item["passed"]) for item in checks)
        else "BLOCKED_WITH_EXACT_REASONS"
    )
    return status, checks


def write_readiness_report(status: str, checks: list[dict[str, Any]]) -> None:
    failures = [item for item in checks if not bool(item["passed"])]
    lines = [
        "# V6 P0 confirmation freeze-readiness v2",
        "",
        f"Final status: **{status}**",
        "",
        "| Automated check | Result | Detail |",
        "|---|---:|---|",
    ]
    for item in checks:
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['check']} | {'PASS' if item['passed'] else 'FAIL'} | {detail} |")
    lines.extend(
        [
            "",
            "## Scientific identity decisions",
            "",
            "- H3/H4 baseline: `ORIGINAL_GG`, resolved from the earliest `GG_JOINT` registration.",
            "- GG betas: `ORIGINAL_GG = 1.0`; V5 `SELECTED_GG = 0.5`.",
            "- V6 `RAW`: universal beta-1 mechanism reference (choice A), not the V5 task-specific selected RAW policy.",
            "- H7: analysis-only descriptive direction table; no singular strategy/baseline, job, familywise binary claim, or confirmation job.",
            "",
            "## Boundary conditions",
            "",
            "- Candidate v4 remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`.",
            "- No confirmation manifest was generated or executed.",
            "- Confirmation seeds 7000-7039 remain prohibited and were not run.",
            "- Broad development was not rerun.",
            "- Development endpoints and matched-beta values were not changed.",
            "",
            "## Exact blockers",
            "",
        ]
    )
    if failures:
        lines.extend(f"- `{item['check']}`: {item['detail']}" for item in failures)
    else:
        lines.append("- None. Human freeze approval is still required; this report does not freeze Candidate v4.")
    prior.atomic_bytes(READINESS_REPORT, ("\n".join(lines) + "\n").encode("utf-8"))


def main() -> None:
    candidate_v3 = load_json(CANDIDATE_V3)
    write_identity_audit(candidate_v3)
    candidate_v4 = build_candidate_v4(candidate_v3)
    status, checks = run_validation(candidate_v4)
    write_readiness_report(status, checks)
    print(
        json.dumps(
            {
                "status": status,
                "checks_passed": sum(bool(item["passed"]) for item in checks),
                "checks_total": len(checks),
                "candidate_v4_sha256": prior.sha256_file(CANDIDATE_V4),
                "candidate_v4_self_hash_valid": prior.verify_candidate_hash(CANDIDATE_V4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
