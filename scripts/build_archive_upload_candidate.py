"""Create a checksum-addressed ZIP for author upload without publishing it."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from release_common import repository_root


ROOT = repository_root(Path(__file__).resolve().parent)
SOURCE = ROOT / "dist/release_candidate"
OUTPUT_DIR = ROOT / "dist/archive_upload_candidate"
ARCHIVE = OUTPUT_DIR / "materials-transportability-v6-1.0.0-release-candidate.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not SOURCE.is_dir():
        raise RuntimeError("build dist/release_candidate first")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in SOURCE.rglob("*") if item.is_file()):
            archive.write(path, Path("materials-transportability-v6-1.0.0") / path.relative_to(SOURCE))
    digest = sha256(ARCHIVE)
    (OUTPUT_DIR / "SHA256SUMS").write_text(f"{digest}  {ARCHIVE.name}\n", encoding="utf-8")
    print(f"archive={ARCHIVE.name} bytes={ARCHIVE.stat().st_size} sha256={digest}")


if __name__ == "__main__":
    main()
