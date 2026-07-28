"""Add explicit P0 sentinel/broad evidence scopes to the frozen registries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.registry_freeze import (
    code_tree_sha256,
    current_git_commit,
    freeze_document,
    sha256_file,
)


def source_hashes() -> dict[str, str]:
    return {
        "v6_code_tree_sha256": code_tree_sha256(ROOT / "src" / "transportability_v6"),
        "v5_authority_lock_sha256": sha256_file(ROOT / "locks" / "v5_frozen_manifest.json"),
        "v5_confirmation_protocol_sha256": sha256_file(
            ROOT / "revision_v5" / "20_confirmation_protocol_v5_rc1.md"
        ),
    }


def write(path: Path, payload: dict[str, object], *, refresh: bool) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists() and path.read_bytes() != content and not refresh:
        raise FileExistsError(f"refusing to overwrite divergent registry without --refresh: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def update_seed_registry() -> dict[str, object]:
    path = ROOT / "analysis_plan" / "v6_seed_registry.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    original_hash = str(document["immutable_freeze_hash"])
    namespaces = list(document["namespaces"])
    development = next(item for item in namespaces if item["class"] == "V6-development")
    development.update(
        {
            "evidence_class": "V6-P0-SENTINEL-DEVELOPMENT",
            "scope": "matbench_expt_gap only; IID and chemical-system group-disjoint; Random Forest only",
            "inferential_status": "development_only_non_confirmatory",
            "transferability": "not transferable to the remaining V5 task/model universe",
        }
    )
    if not any(item["class"] == "V6-P0-BROAD-DEVELOPMENT" for item in namespaces):
        namespaces.append(
            {
                "class": "V6-P0-BROAD-DEVELOPMENT",
                "range": [6100, 6109],
                "use": "prospective broad development only; all 16 V5 task/split/model environments",
                "allowed_for_v6_fitting": True,
                "inferential_status": "development_only_non_confirmatory",
                "confirmation_seed_range_forbidden": [7000, 7039],
            }
        )
    confirmation = next(item for item in namespaces if item["class"] == "V6-confirmation")
    confirmation["status"] = "untouched_not_read_not_generated"
    document["namespaces"] = namespaces
    document["status"] = "STAGE_2_5_FROZEN_WITH_P0_EVIDENCE_SCOPE_ADDENDUM"
    document["stage_2_5_freeze_hash"] = original_hash
    document["p0_evidence_classes"] = {
        "V6-P0-SENTINEL-DEVELOPMENT": {
            "scope": "matbench_expt_gap only; two splits; Random Forest; seeds 6000-6009",
            "status": "accepted_development_only_non_confirmatory",
            "draft_map": "analysis_plan/v6_selection_map_SENTINEL_DRAFT.json",
            "transferability": "not sufficient for a full-universe confirmation policy",
        },
        "V6-P0-BROAD-DEVELOPMENT": {
            "scope": "four tasks; two splits; Random Forest and ExtraTrees; seeds 6100-6109",
            "status": "prospective_pending_final_broad_lock",
            "confirmation_boundary": "seeds 7000-7039 remain untouched",
        },
    }
    return freeze_document(document, git_commit=current_git_commit(ROOT), source_hashes=source_hashes())


def update_strategy_registry() -> dict[str, object]:
    path = ROOT / "analysis_plan" / "v6_strategy_registry.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    original_hash = str(document["immutable_freeze_hash"])
    scope = dict(document["environment_scope"])
    scope["P0_development_sentinel_scope"] = (
        "V6-P0-SENTINEL-DEVELOPMENT: matbench_expt_gap only, IID and chemical-system group-disjoint, "
        "Random Forest, seeds 6000-6009; development-only and non-transferable."
    )
    scope["P0_broad_development_scope"] = (
        "V6-P0-BROAD-DEVELOPMENT: all 16 V5 task/split/model environments, seeds 6100-6109; "
        "prospective development only."
    )
    document["environment_scope"] = scope
    document["status"] = "STAGE_2_5_FROZEN_WITH_P0_EVIDENCE_SCOPE_ADDENDUM"
    document["stage_2_5_freeze_hash"] = original_hash
    document["simple_scaling_roles"] = {
        "IDENTITY_CONTROL": "negative implementation control; never the sole scaling winner",
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO": "candidate simple non-identity scalar baseline",
        "SCALAR_TEMPERATURE_NLL": "prespecified mechanistic scalar baseline",
        "POWER_SCALING": "flexible parametric secondary baseline",
        "ISOTONIC_ABS_RESIDUAL": "monotonic nonparametric secondary baseline",
        "CONFORMAL_INTERVAL_ONLY": "L1 calibration-only secondary method; no universal acquisition sigma",
    }
    document["simple_scaling_selection_boundary"] = (
        "Observed sentinel outcomes are descriptive only; no post-hoc winner selection across all simple scalers is permitted."
    )
    document["p0_evidence_classes"] = {
        "V6-P0-SENTINEL-DEVELOPMENT": "accepted sentinel evidence only; not a universal policy-selection cohort",
        "V6-P0-BROAD-DEVELOPMENT": "separate prospective broad cohort; leave-one-task-out maps only",
    }
    for item in document["strategies"]:
        role = document["simple_scaling_roles"].get(str(item["id"]))
        if role:
            item["p0_role"] = role
    return freeze_document(document, git_commit=current_git_commit(ROOT), source_hashes=source_hashes())


def main(*, refresh: bool) -> None:
    seed = update_seed_registry()
    strategy = update_strategy_registry()
    write(ROOT / "analysis_plan" / "v6_seed_registry.json", seed, refresh=refresh)
    write(ROOT / "analysis_plan" / "v6_strategy_registry.json", strategy, refresh=refresh)
    print(
        json.dumps(
            {
                "seed_registry_freeze_hash": seed["immutable_freeze_hash"],
                "strategy_registry_freeze_hash": strategy["immutable_freeze_hash"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    main(refresh=parser.parse_args().refresh)
