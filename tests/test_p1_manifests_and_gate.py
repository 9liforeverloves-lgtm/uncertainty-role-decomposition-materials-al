from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_candidate_manifest_is_complete_unique_and_confirmation_is_sealed() -> None:
    manifest = pd.read_csv(ROOT / "manifests/p1_extension_confirmation_candidate_manifest.csv")
    assert len(manifest) == 3520
    assert not manifest.job_id.duplicated().any()
    assert set(manifest.seed) == set(range(8200, 8240))
    assert manifest.groupby(["seed", "task", "split"]).size().eq(11).all()
    assert (~manifest.ready.astype(bool)).sum() == 640
    assert set(manifest.phase) == {"P1_INDEPENDENT_CONFIRMATION"}


def test_manifest_lock_matches_and_development_seeds_are_disjoint() -> None:
    lock = json.loads((ROOT / "locks/p1_extension_job_manifest_lock.json").read_text(encoding="utf-8"))
    for relative, expected in lock["files"].items():
        assert sha(ROOT / relative) == expected
    development = pd.read_csv(ROOT / "manifests/p1_extension_reduced_development_manifest.csv")
    assert set(development.seed) == set(range(8100, 8110))
    assert not set(development.seed) & set(range(8200, 8240))
    assert not development.confirmation_eligible.astype(bool).any()


def test_all_p1_figure_formats_and_sources_are_hash_bound() -> None:
    inventory = pd.read_csv(ROOT / "tables/p1_extension/p1_figure_source_inventory.csv")
    assert len(inventory) == 21
    assert set(Path(value).suffix for value in inventory.output_file) == {".png", ".pdf", ".svg"}
    assert inventory.groupby("figure").size().eq(3).all()
    assert not inventory.manual_values.astype(bool).any()
    for row in inventory.itertuples(index=False):
        assert sha(ROOT / row.output_file) == row.output_sha256
        assert sha(ROOT / row.source_file) == row.source_sha256
