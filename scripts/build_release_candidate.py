"""Build a curated, checksum-addressed external release candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from release_common import assert_authorities, repository_root


ROOT = repository_root(Path(__file__).resolve().parent)
DIST = ROOT / "dist/release_candidate"
ROOT_FILES = [
    ".gitignore", ".gitattributes", ".dockerignore", "README.md", "CITATION.cff", "NOTICE", "THIRD_PARTY_NOTICES",
    "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "SECURITY.md",
    "LICENSE", "LICENSE_AND_DATA_SCOPE.md", "pyproject.toml",
    "requirements-lock.txt", "environment.yml", "Dockerfile",
]
DIRECTORIES = [".github", "src", "p1_extension", "tests", "v6_revision", "analysis_plan", "data_manifest", "docs", "release_config", "configs"]
SCRIPTS = [
    "release_common.py", "verify_release.py", "reproduce_smoke.py", "reproduce_tables.py",
    "reproduce_figures.py", "reproduce_manuscript.py", "fetch_matbench_data.py",
    "build_final_optimization_assets.py", "generate_p1_confirmation_figures.py",
    "compile_p1_complete_manuscript.py", "build_release_candidate.py",
    "run_external_reproduction_test.py", "run_linux_reproduction_test.py",
    "verify_archive_checksums.py", "validate_bsd3_release.py",
    "build_archive_upload_candidate.py",
]
TABLES = [
    "p1_confirmation_environment_effects.csv", "p1_confirmation_multiplicity.csv",
    "p1_confirmation_pair_completeness.csv", "p1_confirmation_primary_contrasts.csv",
    "p1_confirmation_seed_block_effects.csv", "p1_confirmation_seed_level_endpoints.csv",
    "p1_confirmation_split_effects.csv", "p1_confirmation_task_effects.csv",
    "p1_confirmation_checkpoint_endpoints.csv", "p1_confirmation_calibration_diagnostics.csv",
    "p1_confirmation_trajectory_points.csv", "p1_confirmation_discovery_endpoints.csv",
    "p1_confirmation_robustness.csv", "p1_confirmation_execution_provenance.csv",
    "p1_strategy_role_map.csv", "p1_primary_table_display.csv", "p1_claim_evidence_classification.csv",
    "p1_final_diagnostic_summary.csv", "p1_compute_provenance_summary.csv", "p1_related_work_verified.csv",
    "p1_figure_source_inventory.csv", "v6_p0_confirmation_environment_effects.csv",
    "v6_p0_confirmation_multiplicity.csv", "v6_p0_confirmation_pair_completeness.csv",
    "v6_p0_confirmation_primary_contrasts.csv", "v6_p0_confirmation_seed_level_endpoints.csv",
    "v6_main_figure_source_inventory.csv", "p0_p1_main_absolute_endpoints.csv",
    "revised_figure_source_inventory.csv", "v6_historical_version_lineage.csv",
    "v6_p0_broad_seed_endpoints.csv", "v6_p0_broad_seed_endpoints_CORRECTED.csv",
    "v6_p0_broad_recovery_inventory.csv", "v6_p0_identity_pair_audit.csv",
    "v6_p0_cs_joint_acquisition_pair_audit.csv",
]
REPORTS = [
    "09_p0_confirmation_inference.md",
    "BSD3_RELEASE_BASELINE.md", "BSD3_RELEASE_VALIDATION_REPORT.md", "PYTHON_PACKAGE_CONTENT_AUDIT.md",
    "LICENSE_COMPATIBILITY_MATRIX.md", "THIRD_PARTY_DATA_RIGHTS_MATRIX.md", "THIRD_PARTY_CODE_PROVENANCE.md",
    "EXTERNAL_REPRODUCTION_TEST.md",
    "LICENSE_AND_DATA_RIGHTS_AUDIT.md", "PUBLIC_RELEASE_SECURITY_AUDIT.md",
    "PUBLIC_RELEASE_FILE_AUDIT.md", "PUBLIC_RELEASE_CLAIM_DIFF.md",
    "PUBLIC_RELEASE_METADATA_STATUS.md", "DATA_AVAILABILITY_CANDIDATES.md",
    "CODE_AVAILABILITY_CANDIDATES.md", "REPRODUCIBILITY_STATEMENT_CANDIDATE.md",
    "P1_EXECUTION_PROVENANCE.md", "compute_gate_provenance_gap.md",
    "ONLINE_PUBLICATION_BASELINE.md", "GITHUB_RELEASE_PR_BODY.md", "ONLINE_CI_RESULTS.md",
    "ONLINE_PUBLICATION_PROVENANCE.md", "GITHUB_RELEASE_NOTES_v1.0.0.md",
    "ZENODO_DRAFT_STATUS.md", "PRE_PUBLIC_VISIBILITY_AUDIT.md", "SUBMISSION_READINESS_STATUS.md",
    "external_reproduction_status.json", "linux_reproduction_status.json",
    "bsd3_release_validation_status.json", "bsd3_candidate_final_verification.json",
]
SECRET = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
ABSOLUTE = re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|home)[^\s'\"<>]*|/(?:home|Users)/[^\s'\"<>]+)")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(relative: str) -> None:
    source = ROOT / relative
    if not source.is_file():
        raise RuntimeError(f"required release file missing: {relative}")
    target = DIST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(relative: str) -> None:
    source = ROOT / relative
    if source.is_dir():
        shutil.copytree(source, DIST / relative, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.log"))


def category(path: str) -> str:
    if path.startswith("tables/") or path.startswith("locks/") or path.startswith("manifests/"):
        return "locked_evidence"
    if path.startswith("manuscript/"):
        return "manuscript"
    if path.startswith("data_manifest/"):
        return "data_metadata"
    if path.startswith("reports/") or path.startswith("docs/"):
        return "documentation"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith(".github/") or path == "Dockerfile":
        return "automation"
    return "source_and_metadata"


def scan_candidate() -> None:
    findings = []
    for path in DIST.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".csv", ".tex", ".bib", ".cff", ".sh", ".ps1"} or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append((path, "NON_UTF8")); continue
        if SECRET.search(text): findings.append((path, "SECRET_PATTERN"))
        if ABSOLUTE.search(text): findings.append((path, "DEVELOPER_ABSOLUTE_PATH"))
        for email in EMAIL.findall(text):
            if not email.endswith("@example.org"):
                findings.append((path, "EMAIL_ADDRESS"))
    if findings:
        raise RuntimeError("release security scan failed: " + str([(p.relative_to(DIST).as_posix(), k) for p, k in findings[:30]]))


def main() -> None:
    assert_authorities(ROOT)
    resolved = DIST.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError("release target escaped repository")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    for name in ROOT_FILES: copy_file(name)
    for name in DIRECTORIES: copy_tree(name)
    # Three retained regression tests import the legacy implementation through
    # tests/conftest.py. Include only that exact source package, not the V5
    # historical workspace or its data/results.
    copy_tree("revision_v5/experiments_v4/src/transportability_v5")
    v5_manifest = json.loads((ROOT / "locks/v5_frozen_manifest.json").read_text(encoding="utf-8"))
    for record in v5_manifest["files"]:
        copy_file(record["path"])
    for record in v5_manifest["lock_file_inventory"]:
        copy_file(record["path"])
    copy_tree("tables/p1_extension")
    copy_tree("manuscript/figures_p1")
    for name in SCRIPTS: copy_file(f"scripts/{name}")
    for path in (ROOT / "locks").glob("*.json"): copy_file(path.relative_to(ROOT).as_posix())
    for path in (ROOT / "manifests").glob("*p1*.csv"): copy_file(path.relative_to(ROOT).as_posix())
    for name in TABLES: copy_file(f"tables/{name}")
    manuscript_files = [
        "manuscript_submission_revised.tex",
        "manuscript_submission_P1_COMPLETE.tex", "manuscript_submission_P1_COMPLETE.pdf",
        "manuscript_submission_P1_COMPLETE_twocolumn.tex", "manuscript_submission_P1_COMPLETE_twocolumn.pdf",
        "supplement_submission_P1_COMPLETE.tex", "supplement_submission_P1_COMPLETE.pdf",
        "references_submission_candidate_v4_final_r1.bib",
    ]
    for name in manuscript_files: copy_file(f"manuscript/{name}")
    for folder in ("figures_p1_confirmation", "figures_v6"):
        for path in (ROOT / "manuscript" / folder).glob("*"):
            if path.is_file() and path.suffix.lower() in {".png", ".pdf", ".svg"}:
                copy_file(path.relative_to(ROOT).as_posix())
    # The adapter checks these canonical data roots before loading the legacy
    # registry/checkpoint modules. Public raw datasets are deliberately absent;
    # a marker keeps the directory contract explicit and auditable.
    for relative in ("最终/_code_package/src", "最终/_code_package/results/benchmark"):
        marker = DIST / relative / "DATA_NOT_BUNDLED.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "Raw canonical data are not redistributed in this candidate. "
            "Use scripts/fetch_matbench_data.py and docs/data_reproduction.md.\n",
            encoding="utf-8",
        )
    for name in REPORTS:
        if (ROOT / "reports" / name).is_file(): copy_file(f"reports/{name}")
    copy_tree("reports/archive")
    for folder in ("release_metadata",): copy_tree(folder)

    license_text = (DIST / "LICENSE").read_text(encoding="utf-8")
    if not license_text.startswith("Copyright (c) 2026 Renjie Li\n\nRedistribution and use"):
        raise RuntimeError("authorized BSD-3-Clause license is missing or malformed")
    if (DIST / "LICENSE_SELECTION_REQUIRED.md").exists() or (DIST / "AUTHOR_LICENSE_DECISION_REQUIRED.md").exists():
        raise RuntimeError("unresolved license-decision file entered release candidate")
    scan_candidate()
    assert_authorities(DIST)

    exclusions = [
        {"path_or_pattern": ".venv*/", "reason": "local environment", "size_or_scope": "all"},
        {"path_or_pattern": "results/", "reason": "68+ GiB execution store and raw intermediates", "size_or_scope": "all"},
        {"path_or_pattern": "revision_v5/* except experiments_v4/src/transportability_v5/", "reason": "historical data/results excluded; minimal project source retained for regression tests", "size_or_scope": "all other V5 content"},
        {"path_or_pattern": "最终/; 【重跑】/; material-active-learning/", "reason": "historical/local workspaces and third-party raw snapshots", "size_or_scope": "all"},
        {"path_or_pattern": "*.log; revision_audit/; .tmp*/", "reason": "local paths, internal logs and temporary output", "size_or_scope": "all"},
        {"path_or_pattern": "Codex-Windows-Installer.exe; *.docx", "reason": "unrelated binary/private editorial artifact", "size_or_scope": "all"},
        {"path_or_pattern": "LICENSE_SELECTION_REQUIRED.md; AUTHOR_LICENSE_DECISION_REQUIRED.md", "reason": "resolved versions archived under reports/archive", "size_or_scope": "two obsolete root files"},
        {"path_or_pattern": "raw Matbench materials.csv", "reason": "author explicitly prohibited raw-data redistribution; upstream rights remain controlling", "size_or_scope": "four snapshots"},
    ]
    exclusions_path = DIST / "public_release_exclusions.csv"
    with exclusions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=exclusions[0].keys()); writer.writeheader(); writer.writerows(exclusions)

    payload = {
        "status": "READY_FOR_AUTHOR_PUBLICATION",
        "PUBLIC_RELEASE_READY": False,
        "publication_blocker": "public repository, real tag, archive DOI and online CI do not yet exist",
        "file_count_source": "public_release_archive_inventory.csv",
        "checksum_source": "SHA256SUMS",
    }
    status_path = DIST / "release_candidate_status.json"
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    rows = []
    for path in sorted(item for item in DIST.rglob("*") if item.is_file()):
        relative = path.relative_to(DIST).as_posix()
        cat = category(relative)
        rows.append({
            "path": relative, "size": path.stat().st_size, "sha256": sha(path), "category": cat,
            "required_for": "Level 1/2 verification" if cat in {"locked_evidence", "tests", "source_and_metadata"} else "documentation or manuscript",
            "license/source": "BSD-3-Clause / author-authorized processed-output scope" if cat != "data_metadata" else "upstream terms; see rights matrix",
            "redistribution_status": "AUTHORIZED_ORIGINAL_PROJECT_CONTENT" if cat != "data_metadata" else "METADATA_ONLY_RAW_DATA_EXCLUDED",
        })
    inventory = DIST / "public_release_archive_inventory.csv"
    rows.append({
        "path": inventory.name, "size": "SELF", "sha256": "SELF_REFERENTIAL_NOT_APPLICABLE",
        "category": "source_and_metadata", "required_for": "archive audit",
        "license/source": "BSD-3-Clause / author-authorized processed-output scope",
        "redistribution_status": "AUTHORIZED_ORIGINAL_PROJECT_CONTENT",
    })
    with inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    sums = []
    for path in sorted(item for item in DIST.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        sums.append(f"{sha(path)}  {path.relative_to(DIST).as_posix()}")
    (DIST / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    shutil.copy2(inventory, ROOT / "public_release_archive_inventory.csv")
    shutil.copy2(exclusions_path, ROOT / "public_release_exclusions.csv")
    shutil.copy2(DIST / "SHA256SUMS", ROOT / "SHA256SUMS")
    payload["files"] = sum(1 for p in DIST.rglob("*") if p.is_file())
    payload["bytes"] = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
