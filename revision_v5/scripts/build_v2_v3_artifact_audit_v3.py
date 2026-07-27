#!/usr/bin/env python3
"""Build the V2/V3 artifact audit without rerunning trajectories."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "revision_v5" / "editorial_revision_v3"
OUT.mkdir(parents=True, exist_ok=True)

V2_ROOT = REPO / "最终" / "_code_package" / "transportability_study"
V3_PACKAGED = REPO / "最终" / "_code_package" / "transportability_study_v3_l1"
V3_FINAL = REPO / "transportability_study_v3_l1_codex_finalization"
V3_EXPLORATORY = REPO / "transportability_study_v3_l1_l4_exploratory"

INCLUDE_SUFFIXES = {
    ".md", ".json", ".csv", ".yaml", ".yml", ".py", ".pdf", ".parquet",
    ".sqlite", ".bib", ".tex", ".svg", ".png",
}
EXCLUDED_PARTS = {
    "__pycache__", ".pytest_cache", "cache", "render", "build", "compile",
    "trajectories", "progress", "canary", "smoke", "logs",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_type(path: Path) -> str:
    name = path.name.lower()
    if "protocol" in name or path.suffix.lower() in {".yaml", ".yml"}:
        return "protocol/configuration"
    if "manifest" in name or "registry" in name or "lock" in name or "hash" in name:
        return "manifest/lock/provenance"
    if "test" in name or "audit" in name or "gate" in name:
        return "audit/test"
    if path.suffix.lower() in {".csv", ".parquet", ".sqlite"}:
        return "result/data table"
    if path.suffix.lower() in {".pdf", ".png", ".svg"}:
        return "figure/PDF"
    if path.suffix.lower() in {".py"}:
        return "script"
    if path.suffix.lower() in {".tex", ".bib"}:
        return "manuscript source"
    return "report/documentation"


def is_scientific(path: Path) -> str:
    text = path.as_posix().lower()
    if any(token in text for token in (
        "manuscript_review", "appendix", "figure", "render", "reviewer_revision",
        "author_package",
    )):
        return "editorial or scientific presentation"
    if any(token in text for token in (
        "result", "confirm", "analysis", "endpoint", "contrast", "protocol",
        "manifest", "strategy", "seed", "reconstruct",
    )):
        return "scientific evidence or provenance"
    return "engineering/reproducibility"


def metadata(version: str, path: Path) -> dict[str, str]:
    lower = path.as_posix().lower()
    if version == "V2":
        evidence = "historical confirmatory" if (
            "confirmation_v2" in lower or "analysis_v2/confirmatory" in lower
        ) else "historical descriptive/provenance"
        return {
            "tasks": "4 Matbench regression tasks",
            "splits": "IID record; chemical-system OOD",
            "surrogates": "random forest; extra-randomized bagging",
            "strategy_identities": (
                "random; raw UCB beta 0.5/1/2; Gaussian-global; "
                "candidate-specific DA-OOB"
            ),
            "seed_range": "2000-2019",
            "job_count": "1920 scientific jobs",
            "endpoints": "L4 top-1% recall nAUC primary; L2/L3 and secondary L4 endpoints",
            "inference_unit": "paired seed within environment (n=20)",
            "multiplicity_status": "BH over two nondegenerate primary contrasts within environment",
            "frozen_status": "frozen V2 confirmation identity",
            "evidence_class": evidence,
            "known_limitations": (
                "historical cohort; not pooled with V3 or V5; older pre-v2 "
                "1280-row manifest is superseded"
            ),
            "currently_used_by_v5": (
                "historical context only" if "confirmatory" in evidence else "no"
            ),
        }
    post_hoc = any(token in lower for token in (
        "l1_l4_exploratory", "within_cohort", "reconstruct", "exploratory"
    ))
    evidence = "post hoc exploratory reconstruction" if post_hoc else "historical V3 L1 confirmatory"
    return {
        "tasks": "4 Matbench regression tasks",
        "splits": "IID record; chemical-system OOD",
        "surrogates": "random forest; extra-randomized bagging",
        "strategy_identities": "raw UCB beta 1; Gaussian-global; candidate-specific DA-OOB",
        "seed_range": "3000-3039",
        "job_count": "1920 scientific jobs; no new jobs for post hoc reconstruction",
        "endpoints": (
            "L1 campaign MACE primary; post hoc same-cohort L2-L4 where labeled"
        ),
        "inference_unit": "paired seed within environment (n=40)",
        "multiplicity_status": (
            "BH over two L1 contrasts within environment; no new inference for reconstruction"
        ),
        "frozen_status": "frozen V3 L1; reconstruction explicitly post hoc",
        "evidence_class": evidence,
        "known_limitations": (
            "V3 L2-L4 reconstruction is not a new cohort and is not confirmatory"
            if post_hoc else
            "historical cohort; distinct from V2 and V5; Recovery Amendment 001 disclosed"
        ),
        "currently_used_by_v5": "historical context only" if not post_hoc else "no",
    }


targets: list[tuple[str, Path]] = []

v2_scopes = [
    V2_ROOT / "configs",
    V2_ROOT / "docs",
    V2_ROOT / "scripts",
    V2_ROOT / "tests",
    V2_ROOT / "outputs" / "frozen_protocol_v2",
    V2_ROOT / "outputs" / "confirmation_v2" / "frozen_results",
    V2_ROOT / "outputs" / "analysis_v2",
    V2_ROOT / "outputs" / "interpretation_v2",
    V2_ROOT / "outputs" / "reviewer_revision_v2_round2",
]
v3_scopes = [
    V3_PACKAGED / "configs",
    V3_PACKAGED / "docs",
    V3_PACKAGED / "manifests",
    V3_PACKAGED / "scripts",
    V3_PACKAGED / "tests",
    V3_PACKAGED / "outputs" / "frozen_protocol",
    V3_PACKAGED / "outputs" / "analysis",
    V3_PACKAGED / "outputs" / "audit",
    V3_FINAL / "outputs" / "verified_results",
    V3_FINAL / "outputs" / "gate_v2",
    V3_FINAL / "outputs" / "provenance_v2",
    V3_FINAL / "joint_v2_v3",
    V3_EXPLORATORY / "finalization",
]

for version, scopes in (("V2", v2_scopes), ("V3", v3_scopes)):
    for scope in scopes:
        if not scope.exists():
            continue
        for path in scope.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in INCLUDE_SUFFIXES:
                continue
            relative_parts = set(path.relative_to(scope).parts)
            if relative_parts & EXCLUDED_PARTS:
                continue
            targets.append((version, path))

# Raw trajectory collections are represented by their frozen manifests and
# package hash files; individual per-job shards are deliberately not duplicated.
rows = []
seen = set()
for version, path in sorted(targets, key=lambda item: (item[0], str(item[1]))):
    key = (version, path.resolve())
    if key in seen:
        continue
    seen.add(key)
    meta = metadata(version, path)
    rows.append({
        "internal_version": version,
        "artifact_path": path.relative_to(REPO).as_posix(),
        "artifact_type": artifact_type(path),
        "scientific_or_editorial": is_scientific(path),
        **meta,
        "hash": digest(path),
    })

columns = [
    "internal_version", "artifact_path", "artifact_type",
    "scientific_or_editorial", "tasks", "splits", "surrogates",
    "strategy_identities", "seed_range", "job_count", "endpoints",
    "inference_unit", "multiplicity_status", "frozen_status",
    "evidence_class", "known_limitations", "hash", "currently_used_by_v5",
]
inventory = OUT / "01_v2_v3_artifact_inventory.csv"
with inventory.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

v2_manifest = V2_ROOT / "outputs" / "frozen_protocol_v2" / "CONFIRMATION_JOB_MANIFEST_V2.csv"
v3_manifest = V3_PACKAGED / "manifests" / "V3_TASK_MANIFEST.csv"
report = f"""# V2/V3 identity report

