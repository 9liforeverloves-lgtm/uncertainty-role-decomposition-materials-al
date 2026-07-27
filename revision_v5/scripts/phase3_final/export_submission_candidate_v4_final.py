from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "EXPORT_SUBMISSION_CANDIDATE_V4_FINAL"
if EXPORT.exists():
    raise FileExistsError(f"Refusing to overwrite existing export: {EXPORT}")
EXPORT.mkdir()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


copied: list[tuple[Path, Path]] = []


def copy_file(source: Path, relative: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target = EXPORT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if digest(source) != digest(target):
        raise RuntimeError(f"Copy verification failed: {source}")
    copied.append((source, target))


def copy_directory(source: Path, relative: Path, pattern: str = "*") -> None:
    for path in sorted(source.rglob(pattern)):
        if path.is_file():
            copy_file(path, relative / path.relative_to(source))


man = ROOT / "manuscript_v5/submission_candidate_v4_final"
for name in (
    "manuscript_submission_candidate_v4_final.tex",
    "manuscript_submission_candidate_v4_final.pdf",
    "supplement_submission_candidate_v4_final.tex",
    "supplement_submission_candidate_v4_final.pdf",
    "references_submission_candidate_v4_final.bib",
):
    copy_file(man / name, Path(name))

copy_directory(
    ROOT / "figures_v5/submission_candidate_v4_final",
    Path("figures"),
)
copy_directory(
    ROOT / "tables_v5/submission_candidate_v4_final",
    Path("tables/derived_final"),
)
for name in (
    "v5_rc1_primary_contrasts_final.csv",
    "v5_rc1_seed_level_endpoints_final.csv",
    "v5_rc1_recovery_sensitivity_final.csv",
    "FINAL_TABLE_LOCK_V5.json",
):
    copy_file(ROOT / "tables_v5" / name, Path("tables/frozen_authority") / name)

copy_directory(ROOT / "scripts/phase3_final", Path("scripts/phase3_final"))
copy_directory(ROOT / "reviewer_revision_v4/finalization", Path("reports_and_audits"))
copy_directory(ROOT / "reviewer_revision_v4/tests", Path("validation/tests"), "*.py")

for name in ("09_claim_evidence_matrix.csv", "10_number_traceability.csv"):
    copy_file(ROOT / name, Path("provenance") / name)
for name in (
    "CONFIRMATION_RESULT_LOCK_V5_RC1.json",
    "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json",
    "15_development_freeze_lock.json",
    "19_selected_policy_lock.json",
):
    copy_file(ROOT / name, Path("provenance/authority") / name)
for name in (
    "recovery_identity_reconciliation_VERIFIED.csv",
    "recovery_identity_reconciliation_VERIFIED.json",
):
    copy_file(
        ROOT / "audits_v5/reviewer_revision_v4" / name,
        Path("provenance/recovery") / name,
    )
copy_file(
    ROOT / "tables_v5/submission_candidate_v4/final_evidence_count_audit_VERIFIED.csv",
    Path("provenance/final_evidence_count_audit_VERIFIED.csv"),
)
for name in ("finalization_complete_test.log", "finalization_junit.xml"):
    copy_file(
        ROOT / "logs_v5/reviewer_revision_v4/finalization" / name,
        Path("validation") / name,
    )

manifest_rows = []
for _, target in sorted(copied, key=lambda pair: pair[1].as_posix()):
    manifest_rows.append(
        {
            "path": target.relative_to(EXPORT).as_posix(),
            "bytes": target.stat().st_size,
            "sha256": digest(target),
        }
    )

(EXPORT / "EXPORT_MANIFEST.json").write_text(
    json.dumps(
        {
            "schema_version": "submission-candidate-v4-final-export-v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "file_count_excluding_manifests": len(manifest_rows),
            "copy_integrity": "all source/export SHA-256 pairs matched",
            "frozen_scientific_values_changed": False,
            "files": manifest_rows,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
(EXPORT / "SHA256SUMS.txt").write_text(
    "".join(f"{row['sha256']}  {row['path']}\n" for row in manifest_rows),
    encoding="utf-8",
)

print(
    json.dumps(
        {
            "export": str(EXPORT),
            "files_excluding_manifests": len(manifest_rows),
            "manifest": str(EXPORT / "EXPORT_MANIFEST.json"),
        }
    )
)
