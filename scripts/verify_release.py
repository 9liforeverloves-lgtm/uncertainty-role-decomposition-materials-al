"""Verify release integrity, security-sensitive metadata and publication gates."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from release_common import assert_authorities, repository_root, sha256


REQUIRED = [
    "README.md", "CITATION.cff", "LICENSE", "LICENSE_AND_DATA_SCOPE.md", "NOTICE", "THIRD_PARTY_NOTICES", "pyproject.toml",
    "requirements-lock.txt", "environment.yml", "release_config/author_release_decisions.yaml",
    "data_manifest/upstream_sources.yaml", "scripts/reproduce_smoke.py", "scripts/reproduce_tables.py",
    "scripts/reproduce_figures.py", "scripts/reproduce_manuscript.py", "scripts/verify_release.py",
]
SECRET = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
ABSOLUTE = re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|home)[^\s'\"<>]*|/(?:home|Users)/[^\s'\"<>]+)")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".csv", ".tex", ".bib", ".cff", ".ps1", ".sh"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a source/release tree without rerunning scientific experiments.")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    root = (args.root or repository_root()).resolve()
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, evidence: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "evidence": evidence})

    missing = [name for name in REQUIRED if not (root / name).is_file()]
    check("required release files", not missing, str(missing))
    authority = assert_authorities(root)
    check("V6/P1 authority hashes", all(row["passed"] for row in authority), f"{len(authority)} locked files")
    primary = pd.read_csv(root / "tables/p1_confirmation_primary_contrasts.csv")
    check("P1 scientific identity", len(primary) == 5 and set(primary.contrast_id) == {f"P1_C{i}" for i in range(1, 6)}, "five locked contrasts")
    manifest = pd.read_csv(root / "manifests/p1_confirmation_manifest.csv")
    check("P1 manifest", len(manifest) == 3520 and not manifest.job_id.duplicated().any(), "3,520 unique jobs")

    secrets, absolute_paths = [], []
    scan_roots = [root / name for name in ["src", "p1_extension", "tests", "v6_revision", "docs", "data_manifest", "release_config", ".github"]]
    scan_paths = [path for base in scan_roots if base.exists() for path in base.rglob("*")]
    scan_paths += [root / "scripts" / name for name in ["release_common.py", "verify_release.py", "reproduce_smoke.py", "reproduce_tables.py", "reproduce_figures.py", "reproduce_manuscript.py", "fetch_matbench_data.py", "build_final_optimization_assets.py", "generate_p1_confirmation_figures.py", "compile_p1_complete_manuscript.py", "build_release_candidate.py"] if (root / "scripts" / name).is_file()]
    scan_paths += [root / name for name in ["README.md", "CITATION.cff", "NOTICE", "THIRD_PARTY_NOTICES", "CONTRIBUTING.md", "SECURITY.md", "Dockerfile"] if (root / name).is_file()]
    for path in scan_paths:
        if not path.is_file() or any(part in {".git", ".venv", "dist", "revision_audit", "__pycache__"} or part.startswith(".venv") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if SECRET.search(line):
                secrets.append(f"{path.relative_to(root).as_posix()}:{number}")
            if ABSOLUTE.search(line):
                absolute_paths.append(f"{path.relative_to(root).as_posix()}:{number}")
    check("no secret patterns", not secrets, str(secrets[:20]))
    check("no developer absolute paths", not absolute_paths, str(absolute_paths[:20]))

    decisions = yaml.safe_load((root / "release_config/author_release_decisions.yaml").read_text(encoding="utf-8"))
    authorization_ok = (
        decisions.get("code_license") == "BSD-3-Clause"
        and decisions.get("copyright_holder") == "Renjie Li"
        and decisions.get("copyright_year") == 2026
        and decisions.get("allow_public_code_release") is True
        and decisions.get("allow_public_processed_outputs") is True
        and decisions.get("allow_public_raw_data") is False
        and decisions.get("release_tag") == "v1.0.0"
        and (root / "LICENSE").is_file()
        and not (root / "LICENSE_SELECTION_REQUIRED.md").exists()
    )
    check("BSD-3-Clause authorization", authorization_ok, "author decision, root license and raw-data exclusion")
    repository_url = decisions.get("repository_url")
    archive_doi = decisions.get("archive_doi")
    publication_identifiers_exist = bool(repository_url and archive_doi)
    repository_truthful = repository_url in (None, "") or repository_url == "https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al"
    doi_truthful = archive_doi in (None, "") or str(archive_doi).startswith("10.")
    check("publication metadata truthfulness", repository_truthful and doi_truthful, "repository URL may be real while archive DOI remains null")
    tag_check = subprocess.run(
        ["git", "tag", "--list", "v1.0.0"], cwd=root, capture_output=True, text=True
    )
    tag_exists = tag_check.returncode == 0 and tag_check.stdout.strip() == "v1.0.0"
    public_ready = authorization_ok and publication_identifiers_exist and tag_exists
    payload = {
        "verification_status": "PASS" if all(item["passed"] for item in checks) else "FAIL",
        "release_state": "PUBLIC_RELEASE_VERIFIED" if public_ready else "READY_FOR_AUTHOR_PUBLICATION",
        "PUBLIC_RELEASE_READY": public_ready,
        "SUBMISSION_READY": False,
        "python": sys.version,
        "root": root.name,
        "checks": checks,
    }
    output = (args.json_output or root / "reports/release_verification_status.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if payload["verification_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