## Determination

V2 and V3 are **independent scientific experiment cohorts**, not manuscript
version labels and not repackagings of one experiment.

- **V2:** frozen historical confirmation cohort; 4 tasks × 2 splits × 2
  surrogates × 6 strategies × 20 seeds (2000–2019) = **1,920 scientific
  jobs**. Primary endpoint: Layer-4 budget-normalized top-1% recall nAUC.
  L2/L3 and secondary Layer-4 analyses were derived from this cohort.
- **V3:** fresh independent uncertainty-quality confirmation cohort; 4 tasks
  × 2 splits × 2 surrogates × 3 strategies × 40 seeds (3000–3039) =
  **1,920 scientific jobs**. Primary endpoint: Layer-1 campaign MACE.
- **V3 post hoc reconstruction:** later L2–L4 reconstruction used the same V3
  trajectories. It ran zero new trajectories, created no independent cohort,
  and is explicitly exploratory.

Thus the correct classification is **A plus C/D**: two independent historical
scientific cohorts, followed by descriptive and post hoc analyses. Repository
and manuscript revisions also exist, but they are editorial versions, not
experiments.

## Evidence boundary

V2 and V3 seeds, effects, and p-values are never pooled with each other or
with V5-RC1. V5-RC1 uses seeds 5000–5039 and supplies the current locked
confirmation estimates. “Historical CS” denotes an algorithm identity; its
current primary manuscript estimates come from V5-RC1, not historical seeds.

## Supersession and inconsistency

An older V2 frozen-protocol directory contains a 1,280-row design manifest and
states that trajectories were not run. It is superseded by
`outputs/frozen_protocol_v2/CONFIRMATION_JOB_MANIFEST_V2.csv`, which contains
the executed six-strategy, 1,920-job identity. The older artifact is retained
as provenance and must not define V2 geometry.

An early V3 finalization report stopped because it imposed one global ledger
length. The later task-specific ledger audit passed 1,920/1,920 job ledgers
and selected-ID checks and issued the V3 Final Gate V2 PASS. The failed report
remains historical provenance, not the final scientific identity.

## Primary identity sources

- V2 manifest SHA-256: `{digest(v2_manifest)}`
- V3 manifest SHA-256: `{digest(v3_manifest)}`
- Inventory rows: {len(rows)}

Raw per-job trajectory shards are represented by the frozen job manifests,
package hashes, and provenance tables; they are not duplicated as individual
rows in the editorial inventory.
"""
(OUT / "02_v2_v3_identity_report.md").write_text(report, encoding="utf-8")

print({
    "inventory_rows": len(rows),
    "v2_rows": sum(row["internal_version"] == "V2" for row in rows),
    "v3_rows": sum(row["internal_version"] == "V3" for row in rows),
    "classification": "two independent historical cohorts; V3 L2-L4 is post hoc",
})
