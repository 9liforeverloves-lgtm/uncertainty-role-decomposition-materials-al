"""Validate the authorized BSD3 publication candidate without rerunning science."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import tomllib
import yaml

from release_common import assert_authorities, repository_root


ROOT = repository_root(Path(__file__).resolve().parent)
DIST = ROOT / "dist/release_candidate"
LICENSE_SHA256 = "8cffe8837f038e3a6ebe69977b66f39ae90dd895cf31530e3885e48ea54b20bc"
SECRET = re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
PACKAGE_ABSOLUTE = re.compile(rb"(?i)(?:[A-Z]:\\Users\\|/" + b"home" + rb"/[^/]+/)")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, evidence: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "evidence": evidence})

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    check("exact authorized BSD-3-Clause license", sha(ROOT / "LICENSE") == LICENSE_SHA256, LICENSE_SHA256)
    check("license identity", "Copyright (c) 2026 Renjie Li" in license_text, "2026 Renjie Li")
    check("obsolete license gates absent", not (ROOT / "LICENSE_SELECTION_REQUIRED.md").exists() and not (ROOT / "AUTHOR_LICENSE_DECISION_REQUIRED.md").exists(), "resolved copies archived")

    decisions = yaml.safe_load((ROOT / "release_config/author_release_decisions.yaml").read_text(encoding="utf-8"))
    authorization = (
        decisions.get("code_license") == "BSD-3-Clause"
        and decisions.get("copyright_holder") == "Renjie Li"
        and decisions.get("copyright_year") == 2026
        and decisions.get("allow_public_code_release") is True
        and decisions.get("allow_public_processed_outputs") is True
        and decisions.get("allow_public_raw_data") is False
        and len(decisions.get("processed_output_scope", [])) == 11
        and len(decisions.get("excluded_data_scope", [])) == 6
    )
    check("author release authorization", authorization, "code/processed outputs authorized; raw data prohibited")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    check("Python metadata", project["version"] == "1.0.0" and project["license"]["text"] == "BSD-3-Clause" and project["authors"] == [{"name": "Renjie Li"}], "version 1.0.0 / BSD-3-Clause / Renjie Li")

    authority = assert_authorities(ROOT)
    check("V6/P1 authority hashes", all(item["passed"] for item in authority), f"{len(authority)} locked files")
    presentation_lock = json.loads((ROOT / "locks/final_optimization_presentation_lock.json").read_text(encoding="utf-8"))
    presentation_hashes = {**presentation_lock["source_files"], **presentation_lock["generated_files"]}
    presentation_ok = all(sha(ROOT / relative) == expected for relative, expected in presentation_hashes.items())
    check("current manuscript scientific tables", presentation_ok, f"{len(presentation_hashes)} presentation-bound files")
    figure_inventory_sha = sha(ROOT / "tables/p1_figure_source_inventory.csv")
    check("figure source inventory", figure_inventory_sha == "200357edeafa2161b7be23a6ec9980b25afa0a5a3098cdb9f0bc4a7a5d519c71", figure_inventory_sha)

    dependency_rows = list(csv.DictReader((ROOT / "tables/release_audit/dependency_license_inventory.csv").open(encoding="utf-8")))
    check("dependency license audit", len(dependency_rows) == 47 and all(row["Verification status"].startswith("VERIFIED") for row in dependency_rows), "47/47 verified")

    packages = sorted((ROOT / "dist/python_package_bsd3").glob("materials_transportability_v6-1.0.0*"))
    package_results = []
    for path in packages:
        if path.suffix == ".whl":
            with zipfile.ZipFile(path) as archive:
                members = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
        else:
            with tarfile.open(path, "r:gz") as archive:
                members = {item.name: archive.extractfile(item).read() for item in archive.getmembers() if item.isfile()}
        required = all(any(name.endswith("/" + required_name) or name == required_name for name in members) for required_name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES"))
        forbidden = [name for name in members if any(part in name.lower() for part in ("materials.csv", ".venv", "registry.sqlite", "results/p1_extension", "__pycache__"))]
        secret_hits = [name for name, content in members.items() if SECRET.search(content)]
        absolute_hits = [name for name, content in members.items() if PACKAGE_ABSOLUTE.search(content)]
        package_results.append(required and not forbidden and not secret_hits and not absolute_hits)
    check("wheel/sdist content", len(packages) == 2 and all(package_results), "both contain legal notices; no raw data/secrets/absolute paths")

    checksum_lines = (DIST / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    records = dict(line.split("  ", 1)[::-1] for line in checksum_lines)
    actual = {path.relative_to(DIST).as_posix() for path in DIST.rglob("*") if path.is_file() and path.name != "SHA256SUMS"}
    mismatches = [relative for relative in actual & records.keys() if sha(DIST / relative) != records[relative]]
    check("release checksums", actual == records.keys() and not mismatches, f"{len(records)} covered; mismatches={len(mismatches)}")
    inventory = list(csv.DictReader((DIST / "public_release_archive_inventory.csv").open(encoding="utf-8")))
    check("release inventory", len(inventory) == len(actual), f"{len(inventory)} rows including self marker")
    forbidden_release = [
        path.relative_to(DIST).as_posix()
        for path in DIST.rglob("*")
        if path.is_file()
        and (
            any(part in path.relative_to(DIST).parts for part in (".venv", "__pycache__"))
            or ("results" in path.relative_to(DIST).parts and path.name != "DATA_NOT_BUNDLED.md")
        )
    ]
    check("restricted release content absent", not forbidden_release and not (DIST / "LICENSE_SELECTION_REQUIRED.md").exists(), str(forbidden_release[:10]))

    for name, platform in (("external_reproduction_status.json", "Windows"), ("linux_reproduction_status.json", "Linux/WSL")):
        status = json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))
        commands = "\n".join(" ".join(record["command"]) for record in status["commands"])
        passed = status["status"] == "PASS" and all(record["returncode"] == 0 for record in status["commands"])
        coverage = "materials_transportability_v6-1.0.0-py3-none-any.whl" in commands and "materials_transportability_v6-1.0.0.tar.gz" in commands and "pytest" in commands and "reproduce_tables.py" in commands and "reproduce_figures.py" in commands
        check(f"{platform} external reproduction", passed and coverage, f"{len(status['commands'])} zero-return steps")

    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    expected_repository = "https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al"
    check("CFF metadata", cff.get("license") == "BSD-3-Clause" and cff.get("version") == "1.0.0" and cff.get("repository-code") == expected_repository and "doi" not in cff, "real private repository URL; no fabricated DOI")
    check("publication identifiers remain truthful", decisions.get("repository_url") == expected_repository and decisions.get("archive_doi") is None, "real private repository URL; DOI null")
    tags = subprocess.run(["git", "tag", "--list", "v1.0.0"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("tag truthfulness", not tags, "v1.0.0 absent")

    manuscript_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "manuscript").glob("*P1_COMPLETE*.tex"))
    placeholders = ("[PUBLIC REPOSITORY URL]", "[VERSION DOI]", "10.5281/zenodo")
    check("submission manuscript has no unpublished availability claim", not any(value in manuscript_text for value in placeholders), "final templates remain reports-only")

    online_ci_text = (ROOT / "reports/ONLINE_CI_RESULTS.md").read_text(encoding="utf-8")
    audited_main = "1d6fef9ca8dca3fc92877405d967dde40dcdedc6"
    github_actions_status = (
        "PASS"
        if "GITHUB_ACTIONS_STATUS = PASS" in online_ci_text and audited_main in online_ci_text
        else "NOT_RUN"
    )

    overall = all(item["passed"] for item in checks)
    payload = {
        "status": "PASS" if overall else "FAIL",
        "release_state": "READY_FOR_AUTHOR_PUBLICATION" if overall else "VALIDATION_FAILED",
        "PUBLIC_RELEASE_READY": False,
        "SUBMISSION_READY": False,
        "GITHUB_ACTIONS_STATUS": github_actions_status,
        "Docker": "NOT_TESTED" if not (shutil.which("docker") or shutil.which("podman")) else "AVAILABLE_NOT_VALIDATED_BY_THIS_SCRIPT",
        "checks": checks,
        "python": sys.version,
    }
    output = ROOT / "reports/bsd3_release_validation_status.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not overall:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
