from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "EXPORT_SUBMISSION_CANDIDATE_V4_FINAL"
if not EXPORT.is_dir():
    raise FileNotFoundError(EXPORT)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


sources = {
    Path(__file__).resolve():
        EXPORT / "scripts/phase3_final/finalize_export_authority_registry.py",
    ROOT / "EXPORT_VERIFIED_FOUNDATION_AND_FIGURES_V4/01_authoritative_scientific_facts_VERIFIED.json":
        EXPORT / "provenance/authority/01_authoritative_scientific_facts_VERIFIED.json",
    ROOT / "EXPORT_VERIFIED_FOUNDATION_AND_FIGURES_V4/PRIMARY_EVIDENCE_PATHS_FINAL.json":
        EXPORT / "provenance/authority/PRIMARY_EVIDENCE_PATHS_FINAL.json",
    ROOT / "results_v4/confirmation/registry_snapshot.csv":
        EXPORT / "provenance/authority/confirmation_registry_snapshot.csv",
}
for source, target in sources.items():
    if not source.is_file():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite export file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha(source) != sha(target):
        raise RuntimeError(f"Copy verification failed: {source}")

excluded = {"EXPORT_MANIFEST.json", "SHA256SUMS.txt"}
files = sorted(
    p for p in EXPORT.rglob("*")
    if p.is_file() and p.name not in excluded
)
rows = [
    {
        "path": p.relative_to(EXPORT).as_posix(),
        "bytes": p.stat().st_size,
        "sha256": sha(p),
    }
    for p in files
]
(EXPORT / "EXPORT_MANIFEST.json").write_text(
    json.dumps(
        {
            "schema_version": "submission-candidate-v4-final-export-v1",
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "file_count_excluding_manifests": len(rows),
            "copy_integrity": "all copied authority files and initial export copies verified by SHA-256",
            "frozen_scientific_values_changed": False,
            "files": rows,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
(EXPORT / "SHA256SUMS.txt").write_text(
    "".join(f"{row['sha256']}  {row['path']}\n" for row in rows),
    encoding="utf-8",
)
print(json.dumps({"files_excluding_manifests": len(rows), "added_files": 4}))
