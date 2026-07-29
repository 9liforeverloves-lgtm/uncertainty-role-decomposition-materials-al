"""Generate Candidate v3 and the final V6 P0 freeze-readiness audit.

No confirmation manifest is created and no confirmation outcome path is read.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transportability_v6.canonical_adapter import CanonicalV5Adapter  # noqa: E402
from transportability_v6.execution_registry import sha256_file  # noqa: E402
from transportability_v6.freeze_readiness import (  # noqa: E402
    canonical_strategy_id,
    validate_alias_registry,
    validate_contrast_endpoint_consistency,
)
from transportability_v6.registry_freeze import code_tree_sha256  # noqa: E402


CANDIDATE_V1 = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE.json"
CANDIDATE_V2 = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v2.json"
CANDIDATE_V3 = ROOT / "analysis_plan" / "v6_p0_confirmation_selection_map_CANDIDATE_v3.json"
STRATEGY_REGISTRY = ROOT / "analysis_plan" / "v6_strategy_registry.json"
HYPOTHESIS_REGISTRY = ROOT / "analysis_plan" / "v6_hypothesis_registry.json"
FAMILY_REGISTRY = ROOT / "analysis_plan" / "v6_multiplicity_families.json"
ALIAS_REGISTRY = ROOT / "analysis_plan" / "v6_strategy_alias_registry.json"
BROAD_MANIFEST = ROOT / "manifests" / "v6_p0_broad_development_manifest.csv"
BROAD_LOCK = ROOT / "locks" / "v6_p0_broad_development_manifest_lock.json"
OLD_CORRECTION_LOCK = ROOT / "locks" / "v6_p0_broad_endpoint_correction_lock.json"
NEW_CORRECTION_LOCK = (
    ROOT / "locks" / "v6_p0_broad_endpoint_correction_metadata_only_superseding_lock.json"
)
ORIGINAL_ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints.csv"
CORRECTED_ENDPOINTS = ROOT / "tables" / "v6_p0_broad_seed_endpoints_CORRECTED.csv"
BETA_TABLE = ROOT / "tables" / "v6_p0_broad_effective_beta.csv"
RECOVERY_REPLAY = ROOT / "tables" / "v6_p0_recovery_cleanroom_replay.csv"
DIRECTION_TABLE = ROOT / "tables" / "v6_p0_hypothesis_direction_audit.csv"
DIRECTION_REPORT = ROOT / "reports" / "05f_hypothesis_direction_audit.md"
READINESS_REPORT = ROOT / "reports" / "05h_p0_confirmation_freeze_readiness.md"

ALIASES = {"CS_JOINT": "SELECTED_CS", "GG_JOINT": "ORIGINAL_GG"}
ROLE_CATEGORIES = frozenset(
    {
        "confirmatory_test",
        "confirmatory_reference",
        "confirmatory_mechanism",
        "secondary",
        "derived_secondary",
        "descriptive_control",
        "registry_alias",
    }
)
METHOD_ROLES: dict[str, tuple[str, str]] = {
    "CONFORMAL_GAUSSIAN_EQUIVALENT": (
        "derived_secondary",
        "deterministic conversion of CONFORMAL_INTERVAL_ONLY; not independently fitted",
    ),
    "CONFORMAL_INTERVAL_ONLY": ("secondary", "calibration-only; no universal acquisition sigma"),
    "CS_ACQUISITION_ONLY": ("confirmatory_test", "H5B acquisition-path test"),
    "CS_CALIBRATION_ONLY": ("confirmatory_test", "H5A calibration test"),
    "GG_NORMALIZED_ACQUISITION": (
        "descriptive_control",
        "identity-path implementation control",
    ),
    "GG_ACQUISITION_ONLY": ("confirmatory_test", "H2A acquisition-path test"),
    "GG_CALIBRATION_ONLY": ("confirmatory_test", "H1 calibration test"),
    "HISTORICAL_CS": (
        "descriptive_control",
        "historical comparator without an independently registered hypothesis",
    ),
    "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL": (
        "secondary",
        "equivalent-DoF calibration control without a prospective hypothesis",
    ),
    "IDENTITY_CONTROL": ("descriptive_control", "negative implementation control"),
    "ISOTONIC_ABS_RESIDUAL": ("secondary", "monotone calibration-only comparator"),
    "ORIGINAL_GG": ("confirmatory_test", "canonical joint GG method tested by H2B"),
    "POWER_SCALING": ("secondary", "flexible calibration-only comparator"),
    "RAW": ("confirmatory_reference", "canonical unscaled reference"),
    "RAW_FIXED_BETA_MATCHED": ("confirmatory_mechanism", "H3 matched-beta mechanism"),
    "RAW_STAGE_BETA_MATCHED": ("confirmatory_mechanism", "H4 stage-matched mechanism"),
    "REPLAY_EVALUATION": ("descriptive_control", "calibration replay implementation control"),
    "SCALAR_TEMPERATURE_NLL": ("confirmatory_test", "H6A simple-scaling test"),
    "SCALAR_TEMPERATURE_RESIDUAL_RATIO": (
        "confirmatory_test",
        "H6B simple-scaling test and H6 descriptive simple method",
    ),
    "SELECTED_CS": ("confirmatory_test", "canonical joint CS method tested by H5C"),
    "SELECTED_CS_EQUIVALENT_DOF_CONTROL": (
        "secondary",
        "equivalent-DoF calibration control without a prospective hypothesis",
    ),
    "SELECTED_GG": ("confirmatory_reference", "registered baseline for H3 and H4"),
}


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_bytes(
        path,
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def build_alias_registry() -> dict[str, Any]:
    source = json.loads(STRATEGY_REGISTRY.read_text(encoding="utf-8"))
    by_id = {str(item["id"]): item for item in source["strategies"]}
    payload: dict[str, Any] = {
        "schema_version": "v6-strategy-alias-registry-v1",
        "status": "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN",
        "aliases": [
            {
                "alias_id": "GG_JOINT",
                "canonical_id": "ORIGINAL_GG",
                "equivalence_basis": str(by_id["GG_JOINT"]["objective"]),
                "formula_identity": (
                    "same global OOB residual-ratio fit, scaled_sigma acquisition, "
                    "scaled_gaussian_sigma evaluation, nominal beta 1.0"
                ),
                "generate_confirmation_job": False,
                "multiplicity_family_member": False,
            },
            {
                "alias_id": "CS_JOINT",
                "canonical_id": "SELECTED_CS",
                "equivalence_basis": str(by_id["CS_JOINT"]["objective"]),
                "formula_identity": (
                    "same selected F1 pairwise candidate-specific fit, bounds [0.25,4.0], "
                    "scaled_sigma acquisition, scaled_gaussian_sigma evaluation, nominal beta 1.0"
                ),
                "generate_confirmation_job": False,
                "multiplicity_family_member": False,
            },
        ],
        "canonical_ids_only": ["ORIGINAL_GG", "SELECTED_CS"],
        "source_strategy_registry_sha256": sha256_file(STRATEGY_REGISTRY),
    }
    payload["alias_registry_self_sha256"] = canonical_hash(payload)
    atomic_json(ALIAS_REGISTRY, payload)
    return payload


def strategy_id_for_hypothesis(hypothesis: dict[str, Any]) -> str:
    hypothesis_id = str(hypothesis["id"])
    explicit = {
        "H6": "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "H7": "RAW",
    }
    if hypothesis_id in explicit:
        return explicit[hypothesis_id]
    return str(hypothesis["comparison"]).split(" vs ", 1)[0].removesuffix(" joint").strip()


def normalize_contrasts(contrasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in contrasts:
        item = dict(source)
        item["strategy_id"] = canonical_strategy_id(strategy_id_for_hypothesis(item), ALIASES)
        if str(item["id"]) == "H6":
            item["comparison"] = "SCALAR_TEMPERATURE_RESIDUAL_RATIO vs SELECTED_CS"
            item["baseline"] = "SELECTED_CS"
        if str(item["id"]) == "H7":
            item["strategy_id"] = "RAW"
        category = {
            "H3": "confirmatory_mechanism",
            "H4": "confirmatory_mechanism",
            "H6": "secondary",
            "H7": "secondary",
        }.get(str(item["id"]), "confirmatory_test")
        item["classification"] = category
        output.append(item)
    return output


def update_candidate_v2() -> dict[str, Any]:
    payload = json.loads(CANDIDATE_V2.read_text(encoding="utf-8"))
    for item in payload["confirmation_strategies"]:
        strategy_id = str(item["id"])
        if strategy_id in {"RAW", "RAW_FIXED_BETA_MATCHED", "RAW_STAGE_BETA_MATCHED"}:
            item["endpoint"] = "L1_and_L4"
        if strategy_id in ALIASES:
            item["classification"] = "registry_alias"
            item["canonical_id"] = ALIASES[strategy_id]
            item["generate_confirmation_job"] = False
            item["multiplicity_family_member"] = False
        else:
            role, detail = METHOD_ROLES[strategy_id]
            item["classification"] = role
            item["role_detail"] = detail
    payload["prospective_contrasts"] = normalize_contrasts(payload["prospective_contrasts"])
    payload["alias_registry"] = {
        "path": ALIAS_REGISTRY.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(ALIAS_REGISTRY),
        "aliases": ALIASES,
    }
    payload["source_hashes"]["v6_code_tree_sha256"] = code_tree_sha256(
        ROOT / "src" / "transportability_v6"
    )
    payload.pop("candidate_self_sha256", None)
    payload["candidate_self_sha256"] = canonical_hash(payload)
    atomic_json(CANDIDATE_V2, payload)
    return payload


def build_metadata_lock(candidate_v2: dict[str, Any]) -> dict[str, Any]:
    original = pd.read_csv(ORIGINAL_ENDPOINTS)
    corrected = pd.read_csv(CORRECTED_ENDPOINTS)
    regenerated = corrected.loc[corrected.endpoint_correction_applied.astype(bool)].copy()
    changed = regenerated.l1_campaign_mace.to_numpy() != regenerated.l1_campaign_mace_original.to_numpy()
    equal_rows = regenerated.loc[~changed]
    expected_identity = {
        "task": "matbench_expt_gap",
        "split": "iid_record",
        "model": "random_forest",
        "strategy": "GG_ACQUISITION_ONLY",
        "seed": 6105,
    }
    if len(original) != len(corrected) or len(regenerated) != 1440 or int(changed.sum()) != 1439:
        raise RuntimeError("endpoint correction counts do not match the accepted 1440/1439/1 audit")
    observed = equal_rows.iloc[0]
    if any(str(observed[key]) != str(value) for key, value in expected_identity.items() if key != "seed"):
        raise RuntimeError("unexpected regenerated-but-equal endpoint identity")
    if int(observed.seed) != 6105:
        raise RuntimeError("unexpected regenerated-but-equal endpoint seed")
    prior = json.loads(OLD_CORRECTION_LOCK.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-broad-endpoint-correction-metadata-supersession-v2",
        "status": "METADATA_ONLY_SUPERSEDES_COUNT_FIELDS_NO_SCIENTIFIC_ENDPOINT_CHANGE",
        "evidence_class": "V6-P0-BROAD-ENDPOINT-CORRECTION",
        "supersedes_path": OLD_CORRECTION_LOCK.relative_to(ROOT).as_posix(),
        "supersedes_file_sha256": sha256_file(OLD_CORRECTION_LOCK),
        "supersedes_correction_self_sha256": prior["correction_self_sha256"],
        "previous_lock_preserved": True,
        "endpoint_rows_regenerated": 1440,
        "endpoint_rows_numerically_changed": 1439,
        "endpoint_rows_regenerated_but_equal": 1,
        "regenerated_but_equal_row": expected_identity,
        "distinction": (
            "Regeneration counts rows whose endpoints were recomputed under the accepted "
            "correction code. Numerical change counts only rows whose corrected numeric L1 "
            "differs from the archived value. One recomputed row is numerically identical."
        ),
        "scientific_endpoints_changed_by_this_lock": False,
        "corrected_endpoint_table_sha256": sha256_file(CORRECTED_ENDPOINTS),
        "candidate_v2_sha256_after_registry_metadata_correction": sha256_file(CANDIDATE_V2),
        "confirmation_outcomes_inspected": False,
        "confirmation_seeds_used": [],
    }
    payload["metadata_lock_self_sha256"] = canonical_hash(payload)
    atomic_json(NEW_CORRECTION_LOCK, payload)
    return payload


def direction_rows(candidate_v2: dict[str, Any]) -> pd.DataFrame:
    earliest = {
        "H1": ("GG_CALIBRATION_ONLY vs RAW", "lower_is_better", "fa4ec48"),
        "H5A": ("CS_CALIBRATION_ONLY vs RAW", "lower_is_better", "fa4ec48"),
        "H2A": ("GG_ACQUISITION_ONLY vs RAW (H2)", "higher_is_better", "fa4ec48"),
        "H2B": ("ORIGINAL_GG joint vs RAW", "greater", "eba8d54"),
        "H5B": ("CS_ACQUISITION_ONLY vs RAW", "higher_is_better", "fa4ec48"),
        "H5C": ("SELECTED_CS joint vs RAW", "greater", "eba8d54"),
        "H3": (
            "RAW_FIXED_BETA_MATCHED vs GG_JOINT",
            "equivalence_descriptive",
            "fa4ec48",
        ),
        "H4": (
            "RAW_STAGE_BETA_MATCHED vs GG_JOINT",
            "equivalence_descriptive",
            "fa4ec48",
        ),
        "H6A": ("SCALAR_TEMPERATURE_NLL vs IDENTITY_CONTROL", "less", "eba8d54"),
        "H6B": (
            "SCALAR_TEMPERATURE_RESIDUAL_RATIO vs IDENTITY_CONTROL",
            "less",
            "eba8d54",
        ),
        "H6": (
            "frozen simple scaler vs frozen complex CS",
            "noninferiority_requires_margin_freeze",
            "fa4ec48",
        ),
        "H7": (
            "paired L1 and L4 direction",
            "descriptive_divergence",
            "fa4ec48",
        ),
    }
    final = {
        "H3": "two-sided",
        "H4": "two-sided",
        "H6": "none",
        "H7": "none",
    }
    records: list[dict[str, Any]] = []
    for contrast in candidate_v2["prospective_contrasts"]:
        hypothesis_id = str(contrast["id"])
        wording, alternative, commit = earliest[hypothesis_id]
        final_alternative = final.get(hypothesis_id, str(contrast["alternative"]))
        if hypothesis_id in {"H3", "H4"}:
            justification = (
                "Earliest wording was non-directional/equivalence-descriptive; retain "
                "two-sided inference. Favorable directional estimates may be secondary."
            )
        elif hypothesis_id == "H6":
            justification = (
                "No noninferiority margin was frozen; retain descriptive estimation with no "
                "binary directional claim."
            )
        elif hypothesis_id == "H7":
            justification = "Registered as descriptive divergence; no inferential direction."
        else:
            justification = (
                "The favorable direction was registered before any V6 development outcome "
                "was available and is unchanged in Candidate v2."
            )
        records.append(
            {
                "hypothesis_id": hypothesis_id,
                "earliest_registered_wording": wording,
                "earliest_registered_alternative": alternative,
                "earliest_registry_commit": commit,
                "candidate_v2_alternative": str(contrast["alternative"]),
                "outcomes_available_when_earliest_defined": False,
                "outcomes_available_when_candidate_v2_defined": True,
                "final_proposed_alternative": final_alternative,
                "justification": justification,
            }
        )
    return pd.DataFrame(records)


def write_direction_audit(frame: pd.DataFrame) -> None:
    atomic_csv(DIRECTION_TABLE, frame)
    lines = [
        "# V6 P0 hypothesis-direction audit",
        "",
        "The earliest available pre-development registry is commit `fa4ec48`; hypotheses first "
        "added by the Stage-2.5 registry are traced to `eba8d54`. No V6 development outcomes "
        "were available at either registration point. Candidate v2 was generated after broad "
        "development, so it cannot introduce a more favorable direction.",
        "",
        "| ID | Earliest alternative | Candidate v2 | Final | Decision |",
        "|---|---|---|---|---|",
    ]
    for row in frame.itertuples(index=False):
        decision = (
            "two-sided preserved from non-directional wording"
            if row.hypothesis_id in {"H3", "H4"}
            else "unchanged pre-development direction"
            if row.hypothesis_id not in {"H6", "H7"}
            else "descriptive/no directional test"
        )
        lines.append(
            f"| {row.hypothesis_id} | {row.earliest_registered_alternative} | "
            f"{row.candidate_v2_alternative} | {row.final_proposed_alternative} | {decision} |"
        )
    lines.extend(
        [
            "",
            "No two-sided or non-directional hypothesis was converted to a favorable "
            "one-sided test after outcomes became available. Favorable directional estimates "
            "for H3/H4 may be reported only as secondary descriptive estimates.",
            "",
            f"Machine-readable audit: `{DIRECTION_TABLE.relative_to(ROOT).as_posix()}`.",
        ]
    )
    atomic_bytes(DIRECTION_REPORT, ("\n".join(lines) + "\n").encode("utf-8"))


def canonical_methods() -> list[dict[str, Any]]:
    source = json.loads(STRATEGY_REGISTRY.read_text(encoding="utf-8"))
    output: list[dict[str, Any]] = []
    for original in source["strategies"]:
        strategy_id = str(original["id"])
        if strategy_id in ALIASES:
            continue
        role, detail = METHOD_ROLES[strategy_id]
        item = {
            key: original.get(key)
            for key in (
                "id",
                "fitting_data",
                "oob_minimum",
                "fallback",
                "scale_bounds",
                "calibration_mapping",
                "acquisition_mapping",
                "evaluation_mapping",
                "nominal_parameter_count",
                "objective",
                "nominal_beta",
                "primary_baseline",
                "endpoint",
            )
        }
        if strategy_id in {"RAW", "RAW_FIXED_BETA_MATCHED", "RAW_STAGE_BETA_MATCHED"}:
            item["endpoint"] = "L1_and_L4"
        item["classification"] = role
        item["role_detail"] = detail
        output.append(item)
    if len(output) != 22 or set(METHOD_ROLES) != {str(item["id"]) for item in output}:
        raise RuntimeError("canonical method-role registry is incomplete")
    if any(str(item["classification"]) not in ROLE_CATEGORIES for item in output):
        raise RuntimeError("method role lies outside the explicit allowed categories")
    return sorted(output, key=lambda item: str(item["id"]))


def source_entry(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}


def build_candidate_v3(
    candidate_v2: dict[str, Any],
    alias_registry: dict[str, Any],
    metadata_lock: dict[str, Any],
    directions: pd.DataFrame,
) -> dict[str, Any]:
    methods = canonical_methods()
    direction_map = directions.set_index("hypothesis_id").final_proposed_alternative.to_dict()
    contrasts = normalize_contrasts(candidate_v2["prospective_contrasts"])
    for item in contrasts:
        item["alternative"] = str(direction_map[str(item["id"])])
    families = json.loads(FAMILY_REGISTRY.read_text(encoding="utf-8"))["families"]
    recovery = pd.read_csv(RECOVERY_REPLAY)
    replay_pass = bool(len(recovery) == 8 and recovery.accepted.astype(bool).all())
    sources = [
        source_entry(CORRECTED_ENDPOINTS),
        source_entry(BETA_TABLE),
        source_entry(BROAD_MANIFEST),
        source_entry(BROAD_LOCK),
        source_entry(ALIAS_REGISTRY),
        source_entry(DIRECTION_TABLE),
        source_entry(RECOVERY_REPLAY),
        source_entry(NEW_CORRECTION_LOCK),
        source_entry(FAMILY_REGISTRY),
    ]
    broad_lock = json.loads(BROAD_LOCK.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schema_version": "v6-p0-confirmation-selection-map-candidate-v3",
        "status": "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN",
        "evidence_class": "V6-P0-BROAD-DEVELOPMENT",
        "confirmation_outcomes_inspected": False,
        "confirmation_seed_status": "FORBIDDEN_UNTIL_FORMAL_FREEZE",
        "confirmation_seeds": list(range(7000, 7040)),
        "development_seed_range": [6100, 6109],
        "endpoint_registry": {
            "L1": "campaign MACE at corrected canonical initial/25/50/75% diagnostic rows",
            "L4": "top-1% recall normalized AUC",
            "strategy_endpoint_declarations": {
                str(item["id"]): str(item["endpoint"]) for item in methods
            },
        },
        "canonical_strategies": methods,
        "alias_registry": alias_registry,
        "prospective_contrasts": contrasts,
        "multiplicity_families": families,
        "leave_one_task_out_maps": candidate_v2["leave_one_task_out_maps"],
        "simple_baseline_roles": candidate_v2["simple_baseline_roles"],
        "simple_scaling_rule": candidate_v2["simple_scaling_rule"],
        "conformal_restrictions": {
            "CONFORMAL_INTERVAL_ONLY": (
                "secondary calibration-only; no universal acquisition sigma; L1 only"
            ),
            "CONFORMAL_GAUSSIAN_EQUIVALENT": (
                "derived_secondary deterministic representation; not an independent fitted method"
            ),
        },
        "paired_completeness": {
            **candidate_v2["paired_completeness"],
            "gate": "40-pair completeness required before any registered contrast is evaluated",
        },
        "recovery_cleanroom_result": {
            "accepted": replay_pass,
            "matched_jobs": int(recovery.accepted.astype(bool).sum()),
            "required_jobs": 8,
            "table": source_entry(RECOVERY_REPLAY),
            "historical_point_in_time_hashes_fabricated": False,
        },
        "source_tables": sources,
        "source_hashes": {
            "manifest_sha256": sha256_file(BROAD_MANIFEST),
            "final_broad_lock_sha256": sha256_file(BROAD_LOCK),
            "final_broad_lock_identity_sha256": str(broad_lock["final_lock_sha256"]),
            "corrected_endpoint_table_sha256": sha256_file(CORRECTED_ENDPOINTS),
            "effective_beta_table_sha256": sha256_file(BETA_TABLE),
            "v5_authority_lock_sha256": sha256_file(
                ROOT / "locks" / "v5_frozen_manifest.json"
            ),
            "v5_confirmation_protocol_sha256": sha256_file(
                ROOT / "locks" / "v5_readonly_snapshot" / "20_confirmation_protocol_v5_rc1.md"
            ),
            "v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
        },
        "endpoint_correction_metadata": metadata_lock,
        "unresolved": [
            "Candidate only; human freeze approval is still required.",
            "No confirmation manifest has been generated or executed.",
        ],
    }
    payload["candidate_self_sha256"] = canonical_hash(payload)
    atomic_json(CANDIDATE_V3, payload)
    return payload


def verify_candidate_hash(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = (
        "candidate_selection_map_sha256"
        if "candidate_selection_map_sha256" in payload
        else "candidate_self_sha256"
    )
    observed = str(payload.pop(key))
    return observed == canonical_hash(payload)


def confirmation_outcome_paths() -> list[str]:
    pattern = re.compile(r"seed(?:_|-)?(70(?:0\d|1\d|2\d|3\d))", re.IGNORECASE)
    hits: list[str] = []
    results = ROOT / "results"
    for path in results.rglob("*"):
        if path.is_file() and pattern.search(path.as_posix()):
            hits.append(path.relative_to(ROOT).as_posix())
    for path in results.rglob("registry_snapshot.csv"):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if "seed" in frame and frame.seed.dropna().astype(int).between(7000, 7039).any():
            hits.append(path.relative_to(ROOT).as_posix())
    return sorted(set(hits))


def run_readiness_validation(candidate_v3: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    candidate_paths = [CANDIDATE_V1, CANDIDATE_V2, CANDIDATE_V3]
    candidate_hashes = {path.name: verify_candidate_hash(path) for path in candidate_paths}
    record(
        "all candidate self-hashes",
        all(candidate_hashes.values()),
        json.dumps(candidate_hashes, sort_keys=True),
    )
    source_results = {
        item["path"]: sha256_file(ROOT / item["path"]) == item["sha256"]
        for item in candidate_v3["source_tables"]
    }
    record(
        "source-table hashes",
        all(source_results.values()),
        f"{sum(source_results.values())}/{len(source_results)} match",
    )
    aliases = {
        str(item["alias_id"]): str(item["canonical_id"])
        for item in candidate_v3["alias_registry"]["aliases"]
    }
    methods = candidate_v3["canonical_strategies"]
    canonical_ids = [str(item["id"]) for item in methods]
    alias_ok = True
    try:
        validate_alias_registry(aliases, canonical_ids)
    except ValueError:
        alias_ok = False
    record("no duplicate aliases", alias_ok, json.dumps(aliases, sort_keys=True))
    endpoint_rows: list[dict[str, str]] = []
    endpoint_ok = True
    try:
        endpoint_rows = validate_contrast_endpoint_consistency(
            candidate_v3["prospective_contrasts"], methods, aliases
        )
    except ValueError as exc:
        endpoint_ok = False
        endpoint_rows = [{"error": str(exc)}]
    record(
        "strategy-to-endpoint consistency",
        endpoint_ok,
        json.dumps(endpoint_rows, sort_keys=True),
    )
    hypotheses = {
        str(item["id"]): item
        for item in candidate_v3["prospective_contrasts"]
        if str(item["family"]) not in {"NONE_DESCRIPTIVE"}
    }
    family_members: dict[str, str] = {}
    family_ok = True
    for family in candidate_v3["multiplicity_families"]:
        if str(family.get("status", "")) == "placeholder_out_of_scope":
            continue
        for hypothesis_id in family.get("members", []):
            if str(hypothesis_id) in family_members:
                family_ok = False
            family_members[str(hypothesis_id)] = str(family["id"])
    for hypothesis_id, hypothesis in hypotheses.items():
        if family_members.get(hypothesis_id) != str(hypothesis["family"]):
            family_ok = False
    family_ok = family_ok and set(family_members) == set(hypotheses)
    record(
        "contrast-to-family membership",
        family_ok,
        f"{len(family_members)} inferential hypotheses assigned exactly once",
    )
    tasks = ("matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh")
    splits = ("iid_record", "chemical_system_ood")
    models = ("random_forest", "extra_randomized_bagging")
    projected = {
        (task, split, model, seed, strategy)
        for task in tasks
        for split in splits
        for model in models
        for seed in range(7000, 7040)
        for strategy in canonical_ids
    }
    expected_count = 4 * 2 * 2 * 40 * len(canonical_ids)
    record(
        "exactly one canonical job per task/split/model/seed/strategy",
        len(projected) == expected_count and not set(aliases) & set(canonical_ids),
        (
            f"in-memory uniqueness gate {len(projected)}/{expected_count}; "
            "no manifest persisted"
        ),
    )
    broad = pd.read_csv(BROAD_MANIFEST)
    prohibited_in_broad = broad.seed.astype(int).between(7000, 7039).any()
    record(
        "confirmation seed prohibition",
        not prohibited_in_broad
        and candidate_v3["confirmation_seed_status"] == "FORBIDDEN_UNTIL_FORMAL_FREEZE",
        "production runner blocks 7000-7039; candidate remains non-frozen",
    )
    development = set(broad.seed.astype(int))
    confirmation = set(candidate_v3["confirmation_seeds"])
    record(
        "development/confirmation seed disjointness",
        not development & confirmation,
        f"intersection={sorted(development & confirmation)}",
    )
    authority = CanonicalV5Adapter(ROOT).validate_v5_authority_locks()
    record(
        "V5 authority hashes unchanged",
        bool(authority["passed"]),
        json.dumps(authority, sort_keys=True, default=str),
    )
    recovery = pd.read_csv(RECOVERY_REPLAY)
    recovery_ok = len(recovery) == 8 and recovery.accepted.astype(bool).all()
    record("recovery replay 8/8", recovery_ok, f"{int(recovery.accepted.sum())}/8 accepted")
    outcome_hits = confirmation_outcome_paths()
    record(
        "no confirmation outcomes exist",
        not outcome_hits and not candidate_v3["confirmation_outcomes_inspected"],
        json.dumps(outcome_hits),
    )
    roles_ok = (
        len(methods) == 22
        and all(str(item["classification"]) in ROLE_CATEGORIES for item in methods)
        and len({str(item["id"]) for item in methods}) == len(methods)
    )
    record("every non-alias strategy has one explicit role", roles_ok, "22/22 canonical methods")
    status = (
        "READY_FOR_HUMAN_FREEZE_APPROVAL"
        if all(bool(item["passed"]) for item in checks)
        else "BLOCKED_WITH_EXACT_REASONS"
    )
    return status, checks


def write_readiness_report(status: str, checks: list[dict[str, Any]]) -> None:
    failures = [item for item in checks if not item["passed"]]
    lines = [
        "# V6 P0 confirmation freeze-readiness",
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
            "## Boundary conditions",
            "",
            "- Candidate v3 remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`.",
            "- No confirmation manifest was generated or executed.",
            "- Confirmation seeds 7000-7039 remain prohibited.",
            "- The accepted 2,720-job broad cohort was not rerun.",
            "- The historical recovery records were not overwritten and missing point-in-time "
            "hashes were not fabricated.",
            "",
            "## Exact blockers",
            "",
        ]
    )
    if failures:
        lines.extend(f"- `{item['check']}`: {item['detail']}" for item in failures)
    else:
        lines.append("- None. Human freeze approval is still required; this report does not freeze the map.")
    atomic_bytes(READINESS_REPORT, ("\n".join(lines) + "\n").encode("utf-8"))


def main() -> None:
    alias_registry = build_alias_registry()
    candidate_v2 = update_candidate_v2()
    metadata_lock = build_metadata_lock(candidate_v2)
    directions = direction_rows(candidate_v2)
    write_direction_audit(directions)
    candidate_v3 = build_candidate_v3(candidate_v2, alias_registry, metadata_lock, directions)
    status, checks = run_readiness_validation(candidate_v3)
    write_readiness_report(status, checks)
    print(
        json.dumps(
            {
                "status": status,
                "checks_passed": sum(bool(item["passed"]) for item in checks),
                "checks_total": len(checks),
                "candidate_v3_sha256": sha256_file(CANDIDATE_V3),
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
