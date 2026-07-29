from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def _canonical_hash(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def test_corrected_endpoint_layer_and_pair_audits_are_complete():
    original = pd.read_csv(ROOT / "tables" / "v6_p0_broad_seed_endpoints.csv")
    corrected = pd.read_csv(
        ROOT / "tables" / "v6_p0_broad_seed_endpoints_CORRECTED.csv"
    )
    identity = pd.read_csv(ROOT / "tables" / "v6_p0_identity_pair_audit.csv")
    cs = pd.read_csv(
        ROOT / "tables" / "v6_p0_cs_joint_acquisition_pair_audit.csv"
    )
    assert len(original) == len(corrected) == 2720
    assert int(corrected.endpoint_correction_applied.sum()) == 1440
    assert len(identity) == 160 * 4 * 4
    assert identity.matched_checkpoint_vector_equivalence.all()
    assert (identity.raw_empirical_coverage == identity.identity_empirical_coverage).all()
    assert len(cs) == 160 * 4
    assert cs.queried_batch_identity_exact.all()
    assert cs.evaluation_sigma_should_differ.all()


def test_identity_and_cs_endpoint_relations_after_correction():
    corrected = pd.read_csv(
        ROOT / "tables" / "v6_p0_broad_seed_endpoints_CORRECTED.csv"
    )
    keys = ["task", "split", "model", "seed"]
    raw = corrected[corrected.strategy == "RAW"].set_index(keys)
    identity = corrected[corrected.strategy == "IDENTITY_CONTROL"].set_index(keys)
    selected = corrected[corrected.strategy == "SELECTED_CS"].set_index(keys)
    acquisition = corrected[
        corrected.strategy == "CS_ACQUISITION_ONLY"
    ].set_index(keys)
    assert (raw.l1_campaign_mace == identity.l1_campaign_mace).all()
    assert (raw.l4_top1pct_recall_nauc == identity.l4_top1pct_recall_nauc).all()
    assert (selected.l4_top1pct_recall_nauc == acquisition.l4_top1pct_recall_nauc).all()
    assert (selected.l1_campaign_mace != acquisition.l1_campaign_mace).all()


def test_candidate_v2_is_complete_and_self_hashed():
    candidate = json.loads(
        (
            ROOT
            / "analysis_plan"
            / "v6_p0_confirmation_selection_map_CANDIDATE_v2.json"
        ).read_text(encoding="utf-8")
    )
    assert candidate["status"] == "CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN"
    assert candidate["confirmation_seeds"] == list(range(7000, 7040))
    assert candidate["paired_completeness"]["required_pairs_per_contrast"] == 40
    assert len(candidate["leave_one_task_out_maps"]) == 4
    assert len(candidate["confirmation_strategies"]) == 22
    observed = candidate.pop("candidate_self_sha256")
    assert observed == _canonical_hash(candidate)


def test_recovery_counts_and_hashes_reconcile_with_explicit_limitation():
    inventory = pd.read_csv(
        ROOT / "tables" / "v6_p0_broad_recovery_inventory.csv"
    )
    correction = json.loads(
        (
            ROOT / "locks" / "v6_p0_broad_endpoint_correction_lock.json"
        ).read_text(encoding="utf-8")
    )
    assert len(inventory) == 8
    assert (inventory.retry_attempt == 2).all()
    assert inventory.stale_worker_detected.all()
    assert inventory.unchanged_lock_hash.all()
    assert inventory.final_output_hash_verified.all()
    assert inventory.no_duplicate_final_output.all()
    assert not inventory.pre_recovery_last_valid_checkpoint_recorded.any()
    assert correction["recovery_audit"]["count_reconciliation_pass"]
    assert not correction["recovery_audit"][
        "pre_recovery_checkpoint_evidence_complete"
    ]
    observed = correction.pop("correction_self_sha256")
    assert observed == _canonical_hash(correction)
