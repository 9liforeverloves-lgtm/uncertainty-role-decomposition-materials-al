"""Generate the Stage-2.5 source-addressed analysis registries.

This script intentionally creates no development or confirmation execution
jobs.  It only freezes the pre-development design documents requested in
Stage-2.5.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transportability_v6.production_strategies import PRODUCTION_STRATEGIES
from transportability_v6.registry_freeze import (
    code_tree_sha256,
    current_git_commit,
    freeze_document,
    sha256_file,
    write_frozen_document,
)


STATUS = "STAGE_2_5_FROZEN_PRE_DEVELOPMENT"


def _source_hashes() -> dict[str, str]:
    return {
        "v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
        "v5_authority_lock_sha256": sha256_file(ROOT / "locks" / "v5_frozen_manifest.json"),
        "v5_confirmation_protocol_sha256": sha256_file(
            ROOT / "revision_v5" / "20_confirmation_protocol_v5_rc1.md"
        ),
    }


def _hypotheses() -> dict[str, object]:
    return {
        "schema_version": "v6-hypothesis-registry-v3",
        "status": STATUS,
        "bootstrap_root_seed": 610001,
        "sign_flip_root_seed": 610002,
        "paired_inference": "10,000 bootstrap; 10,000 sign flips; add-one p value",
        "hypotheses": [
            {"id": "H1", "comparison": "GG_CALIBRATION_ONLY vs RAW", "baseline": "RAW", "endpoint": "L1", "effect_definition": "test minus baseline MACE", "alternative": "less", "family": "P0_L1_CALIBRATION_ONLY", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H5A", "comparison": "CS_CALIBRATION_ONLY vs RAW", "baseline": "RAW", "endpoint": "L1", "effect_definition": "test minus baseline MACE", "alternative": "less", "family": "P0_L1_CALIBRATION_ONLY", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H2A", "comparison": "GG_ACQUISITION_ONLY vs RAW", "baseline": "RAW", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "greater", "family": "P0_L4_ACQUISITION_AND_JOINT", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H2B", "comparison": "ORIGINAL_GG joint vs RAW", "baseline": "RAW", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "greater", "family": "P0_L4_ACQUISITION_AND_JOINT", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H5B", "comparison": "CS_ACQUISITION_ONLY vs RAW", "baseline": "RAW", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "greater", "family": "P0_L4_ACQUISITION_AND_JOINT", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H5C", "comparison": "SELECTED_CS joint vs RAW", "baseline": "RAW", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "greater", "family": "P0_L4_ACQUISITION_AND_JOINT", "classification": "confirmatory", "evidence_class": "V6-MECH"},
            {"id": "H3", "comparison": "RAW_FIXED_BETA_MATCHED vs SELECTED_GG", "baseline": "SELECTED_GG", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "two-sided", "family": "P0_L4_MATCHED_BETA_MECHANISM", "classification": "confirmatory_mechanism", "evidence_class": "V6-MECH"},
            {"id": "H4", "comparison": "RAW_STAGE_BETA_MATCHED vs SELECTED_GG", "baseline": "SELECTED_GG", "endpoint": "L4", "effect_definition": "test minus baseline nAUC", "alternative": "two-sided", "family": "P0_L4_MATCHED_BETA_MECHANISM", "classification": "confirmatory_mechanism", "evidence_class": "V6-MECH"},
            {"id": "H6A", "comparison": "SCALAR_TEMPERATURE_NLL vs IDENTITY_CONTROL", "baseline": "IDENTITY_CONTROL", "endpoint": "L1", "effect_definition": "test minus baseline MACE", "alternative": "less", "family": "P0_L1_SIMPLE_SCALING", "classification": "confirmatory_simple_scaling", "evidence_class": "V6-MECH"},
            {"id": "H6B", "comparison": "SCALAR_TEMPERATURE_RESIDUAL_RATIO vs IDENTITY_CONTROL", "baseline": "IDENTITY_CONTROL", "endpoint": "L1", "effect_definition": "test minus baseline MACE", "alternative": "less", "family": "P0_L1_SIMPLE_SCALING", "classification": "confirmatory_simple_scaling", "evidence_class": "V6-MECH"},
            {"id": "H6", "comparison": "frozen simple scaler versus frozen complex CS", "baseline": "complex CS", "endpoint": "L1", "effect_definition": "paired effect estimate and interval only", "alternative": "none", "family": "NONE_DESCRIPTIVE", "classification": "descriptive_estimation_no_noninferiority_claim", "binary_claim": False, "evidence_class": "V6-MECH"},
            {"id": "H7", "comparison": "paired L1/L4 direction divergence", "baseline": "RAW", "endpoint": "L1_L4_joint", "effect_definition": "descriptive direction table", "alternative": "none", "family": "NONE_DESCRIPTIVE", "classification": "secondary_descriptive", "evidence_class": "V6-MECH"},
        ],
    }


def _families() -> dict[str, object]:
    return {
        "schema_version": "v6-multiplicity-families-v3",
        "status": STATUS,
        "method": "Benjamini-Hochberg within exact registered family",
        "alpha": 0.05,
        "families": [
            {"id": "P0_L1_CALIBRATION_ONLY", "endpoint": "L1", "members": ["H1", "H5A"], "family_size": 2},
            {"id": "P0_L4_ACQUISITION_AND_JOINT", "endpoint": "L4", "members": ["H2A", "H2B", "H5B", "H5C"], "family_size": 4},
            {"id": "P0_L4_MATCHED_BETA_MECHANISM", "endpoint": "L4", "members": ["H3", "H4"], "family_size": 2},
            {"id": "P0_L1_SIMPLE_SCALING", "endpoint": "L1", "members": ["H6A", "H6B"], "family_size": 2},
            {"id": "P1_MODEL_FAMILY", "endpoint": "L1_and_L4", "members": [], "status": "placeholder_out_of_scope"},
            {"id": "P1_ACQUISITION_FAMILY", "endpoint": "L1_and_L4", "members": [], "status": "placeholder_out_of_scope"},
            {"id": "P1_EXTERNAL_DATASET", "endpoint": "L1_and_L4", "members": [], "status": "placeholder_out_of_scope"},
        ],
        "excluded_from_bh": ["H6", "H7", "smoke engineering validation", "P1 placeholders"],
    }


def _strategy_entry(identifier: str, **updates: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "id": identifier,
        "evidence_class": "V6-MECH",
        "fitting_data": "OOB residual and raw sigma from currently labelled records only",
        "oob_minimum": 0,
        "fallback": "identity_raw_sigma",
        "scale_bounds": None,
        "calibration_mapping": "raw_sigma",
        "acquisition_mapping": "raw_sigma",
        "evaluation_mapping": "raw_gaussian_sigma",
        "nominal_parameter_count": 0,
        "objective": "identity",
        "development_status": "planned",
        "confirmation_status": "not_started",
        "nominal_beta": 1.0,
        "primary_baseline": "RAW",
        "endpoint": "L1_and_L4",
        "direction": "reference",
        "family": "reference",
        "classification": "confirmatory_baseline",
        "selection_criterion": "development-only environment-balanced predeclared rule",
        "required_paired_seed_count": 40,
        "missing_data_handling": "complete paired set required",
        "retry_rule": "unchanged configuration; maximum two automatic retries",
    }
    defaults.update(updates)
    return defaults


def _strategies() -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for spec in PRODUCTION_STRATEGIES.values():
        calibration = "interval_half_width_by_coverage" if spec.id == "CONFORMAL_INTERVAL_ONLY" else spec.evaluation_mapping
        entries.append(
            _strategy_entry(
                spec.id,
                fitting_data=spec.fitting_data,
                oob_minimum=spec.min_oob,
                fallback=spec.fallback,
                scale_bounds=list(spec.scale_bounds) if spec.scale_bounds is not None else None,
                calibration_mapping=calibration,
                acquisition_mapping=spec.acquisition_mapping,
                evaluation_mapping=spec.evaluation_mapping,
                nominal_parameter_count=spec.nominal_parameter_count,
                objective=spec.objective,
                endpoint="L1" if spec.acquisition_mapping == "raw_sigma" else "L1_and_L4",
            )
        )
    aliases = [
        _strategy_entry("GG_JOINT", fitting_data="V5 Gaussian-global OOB records", oob_minimum=8, calibration_mapping="global_scale_times_raw_sigma", acquisition_mapping="scaled_sigma", evaluation_mapping="scaled_gaussian_sigma", nominal_parameter_count=1, objective="alias of ORIGINAL_GG", direction="two_sided", family="P0_L4_ACQUISITION_AND_JOINT", classification="confirmatory"),
        _strategy_entry("CS_JOINT", fitting_data="V5 candidate-specific OOB pairwise records", oob_minimum=10, calibration_mapping="candidate_specific_scale_times_raw_sigma", acquisition_mapping="scaled_sigma", evaluation_mapping="scaled_gaussian_sigma", nominal_parameter_count=2, objective="alias of SELECTED_CS", direction="two_sided", family="P0_L4_ACQUISITION_AND_JOINT", classification="confirmatory"),
        _strategy_entry("GG_NORMALIZED_ACQUISITION", fitting_data="V5 Gaussian-global OOB records", oob_minimum=8, calibration_mapping="global_scale_times_raw_sigma", acquisition_mapping="exact_RAW_expression_with_beta_normalization", evaluation_mapping="scaled_gaussian_sigma", nominal_parameter_count=1, objective="identity-path implementation control", family="NONE_DESCRIPTIVE", classification="secondary_identity"),
        _strategy_entry("REPLAY_EVALUATION", fitting_data="immutable RAW checkpoint models", fallback="block_if_RAW_checkpoint_missing", calibration_mapping="registered alternative map on RAW path", acquisition_mapping="none_replay_only", evaluation_mapping="registered evaluation mapping", objective="calibration-only replay", endpoint="L1", direction="descriptive", family="NONE_DESCRIPTIVE", classification="descriptive"),
    ]
    entries.extend(aliases)
    return {
        "schema_version": "v6-strategy-registry-v2",
        "status": STATUS,
        "environment_scope": {
            "canonical_universe": "all V5 tasks, split protocols, and both ensembles",
            "P0_development_sentinel_scope": "declared in v6_p0_development_manifest.csv",
        },
        "defaults": {},
        "strategies": sorted(entries, key=lambda item: str(item["id"])),
    }


def _endpoints() -> dict[str, object]:
    return {
        "schema_version": "v6-endpoint-registry-v2",
        "status": STATUS,
        "endpoints": [
            {"id": "L1", "name": "campaign MACE at initial/25/50/75% canonical checkpoints", "role": "primary", "direction": "lower_is_better", "unit": "paired seed within environment", "missing_handling": "complete paired set required", "checkpoint_weighting": "equal"},
            {"id": "L4", "name": "top-1% recall normalized AUC", "role": "primary", "direction": "higher_is_better", "x_axis": "canonical campaign budget_fraction", "unit": "paired seed within environment", "missing_handling": "complete paired set required"},
            {"id": "CONFORMAL_COVERAGE", "name": "coverage-specific conformal interval coverage", "role": "secondary_calibration", "direction": "absolute error lower is better", "coverages": [0.50, 0.80, 0.90, 0.95]},
            {"id": "NLL", "name": "Gaussian negative log likelihood", "role": "secondary_conditional", "direction": "lower_is_better", "stability_gate_required": True},
            {"id": "RANKING_DIAGNOSTICS", "name": "stable-order path diagnostics", "role": "mechanism_secondary", "direction": "descriptive"},
        ],
    }


def _seeds() -> dict[str, object]:
    return {
        "schema_version": "v6-seed-registry-v2",
        "status": STATUS,
        "namespaces": [
            {"class": "V5-RC1", "range": [5000, 5039], "use": "read-only frozen historical confirmation", "allowed_for_v6_fitting": False},
            {"class": "V6-development", "range": [6000, 6009], "use": "P0 selection and development only", "allowed_for_v6_fitting": True},
            {"class": "V6-confirmation", "range": [7000, 7039], "use": "reserved; not read or generated in Stage-2.5", "allowed_for_v6_fitting": False},
            {"class": "Stage2-smoke", "values": [91000, 91001], "use": "non-inferential engineering validation", "allowed_for_v6_fitting": False},
        ],
        "bootstrap_root_seed": 610001,
        "sign_flip_root_seed": 610002,
        "child_seed_rule": "first 32 bits of SHA-256(root_seed|family|environment|contrast|endpoint)",
    }


def _failure_rules() -> dict[str, object]:
    return {
        "schema_version": "v6-failure-recovery-v2",
        "status": STATUS,
        "required_paired_seed_count": 40,
        "retry_rule": "retry the unchanged configuration and seed; retain attempt history",
        "maximum_automatic_retries": 2,
        "fallback_rule": "method-specific registered identity/raw fallback with explicit status only",
        "missing_data_handling": "missing P0 rows are reported; incomplete pairs block any future primary inference",
        "failed_job_handling": "retain failed registry row, traceback digest, attempt, and last durable checkpoint",
        "legal_state_transitions": "PLANNED->RUNNING->{COMPLETED,RECOVERED,FAILED,PLANNED}; FAILED->PLANNED only with explicit unchanged retry",
        "crash_boundaries": ["before_model_checkpoint_write", "after_temporary_write_before_rename"],
        "restart_rule": "recover only a hash-validated temporary payload; resume from the last valid checkpoint",
        "silent_drop_prohibited": True,
        "overwrite_rule": "committed artifacts may be reused only when byte-identical and identity-matched",
        "smoke_rule": "smoke artifacts remain non-inferential and cannot enter P0 evidence",
    }


def main() -> None:
    commit = current_git_commit(ROOT)
    source_hashes = _source_hashes()
    documents = {
        "v6_hypothesis_registry.json": _hypotheses(),
        "v6_multiplicity_families.json": _families(),
        "v6_strategy_registry.json": _strategies(),
        "v6_endpoint_registry.json": _endpoints(),
        "v6_seed_registry.json": _seeds(),
        "v6_failure_and_recovery_rules.json": _failure_rules(),
    }
    for filename, document in documents.items():
        frozen = freeze_document(document, git_commit=commit, source_hashes=source_hashes)
        write_frozen_document(ROOT / "analysis_plan" / filename, frozen)
        print(f"wrote {filename}: {frozen['immutable_freeze_hash']}")


if __name__ == "__main__":
    main()
