"""Freeze Candidate v4 and generate a non-executing confirmation manifest audit."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.freeze_readiness import (
    canonical_strategy_id,
    validate_analysis_only_contrasts,
    validate_gg_policy_identity,
    validate_manifest_policy_identity,
)
from transportability_v6.registry_freeze import code_tree_sha256


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v4.json"
FROZEN = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_FROZEN.json"
FREEZE_LOCK = ROOT / "locks" / "v6_p0_confirmation_selection_freeze_lock.json"
MANIFEST = ROOT / "manifests" / "v6_p0_confirmation_manifest.csv"
AUDIT_TABLE = ROOT / "tables" / "v6_p0_confirmation_manifest_audit.csv"
AUDIT_REPORT = ROOT / "reports" / "06_p0_confirmation_manifest_audit.md"

ADMIN_FIELDS = frozenset(
    {
        "status",
        "candidate_self_sha256",
        "frozen_map_self_sha256",
        "frozen_utc",
        "freezing_git_commit",
        "frozen_candidate_sha256",
        "freeze_lock_path",
    }
)
TASKS = (
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
)
SPLITS = ("iid_record", "chemical_system_ood")
MODELS = ("random_forest", "extra_randomized_bagging")
SEEDS = tuple(range(7000, 7040))
NON_JOB_CANONICAL_CONTROLS = frozenset(
    {"GG_NORMALIZED_ACQUISITION", "REPLAY_EVALUATION"}
)
REPLAY_STRATEGIES = frozenset(
    {
        "IDENTITY_CONTROL",
        "GG_CALIBRATION_ONLY",
        "CS_CALIBRATION_ONLY",
        "SCALAR_TEMPERATURE_NLL",
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "POWER_SCALING",
        "ISOTONIC_ABS_RESIDUAL",
        "CONFORMAL_INTERVAL_ONLY",
        "CONFORMAL_GAUSSIAN_EQUIVALENT",
        "SELECTED_CS_EQUIVALENT_DOF_CONTROL",
        "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL",
    }
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def write_json_no_overwrite(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def scientific_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in ADMIN_FIELDS}


def verify_self_hash(payload: dict[str, Any], field: str) -> bool:
    clone = json.loads(json.dumps(payload))
    observed = str(clone.pop(field))
    return observed == canonical_hash(clone)


def assert_scientific_identity(
    candidate: dict[str, Any], frozen: dict[str, Any]
) -> None:
    if scientific_payload(candidate) != scientific_payload(frozen):
        raise RuntimeError("scientific payload differs between Candidate v4 and frozen map")
    contrasts = {str(item["id"]): item for item in frozen["prospective_contrasts"]}
    methods = {str(item["id"]): item for item in frozen["canonical_strategies"]}
    for hypothesis_id in ("H3", "H4"):
        item = contrasts[hypothesis_id]
        if item["baseline"] != "ORIGINAL_GG":
            raise RuntimeError(f"{hypothesis_id} baseline changed")
        if item["matched_beta_source_strategy"] != "ORIGINAL_GG":
            raise RuntimeError(f"{hypothesis_id} matched-beta source changed")
    validate_gg_policy_identity(frozen["canonical_strategies"])
    if methods["ORIGINAL_GG"]["nominal_beta"] != 1.0:
        raise RuntimeError("ORIGINAL_GG beta changed")
    if methods["SELECTED_GG"]["nominal_beta"] != 0.5:
        raise RuntimeError("SELECTED_GG beta changed")
    raw = frozen["raw_policy"]
    if raw["choice"] != "A" or raw["nominal_beta"] != 1.0:
        raise RuntimeError("RAW is no longer the universal beta-1 reference")
    validate_analysis_only_contrasts(frozen["prospective_contrasts"])
    aliases = {
        str(item["alias_id"]): item for item in frozen["alias_registry"]["aliases"]
    }
    for alias_id, target in (("GG_JOINT", "ORIGINAL_GG"), ("CS_JOINT", "SELECTED_CS")):
        alias = aliases[alias_id]
        if canonical_strategy_id(alias_id, {alias_id: target}) != target:
            raise RuntimeError(f"{alias_id} canonical target changed")
        if bool(alias["generate_confirmation_job"]):
            raise RuntimeError(f"{alias_id} became a job alias")


def build_frozen_map() -> tuple[dict[str, Any], str]:
    candidate = read_json(CANDIDATE)
    if candidate["status"] != "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN":
        raise RuntimeError("Candidate v4 is not in its approved pre-freeze state")
    if not verify_self_hash(candidate, "candidate_self_sha256"):
        raise RuntimeError("Candidate v4 self-hash is invalid")
    observed_code_hash = code_tree_sha256(ROOT / "src" / "transportability_v6")
    if candidate["source_hashes"]["v6_code_tree_sha256"] != observed_code_hash:
        raise RuntimeError("Candidate v4 code-tree hash does not match the current code")
    pre_freeze_commit = git("rev-parse", "HEAD")
    frozen = json.loads(json.dumps(candidate))
    frozen.pop("candidate_self_sha256")
    frozen.update(
        {
            "status": "FROZEN_BEFORE_CONFIRMATION_OUTCOMES",
            "frozen_utc": datetime.now(timezone.utc).isoformat(),
            "freezing_git_commit": pre_freeze_commit,
            "frozen_candidate_sha256": sha256_file(CANDIDATE),
            "freeze_lock_path": "locks/v6_p0_confirmation_selection_freeze_lock.json",
        }
    )
    frozen["frozen_map_self_sha256"] = canonical_hash(frozen)
    assert_scientific_identity(candidate, frozen)
    write_json_no_overwrite(FROZEN, frozen)
    return frozen, pre_freeze_commit


def build_freeze_lock(frozen: dict[str, Any], pre_freeze_commit: str) -> dict[str, Any]:
    if (ROOT / "results" / "v6_p0_confirmation").exists():
        raise RuntimeError("confirmation output root already exists")
    if MANIFEST.exists():
        raise RuntimeError("confirmation manifest exists before the freeze commit")
    candidate = read_json(CANDIDATE)
    lock: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-selection-freeze-lock-v1",
        "status": "FROZEN_BEFORE_CONFIRMATION_OUTCOMES",
        "candidate_v4": {
            "path": CANDIDATE.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(CANDIDATE),
            "self_sha256": candidate["candidate_self_sha256"],
        },
        "frozen_map": {
            "path": FROZEN.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(FROZEN),
            "self_sha256": frozen["frozen_map_self_sha256"],
        },
        "v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
        "v5_authority_lock_sha256": candidate["source_hashes"]["v5_authority_lock_sha256"],
        "corrected_endpoint_table_sha256": candidate["source_hashes"][
            "corrected_endpoint_table_sha256"
        ],
        "effective_beta_table_sha256": candidate["source_hashes"][
            "effective_beta_table_sha256"
        ],
        "alias_registry_sha256": sha256_file(
            ROOT / "analysis_plan" / "v6_strategy_alias_registry.json"
        ),
        "hypothesis_direction_audit_sha256": sha256_file(
            ROOT / "tables" / "v6_p0_hypothesis_direction_audit.csv"
        ),
        "matched_beta_baseline_audit_sha256": sha256_file(
            ROOT / "tables" / "v6_p0_matched_beta_baseline_identity_audit.csv"
        ),
        "recovery_cleanroom_audit_sha256": sha256_file(
            ROOT / "tables" / "v6_p0_recovery_cleanroom_replay.csv"
        ),
        "freeze_readiness_v2_report_sha256": sha256_file(
            ROOT / "reports" / "05j_p0_confirmation_freeze_readiness_v2.md"
        ),
        "git_commit": pre_freeze_commit,
        "git_commit_before_freeze": pre_freeze_commit,
        "confirmation_seeds": list(SEEDS),
        "multiplicity_families": frozen["multiplicity_families"],
        "strategy_registry": frozen["canonical_strategies"],
        "leave_one_task_out_beta_maps": frozen["leave_one_task_out_maps"],
        "no_confirmation_outcome_assertion": {
            "asserted": True,
            "confirmation_outcomes_inspected": False,
            "confirmation_output_root_absent": True,
            "confirmation_manifest_absent_at_freeze": True,
        },
    }
    lock["freeze_lock_self_sha256"] = canonical_hash(lock)
    write_json_no_overwrite(FREEZE_LOCK, lock)
    return lock


def freeze() -> None:
    frozen, pre_freeze_commit = build_frozen_map()
    lock = build_freeze_lock(frozen, pre_freeze_commit)
    assert verify_self_hash(frozen, "frozen_map_self_sha256")
    assert verify_self_hash(lock, "freeze_lock_self_sha256")
    print(
        json.dumps(
            {
                "candidate_sha256": sha256_file(CANDIDATE),
                "frozen_map_sha256": sha256_file(FROZEN),
                "freeze_lock_sha256": sha256_file(FREEZE_LOCK),
                "pre_freeze_commit": pre_freeze_commit,
                "scientific_identity": "IDENTICAL",
            },
            indent=2,
        )
    )


def _strategy_slug(strategy_id: str) -> str:
    return strategy_id.lower()


def _job_id(
    task: str, split: str, model: str, strategy_id: str, seed: int
) -> str:
    return (
        f"v6_p0_confirmation__{task}__{split}__{model}__"
        f"{_strategy_slug(strategy_id)}__seed{seed}"
    )


def _operational_beta(
    strategy_id: str, method: dict[str, Any], loto: dict[str, Any]
) -> tuple[str, str, str]:
    if strategy_id == "RAW_FIXED_BETA_MATCHED":
        return (
            "frozen_loto_fixed_matched_beta",
            format(float(loto["fixed_matched_beta"]), ".17g"),
            "",
        )
    if strategy_id == "RAW_STAGE_BETA_MATCHED":
        return (
            "frozen_loto_stage_matched_beta_map",
            "",
            json.dumps(
                loto["stage_matched_beta"],
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if strategy_id == "SELECTED_GG":
        return ("frozen_v5_selected_gg_nominal_beta_0p5", "", "")
    if strategy_id == "ORIGINAL_GG":
        return ("frozen_original_gg_nominal_beta_1", "", "")
    return ("canonical_nominal_beta", "", "")


def build_manifest() -> list[dict[str, str]]:
    frozen = read_json(FROZEN)
    lock = read_json(FREEZE_LOCK)
    assert_scientific_identity(read_json(CANDIDATE), frozen)
    if not verify_self_hash(frozen, "frozen_map_self_sha256"):
        raise RuntimeError("frozen map self-hash failed after commit")
    if not verify_self_hash(lock, "freeze_lock_self_sha256"):
        raise RuntimeError("freeze lock self-hash failed after commit")
    head = git("rev-parse", "HEAD")
    for path in (CANDIDATE, FROZEN, FREEZE_LOCK):
        relative = path.relative_to(ROOT).as_posix()
        tracked = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{relative}"], cwd=ROOT
        )
        if tracked.returncode != 0:
            raise RuntimeError(f"{relative} is not present in freeze commit {head}")
    pre_manifest_status = git("status", "--porcelain")
    freeze_commit_clean = pre_manifest_status == ""
    if not freeze_commit_clean:
        raise RuntimeError(
            "worktree is not clean immediately after the freeze commit: "
            + pre_manifest_status.replace("\n", "; ")
        )

    frozen_map_sha = sha256_file(FROZEN)
    freeze_lock_sha = sha256_file(FREEZE_LOCK)
    code_hash = code_tree_sha256(ROOT / "src" / "transportability_v6")
    if code_hash != lock["v6_code_tree_sha256"]:
        raise RuntimeError("code tree changed after the freeze")
    methods = {
        str(item["id"]): item for item in frozen["canonical_strategies"]
    }
    job_strategies = sorted(set(methods) - set(NON_JOB_CANONICAL_CONTROLS))
    rows: list[dict[str, str]] = []
    for task in TASKS:
        loto = frozen["leave_one_task_out_maps"][task]
        for split in SPLITS:
            for model in MODELS:
                for seed in SEEDS:
                    raw_id = _job_id(task, split, model, "RAW", seed)
                    for strategy_id in job_strategies:
                        method = methods[strategy_id]
                        beta_source, fixed_beta, stage_map = _operational_beta(
                            strategy_id, method, loto
                        )
                        rows.append(
                            {
                                "job_id": _job_id(
                                    task, split, model, strategy_id, seed
                                ),
                                "task": task,
                                "split": split,
                                "model": model,
                                "seed": str(seed),
                                "strategy_id": strategy_id,
                                "policy_key": str(method["policy_key"]),
                                "nominal_beta": format(
                                    float(method["nominal_beta"]), ".17g"
                                ),
                                "operational_beta_source": beta_source,
                                "fixed_matched_beta": fixed_beta,
                                "stage_beta_map_json": stage_map,
                                "acquisition_mapping": str(
                                    method["acquisition_mapping"]
                                ),
                                "evaluation_mapping": str(
                                    method["evaluation_mapping"]
                                ),
                                "evidence_class": "V6-MECH",
                                "endpoint_requirements": str(method["endpoint"]),
                                "dependency_job_id": (
                                    raw_id if strategy_id in REPLAY_STRATEGIES else ""
                                ),
                                "frozen_selection_map_sha256": frozen_map_sha,
                                "freeze_lock_sha256": freeze_lock_sha,
                                "code_tree_sha256": code_hash,
                                "freeze_commit": head,
                            }
                        )
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def audit_manifest(rows: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    frozen = read_json(FROZEN)
    lock = read_json(FREEZE_LOCK)
    methods = {
        str(item["id"]): item for item in frozen["canonical_strategies"]
    }
    aliases = {
        str(item["alias_id"]) for item in frozen["alias_registry"]["aliases"]
    }
    contrasts = [
        item
        for item in frozen["prospective_contrasts"]
        if not bool(item.get("analysis_only", False))
    ]
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    expected_strategies = set(methods) - set(NON_JOB_CANONICAL_CONTROLS)
    expected_count = (
        len(TASKS) * len(SPLITS) * len(MODELS) * len(SEEDS) * len(expected_strategies)
    )
    record("manifest row count", len(rows) == expected_count, f"{len(rows)}/{expected_count}")
    job_ids = [row["job_id"] for row in rows]
    record("unique job IDs", len(job_ids) == len(set(job_ids)), f"{len(set(job_ids))} unique")
    seeds = {int(row["seed"]) for row in rows}
    record("exact confirmation seed range", seeds == set(SEEDS), f"{min(seeds)}-{max(seeds)}")
    record(
        "no development or V5 seed",
        not seeds & (set(range(5000, 5040)) | set(range(6000, 6110))),
        "no intersection",
    )
    manifest_strategies = {row["strategy_id"] for row in rows}
    record("no aliases", not manifest_strategies & aliases, str(sorted(aliases)))
    record(
        "no H7 jobs",
        all("h7" not in row["job_id"].lower() for row in rows),
        "H7 is analysis_only",
    )
    canonical_keys = {
        (
            row["task"],
            row["split"],
            row["model"],
            row["seed"],
            row["strategy_id"],
        )
        for row in rows
    }
    record(
        "no duplicate canonical jobs",
        len(canonical_keys) == len(rows),
        f"{len(canonical_keys)} unique canonical keys",
    )
    try:
        validate_manifest_policy_identity(rows, methods.values())
        policy_ok = True
        policy_detail = "all canonical ID/beta/key triples match"
    except ValueError as exc:
        policy_ok = False
        policy_detail = str(exc)
    record("exact policy ID/beta/key consistency", policy_ok, policy_detail)
    selected_rows = [row for row in rows if row["strategy_id"] == "SELECTED_GG"]
    original_rows = [row for row in rows if row["strategy_id"] == "ORIGINAL_GG"]
    gg_ok = (
        {row["nominal_beta"] for row in selected_rows} == {"0.5"}
        and {row["policy_key"] for row in selected_rows}
        == {"SELECTED_GG__beta_0p5"}
        and {row["nominal_beta"] for row in original_rows} == {"1"}
        and {row["policy_key"] for row in original_rows}
        == {"ORIGINAL_GG__beta_1"}
    )
    record("Original/Selected GG manifest identity", gg_ok, "beta/key bindings exact")
    matched_ok = True
    for row in rows:
        if row["strategy_id"] not in {
            "RAW_FIXED_BETA_MATCHED",
            "RAW_STAGE_BETA_MATCHED",
        }:
            continue
        loto = frozen["leave_one_task_out_maps"][row["task"]]
        if row["strategy_id"] == "RAW_FIXED_BETA_MATCHED":
            matched_ok &= (
                row["operational_beta_source"] == "frozen_loto_fixed_matched_beta"
                and float(row["fixed_matched_beta"])
                == float(loto["fixed_matched_beta"])
                and row["stage_beta_map_json"] == ""
            )
        else:
            matched_ok &= (
                row["operational_beta_source"]
                == "frozen_loto_stage_matched_beta_map"
                and json.loads(row["stage_beta_map_json"])
                == loto["stage_matched_beta"]
                and row["fixed_matched_beta"] == ""
            )
    record("matched-beta task-map binding", matched_ok, "all four frozen LOTO maps bound")
    row_by_id = {row["job_id"]: row for row in rows}
    dependency_ok = all(
        not row["dependency_job_id"] or row["dependency_job_id"] in row_by_id
        for row in rows
    )
    record(
        "dependency paths exist where required",
        dependency_ok,
        "all replay dependencies resolve to RAW jobs in the frozen manifest graph",
    )
    pair_ok = True
    pair_details: list[str] = []
    for contrast in contrasts:
        strategy_id = str(contrast["strategy_id"])
        baseline = str(contrast["baseline"])
        for task in TASKS:
            for split in SPLITS:
                for model in MODELS:
                    strategy_seeds = {
                        int(row["seed"])
                        for row in rows
                        if row["task"] == task
                        and row["split"] == split
                        and row["model"] == model
                        and row["strategy_id"] == strategy_id
                    }
                    baseline_seeds = {
                        int(row["seed"])
                        for row in rows
                        if row["task"] == task
                        and row["split"] == split
                        and row["model"] == model
                        and row["strategy_id"] == baseline
                    }
                    if strategy_seeds != set(SEEDS) or baseline_seeds != set(SEEDS):
                        pair_ok = False
                        pair_details.append(
                            f"{contrast['id']}:{task}/{split}/{model}"
                        )
    record(
        "every registered contrast has 40 paired seeds",
        pair_ok,
        "all 11 non-analysis-only contrasts complete" if pair_ok else str(pair_details),
    )
    required = {
        str(item["strategy_id"]) for item in contrasts
    } | {str(item["baseline"]) for item in contrasts}
    record(
        "every required strategy and baseline exists",
        required <= manifest_strategies,
        f"{len(required)} required IDs present",
    )
    family_members = {
        str(member)
        for family in frozen["multiplicity_families"]
        if str(family.get("status", "")) != "placeholder_out_of_scope"
        for member in family.get("members", [])
    }
    registered_ids = {str(item["id"]) for item in contrasts}
    record(
        "multiplicity-family members complete",
        family_members <= registered_ids,
        f"{len(family_members)} inferential members registered",
    )
    frozen_sha = sha256_file(FROZEN)
    lock_sha = sha256_file(FREEZE_LOCK)
    record(
        "frozen-map hash matches every row",
        {row["frozen_selection_map_sha256"] for row in rows} == {frozen_sha},
        frozen_sha,
    )
    record(
        "freeze-lock hash matches every row",
        {row["freeze_lock_sha256"] for row in rows} == {lock_sha},
        lock_sha,
    )
    authority = CanonicalV5Adapter(ROOT).validate_v5_authority_locks()
    record(
        "V5 locks remain unchanged",
        bool(authority["passed"]),
        f"{authority['checked_files']} authority files checked",
    )
    output_root = ROOT / "results" / "v6_p0_confirmation"
    record(
        "no output or outcome file currently exists",
        not output_root.exists(),
        output_root.relative_to(ROOT).as_posix(),
    )
    record(
        "frozen scientific identity remains exact",
        scientific_payload(read_json(CANDIDATE)) == scientific_payload(frozen),
        "administrative fields excluded",
    )
    record(
        "freeze self-hashes remain valid",
        verify_self_hash(frozen, "frozen_map_self_sha256")
        and verify_self_hash(lock, "freeze_lock_self_sha256"),
        "frozen map and lock",
    )
    status = (
        "READY_TO_EXECUTE_FROZEN_P0_CONFIRMATION"
        if all(bool(item["passed"]) for item in checks)
        else "BLOCKED_WITH_EXACT_REASONS"
    )
    return status, checks


def write_audit(status: str, checks: list[dict[str, Any]]) -> None:
    with AUDIT_TABLE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "passed", "detail"])
        writer.writeheader()
        writer.writerows(checks)
    lock = read_json(FREEZE_LOCK)
    head = git("rev-parse", "HEAD")
    lines = [
        "# V6 P0 confirmation manifest dry-run audit",
        "",
        f"Final status: **{status}**",
        "",
        "| Check | Result | Detail |",
        "|---|---:|---|",
    ]
    for item in checks:
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['check']} | {'PASS' if item['passed'] else 'FAIL'} | {detail} |")
    lines.extend(
        [
            "",
            "## Freeze commit record",
            "",
            f"- Commit before freeze: `{lock['git_commit_before_freeze']}`.",
            f"- Freeze commit: `{head}`.",
            "- Clean-tree status immediately after freeze commit and before manifest generation: `CLEAN`.",
            f"- Code-tree hash after commit: `{code_tree_sha256(ROOT / 'src' / 'transportability_v6')}`.",
            "",
            "## Execution boundary",
            "",
            "- The manifest was generated only after the freeze commit.",
            "- This was a structural dry run; no confirmation worker or job was started.",
            "- No confirmation output or outcome file was read.",
            "- Final execution approval is still required.",
            "",
            "## Exact blockers",
            "",
        ]
    )
    failures = [item for item in checks if not bool(item["passed"])]
    if failures:
        lines.extend(f"- `{item['check']}`: {item['detail']}" for item in failures)
    else:
        lines.append("- None.")
    AUDIT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def manifest_audit() -> None:
    if MANIFEST.exists() or AUDIT_TABLE.exists() or AUDIT_REPORT.exists():
        raise FileExistsError("refusing to overwrite confirmation manifest/audit artifacts")
    rows = build_manifest()
    status, checks = audit_manifest(rows)
    write_audit(status, checks)
    print(
        json.dumps(
            {
                "status": status,
                "manifest_rows": len(rows),
                "checks_passed": sum(bool(item["passed"]) for item in checks),
                "checks_total": len(checks),
                "manifest_sha256": sha256_file(MANIFEST),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "manifest-audit"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        manifest_audit()


if __name__ == "__main__":
    main()
